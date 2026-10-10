"""Lightweight embedding layer using sentence-transformers with a hashing fallback.

Loads the model lazily so tests and Vercel cold starts that only need BM25
retrieval do not pay the download cost. When sentence-transformers or its
model weights are unavailable, a deterministic token-hashing embedding keeps
the hybrid pipeline functional with reduced semantic quality.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional

import numpy as np


class EmbeddingLayer:
    """Encode text to dense vectors and build an HNSW index for similarity search.

    Lazy model loading avoids the ~2s import cost of sentence-transformers on
    every process start. The hash fallback produces 256-dim normalized vectors
    suitable for cosine similarity without downloading weights.
    """

    FALLBACK_DIM = 256

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
                 index_dim: Optional[int] = None):
        self.model_name = model_name
        self.index_dim = index_dim
        self._model: Any = None
        self._dim: Optional[int] = None

    @property
    def model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self._dim = self._model.get_sentence_embedding_dimension()
            except Exception:
                self._model = False  # marked loaded-but-unavailable
                self._dim = self.index_dim or self.FALLBACK_DIM
        return self._model

    @property
    def dim(self) -> int:
        if self._dim is None:
            _ = self.model  # trigger lazy load
        return self._dim

    @property
    def available(self) -> bool:
        """True if a real embedding model is loaded (not the hashing fallback)."""
        return bool(self.model)

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts to a 2-D float32 array of shape (len(texts), dim)."""
        if not texts:
            return np.empty((0, self.dim), dtype=np.float32)
        encoder = self.model
        if encoder:
            vectors = encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vectors, dtype=np.float32)
        return self._hash_encode(texts)

    def _hash_encode(self, texts: List[str]) -> np.ndarray:
        """Deterministic rolling-hash embeddings — no model download required."""
        dim = self.index_dim or self.FALLBACK_DIM
        matrix = np.zeros((len(texts), dim), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = re.findall(r"[\w]+", str(text).casefold())
            for token in tokens:
                seed = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16)
                np.random.seed(seed)
                matrix[row] += np.random.default_rng(seed).standard_normal(dim)
            norm = np.linalg.norm(matrix[row])
            matrix[row] = matrix[row] / norm if norm > 0 else matrix[row]
        return matrix

    def build_index(self, embeddings: np.ndarray) -> Any:
        """Build an HNSW index over pre-computed embeddings for fast ANN search."""
        try:
            import hnswlib
            index = hnswlib.Index(space="cosine", dim=embeddings.shape[1])
            index.init_index(items=len(embeddings))
            index.add_items(embeddings, np.arange(len(embeddings)))
            index.set_ef(50)
            return index
        except ImportError:
            return None

    def search(self, index: Any, query: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
        """Return (labels, distances) from the HNSW index, or empty arrays."""
        if index is None:
            return np.array([], dtype=int), np.array([], dtype=float)
        labels, distances = index.knn_query(query, k=min(k, index.get_current_count()))
        return labels[0], distances[0]
