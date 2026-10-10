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
- `lib/storage.ts` – account and guest progress through the API; old guest-data migration helpers

## Data persistence
Accounts use the FastAPI session cookie and Postgres `users` and `progress` tables. Anonymous guests use a separate HTTP-only cookie and the `guest_sessions` table. Both use the same `/progress` API and JSONB document for Learning DNA, RIASEC answers, Ikigai inputs, roadmap tasks, journal entries, the 30 most recent mentor messages, completed simulation evidence, and unfinished simulation drafts. Each simulation choice and scene transition is saved before the next step appears. Completing a run writes ratings and evidence in one update. The app shows save errors and lets the user retry.

Guest progress is already in Postgres but can be opened only with the private cookie in that browser. The guest session expires after 90 days. Creating an account copies the guest document, and email verification transfers any additional guest work done in that same browser. Older local-only guest progress is imported once on first use. Career descriptions and the sourced market snapshot remain shared reference data versioned with the app.
