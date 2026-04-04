"""
Cross-Encoder Reranking Service
================================

Provides a second-pass reranking step for provider search results.

After Weaviate's wide-net hybrid retrieval (Stage 1), this service runs a
cross-encoder that scores each (query, document) pair *jointly*, giving far
more accurate relevance judgments than the bi-encoder used during retrieval.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2  (~87 MB)
  - Fast (MiniLM backbone), English
  - Trained on MS MARCO passage ranking → good at matching natural language
    queries to descriptive text
  - Bundled under ai-assistant/models/ (Git LFS) — no download on startup
  - Falls back to the HF identifier when the local directory is absent
    (e.g. on a fresh clone before `git lfs pull`)

Usage pattern:
    service = CrossEncoderService()
    reranked = await service.rerank(query="I need a plumber", candidates=[...])
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

# sentence_transformers is intentionally NOT imported at module scope.
# Importing it at startup pulls in torch and other heavy deps even though the
# model is lazy-loaded.  The import is deferred to _load_model() so that the
# module is importable without triggering those side-effects.
CrossEncoder = None  # filled at first use via _load_model()

logger = logging.getLogger(__name__)

_HF_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Bundled path: ai-assistant/models/cross-encoder/ms-marco-MiniLM-L-6-v2/
# Resolves correctly both locally and inside Docker (/app/models/…).
_BUNDLED_MODEL_DIR = (
    Path(__file__).parent  # services/
    .parent                 # ai_assistant/
    .parent                 # src/
    .parent                 # ai-assistant/
    / "models"
    / "cross-encoder"
    / "ms-marco-MiniLM-L-6-v2"
)

_DEFAULT_MODEL = _HF_MODEL_ID  # kept for backward compat / tests that pass a custom name
_DEFAULT_MIN_SCORE = -8.0


def _resolve_model_name() -> str:
    """Return the local bundled path if it exists, else the HF identifier."""
    if (_BUNDLED_MODEL_DIR / "config.json").exists():
        logger.debug("Using bundled cross-encoder model at %s", _BUNDLED_MODEL_DIR)
        return str(_BUNDLED_MODEL_DIR)
    logger.warning(
        "Bundled model not found at %s — will download from HF Hub",
        _BUNDLED_MODEL_DIR,
    )
    return _HF_MODEL_ID


def _candidate_to_text(candidate: dict[str, Any]) -> str:
    """Build a single string representing a provider candidate for the cross-encoder.

    We concatenate the most semantically rich fields so the model can judge
    relevance holistically.

    Registered platform providers:
      - title          — what they do (most important)
      - search_optimized_summary — LLM-refined bio (primary vector source in Weaviate)
      - skills_list    — enumerated keywords

    Google Places providers (no skills_list):
      - title          — business name
      - primary_type   — exact GP type label (e.g. "Wedding Photographer")
      - search_optimized_summary — LLM-synthesised English summary
      - category       — GP broad category (e.g. "Wedding service")
      - description    — editorial summary in its original language
      - review_snippets — raw customer review fragments (up to 5)
    """
    parts = []
    title = candidate.get("title") or candidate.get("category") or ""
    if title:
        parts.append(title)

    summary = candidate.get("search_optimized_summary", "")
    if summary:
        parts.append(summary)

    # Registered-provider skills
    skills = candidate.get("skills_list") or []
    if skills:
        parts.append("Skills: " + ", ".join(skills))

    # GP-provider fields (only populated for Google Places records)
    primary_type = candidate.get("primary_type") or ""
    if primary_type and primary_type not in title:
        parts.append(primary_type)

    category = candidate.get("category") or ""
    if category and category not in title and category not in primary_type:
        parts.append(category)

    description = candidate.get("description") or ""
    if description and description not in summary:
        parts.append(description)

    review_snippets = (candidate.get("review_snippets") or [])[:5]
    if review_snippets:
        parts.append("Customer reviews: " + ". ".join(review_snippets))

    return ". ".join(filter(None, parts)) or "No description available."


class CrossEncoderService:
    """Lazy-loading cross-encoder for provider reranking.

    The model is loaded on the first call to `rerank()` so that the service
    can be constructed without blocking the event loop at startup.

    Constructor injection pattern: pass a single instance to every component
    that needs reranking — do not create multiple instances.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL, min_score: float | None = None) -> None:
        # When using the default HF identifier, prefer the bundled local copy.
        self._model_name = (
            _resolve_model_name() if model_name == _DEFAULT_MODEL else model_name
        )
        self._model: object | None = None  # loaded lazily
        if min_score is None:
            raw = os.environ.get("CROSS_ENCODER_MIN_SCORE")
            if raw is not None:
                try:
                    min_score = float(raw)
                except (ValueError, TypeError):
                    min_score = _DEFAULT_MIN_SCORE
            else:
                min_score = _DEFAULT_MIN_SCORE
        self._min_score: float = min_score
        logger.info(
            "CrossEncoderService created with model '%s' (lazy load), min_score=%.1f",
            self._model_name,
            self._min_score,
        )

    def _load_model(self) -> object:
        """Load the cross-encoder model (called once on first use)."""
        global CrossEncoder  # noqa: PLW0603 — populated lazily so startup is cheap
        if self._model is None:
            logger.info("Loading cross-encoder model '%s' …", self._model_name)
            if CrossEncoder is None:
                try:
                    from sentence_transformers import CrossEncoder as _CE  # type: ignore
                except ImportError as exc:  # pragma: no cover
                    raise RuntimeError(
                        "sentence-transformers is not installed. "
                        "Run: pip install sentence-transformers"
                    ) from exc
                CrossEncoder = _CE  # cache at module scope so tests can patch it
            self._model = CrossEncoder(self._model_name)
            logger.info("Cross-encoder model loaded successfully")
        return self._model

    async def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Re-score and sort candidates using the cross-encoder.

        Runs the CPU-bound `predict()` call in a thread executor to keep
        the async event loop non-blocking.

        Args:
            query: The original user problem summary (plain natural language).
            candidates: Provider dicts from Weaviate hybrid search.
            top_k: How many top-scored candidates to return.

        Returns:
            Candidates sorted by `rerank_score` descending, sliced to `top_k`.
            Each dict is a shallow copy of the original with `rerank_score` added.
        """
        if not candidates:
            return []

        if not query:
            logger.warning("CrossEncoderService.rerank called with empty query — skipping rerank")
            return candidates[:top_k]

        pairs = [(query, _candidate_to_text(c)) for c in candidates]

        loop = asyncio.get_running_loop()
        try:
            model = self._load_model()
            scores: list[float] = await loop.run_in_executor(
                None, lambda: model.predict(pairs).tolist()  # type: ignore[attr-defined]
            )
        except Exception as exc:
            logger.error("Cross-encoder reranking failed: %s — returning original order", exc, exc_info=True)
            return candidates[:top_k]

        # Attach scores and sort
        scored = [
            {**candidate, "rerank_score": float(score)}
            for candidate, score in zip(candidates, scores)
        ]
        scored.sort(key=lambda c: c["rerank_score"], reverse=True)

        # Apply minimum relevance threshold to prevent clearly irrelevant providers
        # (e.g. a software developer returned for an electrician query) from surfacing
        # when the candidate pool is sparse. Configurable via CROSS_ENCODER_MIN_SCORE
        # env var (default -5.0 on the ms-marco model scale, range roughly -10 to +10).
        # NOTE: Google Places providers are exempt — their relevance was already validated
        # by the Places API query, and the cross-encoder (trained on passage retrieval)
        # systematically underscores short business-listing descriptions.
        above_threshold = [
            c for c in scored
            if c["rerank_score"] >= self._min_score
            or c.get("user", {}).get("source") == "google_places"
        ]
        if len(above_threshold) < len(scored):
            logger.info(
                "min_score=%.1f filtered out %d/%d candidates below relevance threshold",
                self._min_score,
                len(scored) - len(above_threshold),
                len(scored),
            )

        logger.info(
            "Reranked %d candidates → returning top %d (scores: %s)",
            len(above_threshold),
            min(top_k, len(above_threshold)),
            [f"{c['rerank_score']:.3f}" for c in above_threshold[:top_k]],
        )
        return above_threshold[:top_k]
