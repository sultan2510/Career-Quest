# CareerQuest API
1. Run `schema.sql` in the Supabase SQL editor.
2. `cp .env.example .env`, fill it in, then `pip install -r requirements.txt`.
3. Start the API: `uvicorn main:app --reload` (docs at http://localhost:8000/docs). `backend/.env` is loaded automatically at startup; on Windows activate the venv first: `.venv\Scripts\activate`.
In dev (no SMTP_HOST) verification and reset links are printed in the server console.

## RAG
1. Re-run `schema.sql` (it adds `rag_chunks` and `rate_limits`; safe to run again).
2. From the repository root run `python -m backend.ingest` (needs `DATABASE_URL`). It applies the additive RAG source migration and idempotently upserts catalog and questionnaire passages without deleting existing rows.
3. Set `ANTHROPIC_API_KEY` for generated answers. Without it the API returns the matching passages only.
Retrieval is Postgres full-text search. To upgrade to embeddings, enable pgvector, add an `embedding` column, and rank by vector distance in `rag_ask`.
