"""Train every model, save the best per task, and write reports/metrics.json.

    python scripts/train.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from f1strategy.models import TRAINERS  # noqa: E402
from f1strategy.paths import METRICS_JSON, MODELS_DIR, ensure_dirs  # noqa: E402

# Which metric decides the best model for each task, and whether higher is better.
SELECTION = {
    "tyre_strategy": ("accuracy", True),
    "positioning": ("mae", False),
    "lap_time": ("mae", False),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task",
        choices=sorted(TRAINERS),
        action="append",
        help="Train only this task (repeatable). Defaults to all.",
    )
    args = parser.parse_args()
    tasks = args.task or sorted(TRAINERS)

    ensure_dirs()
    report: dict[str, dict] = {}

    for task in tasks:
        print(f"\n=== {task} ===")
        results = TRAINERS[task]()
        metric, higher_is_better = SELECTION[task]

        best = max(
            results,
            key=lambda r: r.metrics[metric] * (1 if higher_is_better else -1),
        )

        report[task] = {
            "n_train": best.n_train,
            "n_test": best.n_test,
            "baseline": best.baseline,
            "selected": best.model,
            "selected_on": metric,
            "models": {r.model: r.metrics for r in results},
        }

        for r in results:
            marker = "*" if r.model == best.model else " "
            scores = "  ".join(f"{k}={v:.3f}" for k, v in r.metrics.items())
            print(f" {marker} {r.model:<18} {scores}")
        baseline_scores = "  ".join(f"{k}={v:.3f}" for k, v in best.baseline.items())
        print(f"   {'baseline':<18} {baseline_scores}")

        out = MODELS_DIR / f"{task}.joblib"
        joblib.dump(best.estimator, out, compress=3)
        size_mb = out.stat().st_size / 1e6
        print(f"   saved {out.relative_to(out.parents[1])} ({size_mb:.1f} MB)")

    if len(tasks) == len(TRAINERS):
        METRICS_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {METRICS_JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
