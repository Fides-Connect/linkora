"""
Tests for CrossEncoderService.

The sentence_transformers dependency is mocked so these tests run without
downloading any model weights.
"""
import asyncio
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from ai_assistant.services.cross_encoder_service import CrossEncoderService, _candidate_to_text


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_candidates(n: int = 5) -> list:
    """Build n minimal provider candidate dicts."""
    return [
        {
            "title": f"Provider {i}",
            "search_optimized_summary": f"Summary for provider {i}.",
            "skills_list": [f"skill_{i}_a", f"skill_{i}_b"],
        }
        for i in range(n)
    ]


def _mock_cross_encoder(scores: list):
    """Return a mock CrossEncoder whose predict() returns the given scores."""
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array(scores, dtype=float)
    return mock_model


# ─────────────────────────────────────────────────────────────────────────────
# _candidate_to_text
# ─────────────────────────────────────────────────────────────────────────────

class TestCandidateToText:
    def test_all_fields_present(self):
        candidate = {
            "title": "Electrician",
            "search_optimized_summary": "Expert in residential wiring.",
            "skills_list": ["wiring", "fuse box"],
        }
        text = _candidate_to_text(candidate)
        assert "Electrician" in text
        assert "residential wiring" in text
        assert "wiring" in text
        assert "fuse box" in text

    def test_falls_back_to_category_when_no_title(self):
        candidate = {"category": "Plumber", "search_optimized_summary": "Pipe specialist."}
        text = _candidate_to_text(candidate)
        assert "Plumber" in text

    def test_empty_candidate_returns_default(self):
        text = _candidate_to_text({})
        assert text == "No description available."

    def test_missing_skills_list_does_not_crash(self):
        candidate = {"title": "Painter", "search_optimized_summary": "Interior painting."}
        text = _candidate_to_text(candidate)
        assert "Painter" in text
        assert "Skills:" not in text


# ─────────────────────────────────────────────────────────────────────────────
# CrossEncoderService.rerank
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossEncoderServiceRerank:

    def _build_service_with_mock_model(self, scores: list) -> CrossEncoderService:
        service = CrossEncoderService()
        service._model = _mock_cross_encoder(scores)
        return service

    async def test_returns_top_k_sorted_by_score_descending(self):
        """Candidates must be returned in descending rerank_score order."""
        candidates = _make_candidates(5)
        # Assign scores in reverse so we can verify reordering
        scores = [0.1, 0.9, 0.3, 0.7, 0.5]
        service = self._build_service_with_mock_model(scores)

        result = await service.rerank(query="I need a plumber", candidates=candidates, top_k=5)

        assert len(result) == 5
        assert result[0]["title"] == "Provider 1"   # score 0.9
        assert result[1]["title"] == "Provider 3"   # score 0.7
        assert result[2]["title"] == "Provider 4"   # score 0.5
        assert result[3]["title"] == "Provider 2"   # score 0.3
        assert result[4]["title"] == "Provider 0"   # score 0.1

    async def test_rerank_score_field_added_to_each_candidate(self):
        candidates = _make_candidates(3)
        service = self._build_service_with_mock_model([0.4, 0.8, 0.6])

        result = await service.rerank(query="electrician", candidates=candidates, top_k=3)

        for item in result:
            assert "rerank_score" in item
            assert isinstance(item["rerank_score"], float)

    async def test_top_k_limits_results(self):
        candidates = _make_candidates(10)
        scores = [float(i) for i in range(10)]
        service = self._build_service_with_mock_model(scores)

        result = await service.rerank(query="any", candidates=candidates, top_k=5)

        assert len(result) == 5

    async def test_empty_candidates_returns_empty_list(self):
        service = CrossEncoderService()
        result = await service.rerank(query="test", candidates=[], top_k=5)
        assert result == []

    async def test_empty_query_returns_first_top_k_without_model_call(self):
        """When query is empty, skip the model and return first top_k unchanged."""
        candidates = _make_candidates(10)
        service = CrossEncoderService()
        # _model is NOT loaded — if predict were called it would raise AttributeError
        result = await service.rerank(query="", candidates=candidates, top_k=3)
        assert len(result) == 3
        # No rerank_score should be added (model was not called)
        assert "rerank_score" not in result[0]

    async def test_original_candidates_not_mutated(self):
        """rerank must return new dicts and leave originals untouched."""
        candidates = _make_candidates(3)
        original_keys = [set(c.keys()) for c in candidates]
        service = self._build_service_with_mock_model([0.1, 0.5, 0.9])

        await service.rerank(query="test", candidates=candidates, top_k=3)

        for original_keys_set, c in zip(original_keys, candidates):
            assert set(c.keys()) == original_keys_set, "Original candidate was mutated"

    async def test_model_exception_falls_back_to_original_order(self):
        """If predict() raises, rerank returns first top_k in original order."""
        candidates = _make_candidates(5)
        service = CrossEncoderService()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("GPU OOM")
        service._model = mock_model

        result = await service.rerank(query="plumber", candidates=candidates, top_k=3)

        assert len(result) == 3
        # Order should be original
        assert result[0]["title"] == "Provider 0"
        assert result[1]["title"] == "Provider 1"

    async def test_lazy_model_load_on_first_call(self):
        """_load_model must be called during rerank when model is None."""
        service = CrossEncoderService()
        assert service._model is None

        mock_model = _mock_cross_encoder([0.5])
        with patch("ai_assistant.services.cross_encoder_service.CrossEncoder", return_value=mock_model):
            candidates = _make_candidates(1)
            result = await service.rerank(query="test", candidates=candidates, top_k=1)

        assert service._model is mock_model
        assert len(result) == 1

    async def test_predict_receives_query_candidate_pairs(self):
        """predict must be called with (query, candidate_text) pairs."""
        query = "I need help with wiring"
        candidates = _make_candidates(2)
        service = self._build_service_with_mock_model([0.3, 0.7])

        await service.rerank(query=query, candidates=candidates, top_k=2)

        call_args = service._model.predict.call_args[0][0]
        assert len(call_args) == 2
        for q, doc in call_args:
            assert q == query
            assert isinstance(doc, str) and len(doc) > 0
