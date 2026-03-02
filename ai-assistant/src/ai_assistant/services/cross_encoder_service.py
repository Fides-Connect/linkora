"""
Cross-Encoder Reranking Service
================================

Provides a second-pass reranking step for provider search results.

After Weaviate's wide-net hybrid retrieval (Stage 1), this service runs a
cross-encoder that scores each (query, candidate) pair *jointly*, giving far
more accurate relevance judgments than the bi-encoder used during retrieval.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
  - Fast (MiniLM backbone), English
  - Trained on MS MARCO passage ranking → good at matching natural language
    queries to descriptive text
  - ~22 MB of weights, loads once and is reused across all calls

Usage pattern:
    service = CrossEncoderService()
    reranked = await service.rerank(query="I need a plumber", candidates=[...])
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

try:
    from sentence_transformers import CrossEncoder  # type: ignore
except ImportError:  # pragma: no cover
    CrossEncoder = None  # type: ignore  # filled in tests via patch

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _candidate_to_text(candidate: Dict[str, Any]) -> str:
    """Build a single string representing a provider candidate for the cross-encoder.

    We concatenate the most semantically rich fields so the model can judge
    relevance holistically:
      - title          — what they do (most important)
      - search_optimized_summary — LLM-refined bio (primary vector source in Weaviate)
      - skills_list    — enumerated keywords
    """
    parts = []
    title = candidate.get("title") or candidate.get("category") or ""
    if title:
        parts.append(title)

    summary = candidate.get("search_optimized_summary", "")
    if summary:
        parts.append(summary)

    skills = candidate.get("skills_list") or []
    if skills:
        parts.append("Skills: " + ", ".join(skills))

    return ". ".join(filter(None, parts)) or "No description available."


class CrossEncoderService:
    """Lazy-loading cross-encoder for provider reranking.

    The model is loaded on the first call to `rerank()` so that the service
    can be constructed without blocking the event loop at startup.

    Constructor injection pattern: pass a single instance to every component
    that needs reranking — do not create multiple instances.
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL):
        self._model_name = model_name
        self._model: Optional[Any] = None  # loaded lazily
        logger.info("CrossEncoderService created with model '%s' (lazy load)", model_name)

    def _load_model(self) -> Any:
        """Load the cross-encoder model (called once on first use)."""
        if self._model is None:
            logger.info("Loading cross-encoder model '%s' …", self._model_name)
            if CrossEncoder is None:
                raise RuntimeError(
                    "sentence-transformers is not installed. "
                    "Run: pip install sentence-transformers"
                )
            self._model = CrossEncoder(self._model_name)
            logger.info("Cross-encoder model loaded successfully")
        return self._model

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
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

        loop = asyncio.get_event_loop()
        try:
            model = self._load_model()
            scores: List[float] = await loop.run_in_executor(
                None, lambda: model.predict(pairs).tolist()
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

        logger.info(
            "Reranked %d candidates → returning top %d (scores: %s)",
            len(scored),
            min(top_k, len(scored)),
            [f"{c['rerank_score']:.3f}" for c in scored[:top_k]],
        )
        return scored[:top_k]
