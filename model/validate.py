from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "season.json"


def validate(path: Path = DATA) -> None:
    payload = json.loads(path.read_text())
    games = [game for week in payload["weeks"] for game in week["games"]]
    ids = [game["id"] for game in games]
    assert len(ids) == len(set(ids)), "duplicate game IDs"

    for game in games:
        pred = game["prediction"]
        home = float(pred["homeWinProb"])
        tie = float(pred["tieProb"])
        away = 1.0 - home - tie
        assert 0.0 <= home <= 1.0, f"{game['id']}: invalid home probability"
        assert 0.0 <= away <= 1.0, f"{game['id']}: invalid away probability"
        assert 0.0 <= tie <= 1.0, f"{game['id']}: invalid tie probability"
        assert pred["homeScore"] >= 0 and pred["awayScore"] >= 0

        kind = game["recordKind"]
        assert kind in {"published", "backtest", "provisional"}
        assert game["locked"] == (kind != "provisional")
        assert (game["forecastedAt"] is not None) == game["locked"]

        actual = game["actual"]
        assert (actual is not None) == (game["status"] == "final")
        if actual is not None:
            assert actual["margin"] == actual["homeScore"] - actual["awayScore"]
            assert actual["total"] == actual["homeScore"] + actual["awayScore"]


if __name__ == "__main__":
    validate()
    print(f"Validated {DATA}")
