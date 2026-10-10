# CareerQuest

A playful career-discovery game: choose a character, explore your Learning DNA, try a day in the life of a career, and watch your matches evolve. Next.js 15 frontend; see `../backend` for the FastAPI + Supabase API.

## Run
```bash
npm install
npm run dev     # http://localhost:3000
```

## Deploy on Vercel
Push to GitHub, import the repo in Vercel, and deploy. Set `NEXT_PUBLIC_API_URL` to your deployed API.

## Structure
- `app/` – layout, page, global styles (colors and tokens in `globals.css`)
- `components/providers/` – auth and progress state
- `components/auth/` – log in, sign up (with character pick), guest mode
- `components/quest/` – app shell and views (journey, careers, simulation, reflection, roadmap, profiler, mentor, profile)
- `lib/data/` – characters, careers and scenarios (edit these to add content)
- `lib/scoring.ts` – trait scoring, XP, badges
- `lib/auth.ts` – authenticated API sessions
- `lib/storage.ts` – account progress through the API; browser storage for guests

## Data persistence
Signed-in accounts use the FastAPI session cookie and the Postgres `users` and `progress` tables. The `progress.data` JSONB document contains Learning DNA, RIASEC answers, Ikigai inputs, roadmap tasks, journal entries, completed simulation evidence, and unfinished simulation drafts. Each simulation choice and scene transition is saved through `PUT /progress` before the next step appears. Completing a run writes the ratings and completed evidence in one document update. The app shows save errors and lets the user retry.

Guest progress stays in this browser. Creating an account transfers the saved guest document into Postgres. The backend validates incoming progress and limits its size. Career descriptions and the sourced market snapshot are versioned with the app; they are shared reference data rather than per-user records.
