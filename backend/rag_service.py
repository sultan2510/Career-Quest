"""Connect the local RAG pipeline to CareerQuest's corpus and user progress."""

import json
import logging
import re
from pathlib import Path
from typing import Any

import asyncpg
import numpy as np

from config.settings import IntelligenceDimension
from rag.context_assembler import ContextAssembler, ContextType
from rag.embedding_layer import EmbeddingLayer
from rag.generation_layer import GenerationLayer, ResponseType
from rag.retrieval_layer import RetrievalLayer
from scoring import DeterministicScorer, IntelligenceProfile, ResponseOption, Scenario, ScenarioResponse
from scoring import ProfileVectorizer

try:
    from models.xgboost_scorer import XGBoostScorer
except ImportError:
    XGBoostScorer = None  # type: ignore

try:
    from .progress import ProgressSnapshot
except ImportError:
    from progress import ProgressSnapshot

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent

# The questionnaire has one spatial axis; map it to one canonical dimension
# rather than inventing evidence for three separate spatial measures.
DNA_DIMENSIONS = {
    "logical": IntelligenceDimension.LOGICAL_MATHEMATICAL,
    "spatial": IntelligenceDimension.SPATIAL_TRANSFORMATIONAL,
    "verbal": IntelligenceDimension.VERBAL_LINGUISTIC,
    "inter": IntelligenceDimension.INTERPERSONAL,
    "intra": IntelligenceDimension.INTRAPERSONAL,
    "bodily": IntelligenceDimension.BODILY_KINESTHETIC,
    "musical": IntelligenceDimension.MUSICAL,
    "naturalistic": IntelligenceDimension.NATURALISTIC,
    "existential": IntelligenceDimension.EXISTENTIAL,
    "fluid": IntelligenceDimension.FLUID_INTELLIGENCE,
    "learning": IntelligenceDimension.LEARNING_ABILITY,
    "adapt": IntelligenceDimension.CAREER_ADAPTABILITY,
    "creative": IntelligenceDimension.CREATIVE_PROBLEM_SOLVING,
}
RECONCILIATION = ({"inter": 2, "intra": 2}, {"intra": 3}, {"adapt": 3})


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or DATA_DIR / "catalog.json"
    if not catalog_path.exists():
        return {"careers": [], "dna_scenarios": [], "dna_dimensions": {}}
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def load_documents(catalog: dict | None = None) -> list[dict[str, Any]]:
    """Use the real UI catalog alongside the original questionnaire corpus."""
    catalog = catalog if catalog is not None else load_catalog()
    documents = []
    for career in catalog.get("careers", []):
        career_id = career["id"]
        url = "https://www.onetonline.org/find/quick?s="
        from urllib.parse import quote
        url += quote(career.get("onet", career["name"]))
        text = "\n".join([
            f"Career: {career['name']}. Category: {career.get('category', '')}.",
            career.get("description", ""),
            "Typical tasks: " + "; ".join(career.get("tasks", [])),
            "Work realities: " + career.get("reality", ""),
            "AI and this career: " + career.get("aiNote", ""),
            "Beginner skill: " + career.get("skill", ""),
            "Small project: " + career.get("project", ""),
            "Interests: " + ", ".join(career.get("tags", [])),
            "CareerQuest's Ikigai map uses sourced O*NET, BLS and ILOSTAT evidence for its labour-market circles. These hand-written career notes and scenarios are exploratory.",
        ])
        documents.append({"id": f"career:{career_id}", "title": career["name"], "text": text,
                          "kind": "career", "url": url, "metadata": {"career_id": career_id}})
        for index, scene in enumerate(career.get("scenes", [])):
            scene_text = "\n".join([scene.get("prompt", "")] + [
                f"Choice: {choice['text']}\nScripted outcome: {choice['outcome']}"
                for choice in scene.get("choices", [])
            ])
            documents.append({"id": f"simulation:{career_id}:{index}",
                              "title": f"{career['name']}: {scene['title']}", "text": scene_text,
                              "kind": "scenario", "metadata": {"career_id": career_id}})
    for scenario in catalog.get("dna_scenarios", []):
        text = "\n".join(scenario.get("narrative", []) + [scenario.get("prompt", "")] + [
            f"{option['id']}: {option['text']}" for option in scenario.get("options", [])
        ] + ["Questionnaire rationale: " + scenario.get("rationale", "")])
        documents.append({"id": f"dna:{scenario['id']}", "title": scenario["title"],
                          "text": text, "kind": "scenario", "metadata": {"scenario_id": scenario["id"]}})
    knowledge_path = DATA_DIR / "knowledge.json"
    if knowledge_path.exists():
        for index, chunk in enumerate(json.loads(knowledge_path.read_text(encoding="utf-8"))):
            documents.append({"id": f"questionnaire:{index}", "title": chunk["title"],
                              "text": chunk.get("text", chunk.get("content", "")), "kind": "questionnaire"})
    return documents


def build_user_context_ml(progress: ProgressSnapshot, catalog: dict, user_id: str, ml_scorer: Any = None) -> dict:
    """Build user context with ML-augmented DNA scores when an XGBoost scorer is available.

    The ML model predicts per-dimension scores from scenario response one-hot patterns.
    We blend 30% ML prediction with 70% deterministic rubric score, so the deterministic
    result remains authoritative but the ML layer adds pattern-based nuance.
    """
    context = build_user_context(progress, catalog, user_id)
    if ml_scorer is None or not ml_scorer.available:
        return context

    scorer = DeterministicScorer()

    # Build ALL catalog scenarios for ML encoding (must match training feature space)
    all_scenarios: list[Scenario] = []
    for entry in catalog.get("dna_scenarios", []):
        dimensions = {DNA_DIMENSIONS[key] for option in entry.get("scores", {}).values()
                      for key in option if key in DNA_DIMENSIONS}
        scenario = Scenario(entry["id"], title=entry["title"], tier=2 if entry.get("parent") else 1,
                            target_dimensions=list(dimensions))
        scenario.response_options = [ResponseOption(option, scoring_vector={DNA_DIMENSIONS[key]: score
                                     for key, score in vector.items() if key in DNA_DIMENSIONS})
                                     for option, vector in entry["scores"].items()]
        all_scenarios.append(scenario)

    # Run deterministic scoring on answered scenarios
    dna_profile = IntelligenceProfile(user_id, "careerquest")
    for entry in catalog.get("dna_scenarios", []):
        selected = progress.dna.answers.get(entry["id"])
        if selected not in entry.get("scores", {}):
            continue
        if entry.get("parent") and progress.dna.answers.get(entry["parent"]) != entry.get("option"):
            continue
        dimensions = {DNA_DIMENSIONS[key] for option in entry["scores"].values()
                      for key in option if key in DNA_DIMENSIONS}
        scenario = next(s for s in all_scenarios if s.scenario_id == entry["id"])
        scorer.score_response(scenario, ScenarioResponse(user_id, "careerquest", entry["id"], selected), dna_profile)

    # Collect selected answers for answered scenarios to pass into the ML encoder
    selected_answers: dict[str, str] = {}
    for entry in catalog.get("dna_scenarios", []):
        selected = progress.dna.answers.get(entry["id"])
        if selected in entry.get("scores", {}):
            if not entry.get("parent") or progress.dna.answers.get(entry["parent"]) == entry.get("option"):
                selected_answers[entry["id"]] = selected

    # Get ML predictions using the full scenario tree for consistent feature encoding
    ml_scores = ml_scorer.predict(dna_profile, all_scenarios, selected_answers)
    if not ml_scores:
        return context

    # Blend the ML scores into the context dimensions (30% ML, 70% deterministic)
    dim_by_label = {item["dimension"]: item for item in context["DNA"]["dimensions"]}
    dim_to_key = {dim: key for key, dim in DNA_DIMENSIONS.items()}
    labels = catalog.get("dna_dimensions", {})
    for dim, ml_prediction in ml_scores.items():
        key = dim_to_key.get(dim)
        details = labels.get(key, {}) if key else {}
        label = details.get("label", dim.value.replace("_", "-")) if isinstance(details, dict) else str(details)
        if label in dim_by_label:
            item = dim_by_label[label]
            deterministic_points = item["points"]
            ml_points = float(abs(ml_prediction))  # predictions can be negative; clamp
            blended = 0.7 * deterministic_points + 0.3 * ml_points
            item["points"] = round(blended, 3)
            item["ml_adjusted"] = True

    # Recompute normalized scores with blended points
    for item in context["DNA"]["dimensions"]:
        if item["possible"] > 0:
            item["normalized"] = round(min(1.0, item["points"] / item["possible"]), 3)
            item["weighted"] = round(item["normalized"] * 1.0, 3)

    context["DNA"]["ml_enhanced"] = True
    return context


# Dimension label mapping for ML score lookup
DIM_LABELS = {
    IntelligenceDimension.LOGICAL_MATHEMATICAL: "logical-mathematical",
    IntelligenceDimension.SPATIAL_TRANSFORMATIONAL: "spatial-transformational",
    IntelligenceDimension.SPATIAL_ANALYTICAL: "spatial-analytical",
    IntelligenceDimension.SPATIAL_OBJECT_VISUAL: "spatial-object-visual",
    IntelligenceDimension.VERBAL_LINGUISTIC: "verbal-linguistic",
    IntelligenceDimension.INTERPERSONAL: "interpersonal",
    IntelligenceDimension.INTRAPERSONAL: "intrapersonal",
    IntelligenceDimension.BODILY_KINESTHETIC: "bodily-kinesthetic",
    IntelligenceDimension.MUSICAL: "musical",
    IntelligenceDimension.NATURALISTIC: "naturalistic",
    IntelligenceDimension.EXISTENTIAL: "existential",
    IntelligenceDimension.FLUID_INTELLIGENCE: "fluid-intelligence",
    IntelligenceDimension.LEARNING_ABILITY: "learning-ability",
    IntelligenceDimension.CAREER_ADAPTABILITY: "career-adaptability",
    IntelligenceDimension.CREATIVE_PROBLEM_SOLVING: "creative-problem-solving",
    IntelligenceDimension.EMOTIONAL_INTELLIGENCE: "emotional-intelligence",
    IntelligenceDimension.LEADERSHIP: "leadership",
    IntelligenceDimension.SYSTEMS_THINKING: "systems-thinking",
}

from typing import Any  # noqa: E402  (needed for type hints above)


def build_user_context(progress: ProgressSnapshot, catalog: dict, user_id: str) -> dict:
    """Recompute DNA from known choices; never treat client scores as evidence."""
    scorer = DeterministicScorer()
    dna_profile = IntelligenceProfile(user_id, "careerquest")
    accepted = []
    for entry in catalog.get("dna_scenarios", []):
        selected = progress.dna.answers.get(entry["id"])
        if selected not in entry.get("scores", {}):
            continue
        if entry.get("parent") and progress.dna.answers.get(entry["parent"]) != entry.get("option"):
            continue
        dimensions = {DNA_DIMENSIONS[key] for option in entry["scores"].values()
                      for key in option if key in DNA_DIMENSIONS}
        scenario = Scenario(entry["id"], title=entry["title"], tier=2 if entry.get("parent") else 1,
                            target_dimensions=list(dimensions))
        scenario.response_options = [ResponseOption(option, scoring_vector={DNA_DIMENSIONS[key]: score
                                     for key, score in vector.items() if key in DNA_DIMENSIONS})
                                     for option, vector in entry["scores"].items()]
        scorer.score_response(scenario, ScenarioResponse(user_id, "careerquest", entry["id"], selected), dna_profile)
        accepted.append({"scenario": entry["title"], "option": selected})
    # Match the existing UI's explicit reflection nudges, without adding
    # fabricated scenario counts or evidence to unassessed dimensions.
    if progress.dna.tie in DNA_DIMENSIONS:
        dna_profile.dimensions[DNA_DIMENSIONS[progress.dna.tie]].raw_score += 3
    if progress.dna.recon is not None:
        for key, points in RECONCILIATION[progress.dna.recon].items():
            dna_profile.dimensions[DNA_DIMENSIONS[key]].raw_score += points
    scorer._calculate_riasec(dna_profile)
    scores = []
    labels = catalog.get("dna_dimensions", {})
    for key, dimension in DNA_DIMENSIONS.items():
        score = dna_profile.dimensions[dimension]
        if not score.scenarios_assessed:
            continue
        details = labels.get(key, {})
        label = details.get("label", dimension.value.replace("_", " ")) if isinstance(details, dict) else str(details)
        normalized = min(1, score.raw_score / score.max_possible) if score.max_possible else 0
        weight = details.get("weight", 1) if isinstance(details, dict) else 1
        scores.append({"dimension": label, "points": score.raw_score, "possible": score.max_possible,
                       "normalized": round(normalized, 3), "weighted": round(normalized * weight, 3),
                       "assessed": score.scenarios_assessed, "confidence": score.confidence.value})
    scores.sort(key=lambda item: item["weighted"], reverse=True)
    careers = {career["id"]: career for career in catalog.get("careers", [])}
    evidence = []
    for event in progress.evidence[-3:]:
        career = careers.get(event.careerId, {})
        decisions = []
        for decision in event.decisions[:2]:
            choices = career.get("scenes", [])
            scene = choices[decision.scene] if decision.scene < len(choices) else {}
            known = next((choice for choice in scene.get("choices", []) if choice["text"] == decision.text), None)
            decisions.append({"scene": scene.get("title", str(decision.scene)), "text": decision.text[:240],
                              "outcome": known["outcome"][:240] if known and decision.source == "choice" else "Free-text approach; not scored",
                              "quality": known["quality"] if known and decision.source == "choice" else None})
        evidence.append({"career": career.get("name", event.careerId), "enjoyment_out_of_5": event.enjoyment,
                         "self_confidence_out_of_5": event.confidence,
                         "decisions": decisions})
    plan = careers.get(progress.planCareer, {}) if progress.planCareer else {}
    return {
        "DNA": {"answered": len(accepted), "dimensions": scores, "recent_answers": accepted[-8:],
                "riasec_code": dna_profile.riasec_code if scores else None,
                "note": "Scenario signals are exploratory heuristics, not validated intelligence percentiles or diagnoses.",
                "tie_preference": progress.dna.tie, "social_reflection": progress.dna.recon},
        "discovery": {"character": progress.character, "answers": progress.answers},
        "simulations": evidence,
        "journal": [{"prompt": entry.prompt[:120], "text": entry.text[:500], "at": entry.at}
                    for entry in progress.journal[:3]],
        "roadmap": {"career": plan.get("name", progress.planCareer), "skill": plan.get("skill"),
                    "project": plan.get("project"), "completed_tasks": progress.tasks.get(progress.planCareer, [])[:12]
                    if progress.planCareer else []},
        "explored_careers": [careers.get(key, {}).get("name", key) for key in progress.explored[-15:]],
    }


def personal_documents(context: dict) -> list[dict]:
    """Private passages exist only for this request, never in shared indexes."""
    docs = []
    dna = context["DNA"]
    if dna["answered"]:
        text = "Your Learning DNA scenario strengths (exploratory signals):\n" + "\n".join(
            f"{item['dimension']}: {item['points']:g}/{item['possible']:g} points, "
            f"{item['assessed']} assessed scenarios, evidence confidence {item['confidence']}."
            for item in dna["dimensions"]
        )
        docs.append({"id": "personal:dna", "title": "Your Learning DNA strengths", "text": text, "kind": "personal"})
    for index, event in enumerate(context["simulations"]):
        docs.append({"id": f"personal:simulation:{index}", "title": f"Your simulation reflection: {event['career']}",
                     "text": f"You reported enjoyment {event['enjoyment_out_of_5']}/5 and confidence "
                             f"{event['self_confidence_out_of_5']}/5 for {event['career']}. "
                             "These are self-reported reactions, not a performance diagnosis.\n" + "\n".join(
                                 f"Your decision: {decision['text']}\nScripted outcome: {decision['outcome']}"
                                 for decision in event["decisions"]), "kind": "personal"})
    for index, entry in enumerate(context["journal"]):
        docs.append({"id": f"personal:journal:{index}", "title": "Your journal reflection",
                     "text": f"Your recent journal entry ({entry['at']}):\nPrompt: {entry['prompt']}\n"
                             f"You wrote: {entry['text']}", "kind": "personal"})
    roadmap = context["roadmap"]
    if roadmap["career"]:
        docs.append({"id": "personal:roadmap", "title": f"Your roadmap: {roadmap['career']}",
                     "text": f"Your chosen exploration plan is {roadmap['career']}. "
                             f"Suggested beginner skill: {roadmap['skill']}. Suggested small project: {roadmap['project']}. "
                             f"You completed {len(roadmap['completed_tasks'])} roadmap steps.", "kind": "personal"})
    return docs


def search_query(question: str, context: dict, catalog: dict) -> str:
    """Add personal signals to broad career questions, keeping the question first."""
    if not re.search(r"\b(career|strength|strengths|fit|fits|match|matches|roadmap|plan|next)\b", question, re.I):
        return question
    careers = catalog.get("careers", [])
    # A specifically named profession should retain its own retrieval priority.
    if any(career["name"].lower() in question.lower() for career in careers):
        return question
    signals = [item["dimension"] for item in context["DNA"]["dimensions"][:3]]
    signals += [item["career"] for item in context["simulations"] if item["enjoyment_out_of_5"] >= 4]
    if context["roadmap"]["career"]:
        signals.append(context["roadmap"]["career"])
    return question + ("\nStudent career context: " + "; ".join(signals) if signals else "")


class RagService:
    def __init__(self, catalog: dict | None = None, generation_config: dict | None = None,
                 use_vectors: bool = True, use_ml_scoring: bool = True):
        self.catalog = catalog if catalog is not None else load_catalog()
        self.documents = load_documents(self.catalog)
        self.retriever = RetrievalLayer({"documents": self.documents, "use_vectors": use_vectors})
        self.assembler = ContextAssembler()
        self.generator = GenerationLayer(generation_config)
        self._profile_vectorizer = ProfileVectorizer()
        self._query_embedder = EmbeddingLayer() if use_vectors else None
        self._ml_scorer = XGBoostScorer() if use_ml_scoring and XGBoostScorer is not None else None

    def _profile_vector(self, user_context: dict) -> np.ndarray | None:
        """Encode the user's DNA/dimension scores into a query-context vector."""
        if not self._query_embedder or not self._query_embedder.available:
            return None
        if not user_context.get("DNA", {}).get("dimensions"):
            return None
        dim_scores = {item["dimension"]: item["normalized"]
                      for item in user_context["DNA"]["dimensions"]}
        vector = np.zeros(self._profile_vectorizer.dimension_order.__len__(), dtype=np.float32)
        for i, dim in enumerate(self._profile_vectorizer.dimension_order):
            label = dim.value.replace("_", "-")
            vector[i] = dim_scores.get(label, 0.0)
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else None

    def _fuse_query_and_profile(self, question: str, profile_vector: np.ndarray | None) -> np.ndarray:
        """Encode the question and fuse with the profile vector for personalized retrieval."""
        if self._query_embedder is None or not self._query_embedder.available:
            return np.array([])
        q_vec = self._query_embedder.encode([question])[0]
        if profile_vector is not None:
            fused = 0.7 * q_vec + 0.3 * profile_vector
            norm = np.linalg.norm(fused)
            return fused / norm if norm > 0 else fused
        return q_vec

    async def _database_documents(self, db, question: str) -> tuple[list[dict], str]:
        words = list(dict.fromkeys(re.findall(r"[a-z]{3,}", question.lower())))[:24]
        if not words:
            return [], "bundled"
        try:
            rows = await db.fetch(
                "select id, title, content, to_jsonb(r)->>'source_key' as source_key, "
                "to_jsonb(r)->>'url' as url, to_jsonb(r)->>'kind' as kind "
                "from rag_chunks r where tsv @@ to_tsquery('english', $1) "
                "order by ts_rank(tsv, to_tsquery('english', $1)) desc, id limit 12",
                " | ".join(words),
            )
        except asyncpg.UndefinedTableError:
            # The old account/progress database works before knowledge ingestion.
            # Report that state explicitly; operational DB errors are not ignored.
            return [], "bundled_not_ingested"
        return [{"id": row["source_key"] or f"database:{row['id']}", "title": row["title"],
                 "text": row["content"], "url": row["url"], "kind": row["kind"] or "knowledge"}
                for row in rows], "database_and_bundled" if rows else "bundled"

    async def ask(self, db, user_id: str, question: str, progress: ProgressSnapshot,
                  profile_summary: str | None = None, profile_source: str = "database") -> dict:
        user_context = build_user_context_ml(progress, self.catalog, user_id, self._ml_scorer)
        query = search_query(question, user_context, self.catalog)
        try:
            database_docs, knowledge_source = await self._database_documents(db, query)
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, TimeoutError):
            logger.warning("CareerQuest knowledge database is unavailable")
            return {"status": "unavailable", "mode": "retrieved", "answer": None, "sources": [],
                    "message": "Your mentor is temporarily unavailable. Please try again.",
                    "knowledge_source": "database_unavailable"}
        # Shared identifiers let a database update replace its bundled passage.
        documents = {doc["id"]: doc for doc in self.documents}
        documents.update({doc["id"]: doc for doc in database_docs})
        documents.update({doc["id"]: doc for doc in personal_documents(user_context)})

        # Hybrid retrieval: BM25 lexical + vector similarity fused by profile
        profile_vector = self._profile_vector(user_context)
        use_vectors = self._query_embedder is not None and self._query_embedder.available and profile_vector is not None
        if use_vectors:
            query_vec = self._fuse_query_and_profile(query, profile_vector)
            if query_vec.size > 0:
                vector_items = self.retriever.search_by_profile(query_vec, top_k=5)
            else:
                vector_items = []
            # Re-rank lexical results with vector scores where IDs overlap
            lexical_items = self.retriever.search(query, documents=list(documents.values()), top_k=10)
            vector_ids = {item["id"]: item.get("retrieval_score", 0.0) for item in vector_items}
            lexical_ids = {item["id"]: item for item in lexical_items}
            # Blend: vector items first (they're semantically matched), then remaining lexical
            items = list(vector_items)
            for item in lexical_items:
                if item["id"] not in vector_ids:
                    items.append(item)
            items = items[:5]
        else:
            items = self.retriever.search(query, documents=list(documents.values()), top_k=5)

        if profile_summary:
            user_context["student_supplied_summary"] = profile_summary[:500]
        context = self.assembler.assemble(ContextType.CAREER_GUIDANCE, question, items, user_profile=user_context)
        response = await self.generator.agenerate(ResponseType.CAREER_RECOMMENDATION, question, context,
                                                  user_profile=user_context, retrieved_items=items)
        metadata = response.metadata
        sources = [{"n": source.get("n", index + 1), "title": source["title"],
                    "excerpt": source.get("excerpt", ""),
                    **({"url": source["url"]} if source.get("url") else {})}
                   for index, source in enumerate(response.citations)]
        return {"status": metadata.get("status", "ok"), "mode": metadata.get("mode", "retrieved"),
                "answer": response.content or None, "sources": sources,
                "confidence": response.confidence, "knowledge_source": knowledge_source,
                "profile_source": profile_source}
