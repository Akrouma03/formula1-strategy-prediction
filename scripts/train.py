"""Train chronological baselines and write versioned local model bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from f1strategy.models import TASKS, metadata, train_task  # noqa: E402
from f1strategy.paths import METRICS_JSON, MODELS_DIR, ensure_dirs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=TASKS, action="append")
    args = parser.parse_args()
    ensure_dirs()
    tasks = list(dict.fromkeys(args.task or TASKS))
    existing = json.loads(METRICS_JSON.read_text()) if METRICS_JSON.exists() else {}
    report = existing if existing.get("schema_version") == 2 else {"schema_version": 2, "tasks": {}}
    if report.get("tasks") and report.get("metadata") != metadata() and set(tasks) != set(TASKS):
        parser.error("Data or dependency versions changed. Retrain all tasks before a partial update.")
    report["metadata"] = metadata()
    report["protocol"] = "2014 train; 2015 selection; refit 2014–2015; 2016 held-out season"
    report["scope"] = "Historical condition scenarios; observed race weather is not a forecast."
    for task in tasks:
        artifact, result = train_task(task)
        joblib.dump(artifact, MODELS_DIR / f"{task}.joblib", compress=3)
        report["tasks"][task] = result
        print(f"{task}: selected {result['selected']} on 2015; 2016 test {result['test']}", flush=True)
    METRICS_JSON.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
