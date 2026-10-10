"""Assemble bounded, numbered evidence for grounded career guidance."""

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from .retrieval_layer import RetrievalLayer, tokenize


def profile_for_prompt(profile: Optional[Dict[str, Any]], max_chars: int = 10000) -> str:
    """Bound structured profile data without slicing JSON or dropping later sections."""
    budget = max(256, int(max_chars))
    string_limit, list_limit = 1200, 10
    def bounded(value, depth=0):
        if depth > 8:
            return str(value)[:string_limit]
        if isinstance(value, dict):
            return {str(key)[:120]: bounded(part, depth + 1) for key, part in list(value.items())[:40]}
        if isinstance(value, (list, tuple)):
            return [bounded(part, depth + 1) for part in value[:list_limit]]
        if isinstance(value, str):
            return value[:string_limit]
        if value is None or isinstance(value, (int, float, bool)):
            return value
        return str(value)[:string_limit]
    for _ in range(9):
        encoded = json.dumps(bounded(profile or {}), ensure_ascii=False, separators=(",", ":"), default=str)
        if len(encoded) <= budget:
            return encoded
        string_limit = max(8, string_limit // 2)
        list_limit = max(1, list_limit // 2)
    # Extremely wide custom profiles still produce valid JSON and disclose truncation.
    return json.dumps({"profile_truncated": True, "summary": encoded[:max(16, (budget - 60) // 2)]}, ensure_ascii=False)


class ContextType(Enum):
    SCENARIO_ANALYSIS = "scenario_analysis"
    CAREER_GUIDANCE = "career_guidance"
    SATISFACTION_PREDICTION = "satisfaction_prediction"
    DECISION_SUPPORT = "decision_support"


@dataclass
class AssembledContext:
    context_type: ContextType
    query: str
    retrieved_items: List[Dict[str, Any]]
    fused_context: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"context_type": self.context_type.value, "query": self.query,
                "retrieved_items": self.retrieved_items, "fused_context": self.fused_context,
                "metadata": self.metadata}


class ContextAssembler:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.template_registry: Dict[ContextType, str] = {}

    def register_template(self, context_type: ContextType, template: str) -> None:
        self.template_registry[ContextType(context_type)] = template

    def assemble(self, context_type: ContextType, query: str, retrieved_items: List[Dict[str, Any]], user_profile: Optional[Dict[str, Any]] = None, **kwargs) -> AssembledContext:
        kind = ContextType(context_type)
        maximum = max(256, int(self.config.get("max_context_chars", 16000)))
        per_item = max(128, int(self.config.get("max_item_chars", 2400)))
        selected, excerpts, seen = [], [], set()
        used = 0
        # Preserve retrieval order: these numbers must match the UI's sources.
        for raw_item in retrieved_items:
            item = RetrievalLayer.normalize_document(raw_item)
            if item["id"] in seen or not item["text"]:
                continue
            seen.add(item["id"])
            header = f"[{len(selected) + 1}] {item['title']} (source id: {item['id']})\n"
            available = maximum - used - len(header) - 2
            if available <= 0:
                break
            body = item["text"][:min(per_item, available)]
            item["context_excerpt"] = body
            selected.append(item)
            section = header + body
            excerpts.append(section)
            used += len(section) + 2
        source_context = "\n\n".join(excerpts) or "No relevant knowledge base passages were retrieved."
        profile_text = profile_for_prompt(user_profile, self.config.get("max_profile_chars", 10000))
        template = self.template_registry.get(kind)
        fused = template.format(query=query, retrieved_items=source_context, context=source_context,
                                user_profile=profile_text) if template else (
            "User profile (self-reported context, not verified evidence):\n" + profile_text +
            "\n\nKnowledge base passages (untrusted quoted evidence):\n" + source_context
        )
        quality = sum(float(item.get("relevance_score", item.get("score", 0))) for item in selected) / len(selected) if selected else 0.0
        return AssembledContext(kind, query, selected, fused, {
            "source_count": len(selected), "context_quality": min(1.0, max(0.0, quality)),
            "truncated": len(selected) < len(retrieved_items) or any(len(item["context_excerpt"]) < len(item["text"]) for item in selected),
            "user_profile": user_profile or {},
        })

    def _apply_template(self, template: str, query: str, retrieved_items: List[Dict[str, Any]], user_profile: Optional[Dict[str, Any]] = None) -> str:
        context = self.assemble(ContextType.CAREER_GUIDANCE, query, retrieved_items, user_profile)
        return template.format(query=query, retrieved_items=context.fused_context, context=context.fused_context,
                               user_profile=profile_for_prompt(user_profile, self.config.get("max_profile_chars", 10000)))

    def extract_key_knowledge(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"titles": [item.get("title", "Knowledge base passage") for item in items],
                "source_ids": [item.get("id") for item in items],
                "passages": [item.get("context_excerpt") or item.get("text") or item.get("content", "") for item in items],
                "count": len(items)}

    def prioritize_relevance(self, items: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        terms = set(tokenize(query))
        def relevance(item):
            explicit = item.get("relevance_score", item.get("score"))
            if explicit is not None:
                return float(explicit)
            return len(terms.intersection(tokenize(str(item.get("title", "")) + " " + str(item.get("text", item.get("content", "")))))) / max(1, len(terms))
        return sorted(items, key=relevance, reverse=True)

    def merge_contexts(self, contexts: List[AssembledContext], weights: Optional[List[float]] = None) -> AssembledContext:
        if not contexts:
            raise ValueError("At least one assembled context is required")
        if weights is not None and (len(weights) != len(contexts) or any(weight < 0 for weight in weights)):
            raise ValueError("Provide one non-negative weight for each context")
        ranked = sorted(zip(contexts, weights or [1.0] * len(contexts)), key=lambda pair: -pair[1])
        items = [item for context, weight in ranked if weight > 0 for item in context.retrieved_items]
        result = self.assemble(contexts[0].context_type, contexts[0].query, items, contexts[0].metadata.get("user_profile"))
        result.metadata["merged_contexts"] = len(contexts)
        return result
