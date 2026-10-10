"""Deterministic, local retrieval for the Career Quest knowledge corpus.

Combines weighted BM25 lexical retrieval with optional dense vector similarity
via sentence-transformers. Scores measure text relevance, not predictions
about a person's abilities.
"""

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

try:
    from .embedding_layer import EmbeddingLayer
except ImportError:
    EmbeddingLayer = None  # type: ignore


_STOP_WORDS = frozenset(
    "a an and are as at be been but by can could did do does for from had has have "
    "how i if in into is it its me my of on or our should so than that the their "
    "them there these they this to was we were what when where which who why will "
    "with would you your please tell about help want need like know".split()
)


def tokenize(value: str) -> List[str]:
    """Normalize words without matching arbitrary substrings or discarding C++."""
    words = re.findall(r"[\w]+(?:[+#]+)?", str(value).casefold(), flags=re.UNICODE)
    normalized = []
    for word in words:
        if word in _STOP_WORDS or len(word) < 2:
            continue
        if len(word) > 5 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 5 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        normalized.append(word)
    return normalized


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_text(part) for part in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_text(part) for part in value)
    return str(value)


class RetrievalLayer:
    """Search chunks using title-weighted BM25 and query-token coverage."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.documents: List[Dict[str, Any]] = []
        self.scenario_index: Dict[str, Dict[str, Any]] = {}
        self.career_index: Dict[str, Dict[str, Any]] = {}
        self.user_history_index: Dict[str, Dict[str, Any]] = {}
        self.satisfaction_index: Dict[str, Dict[str, Any]] = {}
        self._embedder: Optional["EmbeddingLayer"] = None
        self._embeddings: Optional[np.ndarray] = None
        self._indices: Dict[str, Any] = {}
        self.use_vectors = bool(self.config.get("use_vectors", False))
        self.load_knowledge_bases()
        if self.use_vectors and EmbeddingLayer is not None:
            self._embedder = EmbeddingLayer(
                model_name=self.config.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"))
            self._build_indices()

    @property
    def embedder(self) -> Optional["EmbeddingLayer"]:
        return self._embedder

    def _build_indices(self) -> None:
        """Encode all documents and build per-index HNSW structures."""
        if self._embedder is None:
            return
        docs = self.documents
        if not docs:
            return
        texts = [item["text"] for item in docs]
        self._embeddings = self._embedder.encode(texts)

        def build_for_index(items: Dict[str, Dict[str, Any]]) -> Any:
            if not items:
                return None
            idx = [i for i, d in enumerate(docs) if d["id"] in items]
            if not idx:
                return None
            sub = self._embeddings[idx]
            index = self._embedder.build_index(sub)
            return (index, idx) if index else None

        self._indices["career"] = build_for_index(self.career_index)
        self._indices["scenario"] = build_for_index(self.scenario_index)
        self._indices["all"] = self._embedder.build_index(self._embeddings) if self._embeddings is not None else None

    @staticmethod
    def normalize_document(document: Dict[str, Any]) -> Dict[str, Any]:
        """Keep source fields and give unlabelled chunks stable IDs."""
        item = dict(document)
        metadata = dict(item.get("metadata") or {})
        title = _text(item.get("title") or item.get("name") or "Knowledge base passage").strip()
        body = _text(item.get("text") or item.get("content") or item.get("description")).strip()
        if not body:
            body = _text({k: v for k, v in item.items() if k not in {"id", "title", "metadata", "url"}}).strip()
        for field in ("field", "required_skills", "skills", "interests", "learning_objectives"):
            value = _text(item.get(field) or metadata.get(field)).strip()
            if value and value.casefold() not in body.casefold():
                body += f"\n{field.replace('_', ' ').capitalize()}: {value}"
        kind = _text(item.get("kind") or metadata.get("kind") or metadata.get("type")).strip()
        if not kind:
            lowered = title.casefold()
            kind = "scenario" if lowered.startswith("scenario") else (
                "career" if "career" in lowered else "knowledge"
            )
        identifier = item.get("id") or item.get("chunk_id") or metadata.get("id")
        if not identifier:
            identifier = "kb-" + hashlib.sha256((title + "\n" + body).encode("utf-8")).hexdigest()[:16]
        metadata.setdefault("kind", kind)
        item.update(id=str(identifier), title=title, text=body, content=body, kind=kind, metadata=metadata)
        url = item.get("url") or metadata.get("url")
        if url:
            item["url"] = str(url)
        return item

    @staticmethod
    def _unpack(payload: Any) -> Iterable[Dict[str, Any]]:
        if isinstance(payload, list):
            return (item for item in payload if isinstance(item, dict))
        if isinstance(payload, dict):
            for key in ("documents", "chunks", "knowledge"):
                if isinstance(payload.get(key), list):
                    return (item for item in payload[key] if isinstance(item, dict))
            combined = []
            for key, kind in (("scenarios", "scenario"), ("careers", "career"), ("satisfaction", "satisfaction")):
                entries = payload.get(key, [])
                if isinstance(entries, dict):
                    entries = list(entries.values())
                if isinstance(entries, list):
                    combined.extend(dict(item, kind=kind) for item in entries if isinstance(item, dict))
            if combined:
                return combined
            return (item for item in payload.values() if isinstance(item, dict))
        raise ValueError("Knowledge corpus must be a JSON array or object")

    def load_knowledge_bases(self) -> None:
        if "documents" in self.config:
            raw_documents = list(self.config["documents"] or [])
        else:
            configured_path = self.config.get("corpus_file") or self.config.get("knowledge_path")
            path = Path(configured_path) if configured_path else Path(__file__).resolve().parents[1] / "backend" / "knowledge.json"
            if not path.exists():
                if configured_path:
                    raise FileNotFoundError(f"Knowledge corpus does not exist: {path}")
                raw_documents = []
            else:
                with path.open(encoding="utf-8-sig") as stream:
                    raw_documents = list(self._unpack(json.load(stream)))
        unique: Dict[str, Dict[str, Any]] = {}
        for document in raw_documents:
            item = self.normalize_document(document)
            if item["text"]:
                unique.setdefault(item["id"], item)
        self.documents = list(unique.values())
        self.scenario_index = {item["id"]: item for item in self.documents if item["kind"] == "scenario"}
        self.career_index = {item["id"]: item for item in self.documents if item["kind"] == "career"}
        self.satisfaction_index = {item["id"]: item for item in self.documents if item["kind"] == "satisfaction"}

    def search(
        self, query: str, documents: Optional[List[Dict[str, Any]]] = None, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Return source chunks; an empty or unrelated query returns []."""
        if top_k <= 0:
            return []
        query_terms = set(tokenize(query))
        if not query_terms:
            return []
        corpus = self.documents if documents is None else [self.normalize_document(item) for item in documents]
        if not corpus:
            return []
        frequencies, lengths, title_terms = [], [], []
        for item in corpus:
            body_terms = tokenize(item["text"])
            heading_terms = tokenize(item["title"])
            terms = body_terms + heading_terms * 3
            frequencies.append(Counter(terms))
            lengths.append(len(terms))
            title_terms.append(set(heading_terms))
        average_length = max(1.0, sum(lengths) / len(corpus))
        document_frequencies = Counter()
        for frequency in frequencies:
            document_frequencies.update(frequency.keys())
        ranked = []
        for item, frequency, length, heading in zip(corpus, frequencies, lengths, title_terms):
            matched = query_terms.intersection(frequency)
            if not matched:
                continue
            score = 0.0
            for term in sorted(matched):
                inverse_frequency = math.log(1 + (len(corpus) - document_frequencies[term] + 0.5) / (document_frequencies[term] + 0.5))
                count = frequency[term]
                score += inverse_frequency * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * length / average_length))
            coverage = len(matched) / len(query_terms)
            score *= 0.5 + 0.5 * coverage
            score += 0.4 * len(query_terms.intersection(heading)) / len(query_terms)
            result = dict(item)
            relevance = coverage * (1 - math.exp(-score))
            result.update(score=round(relevance, 6), relevance_score=round(relevance, 6), retrieval_score=round(score, 6))
            ranked.append(result)
        ranked.sort(key=lambda item: (-item["retrieval_score"], item["id"]))
        minimum_score = float(self.config.get("min_score", 0.0))
        results = [item for item in ranked if item["score"] >= minimum_score][:top_k]
        for rank, item in enumerate(results, start=1):
            item["rank"] = rank
        return results

    def retrieve_scenarios(self, query: str, context: Optional[Dict[str, Any]] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        candidates = list(self.scenario_index.values())
        if context and context.get("theme"):
            candidates = [item for item in candidates if item.get("theme", item["metadata"].get("theme")) == context["theme"]]
        return self.search(self.build_fusion_query("scenario", query, context), candidates, top_k)

    def retrieve_careers(self, query: str, skills: Optional[List[str]] = None, interests: Optional[List[str]] = None, top_k: int = 10) -> List[Dict[str, Any]]:
        fused = self.build_fusion_query("career", query, {"skills": skills, "interests": interests})
        return self.search(fused, list(self.career_index.values()), top_k)

    def retrieve_satisfaction_cases(self, career_id: str, scenario_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        cases = []
        for item in self.satisfaction_index.values():
            data = {**item["metadata"], **item}
            if data.get("career_id") == career_id and data.get("scenario_id") == scenario_id:
                cases.append(dict(item))
        return sorted(cases, key=lambda item: item["id"])[:max(0, limit)]

    def build_fusion_query(self, query_type: str, original_query: str, context: Optional[Dict[str, Any]] = None) -> str:
        additions = [_text((context or {}).get(key)) for key in ("skills", "interests", "theme", "field", "career", "goals")]
        return " ".join(part.strip() for part in [original_query, *additions] if part and part.strip())

    def hybrid_search(self, query: str, index_name: str, alpha: float = 0.5) -> List[Dict[str, Any]]:
        """Combined BM25 lexical + dense vector similarity search.

        Alpha controls the blend: 0 = pure BM25, 1 = pure vector.
        Falls back to lexical-only when no embedding model is available.
        """
        if not 0 <= alpha <= 1:
            raise ValueError("alpha must be between 0 and 1")
        indexes = {"scenario": self.scenario_index, "scenarios": self.scenario_index,
                   "career": self.career_index, "careers": self.career_index,
                   "satisfaction": self.satisfaction_index, "user_history": self.user_history_index}
        name = index_name.removesuffix("_index")
        top_k = int(self.config.get("top_k", 5))

        if name in {"all", "knowledge", "documents"}:
            candidates = self.documents
            candidate_ids = {d["id"] for d in candidates}
        elif name in indexes:
            candidates = list(indexes[name].values())
            candidate_ids = {d["id"] for d in candidates}
        else:
            raise ValueError(f"Unknown retrieval index: {index_name}")

        # Lexical scores
        lexical = {item["id"]: item.get("score", 0.0) for item in
                   self.search(query, candidates, top_k)}

        # Vector scores
        vector: Dict[str, float] = {}
        if self._embedder and self._embeddings is not None and candidates:
            idx_map = {d["id"]: i for i, d in enumerate(self.documents)}
            index = self._indices.get(name, self._indices.get("all"))
            index_ids = self._indices.get(name)
            if index is not None and isinstance(index, tuple):
                hnsw, positions = index
                query_vec = self._embedder.encode([query])[0:1]
                labels, distances = self._embedder.search(hnsw, query_vec, max(top_k * 2, len(candidates)))
                for label, dist in zip(labels, distances):
                    doc_idx = positions[label]
                    doc = self.documents[doc_idx]
                    if doc["id"] in candidate_ids:
                        vector[doc["id"]] = 1.0 - float(dist)  # cosine distance -> similarity
            elif index is not None:
                query_vec = self._embedder.encode([query])[0:1]
                labels, distances = self._embedder.search(index, query_vec, max(top_k * 2, len(candidates)))
                for label, dist in zip(labels, distances):
                    doc = self.documents[label]
                    vector[doc["id"]] = 1.0 - float(dist)

        if not vector:
            return [item for item in candidates if item["id"] in lexical][:top_k]

        # Normalize and blend
        def normalize(scores: Dict[str, float]) -> Dict[str, float]:
            if not scores:
                return {}
            max_s = max(scores.values())
            if max_s == 0:
                return {k: 0.0 for k in scores}
            return {k: v / max_s for k, v in scores.items()}

        lex_norm = normalize(lexical)
        vec_norm = normalize(vector)
        all_ids = set(lex_norm) | set(vec_norm)
        blended = {
            doc_id: (1 - alpha) * lex_norm.get(doc_id, 0.0) + alpha * vec_norm.get(doc_id, 0.0)
            for doc_id in all_ids
        }
        ranked = sorted(blended, key=lambda d: (-blended[d], d))[:top_k]
        lookup = {item["id"]: item for item in candidates}
        results = []
        for rank, doc_id in enumerate(ranked, start=1):
            item = dict(lookup[doc_id])
            item.update(retrieval_score=round(blended[doc_id], 6), rank=rank,
                        lexical_score=round(lex_norm.get(doc_id, 0.0), 6),
                        vector_score=round(vec_norm.get(doc_id, 0.0), 6))
            results.append(item)
        return results

    def search_by_profile(self, profile_vector: np.ndarray, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find documents whose embeddings are closest to a user profile vector.

        This enables retrieving career/knowledge chunks semantically aligned with
        the user's measured intelligence dimensions rather than keyword overlap.
        """
        if self._embedder is None or self._embeddings is None or not self.documents:
            return []
        if len(self._embeddings) == 0 or profile_vector.shape[0] != self._embeddings.shape[1]:
            return []
        index = self._indices.get("all")
        if index is None:
            return []
        hnsw = index if not isinstance(index, tuple) else index[0]
        labels, distances = self._embedder.search(hnsw, profile_vector.reshape(1, -1), max(top_k * 2, len(self.documents)))
        results = []
        for rank, (label, dist) in enumerate(zip(labels, distances), start=1):
            item = dict(self.documents[label])
            item.update(retrieval_score=round(1.0 - float(dist), 6), rank=rank,
                        vector_score=round(1.0 - float(dist), 6))
            results.append(item)
        return results
