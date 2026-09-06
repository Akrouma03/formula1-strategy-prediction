"""Predict tyre strategy, finishing position and lap time for a starting slot.

    python scripts/predict.py --race "Australian Grand Prix" --position 5
    python scripts/predict.py --race Monaco --position 1 --condition Wet

Race names are fuzzy-matched, so "Monaco" resolves to "Monaco Grand Prix".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from f1strategy.data import load_race_data, seconds_to_lap_time  # noqa: E402
from f1strategy.paths import MODELS_DIR  # noqa: E402

TASKS = ("tyre_strategy", "positioning", "lap_time")


def resolve_race(name: str, known: list[str]) -> str:
    """Match a user-typed race to a known one, preferring an exact/prefix hit."""
    lowered = name.strip().lower()
    for race in known:
        if race.lower() == lowered:
            return race
    partial = [r for r in known if lowered in r.lower()]
    if partial:
        return partial[0]

    try:
        from fuzzywuzzy import process
    except ImportError:
        raise SystemExit(
            f"Unknown race {name!r}. Known races:\n  " + "\n  ".join(known)
        )
    match = process.extractOne(name, known)
    if match is None or match[1] < 60:
        raise SystemExit(
            f"Unknown race {name!r}. Known races:\n  " + "\n  ".join(known)
        )
    return match[0]


def load_models() -> dict:
    # joblib.load unpickles, which can execute arbitrary code. These files are
    # produced locally by scripts/train.py and are gitignored, so nothing is
    # loaded that this repository did not just build. Do not point this at a
    # .joblib file from an untrusted source.
    models = {}
    for task in TASKS:
        path = MODELS_DIR / f"{task}.joblib"
        if not path.exists():
            raise SystemExit(
                f"Missing {path}. Train the models first:\n    python scripts/train.py"
            )
        models[task] = joblib.load(path)
    return models


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--race", required=True, help="Race name, e.g. 'Monaco Grand Prix'")
    parser.add_argument("--position", required=True, type=int, help="Starting grid position")
    parser.add_argument("--condition", default="Dry", choices=["Dry", "Mix", "Wet"])
    parser.add_argument("--year", default="2016", help="Season to condition on (2014-2016)")
    args = parser.parse_args()

    races = sorted(load_race_data()["raceName"].unique())
    race = resolve_race(args.race, races)
    if race.lower() != args.race.strip().lower():
        print(f"Matched {args.race!r} -> {race!r}")

    if args.position < 1:
        raise SystemExit("Starting position must be 1 or greater.")

    models = load_models()

    race_features = pd.DataFrame(
        [{
            "positionStart": float(args.position),
            "raceName": race,
            "raceCondition": args.condition,
            "Year": str(args.year),
        }]
    )
    strategy = models["tyre_strategy"].predict(race_features)[0]
    finish = float(models["positioning"].predict(race_features)[0])

    lap_features = pd.DataFrame(
        [{"finish_position": round(finish), "raceName": race, "Year": str(args.year)}]
    )
    lap_seconds = float(models["lap_time"].predict(lap_features)[0])

    print(f"\n{race} - starting P{args.position} in {args.condition.lower()} conditions\n")
    print(f"  Opening tyre strategy   {strategy}")
    print(f"  Predicted finish        P{round(finish)}")
    print(f"  Average lap time        {seconds_to_lap_time(lap_seconds)}")
    print("\nTrained on 2014-2016 data; see reports/metrics.json for accuracy.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
