# CareerQuest full stack
- `backend/`: FastAPI + Supabase Postgres (see backend/README.md)
- `frontend/`: Next.js app (`cp .env.local.example .env.local`, `npm install`, `npm run dev` — or just `npm run dev` at the repo root)
Run the API on :8000 and the frontend on :3000. Dev emails (verify/reset links) print in the API console.

## Ikigai map and independent text baseline

The frontend now has an 18-item interest screener and a four-circle Ikigai map. It joins O*NET 31.0 occupation profiles to BLS US wages/projections and ILOSTAT Pakistan employment/earnings. The supplied repository had no job-postings dataset, so the app does not claim to show posting counts. The Pakistan wage data are broad occupation-group proxies. Numbeo is displayed as country cost context. See [the step-by-step method and research sources](docs/IKIGAI_METHOD.md) for the scoring, data limitations, and Baseline A development plan.

Run the independent TF-IDF/cosine baseline with `python backend/baseline_a.py --profile "statistics and programming"`. Add `--jobs data/job_postings.csv --country PK` when a real postings CSV with `title,description,country` is available. Rebuild and verify the data snapshot with `python scripts/build_ikigai_data.py` and `python scripts/validate_ikigai_data.py`. Check diagram membership with `node scripts/test_venn.cjs`.

On Windows PowerShell, use `npm.cmd` when the shell blocks `npm.ps1`: `cd frontend; npm.cmd ci; npm.cmd run dev`. Start the backend from `backend/` with `..\.venv\Scripts\python.exe -m uvicorn main:app --reload`. Add the database URL and JWT secret to `backend/.env` as described in its README; keep that file private.

## New in this version
- Learning DNA Profiler (branching + ambiguous-answer follow-ups) built from lessgo.docx, with the references at the bottom of every section.
- Ask Yuki: RAG over the questionnaire (see backend/README.md; run `python ingest.py` once).
- API origin proxy in `frontend/next.config.mjs`; set `NEXT_PUBLIC_API_URL=/api` and, on Vercel, `API_ORIGIN`.
