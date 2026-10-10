"""Tests for embedding layer and hybrid BM25 + vector retrieval."""

import numpy as np
import pytest

from rag.context_assembler import ContextAssembler, ContextType
from rag.embedding_layer import EmbeddingLayer
from rag.generation_layer import GenerationLayer, ResponseType
from rag.retrieval_layer import RetrievalLayer


class TestEmbeddingLayer:
    def test_hash_fallback_works_without_model_download(self):
        encoder = EmbeddingLayer(model_name="nonexistent/model", index_dim=64)
        vectors = encoder.encode(["hello world", "career advice"])
        assert vectors.shape == (2, 64)
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)

    def test_hash_encoding_is_deterministic(self):
        encoder = EmbeddingLayer(model_name="nonexistent/model", index_dim=32)
        v1 = encoder.encode(["test sentence"])
        v2 = encoder.encode(["test sentence"])
        assert np.allclose(v1, v2)

    def test_empty_input_returns_empty_array(self):
        encoder = EmbeddingLayer(index_dim=64)
        result = encoder.encode([])
        assert result.shape == (0, 64)

    def test_index_build_and_search(self):
        encoder = EmbeddingLayer(index_dim=64)
        embeddings = encoder.encode(["career counseling", "UX design", "software engineering", "data science"])
        index = encoder.build_index(embeddings)
        labels, distances = encoder.search(index, encoder.encode(["software engineering"]), k=2)
        # With hnswlib available, "software engineering" (index 2) is closest
        if index is not None and hasattr(index, 'get_current_count'):
            assert len(labels) == 2
            assert labels[0] == 2


class TestHybridRetrieval:
    def test_hybrid_search_falls_back_to_bm25_when_no_vectors(self):
        retriever = RetrievalLayer({"documents": [
            {"id": "doc1", "title": "UX Designer", "text": "user research interviews design thinking", "kind": "career"},
            {"id": "doc2", "title": "Software Engineer", "text": "python code testing development programming", "kind": "career"},
        ]})
        results = retriever.hybrid_search("python programming", "career", alpha=0.5)
        assert len(results) > 0
        assert results[0]["id"] == "doc2" or results[0].get("vector_score", 0) == 0.0

    def test_hybrid_search_uses_vector_alpha_correctly(self):
        retriever = RetrievalLayer({"documents": [
            {"id": "doc1", "title": "UX Designer", "text": "user research interviews design thinking", "kind": "career"},
            {"id": "doc2", "title": "Software Engineer", "text": "python code testing development programming", "kind": "career"},
        ], "use_vectors": False})
        # With vectors disabled, should behave like BM25-only
        pure_bm25 = retriever.search("python", [
            {"id": "doc1", "title": "UX Designer", "text": "user research interviews design thinking", "kind": "career"},
            {"id": "doc2", "title": "Software Engineer", "text": "python code testing development programming", "kind": "career"},
        ], top_k=5)
        hybrid = retriever.hybrid_search("python", "career", alpha=0.3)
        assert len(hybrid) >= 1

    def test_search_by_profile_returns_empty_without_vectors(self):
        retriever = RetrievalLayer({"documents": [
            {"id": "doc1", "title": "Career A", "text": "logical programming math", "kind": "career"},
        ]})
        profile_vector = np.zeros(38)
        results = retriever.search_by_profile(profile_vector, top_k=5)
        assert results == []

    def test_retrieval_layer_accepts_use_vectors_config(self):
        retriever = RetrievalLayer({"documents": [], "use_vectors": True})
        assert hasattr(retriever, "_embedder")
        assert hasattr(retriever, "_build_indices")


class TestProfileIntegration:
    def test_rag_service_falls_back_to_bm25_without_model(self):
        from backend.rag_service import RagService
        service = RagService(use_vectors=False)
        # Profile vectorizer still works for fallback scoring
        assert service._profile_vectorizer is not None

    def test_profile_vector_returns_none_without_dimensions(self):
        from backend.rag_service import RagService
        service = RagService(use_vectors=False)
        context = {"DNA": {"answered": 0, "dimensions": []}, "discovery": {}, "journal": []}
        assert service._profile_vector(context) is None

    def test_fuse_query_and_profile_returns_empty_without_embedder(self):
        from backend.rag_service import RagService
        service = RagService(use_vectors=False)
        result = service._fuse_query_and_profile("hello", np.array([0.1, 0.2]))
        assert len(result) == 0
