# CareerQuest API
1. Run `schema.sql` in the Supabase SQL editor.
2. `cp .env.example .env`, fill it in, then `pip install -r requirements.txt`.
3. Start the API: `uvicorn main:app --reload` (docs at http://localhost:8000/docs). `backend/.env` is loaded automatically at startup; on Windows activate the venv first: `.venv\Scripts\activate`.
In dev (no SMTP_HOST) verification and reset links are printed in the server console.

## Saved application data
The API owns authentication and writes signed-in user data to `progress.data` in Postgres. `GET /progress` loads the saved document; `PUT /progress` validates and saves it. It includes the profiler, interests, Ikigai notes and country, roadmap, journal, completed simulation evidence, and one resumable draft per career. The frontend sends each simulation decision immediately and waits for the save before continuing. Guest data remains in browser storage until account creation. No Supabase browser client or `auth.users` RLS policy is used: accounts are in the app's `users` table and the backend enforces ownership from its HTTP-only session cookie.

## RAG
1. Re-run `schema.sql` (it adds `rag_chunks` and `rate_limits`; safe to run again).
2. From the repository root run `python -m backend.ingest` (needs `DATABASE_URL`). It applies the additive RAG source migration and idempotently upserts catalog and questionnaire passages without deleting existing rows.
3. Set `ANTHROPIC_API_KEY` for generated answers. Without it the API returns the matching passages only.
Retrieval is Postgres full-text search. To upgrade to embeddings, enable pgvector, add an `embedding` column, and rank by vector distance in `rag_ask`.
