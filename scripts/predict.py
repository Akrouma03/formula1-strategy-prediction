"""Historical 2016 scenarios using models fitted on 2014–2015."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from f1strategy.data import CONDITIONS, RACE_NAMES, circuit_id, load_race_data, seconds_to_lap_time  # noqa: E402
from f1strategy.models import TASKS, predict  # noqa: E402
from f1strategy.paths import MODELS_DIR  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", required=True, help="Circuit name, e.g. Monaco")
    parser.add_argument("--position", required=True, type=int, choices=range(1, 23), metavar="1–22")
    parser.add_argument("--condition", default="Dry", choices=CONDITIONS)
    parser.add_argument("--year", type=int, default=2016, choices=[2016], help="Evaluation season")
    parser.add_argument("--json", action="store_true", help="Print machine-readable results")
    args = parser.parse_args(argv)
    try:
        circuit = circuit_id(args.race)
    except ValueError as exc:
        parser.error(str(exc))
    events = load_race_data()
    if events[(events.circuit_id == circuit) & (events.Year == args.year)].empty:
        parser.error("That circuit is not present in the 2016 source data.")
    features = pd.DataFrame(
        [{"positionStart": float(args.position), "circuit_id": circuit, "raceCondition": args.condition}]
    )
    results = {}
    notes = ["Historical scenario; race conditions are assumed, not forecast."]
    for task in TASKS:
        path = MODELS_DIR / f"{task}.joblib"
        if not path.exists():
            parser.error("Models are missing. Run python scripts/train.py first.")
        # Only load local bundles you built: joblib/pickle can execute code.
        artifact = joblib.load(path)
        try:
            value = predict(artifact, features)[0]
        except ValueError as exc:
            parser.error(str(exc))
        results[task] = str(value) if task == "tyre_strategy" else float(value)
        if circuit not in artifact["circuits"]:
            notes.append(f"{task}: circuit unseen in training; estimate has limited support.")
    output = {
        "race": RACE_NAMES[circuit],
        "season": args.year,
        "grid": args.position,
        "condition": args.condition,
        "predictions": results,
        "notes": notes,
    }
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"{output['race']} · {args.year} · P{args.position} · {args.condition}")
        print(f"Historical opening: {results['tyre_strategy']}")
        print(f"Finish among classified drivers: P{results['positioning']:.1f}")
        print(f"Pit-filtered average pace: {seconds_to_lap_time(results['lap_time'])}")
        print("\n".join(notes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
