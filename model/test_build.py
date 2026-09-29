import unittest

import numpy as np

from model.build import (
    QuarterbackRating,
    Rating,
    bounded_means,
    calibrated_probs,
    fit_forecast_model,
    freeze_published_forecasts,
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
            strength = (index % 21) - 10
            margin = 1.5 + 0.8 * strength
            training.append(
                {
                    "season": 2010 + index // 100,
                    "marginFeatures": [
                        1.0,
                        1.0,
                        strength,
                        strength / 4,
                        0.0,
                        strength / 8,
                    ],
                    "totalFeatures": [
                        1.0,
                        float(index % 9),
                        abs(strength) / 4,
                        strength / 8,
                    ],
                    "margin": margin,
                    "total": 44.0 + (index % 9),
                    "homeOutcome": 1.0 if margin > 0 else 0.0,
                }
            )
        model = fit_forecast_model(training)
        self.assertEqual(model["margin"].shape, (6,))
        self.assertEqual(model["total"].shape, (4,))
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
        self.assertEqual(game["forecastModelVersion"], "yardline-3.1")

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
        }
        overall = summarize([game])["overall"]
        self.assertEqual(overall["marginMae"], 3.4)
        self.assertEqual(overall["totalMae"], 3.3)
        self.assertEqual(overall["marketGames"], 1)
        self.assertEqual(overall["pairedBrier"], 0.16)
        self.assertEqual(overall["marketBrier"], 0.122)


if __name__ == "__main__":
    unittest.main()
