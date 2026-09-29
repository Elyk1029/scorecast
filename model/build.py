"""Build Yardline forecasts from nflverse data.

Ratings use only games already played. Weather, travel, and scheme notes are
explanatory and do not move the score. A quarterback ruled out or doubtful
does. The posted betting line is stored for comparison and is not a model input.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import nflreadpy as nfl
import numpy as np
import polars as pl

ALIASES = {
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
    "JAC": "JAX",
}


def canon(team: str | None) -> str | None:
    if team is None:
        return None
    return ALIASES.get(team, team)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "season.json"
SEASONS = [2023, 2024, 2025, 2026]
TRAINING_SEASONS = list(range(2010, 2027))
PUBLISH_FROM = 2024
PLAYS = 60.0
MODEL_VERSION = "yardline-3.2"
# Plays of memory carried into a new season. About one or two games, so a
# three-game stretch can outweigh last year without letting one Sunday rewrite it.
SEASON_PRIOR_PLAYS = 80.0
# Score means stay. A normal on the margin is still too confident for this
# model's historical win rate, so the published probability is pulled toward 0.5.
MARGIN_SD = 13.5
WIN_SHRINK = 0.28
# Penalty on the home and away score equations. Selected on 2021–2023
# holdouts; 100 was nearly identical and 300 had the lower combined error.
SCORE_PENALTY = 300.0
LOGISTIC_PENALTY = 10.0

# City, nickname, hours behind Eastern.
TEAMS: dict[str, tuple[str, str, int]] = {
    "ARI": ("Arizona", "Cardinals", 2),
    "ATL": ("Atlanta", "Falcons", 0),
    "BAL": ("Baltimore", "Ravens", 0),
    "BUF": ("Buffalo", "Bills", 0),
    "CAR": ("Carolina", "Panthers", 0),
    "CHI": ("Chicago", "Bears", 1),
    "CIN": ("Cincinnati", "Bengals", 0),
    "CLE": ("Cleveland", "Browns", 0),
    "DAL": ("Dallas", "Cowboys", 1),
    "DEN": ("Denver", "Broncos", 2),
    "DET": ("Detroit", "Lions", 0),
    "GB": ("Green Bay", "Packers", 1),
    "HOU": ("Houston", "Texans", 1),
    "IND": ("Indianapolis", "Colts", 0),
    "JAX": ("Jacksonville", "Jaguars", 0),
    "KC": ("Kansas City", "Chiefs", 1),
    "LAC": ("Los Angeles", "Chargers", 3),
    "LAR": ("Los Angeles", "Rams", 3),
    "LV": ("Las Vegas", "Raiders", 3),
    "MIA": ("Miami", "Dolphins", 0),
    "MIN": ("Minnesota", "Vikings", 1),
    "NE": ("New England", "Patriots", 0),
    "NO": ("New Orleans", "Saints", 1),
    "NYG": ("New York", "Giants", 0),
    "NYJ": ("New York", "Jets", 0),
    "PHI": ("Philadelphia", "Eagles", 0),
    "PIT": ("Pittsburgh", "Steelers", 0),
    "SEA": ("Seattle", "Seahawks", 3),
    "SF": ("San Francisco", "49ers", 3),
    "TB": ("Tampa Bay", "Buccaneers", 0),
    "TEN": ("Tennessee", "Titans", 1),
    "WAS": ("Washington", "Commanders", 0),
}


class Rating:
    def __init__(self) -> None:
        self.off = 0.0
        self.defn = 0.0
        self.off_n = SEASON_PRIOR_PLAYS
        self.def_n = SEASON_PRIOR_PLAYS
        self.points_off = 0.0
        self.points_def = 0.0
        self.elo = 0.0
        self.games = 0

    def snapshot(self) -> dict[str, float]:
        return {"off": round(self.off, 4), "def": round(self.defn, 4), "games": self.games}

    def regress_season(self) -> None:
        self.off *= 0.55
        self.defn *= 0.55
        self.off_n = SEASON_PRIOR_PLAYS
        self.def_n = SEASON_PRIOR_PLAYS
        self.points_off *= 0.55
        self.points_def *= 0.55
        self.elo *= 0.65
        self.games = 0

    def update(
        self,
        off_epa: float,
        def_epa: float,
        off_plays: float,
        def_plays: float,
    ) -> None:
        off_plays = max(off_plays, 1.0)
        def_plays = max(def_plays, 1.0)
        off_a = off_plays / (off_plays + self.off_n)
        def_a = def_plays / (def_plays + self.def_n)
        self.off = (1 - off_a) * self.off + off_a * off_epa
        self.defn = (1 - def_a) * self.defn + def_a * def_epa
        self.off_n = min(260.0, self.off_n + off_plays * 0.2)
        self.def_n = min(260.0, self.def_n + def_plays * 0.2)

    def update_score(
        self,
        points_for: float,
        points_against: float,
        league_points: float,
    ) -> None:
        alpha = 0.18 if self.games >= 3 else 0.25
        self.points_off = (1 - alpha) * self.points_off + alpha * (
            points_for - league_points
        )
        self.points_def = (1 - alpha) * self.points_def + alpha * (
            points_against - league_points
        )
        self.games += 1


class QuarterbackRating:
    """Shrunk passing EPA for the most recent starter known before a game."""

    def __init__(self) -> None:
        self.epa = 0.0
        self.plays = 100.0

    def regress_season(self) -> None:
        self.epa *= 0.70
        self.plays = max(100.0, self.plays * 0.60)

    def update(
        self,
        passing_epa: float,
        attempts: float,
        sacks: float,
    ) -> None:
        passing_epa = passing_epa if math.isfinite(passing_epa) else 0.0
        attempts = attempts if math.isfinite(attempts) else 0.0
        sacks = sacks if math.isfinite(sacks) else 0.0
        game_plays = max(attempts + sacks, 1.0)
        game_epa = passing_epa / game_plays
        alpha = game_plays / (game_plays + self.plays)
        self.epa = (1.0 - alpha) * self.epa + alpha * game_epa
        self.plays = min(300.0, self.plays + game_plays * 0.2)


def parse_wind(value: object) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group()) if match else None


def american_implied(odds: int | None) -> float | None:
    if odds is None or odds == 0:
        return None
    if odds < 0:
        return (-odds) / ((-odds) + 100)
    return 100 / (odds + 100)


def no_vig(home_odds: int | None, away_odds: int | None) -> float | None:
    home = american_implied(home_odds)
    away = american_implied(away_odds)
    if home is None or away is None:
        return None
    total = home + away
    if total <= 0:
        return None
    return home / total


def score_band(mean: float) -> list[int]:
    """Window that held both scores in about 80% of past games.

    A single team's score usually misses by about 14 points. Both scores land
    inside an 18-point window around the forecast about four times in five.
    """
    center = int(round(mean))
    return [max(0, center - 18), center + 18]


def round_half(value: float) -> float:
    return round(value * 2) / 2


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# Since the 10-minute period began, roughly six percent of regular-season
# overtimes have still been level when time expired.
OT_STILL_TIED = 0.06


def regulation_tie_prob(expected_margin: float) -> float:
    """Chance the score is level after 60 minutes and overtime starts."""
    return normal_cdf((0.5 - expected_margin) / MARGIN_SD) - normal_cdf(
        (-0.5 - expected_margin) / MARGIN_SD
    )


def calibrated_probs(
    expected_margin: float,
    logistic_beta: np.ndarray | None = None,
) -> tuple[float, float]:
    """Return home win probability and the chance the game is still tied after overtime.

    Win probability is a normal with SD 13.5, then shrunk toward 0.5 so the Brier
    score is not worse than a coin flip. A regulation tie plays overtime. The
    published tie rate is only the games that stay level after that period.
    """
    p_reg_tie = regulation_tie_prob(expected_margin)
    tie = p_reg_tie * OT_STILL_TIED
    if logistic_beta is None:
        raw = normal_cdf(expected_margin / MARGIN_SD)
        conditional_home = 0.5 + WIN_SHRINK * (raw - 0.5)
    else:
        logit = float(logistic_beta[0] + logistic_beta[1] * expected_margin)
        conditional_home = 1.0 / (1.0 + math.exp(-float(np.clip(logit, -30, 30))))
    home = (1.0 - tie) * conditional_home
    return home, tie


def bounded_means(total: float, margin: float) -> tuple[float, float]:
    """Keep score, total, and margin mathematically consistent while clipping."""
    total = float(np.clip(total, 12.0, 84.0))
    min_margin = max(12.0 - total, total - 84.0)
    max_margin = min(84.0 - total, total - 12.0)
    margin = float(np.clip(margin, min_margin, max_margin))
    return (total + margin) / 2.0, (total - margin) / 2.0


def game_key(game: dict) -> tuple[int, int]:
    return int(game["season"]), int(game["week"])


def freeze_published_forecasts(
    weeks: list[dict],
    current: dict,
    previous: dict | None,
    generated_at: str,
) -> None:
    """Keep live-published forecasts unchanged and refresh honest backtests.

    A row labeled published is an immutable forecast users could have seen.
    Historical backtests are rebuilt when the model changes, and future
    schedule rows remain provisional until their week becomes current.
    """
    old_games = {
        game["id"]: game
        for week in (previous or {}).get("weeks", [])
        for game in week["games"]
    }
    old_current = (previous or {}).get("current")
    old_cutoff = (
        (int(old_current["season"]), int(old_current["week"]))
        if old_current
        else None
    )
    new_cutoff = (int(current["season"]), int(current["week"]))
    frozen_fields = (
        "prediction",
        "players",
        "adjustments",
        "context",
        "xfactor",
        "postedSpreadHome",
        "postedTotal",
        "postedHomeWinProb",
    )

    for week in weeks:
        for game in week["games"]:
            key = game_key(game)
            old = old_games.get(game["id"])
            old_was_published = old is not None and (
                old.get("recordKind") == "published"
                or (old.get("recordKind") is None and key == old_cutoff)
            )
            if old_was_published and old_cutoff is not None and key <= old_cutoff:
                for field in frozen_fields:
                    game[field] = old[field]
                game["forecastedAt"] = old.get(
                    "forecastedAt", (previous or {}).get("generatedAt", generated_at)
                )
                game["forecastModelVersion"] = old.get(
                    "forecastModelVersion",
                    (previous or {}).get("modelVersion", "unknown"),
                )
                game["locked"] = True
                game["recordKind"] = "published"
            elif key == new_cutoff:
                game["forecastedAt"] = generated_at
                game["forecastModelVersion"] = MODEL_VERSION
                game["locked"] = True
                game["recordKind"] = "published"
            elif key < new_cutoff:
                game["forecastedAt"] = generated_at
                game["forecastModelVersion"] = MODEL_VERSION
                game["locked"] = True
                game["recordKind"] = "backtest"
            else:
                game["forecastedAt"] = None
                game["forecastModelVersion"] = MODEL_VERSION
                game["locked"] = False
                game["recordKind"] = "provisional"


def team_payload(abbr: str) -> dict[str, str | int]:
    city, name, tz = TEAMS.get(abbr, (abbr, abbr, 0))
    return {"abbr": abbr, "city": city, "name": name, "tz": tz}


def shrunk_rate(total: float, count: float, prior: float, prior_n: float) -> float:
    return (total + prior * prior_n) / (count + prior_n) if count + prior_n else prior


def fit_ridge(
    features: list[list[float]],
    targets: list[float],
    penalty: float = SCORE_PENALTY,
) -> np.ndarray:
    x = np.asarray(features, dtype=float)
    y = np.asarray(targets, dtype=float)
    regularizer = np.eye(x.shape[1]) * penalty
    regularizer[0, 0] = 0.0
    return np.linalg.solve(x.T @ x + regularizer, x.T @ y)


def fit_logistic(
    margins: np.ndarray,
    outcomes: list[float],
    penalty: float = LOGISTIC_PENALTY,
) -> np.ndarray:
    x = np.column_stack([np.ones(len(margins)), margins])
    y = np.asarray(outcomes, dtype=float)
    beta = np.array([0.0, 0.12])
    for _ in range(30):
        logits = np.clip(x @ beta, -30, 30)
        probs = 1.0 / (1.0 + np.exp(-logits))
        weights = probs * (1.0 - probs)
        hessian = x.T @ (weights[:, None] * x) + np.diag([0.0, penalty])
        gradient = x.T @ (probs - y) + np.array([0.0, penalty * beta[1]])
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return beta


def fallback_model() -> dict[str, np.ndarray]:
    """Priors used only before 500 completed games exist."""
    return {
        "home": np.array([22.5, 1.2, 0.35, 0.35, 1.25, 0.25, 0.08, 0.04]),
        "away": np.array([22.0, -0.5, 0.35, 0.35, 1.25, 0.25, 0.08, 0.04]),
        "logistic": np.array([0.0, 0.13]),
    }


def home_field_edge(model: dict[str, np.ndarray]) -> float:
    """Margin points from playing at home: home-score field minus away-score field."""
    return float(model["home"][1] - model["away"][1])


def fit_score_pair(
    rows: list[dict],
    penalty: float = SCORE_PENALTY,
) -> tuple[np.ndarray, np.ndarray]:
    home_beta = fit_ridge(
        [row["homeFeatures"] for row in rows],
        [row["homeScore"] for row in rows],
        penalty,
    )
    away_beta = fit_ridge(
        [row["awayFeatures"] for row in rows],
        [row["awayScore"] for row in rows],
        penalty,
    )
    return home_beta, away_beta


def predicted_margin(
    row: dict,
    home_beta: np.ndarray,
    away_beta: np.ndarray,
) -> float:
    return float(
        np.dot(row["homeFeatures"], home_beta) - np.dot(row["awayFeatures"], away_beta)
    )


def fit_forecast_model(training: list[dict]) -> dict[str, np.ndarray]:
    """Fit only completed prior-season rows; never use the season being scored."""
    if len(training) < 500:
        return fallback_model()
    home_beta, away_beta = fit_score_pair(training)
    # Calibrate only on predictions made by models that had not seen the
    # predicted season. This avoids an optimistic probability slope caused by
    # calibrating against the final regression's in-sample fitted values.
    calibration_margins: list[float] = []
    calibration_outcomes: list[float] = []
    for held_out_season in sorted({int(row["season"]) for row in training}):
        prior = [
            row for row in training if int(row["season"]) < held_out_season
        ]
        held_out = [
            row for row in training if int(row["season"]) == held_out_season
        ]
        if len(prior) < 500:
            continue
        fold_home, fold_away = fit_score_pair(prior)
        calibration_margins.extend(
            predicted_margin(row, fold_home, fold_away) for row in held_out
        )
        calibration_outcomes.extend(row["homeOutcome"] for row in held_out)
    if len(calibration_margins) >= 500:
        logistic_beta = fit_logistic(
            np.asarray(calibration_margins),
            calibration_outcomes,
        )
    else:
        logistic_beta = np.array([0.0, 0.13])
    return {
        "home": home_beta,
        "away": away_beta,
        "logistic": logistic_beta,
    }


def score_features(
    row: dict,
    home_rating: Rating,
    away_rating: Rating,
    home_qb: QuarterbackRating,
    away_qb: QuarterbackRating,
) -> tuple[list[float], list[float]]:
    """Home and away score features.

    Columns: intercept, home field, own offense, opposing defense, signed
    Elo/100, signed rest/7, own quarterback form, opposing quarterback form.
    Elo and rest flip sign on the away side. Offense, defense, and the two
    quarterback slots swap so each equation is from that team's point of view.
    """
    field = 0.0 if row["location"] == "Neutral" else 1.0
    home_rest = float(row.get("home_rest") or 7)
    away_rest = float(row.get("away_rest") or 7)
    rest_edge = float(np.clip(home_rest - away_rest, -7, 7)) / 7.0
    elo_edge = (home_rating.elo - away_rating.elo) / 100.0
    home_qb_form = PLAYS * home_qb.epa
    away_qb_form = PLAYS * away_qb.epa
    home_x = [
        1.0,
        field,
        home_rating.points_off,
        away_rating.points_def,
        elo_edge,
        rest_edge,
        home_qb_form,
        away_qb_form,
    ]
    away_x = [
        1.0,
        field,
        away_rating.points_off,
        home_rating.points_def,
        -elo_edge,
        -rest_edge,
        away_qb_form,
        home_qb_form,
    ]
    return home_x, away_x


def main() -> None:
    print("Loading nflverse schedules, play-by-play, player stats, and injuries...")
    schedules = nfl.load_schedules(TRAINING_SEASONS).filter(
        pl.col("game_type") == "REG"
    )
    pbp = nfl.load_pbp(SEASONS)
    if "season_type" in pbp.columns:
        pbp = pbp.filter(pl.col("season_type") == "REG")
    players = nfl.load_player_stats(TRAINING_SEASONS)
    if "season_type" in players.columns:
        players = players.filter(pl.col("season_type") == "REG")
    injuries = nfl.load_injuries([2024, 2025, 2026])

    plays = pbp.filter(
        pl.col("play_type").is_in(["pass", "run"])
        & pl.col("epa").is_not_null()
        & pl.col("posteam").is_not_null()
        & pl.col("defteam").is_not_null()
        & pl.col("wp").is_not_null()
        & pl.col("wp").is_between(0.10, 0.90)
        & (pl.col("week") <= 18)
    )
    game_epa = plays.group_by(["season", "week", "game_id", "posteam", "defteam"]).agg(
        pl.col("epa").mean().alias("off_epa"),
        pl.len().alias("plays"),
    )

    epa_lookup: dict[tuple[int, str, str], tuple[float, int]] = {}
    for row in game_epa.iter_rows(named=True):
        team = canon(row["posteam"])
        if team not in TEAMS:
            continue
        epa_lookup[(row["season"], row["game_id"], team)] = (
            float(row["off_epa"]),
            int(row["plays"]),
        )

    player_index: dict[tuple[int, int, str], list[dict]] = {}
    keep = [
        "season",
        "week",
        "team",
        "player_id",
        "player_display_name",
        "position",
        "attempts",
        "passing_yards",
        "passing_epa",
        "sacks_suffered",
        "carries",
        "rushing_yards",
    ]
    for row in players.select(keep).iter_rows(named=True):
        team = canon(row["team"])
        if team not in TEAMS:
            continue
        row = {**row, "team": team}
        player_index.setdefault((row["season"], row["week"], team), []).append(row)

    injury_index: dict[tuple[int, int, str, str], str] = {}
    for row in injuries.iter_rows(named=True):
        status = row["report_status"]
        if status:
            team = canon(row["team"])
            if team in TEAMS:
                injury_index[(row["season"], row["week"], team, row["gsis_id"])] = status

    recent: dict[str, list[dict]] = {abbr: [] for abbr in TEAMS}
    ratings = {abbr: Rating() for abbr in TEAMS}
    quarterback_ratings: dict[str, QuarterbackRating] = {}
    last_quarterback: dict[str, str] = {}
    training_rows: list[dict] = []
    current_model = fit_forecast_model(training_rows)
    home_field = home_field_edge(current_model)
    league_points_sum = 22.5 * 200.0
    league_team_games = 200.0
    weeks_out: list[dict] = []
    learned: list[dict] = []
    last_season = None

    ordered = schedules.sort(["season", "week", "gameday", "gametime"])
    week_rows: dict[tuple[int, int], list[dict]] = {}
    for row in ordered.iter_rows(named=True):
        row = {
            **row,
            "home_team": canon(row["home_team"]),
            "away_team": canon(row["away_team"]),
        }
        if row["home_team"] not in TEAMS or row["away_team"] not in TEAMS:
            continue
        week_rows.setdefault((row["season"], row["week"]), []).append(row)

    for season, week in sorted(week_rows):
        if last_season is not None and season != last_season:
            for rating in ratings.values():
                rating.regress_season()
            for quarterback in quarterback_ratings.values():
                quarterback.regress_season()
            for abbr in recent:
                recent[abbr] = recent[abbr][-6:]
        if season != last_season:
            current_model = fit_forecast_model(training_rows)
            home_field = home_field_edge(current_model)
        last_season = season

        league_points = league_points_sum / league_team_games
        before = {abbr: ratings[abbr].snapshot() for abbr in TEAMS}
        games_out = []
        for row in week_rows[(season, week)]:
            home_features, away_features = score_features(
                row,
                ratings[row["home_team"]],
                ratings[row["away_team"]],
                quarterback_ratings.get(
                    last_quarterback.get(row["home_team"], ""),
                    QuarterbackRating(),
                ),
                quarterback_ratings.get(
                    last_quarterback.get(row["away_team"], ""),
                    QuarterbackRating(),
                ),
            )
            game = forecast_game(
                row,
                recent,
                injury_index,
                player_index,
                current_model,
                home_features,
                away_features,
            )
            games_out.append(game)
            if game["actual"] is not None:
                margin = float(game["actual"]["margin"])
                training_rows.append(
                    {
                        "season": season,
                        "homeFeatures": home_features,
                        "awayFeatures": away_features,
                        "homeScore": float(game["actual"]["homeScore"]),
                        "awayScore": float(game["actual"]["awayScore"]),
                        "homeOutcome": (
                            1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
                        ),
                    }
                )

        # Freeze the full weekly slate before learning any result from it.
        # This also prevents co-kickoff games from depending on row order.
        games_by_id = {game["id"]: game for game in games_out}
        for row in week_rows[(season, week)]:
            game = games_by_id[row["game_id"]]
            if game["actual"] is not None:
                update_after_game(
                    row,
                    ratings,
                    epa_lookup,
                    recent,
                    player_index,
                    quarterback_ratings,
                    last_quarterback,
                    league_points,
                )
                league_points_sum += float(row["home_score"]) + float(
                    row["away_score"]
                )
                league_team_games += 2.0

        if season >= PUBLISH_FROM:
            weeks_out.append(
                {
                    "season": season,
                    "week": week,
                    "games": games_out,
                }
            )
            movers = []
            played = {g["home"] for g in games_out} | {g["away"] for g in games_out}
            for abbr in sorted(played):
                prev = before[abbr]
                now = ratings[abbr].snapshot()
                delta = now["off"] - prev["off"]
                if abs(delta) < 0.012:
                    continue
                direction = "up" if delta > 0 else "down"
                city, name, _tz = TEAMS[abbr]
                movers.append(
                    f"{city} {name} offense moved {direction} to {now['off']:+.2f} EPA per play after week {week}."
                )
            if any(g["actual"] is not None for g in games_out):
                learned.append(
                    {
                        "season": season,
                        "week": week,
                        "homeField": round(home_field, 2),
                        "sentences": movers[:6]
                        or [
                            f"Week {week} did not move any offense enough to change the prior."
                        ],
                    }
                )

    current = next(
        (week for week in weeks_out if any(g["status"] == "upcoming" for g in week["games"])),
        weeks_out[-1],
    )
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    previous = json.loads(OUT.read_text()) if OUT.exists() else None
    freeze_published_forecasts(weeks_out, current, previous, generated_at)
    accuracy_games = [
        game
        for week in weeks_out
        for game in week["games"]
        if game["actual"] is not None
    ]
    payload = {
        "generatedAt": generated_at,
        "modelVersion": MODEL_VERSION,
        "current": {"season": current["season"], "week": current["week"]},
        "homeField": round(home_field, 2),
        "teams": {abbr: team_payload(abbr) for abbr in TEAMS},
        "weeks": weeks_out,
        "accuracy": summarize(accuracy_games),
        "learned": learned[-8:],
        "notes": [
            "Forecasts use only games already played.",
            "The posted line is a comparison, not an input.",
            "Weather and travel are shown as context and do not change the score in this version.",
            "Score coefficients and win calibration are fit on completed prior seasons only.",
            "A rounded tie indicates likely overtime. About six percent of regular-season overtimes still end tied.",
            "A locked game keeps the forecast that was published before kickoff.",
            "This is research, not a recommendation to bet.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload))
    print(
        f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB) "
        f"current {current['season']} week {current['week']} "
        f"home field {home_field:.2f}"
    )
    overall = payload["accuracy"]["overall"]
    print(
        f"Finished games {overall['games']} straight-up {overall['straightUp']:.1%} "
        f"margin MAE {overall['marginMae']:.2f} total MAE {overall['totalMae']:.2f} "
        f"home {overall['homeScoreMae']:.2f} away {overall['awayScoreMae']:.2f} "
        f"Brier {overall['brier']:.3f}"
    )


def margin_component(
    model: dict[str, np.ndarray],
    home_features: list[float],
    away_features: list[float],
    index: int,
) -> float:
    """Home-margin points from one column of the two score equations."""
    return float(
        model["home"][index] * home_features[index]
        - model["away"][index] * away_features[index]
    )


def forecast_game(
    row: dict,
    recent: dict[str, list[dict]],
    injury_index: dict[tuple[int, int, str, str], str],
    player_index: dict[tuple[int, int, str], list[dict]],
    model: dict[str, np.ndarray],
    home_features: list[float],
    away_features: list[float],
) -> dict:
    home = row["home_team"]
    away = row["away_team"]
    neutral = row["location"] == "Neutral"
    home_hat = float(np.dot(home_features, model["home"]))
    away_hat = float(np.dot(away_features, model["away"]))
    raw_margin = home_hat - away_hat

    upcoming = row["home_score"] is None or row["away_score"] is None
    qb_note, qb_home_points, qb_away_points = quarterback_adjustment(
        row, recent, injury_index, use_injuries=upcoming
    )
    home_mean_raw = home_hat + qb_home_points
    away_mean_raw = away_hat + qb_away_points
    expected_total = home_mean_raw + away_mean_raw
    expected_margin = home_mean_raw - away_mean_raw
    home_mean, away_mean = bounded_means(expected_total, expected_margin)

    expected_margin = float(home_mean - away_mean)
    home_wins, ties = calibrated_probs(expected_margin, model["logistic"])
    home_score = int(round(home_mean))
    away_score = int(round(away_mean))
    overtime = home_score == away_score

    wind = parse_wind(row["wind"])
    indoor = str(row["roof"] or "").lower() in {"dome", "closed"}
    context = context_lines(row, wind, indoor, neutral, qb_note)
    xfactor = x_factor(row, wind, indoor, neutral)

    def component(index: int) -> float:
        return margin_component(model, home_features, away_features, index)

    adjustments = [
        {
            "label": "Offense",
            "points": round(component(2), 1),
            "detail": (
                "Recent points scored, relative to the league average, updated "
                "only after the whole prior week is complete."
            ),
        },
        {
            "label": "Opposing defense",
            "points": round(component(3), 1),
            "detail": "Recent points allowed by the opponent, relative to the league average.",
        },
        {
            "label": "Quarterback form",
            "points": round(component(6) + component(7), 1),
            "detail": (
                "Shrunk passing EPA of the most recent starters, scaled to a "
                "60-play game. It moves both team scores."
            ),
        },
        {
            "label": "Elo strength",
            "points": round(component(4), 1),
            "detail": (
                "A result-based team-strength rating trained on completed prior "
                "seasons. It does not use the betting line."
            ),
        },
        {
            "label": "Rest",
            "points": round(component(5), 1),
            "detail": "Difference in days of rest, capped at one week either way.",
        },
    ]
    if not neutral:
        adjustments.append(
            {
                "label": "Home field",
                "points": round(component(1), 1),
                "detail": "Learned from completed prior seasons. Neutral sites get none.",
            }
        )
    if abs(component(0)) >= 0.1:
        adjustments.append(
            {
                "label": "League baseline",
                "points": round(component(0), 1),
                "detail": "The fitted difference between the home-score and away-score intercepts.",
            }
        )
    if qb_home_points or qb_away_points:
        adjustments.append(
            {
                "label": "Quarterback availability",
                "points": round(qb_home_points - qb_away_points, 1),
                "detail": qb_note or "Starter availability changed the expected points.",
            }
        )
    if overtime:
        context.append(
            "The rounded score is level, so overtime is likely. The win chance accounts for overtime; about six percent of regular-season overtimes still end tied."
        )

    prediction = {
        "homeScore": home_score,
        "awayScore": away_score,
        "homeWinProb": round(home_wins, 3),
        "tieProb": round(ties, 3),
        "overtime": overtime,
        "spreadHome": round_half(-expected_margin),
        "total": round_half(home_mean + away_mean),
        "meanMargin": round(expected_margin, 4),
        "meanTotal": round(home_mean + away_mean, 4),
        "homeRange": score_band(home_mean),
        "awayRange": score_band(away_mean),
        "rawMargin": round(raw_margin, 2),
    }
    home_players, home_player_notes = project_players(
        recent.get(home, []), row, home, injury_index, use_injuries=upcoming
    )
    away_players, away_player_notes = project_players(
        recent.get(away, []), row, away, injury_index, use_injuries=upcoming
    )
    context.extend(home_player_notes)
    context.extend(away_player_notes)
    actual = None
    status = "upcoming"
    if row["home_score"] is not None and row["away_score"] is not None:
        status = "final"
        actual = {
            "homeScore": int(row["home_score"]),
            "awayScore": int(row["away_score"]),
            "margin": int(row["home_score"]) - int(row["away_score"]),
            "total": int(row["home_score"]) + int(row["away_score"]),
            "players": actual_players(player_index, row, home_players, away_players),
        }

    return {
        "id": row["game_id"],
        "season": row["season"],
        "week": row["week"],
        "status": status,
        "weekday": row["weekday"],
        "date": row["gameday"],
        "time": row["gametime"],
        "home": home,
        "away": away,
        "stadium": row["stadium"],
        "neutral": neutral,
        "roof": row["roof"],
        "temp": row["temp"],
        "wind": wind,
        "prediction": prediction,
        "players": {"home": home_players, "away": away_players},
        "actual": actual,
        "adjustments": adjustments,
        "context": context,
        "xfactor": xfactor,
        # nflverse spread_line is positive when the home team is favored. It
        # matches the home moneyline in every 2024-2026 game checked. Store the
        # betting number instead: negative means the home team is favored.
        "postedSpreadHome": None if row["spread_line"] is None else -float(row["spread_line"]),
        "postedTotal": row["total_line"],
        "postedHomeWinProb": (
            None
            if no_vig(row["home_moneyline"], row["away_moneyline"]) is None
            else round(no_vig(row["home_moneyline"], row["away_moneyline"]), 6)
        ),
    }


def quarterback_adjustment(
    row: dict,
    recent: dict[str, list[dict]],
    injury_index: dict[tuple[int, int, str, str], str],
    use_injuries: bool,
) -> tuple[str | None, float, float]:
    notes = []
    home_points = 0.0
    away_points = 0.0
    for side, team, bucket in (
        ("home", row["home_team"], "home"),
        ("away", row["away_team"], "away"),
    ):
        starter = lead_passer(recent.get(team, []))
        if not starter:
            continue
        status = (
            injury_index.get((row["season"], row["week"], team, starter["player_id"]))
            if use_injuries
            else None
        )
        if status in {"Out", "Doubtful"}:
            if bucket == "home":
                home_points -= 3.5
            else:
                away_points -= 3.5
            notes.append(
                f"{starter['name']} is {status.lower()}, so {TEAMS[team][1]} are docked 3.5 points."
            )
        elif status == "Questionable":
            notes.append(f"{starter['name']} is questionable. The range is the uncertain part, not a point deduction.")
    return (" ".join(notes) if notes else None, home_points, away_points)


def lead_passer(games: list[dict]) -> dict | None:
    """Passer who just played, not the four-game attempt leader.

    A four-game sum keeps last month's starter on the card after a change.
    The last game's attempt leader is the walk-forward starter.
    """
    for game in reversed(games[-4:]):
        if not game["passers"]:
            continue
        leader = max(game["passers"], key=lambda player: player["attempts"] or 0)
        if (leader["attempts"] or 0) > 0:
            return leader
    return None


def unavailable(
    injury_index: dict,
    row: dict,
    team: str,
    player_id: str,
    use_injuries: bool,
) -> bool:
    if not use_injuries:
        return False
    status = injury_index.get((row["season"], row["week"], team, player_id))
    return status in {"Out", "Doubtful"}


def project_players(
    games: list[dict],
    row: dict,
    team: str,
    injury_index: dict,
    use_injuries: bool,
) -> tuple[dict, list[str]]:
    notes: list[str] = []
    recent_games = games[-4:]
    passers: dict[str, dict] = {}
    rushers: dict[str, dict] = {}
    team_attempts = []
    team_carries = []
    for game in recent_games:
        team_attempts.append(sum((p["attempts"] or 0) for p in game["passers"]))
        team_carries.append(sum((p["carries"] or 0) for p in game["rushers"]))
        for player in game["passers"]:
            item = passers.setdefault(
                player["player_id"],
                {"id": player["player_id"], "name": player["name"], "attempts": 0, "yards": 0, "games": 0},
            )
            item["attempts"] += player["attempts"] or 0
            item["yards"] += player["passing_yards"] or 0
            item["games"] += 1
        for player in game["rushers"]:
            if player["position"] not in {"RB", "FB", "QB"}:
                continue
            item = rushers.setdefault(
                player["player_id"],
                {
                    "id": player["player_id"],
                    "name": player["name"],
                    "position": player["position"],
                    "carries": 0,
                    "yards": 0,
                    "games": 0,
                },
            )
            item["carries"] += player["carries"] or 0
            item["yards"] += player["rushing_yards"] or 0
            item["games"] += 1

    qb = None
    if passers:
        recent_order: list[str] = []
        for game in reversed(recent_games):
            if not game["passers"]:
                continue
            leader = max(game["passers"], key=lambda player: player["attempts"] or 0)
            if (leader["attempts"] or 0) <= 0 or leader["player_id"] in recent_order:
                continue
            recent_order.append(leader["player_id"])
        ranked_ids = recent_order + [
            item["id"] for item in sorted(passers.values(), key=lambda item: item["attempts"], reverse=True)
            if item["id"] not in recent_order
        ]
        ranked = [passers[item_id] for item_id in ranked_ids if item_id in passers]
        available = [
            item
            for item in ranked
            if not unavailable(injury_index, row, team, item["id"], use_injuries)
        ]
        leader = ranked[0]
        starter = available[0] if available else None
        if starter and starter["id"] != leader["id"]:
            notes.append(
                f"{leader['name']} is out or doubtful, so the passing line is {starter['name']}."
            )
        if starter and starter["attempts"] >= 8:
            attempts = shrunk_rate(starter["attempts"], starter["games"], 32, 2)
            ypa = shrunk_rate(starter["yards"], starter["attempts"], 7.0, 80)
            yards = attempts * ypa
            qb = {
                "id": starter["id"],
                "name": starter["name"],
                "attempts": round(attempts, 1),
                "attemptsLow": round(max(0.0, attempts - 8), 1),
                "attemptsHigh": round(attempts + 8, 1),
                "yards": round(yards),
                "low": max(0, round(yards - 70)),
                "high": round(yards + 70),
            }
    rb = None
    ball_carriers = [item for item in rushers.values() if item["position"] in {"RB", "FB"}]
    pool = ball_carriers or list(rushers.values())
    if pool:
        recent_order = []
        for game in reversed(recent_games):
            backs = [player for player in game["rushers"] if player["position"] in {"RB", "FB"}] or game["rushers"]
            if not backs:
                continue
            leader = max(backs, key=lambda player: player["carries"] or 0)
            if (leader["carries"] or 0) <= 0 or leader["player_id"] in recent_order:
                continue
            recent_order.append(leader["player_id"])
        ranked_ids = recent_order + [
            item["id"] for item in sorted(pool, key=lambda item: item["carries"], reverse=True)
            if item["id"] not in recent_order
        ]
        ranked = [next(item for item in pool if item["id"] == item_id) for item_id in ranked_ids if any(item["id"] == item_id for item in pool)]
        available = [
            item
            for item in ranked
            if not unavailable(injury_index, row, team, item["id"], use_injuries)
        ]
        leader = ranked[0]
        lead = available[0] if available else None
        if lead and lead["id"] != leader["id"]:
            notes.append(
                f"{leader['name']} is out or doubtful, so the rushing line is {lead['name']}."
            )
        if lead and lead["carries"] >= 5:
            carries = shrunk_rate(lead["carries"], lead["games"], 14, 2)
            ypc = shrunk_rate(lead["yards"], lead["carries"], 4.3, 40)
            yards = carries * ypc
            rb = {
                "id": lead["id"],
                "name": lead["name"],
                "carries": round(carries, 1),
                "carriesLow": round(max(0.0, carries - 5), 1),
                "carriesHigh": round(carries + 5, 1),
                "yards": round(yards),
                "low": max(0, round(yards - 32)),
                "high": round(yards + 32),
            }
    return {"qb": qb, "rb": rb}, notes


def actual_players(player_index, row, home_proj, away_proj) -> dict:
    found = {}
    for side, team, proj in (
        ("home", row["home_team"], home_proj),
        ("away", row["away_team"], away_proj),
    ):
        rows = player_index.get((row["season"], row["week"], team), [])
        side_actual = {"qb": None, "rb": None}
        for role in ("qb", "rb"):
            projected = proj.get(role)
            if not projected:
                continue
            match = next((item for item in rows if item["player_id"] == projected["id"]), None)
            if not match:
                continue
            if role == "qb":
                side_actual["qb"] = {
                    "attempts": match["attempts"] or 0,
                    "yards": match["passing_yards"] or 0,
                }
            else:
                side_actual["rb"] = {
                    "carries": match["carries"] or 0,
                    "yards": match["rushing_yards"] or 0,
                }
        found[side] = side_actual
    return found


def update_after_game(
    row,
    ratings,
    epa_lookup,
    recent,
    player_index,
    quarterback_ratings,
    last_quarterback,
    league_points,
) -> None:
    home = ratings[row["home_team"]]
    away = ratings[row["away_team"]]
    home_score = float(row["home_score"])
    away_score = float(row["away_score"])
    margin = home_score - away_score
    elo_edge = home.elo - away.elo
    expected_home = 1.0 / (1.0 + 10 ** (-elo_edge / 400.0))
    actual_home = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
    multiplier = (
        math.log(abs(margin) + 1.0) * 2.2 / (elo_edge * 0.001 + 2.2)
        if margin
        else 1.0
    )
    elo_delta = 18.0 * multiplier * (actual_home - expected_home)
    home.elo += elo_delta
    away.elo -= elo_delta
    home.update_score(home_score, away_score, league_points)
    away.update_score(away_score, home_score, league_points)

    for team, opponent in (
        (row["home_team"], row["away_team"]),
        (row["away_team"], row["home_team"]),
    ):
        stats = epa_lookup.get((row["season"], row["game_id"], team))
        allowed = epa_lookup.get((row["season"], row["game_id"], opponent))
        if stats and allowed:
            off_epa, off_plays = stats
            def_epa, def_plays = allowed
            ratings[team].update(off_epa, def_epa, off_plays, def_plays)
        rows = player_index.get((row["season"], row["week"], team), [])
        passers = [item for item in rows if (item["attempts"] or 0) > 0]
        if passers:
            starter = max(passers, key=lambda item: item["attempts"] or 0)
            player_id = starter["player_id"]
            quarterback = quarterback_ratings.setdefault(
                player_id, QuarterbackRating()
            )
            quarterback.update(
                float(starter["passing_epa"] or 0.0),
                float(starter["attempts"] or 0.0),
                float(starter["sacks_suffered"] or 0.0),
            )
            last_quarterback[team] = player_id
        recent[team].append(
            {
                "passers": [
                    {
                        "player_id": item["player_id"],
                        "name": item["player_display_name"],
                        "attempts": item["attempts"] or 0,
                        "passing_yards": item["passing_yards"] or 0,
                    }
                    for item in rows
                    if (item["attempts"] or 0) > 0
                ],
                "rushers": [
                    {
                        "player_id": item["player_id"],
                        "name": item["player_display_name"],
                        "position": item["position"],
                        "carries": item["carries"] or 0,
                        "rushing_yards": item["rushing_yards"] or 0,
                    }
                    for item in rows
                    if (item["carries"] or 0) > 0
                ],
            }
        )
        recent[team] = recent[team][-8:]


def context_lines(row, wind, indoor, neutral, qb_note) -> list[str]:
    lines = []
    if indoor:
        lines.append("Indoors, so temperature and wind are ignored.")
    else:
        bits = []
        if row["temp"] is not None:
            bits.append(f"{int(row['temp'])}°F")
        if wind is not None:
            bits.append(f"wind {wind} mph")
        if bits:
            lines.append(", ".join(bits) + ".")
    if neutral:
        lines.append("Neutral site. No home-field points.")
    away_tz = TEAMS.get(row["away_team"], ("", "", 0))[2]
    home_tz = TEAMS.get(row["home_team"], ("", "", 0))[2]
    if away_tz - home_tz >= 2:
        lines.append(
            f"Visitor is {away_tz - home_tz} time zones from home. Shown as context only."
        )
    if qb_note:
        lines.append(qb_note)
    return lines


def x_factor(row, wind, indoor, neutral) -> dict | None:
    away_tz = TEAMS.get(row["away_team"], ("", "", 0))[2]
    home_tz = TEAMS.get(row["home_team"], ("", "", 0))[2]
    early = str(row["gametime"] or "23:59") <= "13:00"
    if not neutral and away_tz >= 3 and home_tz <= 1 and early:
        return {
            "label": "Body clock",
            "points": 0,
            "detail": "West Coast visitor in an early Eastern window. This version flags it and does not add points.",
        }
    if not indoor and wind is not None and wind >= 20:
        return {
            "label": "Wind",
            "points": 0,
            "detail": f"Wind is {wind} mph. Extreme weather is flagged and does not change the score until it earns a backtest.",
        }
    return None


def summarize(games: list[dict]) -> dict:
    def pack(subset: list[dict]) -> dict:
        if not subset:
            return {
                "games": 0,
                "straightUp": 0,
                "marginMae": 0,
                "totalMae": 0,
                "brier": 0,
                "withinRange": 0,
                "marketBrier": None,
                "pairedBrier": None,
                "marketGames": 0,
                "marketMarginMae": None,
                "pairedMarginMae": None,
                "spreadGames": 0,
                "marketTotalMae": None,
                "pairedTotalMae": None,
                "totalGames": 0,
                "homeScoreMae": 0,
                "awayScoreMae": 0,
                "marketHomeScoreMae": None,
                "pairedHomeScoreMae": None,
                "marketAwayScoreMae": None,
                "pairedAwayScoreMae": None,
                "scoreGames": 0,
            }
        correct = 0
        margin_err = []
        total_err = []
        brier = []
        market = []
        paired = []
        market_margin = []
        paired_margin = []
        market_total = []
        paired_total = []
        home_err = []
        away_err = []
        market_home = []
        paired_home = []
        market_away = []
        paired_away = []
        covered = 0
        decided = 0
        for game in subset:
            actual = game["actual"]
            pred = game["prediction"]
            margin = actual["margin"]
            away_win_prob = 1.0 - pred["homeWinProb"] - pred["tieProb"]
            picked_home = pred["homeWinProb"] >= away_win_prob
            if margin > 0 and picked_home:
                correct += 1
            elif margin < 0 and not picked_home:
                correct += 1
            elif margin == 0:
                correct += 0.5
            decided += 1
            predicted_margin = pred.get("meanMargin", -pred["spreadHome"])
            predicted_total = pred.get("meanTotal", pred["total"])
            predicted_home = (predicted_total + predicted_margin) / 2.0
            predicted_away = (predicted_total - predicted_margin) / 2.0
            margin_err.append(abs(margin - predicted_margin))
            total_err.append(abs(actual["total"] - predicted_total))
            home_err.append(abs(actual["homeScore"] - predicted_home))
            away_err.append(abs(actual["awayScore"] - predicted_away))
            outcome = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
            # Binary Brier treats a final tie as half a home win. Match that
            # target by assigning half of the explicit tie probability to home.
            home_equivalent = pred["homeWinProb"] + 0.5 * pred["tieProb"]
            brier.append((home_equivalent - outcome) ** 2)
            if game["postedHomeWinProb"] is not None:
                paired.append((home_equivalent - outcome) ** 2)
                market.append((game["postedHomeWinProb"] - outcome) ** 2)
            if game["postedSpreadHome"] is not None:
                paired_margin.append(abs(margin - predicted_margin))
                market_margin.append(
                    abs(margin - (-float(game["postedSpreadHome"])))
                )
            if game["postedTotal"] is not None:
                paired_total.append(abs(actual["total"] - predicted_total))
                market_total.append(
                    abs(actual["total"] - float(game["postedTotal"]))
                )
            if (
                game["postedSpreadHome"] is not None
                and game["postedTotal"] is not None
            ):
                market_margin_pts = -float(game["postedSpreadHome"])
                market_total_pts = float(game["postedTotal"])
                market_home_pts = (market_total_pts + market_margin_pts) / 2.0
                market_away_pts = (market_total_pts - market_margin_pts) / 2.0
                paired_home.append(abs(actual["homeScore"] - predicted_home))
                paired_away.append(abs(actual["awayScore"] - predicted_away))
                market_home.append(abs(actual["homeScore"] - market_home_pts))
                market_away.append(abs(actual["awayScore"] - market_away_pts))
            home_low, home_high = pred["homeRange"]
            away_low, away_high = pred["awayRange"]
            if home_low <= actual["homeScore"] <= home_high and away_low <= actual["awayScore"] <= away_high:
                covered += 1
        return {
            "games": len(subset),
            "straightUp": round(correct / decided, 3) if decided else 0,
            "marginMae": round(float(np.mean(margin_err)), 2),
            "totalMae": round(float(np.mean(total_err)), 2),
            "brier": round(float(np.mean(brier)), 3),
            "withinRange": round(covered / len(subset), 3),
            "marketBrier": None if not market else round(float(np.mean(market)), 3),
            "pairedBrier": None if not paired else round(float(np.mean(paired)), 3),
            "marketGames": len(market),
            "marketMarginMae": (
                None if not market_margin else round(float(np.mean(market_margin)), 2)
            ),
            "pairedMarginMae": (
                None if not paired_margin else round(float(np.mean(paired_margin)), 2)
            ),
            "spreadGames": len(market_margin),
            "marketTotalMae": (
                None if not market_total else round(float(np.mean(market_total)), 2)
            ),
            "pairedTotalMae": (
                None if not paired_total else round(float(np.mean(paired_total)), 2)
            ),
            "totalGames": len(market_total),
            "homeScoreMae": round(float(np.mean(home_err)), 2),
            "awayScoreMae": round(float(np.mean(away_err)), 2),
            "marketHomeScoreMae": (
                None if not market_home else round(float(np.mean(market_home)), 2)
            ),
            "pairedHomeScoreMae": (
                None if not paired_home else round(float(np.mean(paired_home)), 2)
            ),
            "marketAwayScoreMae": (
                None if not market_away else round(float(np.mean(market_away)), 2)
            ),
            "pairedAwayScoreMae": (
                None if not paired_away else round(float(np.mean(paired_away)), 2)
            ),
            "scoreGames": len(market_home),
        }

    by_season = {}
    seasons = sorted({game["season"] for game in games})
    for season in seasons:
        by_season[str(season)] = pack([game for game in games if game["season"] == season])
    weekly = []
    for season, week in sorted({(game["season"], game["week"]) for game in games}):
        subset = [game for game in games if game["season"] == season and game["week"] == week]
        item = pack(subset)
        item["season"] = season
        item["week"] = week
        weekly.append(item)
    return {"overall": pack(games), "bySeason": by_season, "weekly": weekly}


if __name__ == "__main__":
    main()
