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

ALIASES = {"LA": "LAR"}


def canon(team: str | None) -> str | None:
    if team is None:
        return None
    return ALIASES.get(team, team)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "season.json"
SEASONS = [2023, 2024, 2025, 2026]
PUBLISH_FROM = 2024
PLAYS = 60.0
SIMS = 2500
MODEL_VERSION = "yardline-1.4"
# Plays of memory carried into a new season. About one or two games, so a
# three-game stretch can outweigh last year without letting one Sunday rewrite it.
SEASON_PRIOR_PLAYS = 80.0
# Score means stay. A normal on the margin is still too confident for this
# model's historical win rate, so the published probability is pulled toward 0.5.
MARGIN_SD = 13.5
WIN_SHRINK = 0.28

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
        self.games = 0

    def snapshot(self) -> dict[str, float]:
        return {"off": round(self.off, 4), "def": round(self.defn, 4), "games": self.games}

    def regress_season(self) -> None:
        self.off *= 0.55
        self.defn *= 0.55
        self.off_n = SEASON_PRIOR_PLAYS
        self.def_n = SEASON_PRIOR_PLAYS
        self.games = 0

    def update(self, off_epa: float, def_epa: float, plays: float) -> None:
        plays = max(plays, 1.0)
        off_a = plays / (plays + self.off_n)
        def_a = plays / (plays + self.def_n)
        self.off = (1 - off_a) * self.off + off_a * off_epa
        self.defn = (1 - def_a) * self.defn + def_a * def_epa
        self.off_n = min(260.0, self.off_n + plays * 0.2)
        self.def_n = min(260.0, self.def_n + plays * 0.2)
        self.games += 1


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


def simulate_score(
    home_mean: float, away_mean: float, n: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Integer scores with a realistic miss size.

    Margin noise is about 13.5 points and the total noise is about 11, which is
    the historical width of an NFL forecast. Independent drive draws were too
    narrow, so the published 10th–90th band did not cover 80% of results.
    """
    margin = home_mean - away_mean
    total = home_mean + away_mean
    # Wider than the win-probability scale. The point forecast is often off by
    # about a touchdown, so the published band has to be wide enough to cover it.
    margin_noise = rng.normal(0, 18.0, n)
    total_noise = rng.normal(0, 16.0, n)
    home = np.clip(np.round((total + total_noise + margin + margin_noise) / 2), 0, 70)
    away = np.clip(np.round((total + total_noise - (margin + margin_noise)) / 2), 0, 70)
    return home.astype(int), away.astype(int)


def sample_scores(mean: float, n: int, rng: np.random.Generator) -> np.ndarray:
    drives = 11
    mean = float(np.clip(mean, 3, 45))
    p_td = float(np.clip(mean * 0.64 / (7 * drives), 0.02, 0.42))
    p_fg = float(np.clip(mean * 0.32 / (3 * drives), 0.01, 0.30))
    expected = drives * (7 * p_td + 3 * p_fg)
    scale = mean / expected if expected else 1.0
    p_td = min(0.48, p_td * scale)
    p_fg = min(0.36, p_fg * scale * 0.92)
    draws = rng.random((n, drives))
    xp = rng.random((n, drives))
    td = draws < p_td
    fg = (draws >= p_td) & (draws < p_td + p_fg)
    points = td * np.where(xp > 0.06, 7, 6) + fg * 3
    return points.sum(axis=1).astype(int)


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


# Regular-season overtime is 10 minutes. Most regulation ties become a field
# goal for one side. About one overtime in ten is still level when the clock expires.
OT_POINTS = 3.0
OT_STILL_TIED = 0.10


def regulation_tie_prob(expected_margin: float) -> float:
    """Chance the score is level after 60 minutes and overtime starts."""
    return normal_cdf((0.5 - expected_margin) / MARGIN_SD) - normal_cdf(
        (-0.5 - expected_margin) / MARGIN_SD
    )


def calibrated_probs(expected_margin: float) -> tuple[float, float]:
    """Return home win probability and the chance the game is still tied after overtime.

    Win probability is a normal with SD 13.5, then shrunk toward 0.5 so the Brier
    score is not worse than a coin flip. A regulation tie plays overtime. The
    published tie rate is only the games that stay level after that period.
    """
    raw = normal_cdf(expected_margin / MARGIN_SD)
    p_reg_tie = regulation_tie_prob(expected_margin)
    p_home_reg = max(0.0, raw - 0.5 * p_reg_tie)
    edge = math.tanh(expected_margin / 3.0)
    home_given_ot = (1.0 - OT_STILL_TIED) * (0.5 + 0.08 * edge)
    p_home = p_home_reg + p_reg_tie * home_given_ot
    home = 0.5 + WIN_SHRINK * (p_home - 0.5)
    tie = p_reg_tie * OT_STILL_TIED
    return home, tie


def apply_overtime(
    home_mean: float, away_mean: float, neutral: bool
) -> tuple[int, int, float, bool]:
    """Break a rounded regulation tie with the usual overtime field goal.

    The points go to the team with the higher unrounded score. A dead heat at
    home goes to the home team. A dead heat on a neutral field stays level,
    because overtime is a coin flip and neither side has earned the kick.
    """
    home_score = int(round(home_mean))
    away_score = int(round(away_mean))
    if home_score != away_score:
        return home_score, away_score, 0.0, False
    if away_mean > home_mean:
        return home_score, away_score + int(OT_POINTS), -OT_POINTS, True
    if home_mean > away_mean or not neutral:
        return home_score + int(OT_POINTS), away_score, OT_POINTS, True
    return home_score, away_score, 0.0, True


def team_payload(abbr: str) -> dict[str, str | int]:
    city, name, tz = TEAMS.get(abbr, (abbr, abbr, 0))
    return {"abbr": abbr, "city": city, "name": name, "tz": tz}


def shrunk_rate(total: float, count: float, prior: float, prior_n: float) -> float:
    return (total + prior * prior_n) / (count + prior_n) if count + prior_n else prior


def main() -> None:
    print("Loading nflverse schedules, play-by-play, player stats, and injuries...")
    schedules = nfl.load_schedules(SEASONS).filter(pl.col("game_type") == "REG")
    pbp = nfl.load_pbp(SEASONS)
    if "season_type" in pbp.columns:
        pbp = pbp.filter(pl.col("season_type") == "REG")
    players = nfl.load_player_stats(SEASONS)
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
    home_field = 1.7
    home_n = 40.0
    rng = np.random.default_rng(2026)

    weeks_out: list[dict] = []
    current_week_bucket: dict | None = None
    accuracy_games: list[dict] = []
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
            for abbr in recent:
                recent[abbr] = recent[abbr][-6:]
        last_season = season

        before = {abbr: ratings[abbr].snapshot() for abbr in TEAMS}
        games_out = []
        for row in week_rows[(season, week)]:
            game = forecast_game(
                row,
                ratings,
                recent,
                injury_index,
                player_index,
                home_field,
                rng,
            )
            games_out.append(game)
            if game["actual"] is not None:
                accuracy_games.append(game)
                update_after_game(row, ratings, epa_lookup, recent, player_index)
                if row["location"] != "Neutral" and game["actual"]["margin"] is not None:
                    raw = game["prediction"]["rawMargin"]
                    resid = game["actual"]["margin"] - raw
                    home_field = (home_field * home_n + resid) / (home_n + 1)
                    home_n += 1
                    home_field = float(np.clip(home_field, 0.8, 2.6))

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
    payload = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
            "Win probability is a margin normal (SD 13.5) shrunk toward 0.5.",
            "A regulation tie plays a 10-minute overtime. The score adds a field goal for the side ahead. About one overtime in ten still ends tied.",
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
        f"margin MAE {overall['marginMae']:.2f} Brier {overall['brier']:.3f}"
    )


def forecast_game(
    row: dict,
    ratings: dict[str, Rating],
    recent: dict[str, list[dict]],
    injury_index: dict[tuple[int, int, str, str], str],
    player_index: dict[tuple[int, int, str], list[dict]],
    home_field: float,
    rng: np.random.Generator,
) -> dict:
    home = row["home_team"]
    away = row["away_team"]
    neutral = row["location"] == "Neutral"
    field = 0.0 if neutral else home_field
    home_rating = ratings[home]
    away_rating = ratings[away]
    # defn is EPA allowed. Higher means a worse defense, so it adds to the
    # opponent's expected EPA. Subtracting it counted a leaky defense as a strength.
    home_epa = home_rating.off + away_rating.defn
    away_epa = away_rating.off + home_rating.defn
    raw_margin = PLAYS * (home_epa - away_epa)
    base_total = 45.0 + PLAYS * (home_epa + away_epa)
    base_total = float(np.clip(base_total, 32, 60))

    qb_note, qb_home_points, qb_away_points = quarterback_adjustment(
        row, recent, injury_index
    )
    home_mean = base_total / 2 + (raw_margin + field) / 2 + qb_home_points
    away_mean = base_total / 2 - (raw_margin + field) / 2 + qb_away_points
    home_mean = float(np.clip(home_mean, 6, 42))
    away_mean = float(np.clip(away_mean, 6, 42))

    expected_margin = float(home_mean - away_mean)
    home_wins, ties = calibrated_probs(expected_margin)
    home_score, away_score, ot_points, overtime = apply_overtime(
        home_mean, away_mean, neutral
    )

    wind = parse_wind(row["wind"])
    indoor = str(row["roof"] or "").lower() in {"dome", "closed"}
    context = context_lines(row, wind, indoor, neutral, qb_note)
    xfactor = x_factor(row, wind, indoor, neutral)

    adjustments = [
        {
            "label": f"{TEAMS[home][1]} offense",
            "points": round(PLAYS * home_epa, 1),
            "detail": (
                f"{TEAMS[home][1]} offense {home_rating.off:+.2f} EPA/play "
                f"against a {TEAMS[away][1]} defense allowing {away_rating.defn:+.2f}. "
                "Allowing more EPA raises the opponent's score."
            ),
        },
        {
            "label": f"{TEAMS[away][1]} offense",
            "points": round(-PLAYS * away_epa, 1),
            "detail": (
                f"{TEAMS[away][1]} offense {away_rating.off:+.2f} EPA/play "
                f"against a {TEAMS[home][1]} defense allowing {home_rating.defn:+.2f}. "
                "Shown from the home side, so a weak day for this offense adds to the home margin."
            ),
        },
    ]
    if not neutral:
        adjustments.append(
            {
                "label": "Home field",
                "points": round(field, 1),
                "detail": "Fitted from earlier games this model has already scored. Neutral sites get none.",
            }
        )
    if qb_home_points or qb_away_points:
        adjustments.append(
            {
                "label": "Quarterback",
                "points": round(qb_home_points - qb_away_points, 1),
                "detail": qb_note or "Starter availability changed the expected points.",
            }
        )
    if overtime and ot_points:
        winner = TEAMS[home][1] if ot_points > 0 else TEAMS[away][1]
        adjustments.append(
            {
                "label": "Overtime",
                "points": ot_points,
                "detail": (
                    f"Regulation rounds to a tie, so this plays a 10-minute overtime. "
                    f"The score adds a field goal for the {winner}, the usual finish. "
                    "About one overtime in ten still ends tied."
                ),
            }
        )
        context.append(
            f"Regulation is level. The score includes an overtime field goal for the {winner}. About one overtime in ten still ends tied."
        )
    elif overtime:
        context.append(
            "Regulation is level on a neutral field. Overtime is a coin flip, so the score stays level. About one overtime in ten ends tied."
        )

    prediction = {
        "homeScore": home_score,
        "awayScore": away_score,
        "homeWinProb": round(home_wins, 3),
        "tieProb": round(ties, 3),
        "overtime": overtime,
        "spreadHome": round_half(-(home_score - away_score)),
        "total": round_half(home_score + away_score),
        "homeRange": score_band(home_score),
        "awayRange": score_band(away_score),
        "rawMargin": round(raw_margin, 2),
    }
    home_players, home_player_notes = project_players(
        recent.get(home, []), row, home, injury_index
    )
    away_players, away_player_notes = project_players(
        recent.get(away, []), row, away, injury_index
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
            else round(no_vig(row["home_moneyline"], row["away_moneyline"]), 3)
        ),
    }


def quarterback_adjustment(
    row: dict,
    recent: dict[str, list[dict]],
    injury_index: dict[tuple[int, int, str, str], str],
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
        status = injury_index.get((row["season"], row["week"], team, starter["player_id"]))
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


def unavailable(injury_index: dict, row: dict, team: str, player_id: str) -> bool:
    status = injury_index.get((row["season"], row["week"], team, player_id))
    return status in {"Out", "Doubtful"}


def project_players(
    games: list[dict],
    row: dict,
    team: str,
    injury_index: dict,
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
        available = [item for item in ranked if not unavailable(injury_index, row, team, item["id"])]
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
        available = [item for item in ranked if not unavailable(injury_index, row, team, item["id"])]
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


def update_after_game(row, ratings, epa_lookup, recent, player_index) -> None:
    for team, opponent in (
        (row["home_team"], row["away_team"]),
        (row["away_team"], row["home_team"]),
    ):
        stats = epa_lookup.get((row["season"], row["game_id"], team))
        allowed = epa_lookup.get((row["season"], row["game_id"], opponent))
        if stats and allowed:
            off_epa, plays = stats
            ratings[team].update(off_epa, allowed[0], plays)
        rows = player_index.get((row["season"], row["week"], team), [])
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
            }
        correct = 0
        margin_err = []
        total_err = []
        brier = []
        market = []
        covered = 0
        decided = 0
        for game in subset:
            actual = game["actual"]
            pred = game["prediction"]
            margin = actual["margin"]
            if margin > 0 and pred["homeWinProb"] >= 0.5:
                correct += 1
            elif margin < 0 and pred["homeWinProb"] < 0.5:
                correct += 1
            elif margin == 0:
                correct += 0.5
            decided += 1
            margin_err.append(abs(margin - (pred["homeScore"] - pred["awayScore"])))
            total_err.append(abs(actual["total"] - pred["total"]))
            outcome = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
            brier.append((pred["homeWinProb"] - outcome) ** 2)
            if game["postedHomeWinProb"] is not None and margin != 0:
                market.append((game["postedHomeWinProb"] - outcome) ** 2)
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
