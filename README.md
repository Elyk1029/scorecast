# Yardline

Yardline is a weekly NFL forecast you can check against the scoreboard. It publishes an expected score, a calibrated win probability, a model spread and total, and a short record of how those calls have actually done.

The site is research. It is for adults 21+ where wagering is legal, and it is not a bet recommendation. The side the model rates above the stored no-vig price is shown with its hit rate. That comparison has not cleared the posted price, so there is no recommended play. Weather and travel are shown as context and do not move the score. There is no live odds feed. The posted line, when one is stored, comes from nflverse and is a comparison, not a model input.

Forecasts are built in Python from games already played and written to `data/season.json`. Separate regularized regressions estimate home points and away points from scoring form, opposing defense, Elo, rest, home field, and shrunk quarterback passing form. Player lines are separate from that score: the last eight games with a three-game half-life, opponent yards per play, and a window fit to earlier misses. The record compares that line with the previous four-game formula. Margin and total are the difference and the sum of those two scores. The game page also weights earlier finals whose margin and total were close to that forecast, so a 3-point finish stays 3 points. That cloud does not change the win probability. A cross-fitted logistic calibration converts that margin to win probability. Each season is an expanding-window holdout: coefficients are fit on completed prior seasons, then held fixed while that season is scored. Accuracy uses unrounded model means, and every market comparison — win probability, margin, total, and each team’s score — uses an identical cohort. Betting lines are benchmarks only, never model features.

The current week is locked: later refreshes add results without rewriting what was published. Older reconstructed games are labeled as backtests, and future weeks remain provisional. The Next.js app only reads the JSON file; the model does not run on Vercel.

## Run locally

```bash
npm install
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m model.build
.venv/bin/python -m model.validate
npm run dev -- -p 43123
```

Then open [http://localhost:43123](http://localhost:43123).

## Deploy

1. Push this repo to GitHub.
2. In Vercel, import the GitHub repo.
3. Framework preset: Next.js.
4. No environment variables.
5. Production branch: `main`.

Vercel builds the Next.js app only. It serves the committed `data/season.json`.

A GitHub Action in `.github/workflows/refresh.yml` refreshes results after Thursday, Sunday, and Monday night games, then locks the next slate on Tuesday afternoon. It can also run manually. The workflow runs model tests, validates the JSON, and builds the website before committing. If the file changed, it pushes to `main`, which makes Vercel redeploy. Do not add a Python build step on Vercel.

## Scripts

- `npm run dev` — local Next.js dev server
- `npm run build` — production build
- `npm start` — serve the production build
- `npm run lint` — ESLint
