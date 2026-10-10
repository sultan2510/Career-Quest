"""Regression tests for retrieval and numbered, bounded evidence assembly."""

import json

import pytest

from rag import ContextAssembler, ContextType, RetrievalLayer


@pytest.fixture
def corpus():
    return [
        {"id": "career-data", "title": "Data Scientist", "text": "Analyze data with Python and statistics. Build machine learning experiments.", "kind": "career", "url": "https://example.test/data"},
        {"id": "career-design", "title": "UX Designer", "content": "Design interfaces and test usability with interviews and prototypes.", "metadata": {"kind": "career"}},
        {"id": "scenario-puzzle", "title": "Scenario: Data puzzle", "text": "Analyze a spreadsheet and compare bar charts to find regional sales changes.", "kind": "scenario", "metadata": {"theme": "logical"}},
        {"id": "scenario-conflict", "title": "Scenario: Team conflict", "text": "Listen to team members and facilitate a discussion to resolve conflict.", "kind": "scenario", "metadata": {"theme": "social"}},
    ]


def test_title_weight_and_word_boundaries(corpus):
    retriever = RetrievalLayer({"documents": corpus})
    results = retriever.search("data scientist")
    assert results[0]["id"] == "career-data"
    assert all(0 < item["score"] <= 1 for item in results)
    assert retriever.search("scient") == []
    assert retriever.search("opaque quasiparticle") == []


def test_no_query_or_no_documents_is_not_a_match(corpus):
    retriever = RetrievalLayer({"documents": corpus})
    assert retriever.search("") == []
    assert retriever.search("the and please") == []
    assert retriever.search("Python", documents=[]) == []
    assert retriever.search("Python", top_k=0) == []


def test_structured_skills_are_retrieved_and_retained_in_evidence():
    retriever = RetrievalLayer({"documents": [{
        "id": "career-python", "kind": "career", "title": "Developer",
        "description": "Build applications.", "required_skills": [{"name": "Python"}],
    }]})
    item = retriever.retrieve_careers("", skills=["Python"])[0]
    assert item["id"] == "career-python"
    assert "Required skills: Python" in item["text"]


def test_search_is_stable_and_does_not_mutate_documents(corpus):
    retriever = RetrievalLayer({"documents": corpus})
    first = retriever.search("data")
    second = retriever.search("data")
    assert first == second
    assert [item["rank"] for item in first] == list(range(1, len(first) + 1))
    assert "score" not in corpus[0]
    assert "score" not in retriever.documents[0]


def test_scenario_search_is_filtered_and_grounded(corpus):
    retriever = RetrievalLayer({"documents": corpus})
    matches = retriever.retrieve_scenarios("team conflict", {"theme": "social"})
    assert [item["id"] for item in matches] == ["scenario-conflict"]
    assert retriever.retrieve_scenarios("team conflict", {"theme": "unknown"}) == []


def test_career_search_fuses_skills_without_scenario_results(corpus):
    retriever = RetrievalLayer({"documents": corpus})
    matches = retriever.retrieve_careers("", skills=["Python"], interests=["statistics"])
    assert [item["id"] for item in matches] == ["career-data"]
    assert matches[0]["url"] == "https://example.test/data"


def test_hybrid_compatibility_reports_real_local_scores(corpus):
    retriever = RetrievalLayer({"documents": corpus})
    assert retriever.hybrid_search("data", "career_index", 0.7)[0]["id"] == "career-data"
    assert retriever.hybrid_search("data", "all")
    with pytest.raises(ValueError):
        retriever.hybrid_search("data", "invented")
    with pytest.raises(ValueError):
        retriever.hybrid_search("data", "all", 2)


def test_fusion_uses_relevant_profile_fields_only():
    retriever = RetrievalLayer({"documents": []})
    query = retriever.build_fusion_query("career", "Career choices", {
        "skills": ["Python", "statistics"], "goals": "research",
        "interests": ["analysis"], "token": "secret-value",
    })
    assert query == "Career choices Python statistics analysis research"
    assert "secret-value" not in query


def test_json_corpus_loading_and_stable_ids(tmp_path):
    path = tmp_path / "knowledge.json"
    path.write_text(json.dumps([{"title": "Scenario: Spatial reasoning", "text": "Read maps and rotate shapes."}]), encoding="utf-8")
    first = RetrievalLayer({"corpus_file": str(path)})
    second = RetrievalLayer({"corpus_file": str(path)})
    assert first.documents == second.documents
    assert first.retrieve_scenarios("maps")[0]["id"].startswith("kb-")
    with pytest.raises(FileNotFoundError):
        RetrievalLayer({"knowledge_path": str(tmp_path / "missing.json")})


def test_satisfaction_cases_match_both_identifiers():
    retriever = RetrievalLayer({"documents": [
        {"id": "a", "kind": "satisfaction", "title": "Recorded feedback", "text": "User feedback.", "metadata": {"career_id": "design", "scenario_id": "team"}},
        {"id": "b", "kind": "satisfaction", "title": "Recorded feedback", "text": "Different feedback.", "career_id": "design", "scenario_id": "data"},
    ]})
    assert [item["id"] for item in retriever.retrieve_satisfaction_cases("design", "team")] == ["a"]
    assert retriever.retrieve_satisfaction_cases("unknown", "team") == []


def test_context_preserves_source_order_deduplicates_and_bounds(corpus):
    items = RetrievalLayer({"documents": corpus}).search("data")
    items[0]["text"] *= 100
    assembled = ContextAssembler({"max_context_chars": 700, "max_item_chars": 400}).assemble(
        ContextType.CAREER_GUIDANCE, "data", [items[0], items[0], *items[1:]], {"skills": ["Python"]}
    )
    assert assembled.retrieved_items[0]["id"] == items[0]["id"]
    assert len({item["id"] for item in assembled.retrieved_items}) == len(assembled.retrieved_items)
    for n, item in enumerate(assembled.retrieved_items, 1):
        assert f"[{n}] {item['title']}" in assembled.fused_context
    assert len(assembled.retrieved_items[0]["context_excerpt"]) <= 400
    assert assembled.metadata["truncated"] is True
    assert assembled.metadata["user_profile"]["skills"] == ["Python"]


def test_merge_contexts_renumbers_unique_evidence(corpus):
    assembler = ContextAssembler()
    first = assembler.assemble("career_guidance", "data", corpus[:2])
    second = assembler.assemble("career_guidance", "data", corpus[1:3])
    merged = assembler.merge_contexts([first, second], [1, 2])
    assert [item["id"] for item in merged.retrieved_items] == ["career-design", "scenario-puzzle", "career-data"]
    assert "[3] Data Scientist" in merged.fused_context
    with pytest.raises(ValueError):
        assembler.merge_contexts([])
    with pytest.raises(ValueError):
        assembler.merge_contexts([first, second], [1])


def test_bundled_career_quest_scenarios_are_searchable():
    retriever = RetrievalLayer()
    results = retriever.retrieve_scenarios("Unfamiliar City")
    assert results
    assert results[0]["title"] == "Scenario 1.1: The Unfamiliar City"
