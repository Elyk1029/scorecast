import unittest

from model.build import (
    Rating,
    bounded_means,
    calibrated_probs,
    freeze_published_forecasts,
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


if __name__ == "__main__":
    unittest.main()
