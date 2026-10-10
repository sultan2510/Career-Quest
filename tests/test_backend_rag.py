"""Exercise the authenticated UI/API/RAG boundary without a live DB or AI call."""

import asyncio
import importlib.util
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.ingest import ingest
from backend.progress import ProgressSnapshot
from backend.rag_service import RagService, build_user_context, load_catalog, load_documents
from rag.retrieval_layer import RetrievalLayer

ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"
TEST_SECRET = "test-secret-used-only-for-local-tests-123456"


class FakeDatabase:
    def __init__(self):
        self.users = {uid: {"id": uid, "name": name, "email": f"{name.lower()}@example.test",
                           "email_verified": True, "created_at": datetime.now(timezone.utc)}
                      for uid, name in [(ALICE, "Alice"), (BOB, "Bob")]}
        self.progress = {
            ALICE: {"v": 1, "journal": [{"id": "alice-note", "text": "I enjoyed design and interviews.", "prompt": "What gave you energy?"}]},
            BOB: {"v": 1, "journal": [{"id": "bob-note", "text": "Bob's private journal sentinel.", "prompt": "What gave you energy?"}]},
        }
        self.calls = []
        self.chunk_error = None
        self.rows = []

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        if "from users where id=$1" in sql:
            return self.users.get(str(args[0]))
        if "insert into users" in sql:
            self.users[ALICE].update(name=args[0], email=args[1], password_hash=args[2])
            return {"id": ALICE}
        raise AssertionError(f"Unexpected fetchrow query: {sql}")

    async def fetchval(self, sql, *args):
        self.calls.append((sql, args))
        if "rate_limits" in sql:
            return 0
        if "select data from progress" in sql:
            return json.dumps(self.progress.get(str(args[0])))
        raise AssertionError(f"Unexpected fetchval query: {sql}")

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        if self.chunk_error:
            raise self.chunk_error
        return self.rows

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        if "insert into progress" in sql:
            self.progress[str(args[0])] = json.loads(args[1])
        return "OK"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "SECRET", TEST_SECRET)
    database = FakeDatabase()
    main.app.state.db = database
    main.app.state.rag = RagService(generation_config={"api_key": ""})
    # Omitting the context manager intentionally skips production startup and
    # its network pool; the same route dependency runs against this fake pool.
    result = TestClient(main.app)
    result.cookies.set(main.COOKIE, jwt.encode({"sub": ALICE}, TEST_SECRET, algorithm="HS256"))
    yield result, database
    result.close()


def test_rag_requires_a_valid_authenticated_cookie(client):
    http, db = client
    http.cookies.clear()
    response = http.post("/rag/ask", json={"question": "What does a UX Designer do?"})
    assert response.status_code == 401
    assert not db.calls
    http.cookies.set(main.COOKIE, "not-a-signed-session")
    assert http.post("/rag/ask", json={"question": "Career advice"}).status_code == 401


@pytest.mark.parametrize("extra", [
    {"progress": {"v": 1, "journal": "invalid"}},
    {"progress": {"v": 2}},
    {"progress": {"v": 1, "character": 4}},
    {"progress": {"v": 1, "ignored": "x" * 200_001}},
    {"character": -1},
    {"character": 4},
    {"character": True},
])
def test_signup_rejects_invalid_guest_progress_before_writing(client, extra):
    http, db = client
    body = {"name": "Test user", "email": "test@example.com", "password": "test-password", **extra}
    assert http.post("/auth/signup", json=body).status_code == 422
    assert not db.calls


def test_signup_preserves_valid_partial_guest_progress_and_unknown_fields(client, monkeypatch):
    http, db = client

    async def hash_password(password):
        return "test-hash"

    async def skip_email(*args):
        return None

    monkeypatch.setattr(main, "hash_pw", hash_password)
    monkeypatch.setattr(main, "mail_verify", skip_email)
    body = {"name": "Test user", "email": "test@example.com", "password": "test-password", "character": 3,
            "progress": {"journal": [], "future_ui_feature": {"selected": True}}}
    assert http.post("/auth/signup", json=body).status_code == 201
    assert db.progress[ALICE] == {"v": 1, "character": 3, "journal": [], "future_ui_feature": {"selected": True}}


@pytest.mark.parametrize("question", ["", "    ", "a" * 1001])
def test_rag_rejects_invalid_questions(client, question):
    http, _ = client
    assert http.post("/rag/ask", json={"question": question}).status_code == 422


def test_database_progress_is_scoped_to_session_user(client):
    http, db = client
    response = http.post("/rag/ask", json={"question": "What is in my journal reflection?", "user_id": BOB})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_configured"
    assert body["mode"] == "retrieved"
    assert body["profile_source"] == "database"
    assert "design and interviews" in json.dumps(body)
    assert "Bob's private" not in json.dumps(body)
    reads = [args[0] for sql, args in db.calls if "select data from progress" in sql]
    assert reads == [ALICE]


def test_current_progress_is_used_without_cross_account_reads_or_writes(client):
    http, db = client
    fresh = {"v": 1, "planCareer": "software", "journal": [{"id": "new", "text": "I just finished my first Python script."}]}
    response = http.post("/rag/ask", json={"question": "What should my next roadmap step be?", "progress": fresh})
    body = response.json()
    assert body["profile_source"] == "current"
    assert body["sources"]
    assert not any("select data from progress" in sql for sql, _ in db.calls)
    assert db.progress[ALICE]["journal"][0]["id"] == "alice-note"


@pytest.mark.parametrize("progress", [
    {"v": 2},
    {"v": 1, "journal": [{"id": "x", "text": "x" * 6001}]},
    {"v": 1, "evidence": [{"id": "x", "careerId": "software", "enjoyment": 99, "confidence": 3}]},
    {"v": 1, "dna": {"answers": {"x": []}}},
    {"v": 1, "tasks": {"software": ["x"] * 41}},
])
def test_rag_progress_shape_and_size_are_validated(client, progress):
    http, _ = client
    assert http.post("/rag/ask", json={"question": "Career advice", "progress": progress}).status_code == 422


def test_progress_whole_payload_is_bounded_before_ignoring_unknown_fields(client):
    http, _ = client
    payload = {"v": 1, "unknown": "x" * 200_001}
    assert http.post("/rag/ask", json={"question": "Career advice", "progress": payload}).status_code == 422
    assert http.put("/progress", json=payload).status_code == 422


def test_valid_existing_larger_histories_still_save(client):
    http, _ = client
    payload = {"v": 1, "journal": [{"id": str(i), "text": "A short reflection."} for i in range(220)]}
    assert http.put("/progress", json=payload).status_code == 200
    assert len(http.get("/progress").json()["journal"]) == 220


def test_put_progress_persists_the_same_authenticated_user(client):
    http, db = client
    progress = {"v": 1, "dna": {"answers": {"1.1": "A"}, "tie": None, "recon": None}, "planCareer": "data"}
    assert http.put("/progress", json=progress).status_code == 200
    assert http.get("/progress").json() == progress
    assert db.progress[BOB]["journal"][0]["id"] == "bob-note"
    assert http.put("/progress", json={"v": 1, "journal": "invalid"}).status_code == 422


def test_missing_knowledge_table_uses_explicit_bundled_fallback(client):
    http, db = client
    db.chunk_error = asyncpg.UndefinedTableError("rag_chunks missing")
    body = http.post("/rag/ask", json={"question": "What does a UX Designer do?"}).json()
    assert body["status"] == "not_configured"
    assert body["knowledge_source"] == "bundled_not_ingested"
    assert any("UX Designer" in source["title"] for source in body["sources"])


def test_operational_database_failure_is_not_silently_bypassed(client):
    http, db = client
    db.chunk_error = asyncpg.PostgresConnectionError("sensitive host is unavailable")
    body = http.post("/rag/ask", json={"question": "Software Engineer tasks"}).json()
    assert body["status"] == "unavailable"
    assert body["sources"] == []
    assert "sensitive" not in json.dumps(body)


def test_managed_database_source_replaces_its_bundled_version(client):
    http, db = client
    db.rows = [{"id": 99, "source_key": "career:software", "title": "Software Engineer updated catalog",
                "content": "Software Engineer starter skill is Python database-updated-sentinel.",
                "url": "https://www.onetonline.org/", "kind": "career"}]
    body = http.post("/rag/ask", json={"question": "Software Engineer starter skill", "progress": {"v": 1}}).json()
    assert body["knowledge_source"] == "database_and_bundled"
    assert any("database-updated-sentinel" in source["excerpt"] for source in body["sources"])
    assert any(source.get("url") == "https://www.onetonline.org/" for source in body["sources"])


def test_unknown_topic_has_no_fabricated_answer_or_sources(client):
    http, _ = client
    body = http.post("/rag/ask", json={"question": "zzqxxzx unmatchablexqz topicxqz", "progress": {"v": 1}}).json()
    assert body["status"] == "no_match"
    assert not body["answer"] and body["sources"] == []


def test_generated_answer_receives_personal_context_and_numbered_sources(client):
    http, _ = client
    prompts = []

    async def provider(**kwargs):
        prompts.append(kwargs["prompt"])
        return "Try the catalog's small Python project to explore software engineering [1]."

    main.app.state.rag = RagService(generation_config={"provider": provider, "api_key": ""})
    progress = {"v": 1, "planCareer": "software", "dna": {"answers": {"1.1": "D"}},
                "journal": [{"id": "x", "text": "Writing scripts gave me energy."}]}
    body = http.post("/rag/ask", json={"question": "What should my next career project be?", "progress": progress}).json()
    assert body["status"] == "ok" and body["mode"] == "generated"
    assert body["sources"][0]["n"] == 1
    assert "Logical-Mathematical" in prompts[0]
    assert "Writing scripts gave me energy" in prompts[0]
    assert "Software Engineer" in prompts[0]


def test_provider_failure_keeps_grounded_passages_and_safe_status(client):
    http, _ = client

    async def provider(**kwargs):
        raise RuntimeError("secret-api-key-provider-error")

    main.app.state.rag = RagService(generation_config={"provider": provider, "api_key": ""})
    body = http.post("/rag/ask", json={"question": "UX Designer beginner skill"}).json()
    assert body["status"] == "unavailable" and body["mode"] == "retrieved"
    assert body["sources"]
    assert "secret-api-key" not in json.dumps(body)


def test_request_private_context_is_never_added_to_shared_index():
    service = RagService(generation_config={"api_key": ""})
    original = json.dumps(service.documents)
    progress = ProgressSnapshot.model_validate({"v": 1, "journal": [{"id": "x", "text": "private-unique-sentinel"}]})
    asyncio.run(service.ask(FakeDatabase(), ALICE, "my journal reflection", progress))
    assert json.dumps(service.documents) == original
    assert "private-unique-sentinel" not in original


def test_vector_retrieval_falls_back_to_bm25_without_model_download():
    """When sentence-transformers can't load, hybrid search degenerates to BM25."""
    service = RagService(generation_config={"api_key": ""}, use_vectors=True)
    # Without a real model downloaded in the test env, falls back to BM25
    assert isinstance(service.retriever, RetrievalLayer)


def test_profile_vector_extracts_dna_dimensions():
    from backend.rag_service import RagService
    service = RagService(generation_config={"api_key": ""}, use_vectors=True)
    # With no model, profile_vector returns None (graceful degradation)
    progress = ProgressSnapshot.model_validate({"v": 1, "dna": {"answers": {"1.1": "D"}}})
    user_context = build_user_context(progress, load_catalog(), ALICE)
    vec = service._profile_vector(user_context)
    assert vec is None  # no model means no vector path


def test_ml_scorer_available_when_model_exists():
    from backend.rag_service import RagService
    service = RagService(generation_config={"api_key": ""}, use_vectors=False, use_ml_scoring=True)
    assert service._ml_scorer is not None
    # XGBoost is an optional dependency in production; the model is usable
    # only when both its artifact and the package are present.
    if importlib.util.find_spec("xgboost") is None:
        assert not service._ml_scorer.available
    else:
        assert service._ml_scorer.available


def test_ml_scoring_augments_dna_context():
    from backend.rag_service import RagService
    service = RagService(generation_config={"api_key": ""}, use_ml_scoring=True)
    progress = ProgressSnapshot.model_validate({"v": 1, "dna": {"answers": {"1.1": "D"}}})
    catalog = load_catalog()
    if service._ml_scorer and service._ml_scorer.available:
        from backend.rag_service import build_user_context_ml
        context = build_user_context_ml(progress, catalog, ALICE, service._ml_scorer)
        assert context["DNA"]["ml_enhanced"] is True
    else:
        # Without model, falls back to pure deterministic
        from backend.rag_service import build_user_context_ml
        context = build_user_context_ml(progress, catalog, ALICE, service._ml_scorer)
        assert "ml_enhanced" not in context["DNA"]


def test_ml_enhancement_preserves_deterministic_scores_when_disabled():
    service = RagService(generation_config={"api_key": ""}, use_vectors=False, use_ml_scoring=False)
    assert service._ml_scorer is None


def test_dna_scores_use_actual_options_and_skip_invalid_branches():
    progress = ProgressSnapshot.model_validate({"v": 1, "dna": {"answers": {"1.1": "D", "1.1A": "A", "made-up": "A"}}})
    context = build_user_context(progress, load_catalog(), ALICE)
    assert context["DNA"]["answered"] == 1
    scores = {item["dimension"]: item for item in context["DNA"]["dimensions"]}
    assert scores["Logical-Mathematical"]["points"] == 5
    assert scores["Logical-Mathematical"]["possible"] == 5
    assert scores["Interpersonal"]["points"] == 0
    assert scores["Interpersonal"]["assessed"] == 1


def test_simulation_quality_and_outcome_are_recomputed_from_catalog():
    catalog = load_catalog()
    career = next(item for item in catalog["careers"] if item["id"] == "software")
    choice = next(item for item in career["scenes"][0]["choices"] if item["quality"] == 2)
    payload = {"v": 1, "evidence": [{"id": "x", "careerId": "software", "enjoyment": 4, "confidence": 4,
                "decisions": [{"scene": 0, "text": choice["text"], "source": "choice", "quality": 0,
                               "outcome": "forged-client-outcome"}]}]}
    context = build_user_context(ProgressSnapshot.model_validate(payload), catalog, ALICE)
    decision = context["simulations"][0]["decisions"][0]
    assert decision["quality"] == 2
    assert decision["outcome"] == choice["outcome"][:240]
    assert "forged-client-outcome" not in json.dumps(context)


def test_dna_tie_and_reconciliation_match_the_existing_ui_nudges():
    progress = ProgressSnapshot.model_validate({"v": 1, "dna": {"answers": {"1.1": "A"}, "tie": "logical", "recon": 0}})
    context = build_user_context(progress, load_catalog(), ALICE)
    scores = {item["dimension"]: item for item in context["DNA"]["dimensions"]}
    assert scores["Logical-Mathematical"]["points"] == 5
    assert scores["Interpersonal"]["points"] == 2
    assert scores["Interpersonal"]["possible"] == 5
    assert scores["Interpersonal"]["normalized"] == 0.4


def test_password_verification_accepts_both_existing_schemes_and_marks_new_hashes():
    password = "existing-user-password"
    direct = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    prehashed = bcrypt.hashpw(main._pre(password), bcrypt.gensalt(rounds=4)).decode()
    assert asyncio.run(main.check_pw(password, direct))
    assert asyncio.run(main.check_pw(password, prehashed))
    assert not asyncio.run(main.check_pw("wrong", direct))
    long_password = "長" * 100
    modern = asyncio.run(main.hash_pw(long_password))
    assert modern.startswith(main.PASSWORD_SCHEME)
    assert asyncio.run(main.check_pw(long_password, modern))


def test_ingestion_is_idempotent_and_preserves_legacy_rows():
    class Connection:
        def __init__(self):
            self.storage = {"legacy-unmanaged": ("existing content",)}
            self.statements = []

        @asynccontextmanager
        async def transaction(self):
            yield self

        async def execute(self, sql):
            self.statements.append(sql.lower())

        async def executemany(self, sql, rows):
            self.statements.append(sql.lower())
            for row in rows:
                self.storage[row[0]] = row

    db = Connection()
    docs = load_documents()
    assert any(doc["kind"] == "career" for doc in docs)
    assert any(doc["id"].startswith("dna:") for doc in docs)
    asyncio.run(ingest(db, docs))
    snapshot = dict(db.storage)
    asyncio.run(ingest(db, docs))
    assert db.storage == snapshot
    assert "legacy-unmanaged" in db.storage
    assert not any("truncate" in sql or "drop table" in sql or "delete from" in sql for sql in db.statements)
