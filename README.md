# Yardline

Yardline is a weekly NFL forecast you can check against the scoreboard. It publishes an expected score, a calibrated win probability, a model spread and total, and a short record of how those calls have actually done.

The site is research. It is for adults 21+ where wagering is legal, and it is not a bet recommendation. Weather and travel are shown as context and do not move the score. There is no live odds feed. The posted line, when one is stored, comes from nflverse and is a comparison, not a model input.

Forecasts are built in Python from games already played and written to `data/season.json`. The Next.js app only reads that file. The model does not run on Vercel.

## Run locally

```bash
npm install
python -m model.build
npm run dev -- -p 43123
```

`python -m model.build` needs the packages in `requirements.txt` (a virtualenv is fine). It rewrites `data/season.json`. Then open [http://localhost:43123](http://localhost:43123).

## Deploy

1. Push this repo to GitHub.
2. In Vercel, import the GitHub repo.
3. Framework preset: Next.js.
4. No environment variables.
5. Production branch: `main`.

Vercel builds the Next.js app only. It serves the committed `data/season.json`.

A GitHub Action in `.github/workflows/refresh.yml` rebuilds `data/season.json` every Tuesday and on manual dispatch. If the file changed, the action commits it and pushes to `main`, which is what makes Vercel redeploy. Do not add a Python build step on Vercel.

## Scripts

- `npm run dev` — local Next.js dev server
- `npm run build` — production build
- `npm start` — serve the production build
- `npm run lint` — ESLint
