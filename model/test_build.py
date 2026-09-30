import unittest

import numpy as np

from model.build import (
    DEFAULT_PLAYER_WIDTHS,
    QuarterbackRating,
    Rating,
    bounded_means,
    calibrated_probs,
    empirical_player_widths,
    fit_forecast_model,
    score_shape,
    freeze_published_forecasts,
    project_players,
    score_features,
    summarize,
)


class ForecastMathTests(unittest.TestCase):
    def test_probabilities_leave_room_for_tie(self) -> None:
        for margin in (-21.0, -3.0, 0.0, 3.0, 21.0):
            home, tie = calibrated_probs(margin)
            away = 1.0 - home - tie
            self.assertGreaterEqual(home, 0.0)
            self.assertGreaterEqual(away, 0.0)
            self.assertGreaterEqual(tie, 0.0)
            self.assertAlmostEqual(home + away + tie, 1.0)

    def test_bounded_means_keep_total_and_margin_consistent(self) -> None:
        home, away = bounded_means(45.0, 60.0)
        self.assertGreaterEqual(home, 6.0)
        self.assertGreaterEqual(away, 6.0)
        self.assertLessEqual(home, 42.0)
        self.assertLessEqual(away, 42.0)
        self.assertAlmostEqual(home + away, 45.0)

    def test_defense_uses_its_own_play_count(self) -> None:
        rating = Rating()
        rating.update(0.2, -0.2, off_plays=60, def_plays=30)
        self.assertGreater(rating.off, 0.0)
        self.assertLess(rating.defn, 0.0)
        self.assertNotEqual(abs(rating.off), abs(rating.defn))

    def test_quarterback_rating_is_shrunk_and_regressed(self) -> None:
        rating = QuarterbackRating()
        rating.update(passing_epa=12.0, attempts=30.0, sacks=2.0)
        learned = rating.epa
        self.assertGreater(learned, 0.0)
        self.assertLess(learned, 12.0 / 32.0)
        rating.regress_season()
        self.assertLess(rating.epa, learned)

    def test_fitted_model_produces_valid_calibrated_probabilities(self) -> None:
        training = []
        for index in range(600):
            offense = float((index % 21) - 10)
            defense = float(((index * 3) % 17) - 8)
            elo = offense / 4.0
            rest = float((index % 5) - 2) / 7.0
            field = 0.0 if index % 17 == 0 else 1.0
            own_qb = offense / 30.0
            opp_qb = defense / 30.0
            home_score = 22.0 + 0.4 * offense + 0.25 * defense + 1.2 * field
            away_score = 21.0 + 0.4 * defense + 0.25 * offense - 0.4 * field
            margin = home_score - away_score
            training.append(
                {
                    "season": 2010 + index // 100,
                    "homeFeatures": [
                        1.0,
                        field,
                        offense,
                        defense,
                        elo,
                        rest,
                        60.0 * own_qb,
                        60.0 * opp_qb,
                    ],
                    "awayFeatures": [
                        1.0,
                        field,
                        defense,
                        offense,
                        -elo,
                        -rest,
                        60.0 * opp_qb,
                        60.0 * own_qb,
                    ],
                    "homeScore": home_score,
                    "awayScore": away_score,
                    "homeOutcome": 1.0 if margin > 0 else 0.0,
                }
            )
        model = fit_forecast_model(training)
        self.assertEqual(model["home"].shape, (8,))
        self.assertEqual(model["away"].shape, (8,))
        self.assertEqual(model["logistic"].shape, (2,))
        home, tie = calibrated_probs(3.0, model["logistic"])
        self.assertTrue(np.isfinite(model["logistic"]).all())
        self.assertGreaterEqual(home, 0.0)
        self.assertGreaterEqual(tie, 0.0)
        self.assertLessEqual(home + tie, 1.0)

    def test_published_forecast_is_frozen(self) -> None:
        old_prediction = {
            "homeScore": 20,
            "awayScore": 17,
            "homeWinProb": 0.52,
            "tieProb": 0.002,
        }
        previous = {
            "generatedAt": "2026-09-29T00:00:00Z",
            "modelVersion": "old",
            "current": {"season": 2026, "week": 4},
            "weeks": [
                {
                    "season": 2026,
                    "week": 4,
                    "games": [
                        {
                            "id": "game",
                            "season": 2026,
                            "week": 4,
                            "prediction": old_prediction,
                            "players": {},
                            "adjustments": [],
                            "context": [],
                            "xfactor": None,
                            "postedSpreadHome": -3.0,
                            "postedTotal": 37.0,
                            "postedHomeWinProb": 0.6,
                        }
                    ],
                }
            ],
        }
        weeks = [
            {
                "season": 2026,
                "week": 4,
                "games": [
                    {
                        "id": "game",
                        "season": 2026,
                        "week": 4,
                        "prediction": {"homeScore": 31, "awayScore": 10},
                        "players": {"new": True},
                        "adjustments": [{"new": True}],
                        "context": ["new"],
                        "xfactor": {"new": True},
                        "postedSpreadHome": -10.0,
                        "postedTotal": 41.0,
                        "postedHomeWinProb": 0.8,
                    }
                ],
            }
        ]
        freeze_published_forecasts(
            weeks,
            {"season": 2026, "week": 4},
            previous,
            "2026-10-01T00:00:00Z",
        )
        game = weeks[0]["games"][0]
        self.assertEqual(game["prediction"], old_prediction)
        self.assertEqual(game["forecastedAt"], previous["generatedAt"])
        self.assertEqual(game["forecastModelVersion"], "old")
        self.assertEqual(game["recordKind"], "published")

    def test_backtest_is_recomputed_instead_of_frozen(self) -> None:
        previous_game = {
            "id": "old-game",
            "season": 2025,
            "week": 1,
            "prediction": {"homeScore": 10, "awayScore": 7},
            "players": {},
            "adjustments": [],
            "context": [],
            "xfactor": None,
            "postedSpreadHome": -1.0,
            "postedTotal": 35.0,
            "postedHomeWinProb": 0.55,
            "recordKind": "backtest",
        }
        previous = {
            "generatedAt": "2026-09-29T00:00:00Z",
            "modelVersion": "old",
            "current": {"season": 2026, "week": 4},
            "weeks": [{"season": 2025, "week": 1, "games": [previous_game]}],
        }
        new_prediction = {"homeScore": 24, "awayScore": 20}
        weeks = [
            {
                "season": 2025,
                "week": 1,
                "games": [{**previous_game, "prediction": new_prediction}],
            }
        ]
        freeze_published_forecasts(
            weeks,
            {"season": 2026, "week": 4},
            previous,
            "2026-10-01T00:00:00Z",
        )
        game = weeks[0]["games"][0]
        self.assertEqual(game["prediction"], new_prediction)
        self.assertEqual(game["recordKind"], "backtest")
        self.assertEqual(game["forecastModelVersion"], "yardline-3.2")

    def test_accuracy_uses_raw_means_and_paired_market_cohort(self) -> None:
        game = {
            "season": 2025,
            "week": 1,
            "prediction": {
                "homeScore": 24,
                "awayScore": 20,
                "homeWinProb": 0.6,
                "tieProb": 0.0,
                "spreadHome": -4.0,
                "total": 44.0,
                "meanMargin": 3.6,
                "meanTotal": 43.7,
                "homeRange": [6, 42],
                "awayRange": [2, 38],
            },
            "actual": {
                "homeScore": 27,
                "awayScore": 20,
                "margin": 7,
                "total": 47,
            },
            "postedHomeWinProb": 0.65,
            "postedSpreadHome": -5.0,
            "postedTotal": 45.0,
        }
        overall = summarize([game])["overall"]
        self.assertEqual(overall["marginMae"], 3.4)
        self.assertEqual(overall["totalMae"], 3.3)
        self.assertEqual(overall["marketGames"], 1)
        self.assertEqual(overall["pairedBrier"], 0.16)
        self.assertEqual(overall["marketBrier"], 0.122)
        self.assertEqual(overall["pairedMarginMae"], 3.4)
        self.assertEqual(overall["marketMarginMae"], 2.0)
        self.assertEqual(overall["pairedTotalMae"], 3.3)
        self.assertEqual(overall["marketTotalMae"], 2.0)
        self.assertEqual(overall["homeScoreMae"], 3.35)
        self.assertEqual(overall["awayScoreMae"], 0.05)
        self.assertEqual(overall["pairedHomeScoreMae"], 3.35)
        self.assertEqual(overall["marketHomeScoreMae"], 2.0)
        self.assertEqual(overall["pairedAwayScoreMae"], 0.05)
        self.assertEqual(overall["marketAwayScoreMae"], 0.0)
        self.assertEqual(overall["scoreGames"], 1)

    def test_score_features_swap_sides_and_flip_edges(self) -> None:
        home = Rating()
        away = Rating()
        home.points_off = 3.0
        home.points_def = -1.0
        home.elo = 40.0
        away.points_off = -2.0
        away.points_def = 1.0
        away.elo = -10.0
        home_qb = QuarterbackRating()
        away_qb = QuarterbackRating()
        home_qb.epa = 0.1
        away_qb.epa = -0.05
        home_x, away_x = score_features(
            {"location": "Home", "home_rest": 10, "away_rest": 7},
            home,
            away,
            home_qb,
            away_qb,
        )
        self.assertEqual(len(home_x), 8)
        self.assertEqual(len(away_x), 8)
        self.assertAlmostEqual(home_x[2], 3.0)
        self.assertAlmostEqual(away_x[2], -2.0)
        self.assertAlmostEqual(home_x[3], 1.0)
        self.assertAlmostEqual(away_x[3], -1.0)
        self.assertAlmostEqual(home_x[4], -away_x[4])
        self.assertAlmostEqual(home_x[5], -away_x[5])
        self.assertAlmostEqual(home_x[6], 6.0)
        self.assertAlmostEqual(away_x[6], -3.0)
        self.assertAlmostEqual(home_x[7], away_x[6])
        self.assertAlmostEqual(away_x[7], home_x[6])

    def test_short_history_uses_eight_score_coefficients(self) -> None:
        model = fit_forecast_model([])
        self.assertEqual(model["home"].shape, (8,))
        self.assertEqual(model["away"].shape, (8,))
        self.assertEqual(model["logistic"].shape, (2,))

    def _player_history(self) -> list[dict]:
        games = []
        for attempts in (10, 10, 10, 10, 10, 10, 40):
            games.append(
                {
                    "passers": [
                        {
                            "player_id": "qb",
                            "name": "Starter",
                            "attempts": attempts,
                            "passing_yards": attempts * 7,
                        }
                    ],
                    "rushers": [
                        {
                            "player_id": "rb",
                            "name": "Back",
                            "position": "RB",
                            "carries": 12,
                            "rushing_yards": 48,
                        }
                    ],
                }
            )
        return games

    def test_recent_start_pulls_the_passing_line_up(self) -> None:
        row = {"season": 2024, "week": 1}
        history = self._player_history()
        current, _notes = project_players(history, row, "BUF", {}, False)
        previous, _notes = project_players(
            history, row, "BUF", {}, False, formula="previous"
        )
        self.assertGreater(current["qb"]["attempts"], previous["qb"]["attempts"])

    def test_opponent_yards_allowed_scales_yards_not_volume(self) -> None:
        row = {"season": 2024, "week": 1}
        history = self._player_history()
        base, _notes = project_players(history, row, "BUF", {}, False)
        softer, _notes = project_players(
            history,
            row,
            "BUF",
            {},
            False,
            pass_factor=1.1,
            rush_factor=1.1,
        )
        untouched, _notes = project_players(
            history,
            row,
            "BUF",
            {},
            False,
            formula="previous",
            pass_factor=1.5,
            rush_factor=1.5,
        )
        plain, _notes = project_players(
            history, row, "BUF", {}, False, formula="previous"
        )
        self.assertEqual(base["qb"]["attempts"], softer["qb"]["attempts"])
        self.assertEqual(base["rb"]["carries"], softer["rb"]["carries"])
        self.assertGreater(softer["qb"]["yards"], base["qb"]["yards"])
        self.assertGreater(softer["rb"]["yards"], base["rb"]["yards"])
        self.assertEqual(untouched["qb"]["yards"], plain["qb"]["yards"])
        self.assertAlmostEqual(base["qb"]["attemptsHigh"] - base["qb"]["attempts"], 8.0)

    def test_player_window_stays_fixed_until_enough_misses_exist(self) -> None:
        thin = {key: [1.0] for key in ("attempts", "pass", "carries", "rush")}
        self.assertEqual(empirical_player_widths(thin), DEFAULT_PLAYER_WIDTHS)
        ready = {key: [float(index) for index in range(400)] for key in thin}
        widths = empirical_player_widths(ready)
        self.assertGreater(widths[1], 70)

    def test_score_shape_keeps_a_field_goal_margin(self) -> None:
        prediction = {
            "meanMargin": 3.0,
            "meanTotal": 45.0,
            "spreadHome": -3.0,
            "total": 45.0,
        }
        field_goals = [(24, 21)] * 300
        fours = [(24, 20)] * 100
        self.assertIsNone(score_shape(prediction, field_goals[:10]))
        shape = score_shape(prediction, field_goals + fours)
        self.assertIsNotNone(shape)
        assert shape is not None
        rates = {row["margin"]: row["probability"] for row in shape["keyMargins"]}
        self.assertGreater(rates[3], rates[4])
        self.assertGreater(rates[3], 0.7)
        self.assertEqual(shape["topScores"][0]["home"], 24)
        self.assertEqual(shape["topScores"][0]["away"], 21)
        self.assertEqual(shape["sample"], 400)

    def test_score_shape_moves_with_the_forecast_margin(self) -> None:
        finals = [(24, 21)] * 200 + [(31, 17)] * 200
        pick = score_shape({"meanMargin": 0.0, "meanTotal": 45.0}, finals)
        blowout = score_shape({"meanMargin": 14.0, "meanTotal": 48.0}, finals)
        self.assertIsNotNone(pick)
        self.assertIsNotNone(blowout)
        assert pick is not None and blowout is not None

        def rate(shape: dict, margin: int) -> float:
            return next(row["probability"] for row in shape["keyMargins"] if row["margin"] == margin)

        self.assertGreater(rate(pick, 3), rate(pick, 14))
        self.assertGreater(rate(blowout, 14), rate(pick, 14))
        self.assertEqual(blowout["topScores"][0]["home"], 31)
        self.assertEqual(blowout["topScores"][0]["away"], 17)


if __name__ == "__main__":
    unittest.main()
