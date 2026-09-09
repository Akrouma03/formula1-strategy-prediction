"""Reproduce public data-quality and stint-study results from curated snapshots."""

import json
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from f1strategy.data import lap_time_data_with_audit, load_laps, load_race_data  # noqa: E402
from f1strategy.models import TASKS, dataset, metadata  # noqa: E402
from f1strategy.paths import ROOT  # noqa: E402
from f1strategy.stints import build_study  # noqa: E402


def build_research() -> dict:
    races, laps = load_race_data(), load_laps()
    _, joins = lap_time_data_with_audit()
    quality = {
        "race_rows": len(races),
        "lap_rows": len(laps),
        "events": races.event_id.nunique(),
        "invalid_lap_times": int(laps.time_seconds.isna().sum()),
        "pit_adjacent_laps": int(laps.near_pit.sum()),
        "joins": joins,
        "task_rows": {task: len(dataset(task)) for task in TASKS},
        "duplicate_grid_events": [
            {
                "event_id": event,
                "slots": sorted(
                    int(v)
                    for v in rows.positionStart.dropna()[rows.positionStart.dropna().duplicated()].unique()
                ),
            }
            for event, rows in races.groupby("event_id")
            if rows.positionStart.dropna().duplicated().any()
        ],
        "source_conflicts": [
            {
                "event_id": "2015:bahrain",
                "driver_id": "button",
                "finding": "Lap file has timed laps; race file has no matching record. Official classification says DNS.",
                "action": "Left unmatched and excluded from model rows; no invented grid or stint information.",
                "reference": "https://www.formula1.com/en/results/2015/races/920/bahrain/race-result",
            }
        ],
    }
    return {
        "schema_version": 1,
        "metadata": metadata(),
        "research_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("src/f1strategy/stints.py", "scripts/build_research.py")
        },
        "quality": quality,
        "stints": build_study(),
    }


def main() -> None:
    result = build_research()
    output = ROOT / "reports" / "research.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["quality"]["joins"]))
    print(json.dumps(result["stints"]["audit"]))
    print(json.dumps(result["stints"]["evaluation"]))


if __name__ == "__main__":
    main()
