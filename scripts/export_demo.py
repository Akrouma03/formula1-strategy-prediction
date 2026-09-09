"""Export a small, allowlisted historical dataset and measured model report."""

from __future__ import annotations

import json
import argparse
import hashlib
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from f1strategy.data import STINT_COMPOUNDS, load_lap_time_data, load_laps, load_race_data  # noqa: E402
from f1strategy.models import TASKS, metadata  # noqa: E402
from f1strategy.paths import METRICS_JSON, ROOT  # noqa: E402
from f1strategy.identities import driver_name  # noqa: E402


def build_demo() -> dict:
    races = load_race_data()
    laps = load_laps()
    pace = load_lap_time_data()
    events = []
    for event_id, rows in races[races.Year == 2016].groupby("event_id"):
        event_laps = laps[laps.event_id == event_id]
        event_pace = pace[pace.event_id == event_id]
        if event_laps.empty or event_pace.empty:
            continue
        lap_count = int(event_laps.Lap.max())
        drivers = []
        for _, row in rows.sort_values(["positionFinish", "DriverId"], na_position="last").iterrows():
            stints = []
            for i, col in enumerate(STINT_COMPOUNDS, start=1):
                length = pd.to_numeric(row.get(f"Stint_Laps_{i}"), errors="coerce")
                if row[col]:
                    stints.append(
                        {
                            "compound": row[col],
                            "laps": int(length) if pd.notna(length) and length > 0 else None,
                        }
                    )
            drivers.append(
                {
                    "id": driver_name(row.driver_id, row.DriverId),
                    "grid": int(row.positionStart) if pd.notna(row.positionStart) else None,
                    "finish": int(row.positionFinish) if pd.notna(row.positionFinish) else None,
                    "stints": stints,
                }
            )
        timing = event_laps[~event_laps.near_pit & event_laps.time_seconds.notna()]
        lap_medians = timing.groupby("Lap").time_seconds.median()
        grid = rows.positionStart.dropna()
        duplicate_grid = sorted(int(p) for p in grid[grid.duplicated()].unique())
        events.append(
            {
                "id": event_id,
                "name": rows.iloc[0].raceName,
                "circuit": rows.iloc[0].circuit_id,
                "year": 2016,
                "condition": rows.iloc[0].raceCondition,
                "laps": lap_count,
                "referencePace": round(float(event_pace.avg_lap_time.median()), 3),
                "drivers": drivers,
                "quality": {
                    "duplicateGridSlots": duplicate_grid,
                    "unknownGridRecords": int(rows.positionStart.isna().sum()),
                },
                "pace": [
                    {"lap": int(lap), "seconds": round(float(value), 3)} for lap, value in lap_medians.items()
                ],
            }
        )
    return {
        "schemaVersion": 1,
        "metadata": metadata(),
        "events": events,
        "notes": [
            "2016 source observations; no track-status flags are available.",
            "Simulator coefficients are illustrative and independent of the trained models.",
        ],
    }


def equivalent(left, right) -> bool:
    """Compare generated content, tolerating floating-point/platform metadata differences."""
    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left) - {"metadata"}
        return keys == set(right) - {"metadata"} and all(equivalent(left[k], right[k]) for k in keys)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(equivalent(a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    return left == right


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check committed demo output without writing it")
    args = parser.parse_args(argv)
    if not METRICS_JSON.exists():
        raise SystemExit("Run scripts/train.py before exporting the model report.")
    report = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    if report.get("schema_version") != 2 or set(report.get("tasks", {})) != set(TASKS):
        raise SystemExit("Rebuild all models: the report is missing tasks or has an old format.")
    if report.get("metadata", {}).get("source_sha256") != metadata()["source_sha256"]:
        raise SystemExit("The source data changed. Retrain before exporting.")
    if report.get("metadata", {}).get("pipeline_sha256") != metadata()["pipeline_sha256"]:
        raise SystemExit("The pipeline changed. Retrain before exporting.")
    research_path = ROOT / "reports" / "research.json"
    if not research_path.exists():
        raise SystemExit("Run scripts/build_research.py before exporting.")
    research = json.loads(research_path.read_text(encoding="utf-8"))
    if research.get("schema_version") != 1 or any(
        research.get("metadata", {}).get(key) != metadata()[key]
        for key in ("source_sha256", "pipeline_sha256")
    ):
        raise SystemExit("Rebuild stale research with scripts/build_research.py.")
    expected_hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("src/f1strategy/stints.py", "scripts/build_research.py")
    }
    if research.get("research_sha256") != expected_hashes:
        raise SystemExit("Research code changed. Run scripts/build_research.py.")
    research["catalogue"] = json.loads((ROOT / "data" / "catalogue.json").read_text(encoding="utf-8"))
    output = ROOT / "docs" / "data"
    payloads = {"events.json": build_demo(), "metrics.json": report, "research.json": research}
    if args.check:
        for name, payload in payloads.items():
            path = output / name
            if not path.exists() or not equivalent(json.loads(path.read_text(encoding="utf-8")), payload):
                raise SystemExit(
                    f"Stale demo content: {name}. Run scripts/export_demo.py and commit the export."
                )
        print("Committed demo content matches regenerated results.")
        return 0
    output.mkdir(parents=True, exist_ok=True)
    output.joinpath("events.json").write_text(
        json.dumps(payloads["events.json"], indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    output.joinpath("metrics.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    output.joinpath("research.json").write_text(
        json.dumps(research, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print("Exported historical events, measured evaluation and data research to docs/data/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
