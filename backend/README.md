# CareerQuest API
1. Run `schema.sql` in the Supabase SQL editor.
2. `cp .env.example .env`, fill it in, then `pip install -r requirements.txt`.
3. Start the API: `uvicorn main:app --reload` (docs at http://localhost:8000/docs). `backend/.env` is loaded automatically at startup; on Windows activate the venv first: `.venv\Scripts\activate`.
In dev (no SMTP_HOST) verification and reset links are printed in the server console.

## Saved application data
The API owns authentication and writes account data to `progress.data` and anonymous guest data to `guest_sessions.data` in Postgres. `GET /progress` and `PUT /progress` use the same validated contract for both. It includes the profiler, interests, Ikigai notes and country, roadmap, journal, recent mentor conversation, completed simulation evidence, and one resumable draft per career. Each simulation decision is saved before advancing. Guest identity comes from a 90-day HTTP-only cookie; only its token hash is stored. Signup copies guest progress atomically, and verification transfers any changes made since signup in the same browser. The public Supabase REST API has no RLS policies for these tables; backend cookies and database queries enforce ownership.

For an existing database, apply `migrations/002_guest_sessions.sql` before deploying this API. `schema.sql` already contains the guest table for new installs.

## RAG
1. Re-run `schema.sql` (it adds `rag_chunks` and `rate_limits`; safe to run again).
2. From the repository root run `python -m backend.ingest` (needs `DATABASE_URL`). It applies the additive RAG source migration and idempotently upserts catalog and questionnaire passages without deleting existing rows.
3. Set `ANTHROPIC_API_KEY` for generated answers. Without it the API returns the matching passages only.
Retrieval is Postgres full-text search. To upgrade to embeddings, enable pgvector, add an `embedding` column, and rank by vector distance in `rag_ask`.
