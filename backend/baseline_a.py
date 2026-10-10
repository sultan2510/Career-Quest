"""Baseline A: independent TF-IDF/cosine career retrieval, no Ikigai features.

Examples:
  python backend/baseline_a.py --profile "Python statistics research"
  python backend/baseline_a.py --jobs data/job_postings.csv --country PK --profile "teach biology"

The default corpus is the downloaded O*NET 31.0 occupation snapshot. A postings CSV
must have title, description, country; optional occupation_id and skills columns.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "frontend/lib/data/occupation-evidence.json"
TOKEN = re.compile(r"[a-z][a-z0-9+#.]*", re.I)
SENIORITY = re.compile(r"\b(senior|sr|junior|jr|lead|principal|intern|trainee)\b", re.I)


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(re.sub(r"<[^>]+>", " ", text.lower()))


def normalize_title(title: str) -> str:
    return " ".join(tokenize(SENIORITY.sub(" ", title)))


def load_documents(postings: Path | None = None, country: str | None = None) -> list[dict]:
    if postings:
        with postings.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            required = {"title", "description", "country"}
            if not required <= set(reader.fieldnames or []):
                raise ValueError(f"Posting CSV needs columns: {', '.join(sorted(required))}")
            rows = list(reader)
        docs = [{"id": r.get("occupation_id") or normalize_title(r["title"]),
                 "title": r["title"], "country": r["country"].upper(),
                 "text": " ".join([r["title"], r["description"], r.get("skills", "")])}
                for r in rows if r["title"].strip() and r["description"].strip()]
        # A posting is one document; collapse duplicates by occupation/country so a
        # prolific employer cannot dominate solely through repeated adverts.
        grouped: dict[tuple[str, str], dict] = {}
        for d in docs:
            key = (d["id"], d["country"])
            if key not in grouped:
                grouped[key] = {**d, "text": "", "n_postings": 0}
            grouped[key]["text"] += " " + d["text"]
            grouped[key]["n_postings"] += 1
        docs = list(grouped.values())
    else:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        docs = [{"id": key, "title": occ["title"], "country": "US/PK",
                 "text": occ["title"] + " " + occ["description"] + " " + " ".join(occ.get("keywords", [])), "n_postings": None}
                for key, occ in data["occupations"].items()]
    if country and postings:
        docs = [d for d in docs if d["country"] == country.upper()]
    if not docs:
        raise ValueError("No eligible occupation documents for the selected country")
    return docs


class BaselineA:
    """Smoothed IDF, log term frequency, L2 normalization and cosine similarity."""

    def __init__(self, documents: list[dict]):
        self.documents = documents
        counts = [Counter(tokenize(d["text"])) for d in documents]
        df = Counter(term for count in counts for term in count)
        self.idf = {term: math.log((1 + len(counts)) / (1 + n)) + 1 for term, n in df.items()}
        self.vectors = [self.vector(count) for count in counts]

    def vector(self, counts: Counter) -> dict[str, float]:
        weighted = {term: (1 + math.log(freq)) * self.idf[term]
                    for term, freq in counts.items() if term in self.idf and freq > 0}
        norm = math.sqrt(sum(v * v for v in weighted.values()))
        return {term: value / norm for term, value in weighted.items()} if norm else {}

    def recommend(self, profile: str, k: int = 8) -> list[dict]:
        query = self.vector(Counter(tokenize(profile)))
        if not query:
            raise ValueError("Profile has no terms shared with the occupation corpus")
        scores = []
        for doc, vector in zip(self.documents, self.vectors):
            score = sum(value * vector.get(term, 0) for term, value in query.items())
            terms = sorted(query.keys() & vector.keys(), key=lambda term: query[term] * vector[term], reverse=True)
            scores.append({"id": doc["id"], "title": doc["title"], "country": doc["country"],
                           "cosine": round(score, 6), "shared_terms": terms[:5],
                           "n_postings": doc["n_postings"]})
        return sorted(scores, key=lambda row: (-row["cosine"], row["id"]))[:k]


def evaluate(model: BaselineA, examples: list[dict], k: int = 5) -> dict:
    """Held-out labels: [{"profile": "...", "relevant_ids": ["..."]}]."""
    if not examples:
        raise ValueError("At least one held-out example is required")
    hits = reciprocal = 0.0
    for case in examples:
        relevant = set(case["relevant_ids"])
        if not relevant:
            raise ValueError("Each example needs at least one relevant occupation ID")
        try:
            ranked = [row["id"] for row in model.recommend(case["profile"], k)]
        except ValueError:
            ranked = []  # out-of-vocabulary profiles count as misses
        matches = [i + 1 for i, career in enumerate(ranked) if career in relevant]
        hits += len(matches) / len(relevant)
        reciprocal += 1 / matches[0] if matches else 0
    return {f"recall@{k}": round(hits / len(examples), 4), "mrr": round(reciprocal / len(examples), 4), "n": len(examples)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, help="Real posting CSV; omit to use O*NET occupation descriptions")
    parser.add_argument("--country", choices=["US", "PK"])
    parser.add_argument("--profile", help="User skills and interests in free text")
    parser.add_argument("--labels", type=Path, help="Optional held-out relevance labels JSON")
    parser.add_argument("-k", type=int, default=8)
    args = parser.parse_args()
    model = BaselineA(load_documents(args.jobs, args.country))
    if args.profile:
        print(json.dumps(model.recommend(args.profile, args.k), indent=2))
    if args.labels:
        print(json.dumps(evaluate(model, json.loads(args.labels.read_text(encoding="utf-8")), args.k), indent=2))
    if not args.profile and not args.labels:
        parser.error("Provide --profile or --labels")
