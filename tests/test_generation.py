"""Generation provider tests without external API requests or credentials."""

import asyncio
import json

import pytest

from rag import ContextAssembler, GenerationLayer, ResponseType


def context():
    return ContextAssembler().assemble("career_guidance", "Python", [
        {"id": "data", "title": "Data Scientist", "text": "Use Python and statistics to analyze data.", "score": 0.8},
        {"id": "design", "title": "UX Designer", "text": "Test interfaces with user interviews.", "score": 0.2},
    ], {"skills": ["Python"]})


def test_no_key_returns_real_passages_with_source_numbers():
    result = GenerationLayer({"api_key": ""}).generate(ResponseType.CAREER_RECOMMENDATION, "Python", context())
    assert result.metadata["mode"] == "retrieved"
    assert result.metadata["status"] == "not_configured"
    assert "Use Python and statistics to analyze data." in result.content
    assert result.sources == ["data", "design"]
    assert [(citation["n"], citation["id"]) for citation in result.citations] == [(1, "data"), (2, "design")]
    assert result.metadata["confidence_scope"] == "retrieval_support"


def test_long_career_excerpt_keeps_supporting_tasks_after_intro():
    text = (
        "Career: Software Engineer. Category: Technology.\n"
        "Build and maintain software people use.\n"
        "Typical tasks: Write and review code; test applications; debug problems.\n"
        + "Additional catalog context. " * 30
    )
    excerpt = GenerationLayer._excerpt({'text': text}, 'What does a software developer do?')
    assert 'Write and review code' in excerpt
    assert 'debug problems' in excerpt
    assert len(excerpt) <= 520


def test_no_match_does_not_call_provider():
    async def provider(**kwargs):
        raise AssertionError("Provider must not run without evidence")
    result = asyncio.run(GenerationLayer({"provider": provider}).agenerate(
        "career_recommendation", "unrelated", "", retrieved_items=[]
    ))
    assert result.metadata["status"] == "no_match"
    assert result.sources == []
    assert result.citations == []
    assert result.confidence == 0


def test_injected_provider_receives_numbered_context_and_profile():
    received = {}
    async def provider(**kwargs):
        received.update(kwargs)
        return {"content": [{"text": "Explore a small Python data project [1]."}]}
    result = asyncio.run(GenerationLayer({"provider": provider}).agenerate(
        "career_recommendation", "Python", context(), user_profile={"skills": ["Python"]},
    ))
    assert result.content == "Explore a small Python data project [1]."
    assert result.metadata["mode"] == "generated"
    assert result.metadata["status"] == "ok"
    assert "[1] Data Scientist" in received["prompt"]
    assert '"skills":["Python"]' in received["prompt"]
    assert result.sources == ["data", "design"]


def test_timeout_returns_evidence_instead_of_fake_generation():
    async def provider(**kwargs):
        await asyncio.sleep(1)
        return "Late answer [1]"
    result = asyncio.run(GenerationLayer({"provider": provider, "timeout_seconds": 0.01}).agenerate(
        "career_recommendation", "Python", context(),
    ))
    assert result.metadata["status"] == "unavailable"
    assert result.metadata["mode"] == "retrieved"
    assert result.metadata["error_code"] == "provider_timeout"
    assert "Use Python" in result.content


def test_provider_error_never_leaks_error_message():
    async def provider(**kwargs):
        raise RuntimeError("private-api-key-and-request-payload")
    result = asyncio.run(GenerationLayer({"provider": provider}).agenerate(
        "career_recommendation", "Python", context(),
    ))
    assert result.metadata["error_code"] == "provider_error"
    assert "private-api-key" not in str(result.to_dict())
    assert result.citations[0]["title"] == "Data Scientist"


def test_unknown_or_missing_citations_do_not_reach_the_ui():
    for content in ("A fabricated claim [99]", "An uncited prediction", "A mixed citation [1] [99]", "Wrong zero index [0]"):
        async def provider(**kwargs):
            return content
        result = asyncio.run(GenerationLayer({"provider": provider}).agenerate(
            "career_recommendation", "Python", context(),
        ))
        assert result.metadata["mode"] == "retrieved"
        assert result.metadata["error_code"] == "invalid_provider_evidence"
        assert content not in result.content
        assert result.sources == ["data", "design"]


def test_sources_are_extracted_only_from_known_numeric_citations():
    generator = GenerationLayer({"api_key": ""})
    assert generator.extract_sources("Try this [2] and that [999]", context().retrieved_items) == ["design"]


def test_sync_api_requires_async_api_when_loop_is_running():
    async def exercise():
        try:
            GenerationLayer({"api_key": ""}).generate("career_recommendation", "Python", context())
        except RuntimeError as exception:
            assert "agenerate" in str(exception)
        else:
            raise AssertionError("Sync wrapper must not nest event loops")
    asyncio.run(exercise())


def test_installed_anthropic_sdk_uses_async_messages_without_deprecated_sampling(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    try:
        import httpx2 as httpx
    except ImportError:
        import httpx
    original_client = anthropic.AsyncAnthropic
    requests = []

    async def local_handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path == "/v1/messages"
        assert "temperature" not in payload
        assert payload["thinking"] == {"type": "between_tools"}
        assert payload["output_config"] == {"effort": "low"}
        assert "untrusted data" in payload["system"]
        return httpx.Response(200, json={
            "id": "msg_local_test", "type": "message", "role": "assistant",
            "model": payload["model"],
            "content": [{"type": "text", "text": "Try a Python analysis project [1]."}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 8},
        })

    def local_client(**kwargs):
        assert kwargs["max_retries"] == 0
        return original_client(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(local_handler)))

    monkeypatch.setattr(anthropic, "AsyncAnthropic", local_client)
    response = asyncio.run(GenerationLayer({"api_key": "local-test-key", "model": "claude-sonnet-5-5"}).agenerate(
        "career_recommendation", "Python", context(),
    ))
    assert response.metadata["mode"] == "generated"
    assert response.content == "Try a Python analysis project [1]."
    assert requests[0]["model"] == "claude-sonnet-5-5"


def test_large_profile_keeps_valid_json_and_later_journal_roadmap_sections():
    from rag.context_assembler import profile_for_prompt
    profile = {
        "dna": {f"dimension-{n}": {"evidence": "Repeated evidence. " * 1000} for n in range(15)},
        "simulations": [{"outcome": "Built a prototype"}],
        "journal": [{"text": "I enjoyed the testing tasks" + " reflection" * 1000}],
        "roadmap": {"goal": "Practice interviews"},
    }
    bounded = profile_for_prompt(profile, 6000)
    parsed = json.loads(bounded)
    assert len(bounded) <= 6000
    assert parsed["simulations"][0]["outcome"] == "Built a prototype"
    assert parsed["journal"][0]["text"].startswith("I enjoyed the testing tasks")
    assert parsed["roadmap"]["goal"] == "Practice interviews"
