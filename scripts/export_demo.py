"""Export a small, allowlisted historical dataset and measured model report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from f1strategy.data import STINT_COMPOUNDS, load_lap_time_data, load_laps, load_race_data  # noqa: E402
from f1strategy.models import TASKS, metadata  # noqa: E402
from f1strategy.paths import METRICS_JSON, ROOT  # noqa: E402


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
                    "id": row.DriverId,
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


def main() -> int:
    if not METRICS_JSON.exists():
        raise SystemExit("Run scripts/train.py before exporting the model report.")
    report = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    if report.get("schema_version") != 2 or set(report.get("tasks", {})) != set(TASKS):
        raise SystemExit("Rebuild all models: the report is missing tasks or has an old format.")
    if report.get("metadata", {}).get("source_sha256") != metadata()["source_sha256"]:
        raise SystemExit("The source data changed. Retrain before exporting.")
    output = ROOT / "docs" / "data"
    output.mkdir(parents=True, exist_ok=True)
    output.joinpath("events.json").write_text(
        json.dumps(build_demo(), indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    output.joinpath("metrics.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print("Exported historical events and chronological evaluation to docs/data/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
