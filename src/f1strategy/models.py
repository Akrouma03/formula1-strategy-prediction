"""Chronological model selection and future-season evaluation.

2014 trains candidates; 2015 selects a candidate; 2014–2015 refits the selected
pipeline; 2016 evaluates it once. Entire events stay together.
"""

from __future__ import annotations

import hashlib
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import scipy
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .data import load_lap_time_data, load_race_data
from .paths import LAP_TIME_DATA, RACE_DATA

RANDOM_STATE = 42
TASKS = ("tyre_strategy", "positioning", "lap_time")
FEATURES = ["positionStart", "circuit_id", "raceCondition"]
TARGETS = {"tyre_strategy": "tyre_strategy", "positioning": "positionFinish", "lap_time": "avg_lap_time"}


def dataset(task: str) -> pd.DataFrame:
    if task not in TASKS:
        raise ValueError(f"Unknown task: {task}")
    df = load_lap_time_data() if task == "lap_time" else load_race_data()
    df = df[df["positionStart"].notna() & df["raceCondition"].isin(["Dry", "Mix", "Wet"])]
    if task == "tyre_strategy":
        df = df[df["tyre_strategy"].ne("")]
    else:
        df = df[df[TARGETS[task]].notna()]
    return df.reset_index(drop=True)


def split_seasons(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    parts = tuple(df[df["Year"] == year].copy() for year in (2014, 2015, 2016))
    if any(part.empty for part in parts):
        raise ValueError("Training needs nonempty 2014, 2015 and 2016 seasons.")
    groups = [set(part.event_id) for part in parts]
    if any(groups[a] & groups[b] for a, b in [(0, 1), (0, 2), (1, 2)]):
        raise ValueError("An event appears in more than one split.")
    return parts


def build_pipeline(task: str, model: str) -> Pipeline:
    classifier = task == "tyre_strategy"
    if model == "random_forest":
        cls = RandomForestClassifier if classifier else RandomForestRegressor
        estimator = cls(n_estimators=160, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=1)
    elif model == "gradient_boosting":
        cls = GradientBoostingClassifier if classifier else GradientBoostingRegressor
        estimator = cls(n_estimators=80, max_depth=2, random_state=RANDOM_STATE)
    else:
        raise ValueError(f"Unknown model: {model}")
    preprocessor = ColumnTransformer(
        [
            ("grid", "passthrough", ["positionStart"]),
            (
                "categories",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["circuit_id", "raceCondition"],
            ),
        ]
    )
    return Pipeline([("preprocessor", preprocessor), ("model", estimator)])


def baseline_predict(train: pd.DataFrame, test: pd.DataFrame, task: str) -> np.ndarray:
    """Training-only circuit/condition lookup, or grid for finishing position."""
    if task == "positioning":
        return test.positionStart.to_numpy()
    target = TARGETS[task]
    agg = (lambda s: s.mode().iloc[0]) if task == "tyre_strategy" else "median"
    lookup = train.groupby(["circuit_id", "raceCondition"])[target].agg(agg)
    circuit = train.groupby("circuit_id")[target].agg(agg)
    fallback = train[target].mode().iloc[0] if task == "tyre_strategy" else train[target].median()
    return np.array(
        [
            lookup.get((row.circuit_id, row.raceCondition), circuit.get(row.circuit_id, fallback))
            for row in test.itertuples()
        ]
    )


def scores(y: pd.Series, prediction: np.ndarray, task: str) -> dict[str, float]:
    if task == "tyre_strategy":
        return {
            "accuracy": float(accuracy_score(y, prediction)),
            "macro_f1": float(f1_score(y, prediction, average="macro", zero_division=0)),
            "weighted_f1": float(f1_score(y, prediction, average="weighted", zero_division=0)),
        }
    return {"mae": float(mean_absolute_error(y, prediction)), "r2": float(r2_score(y, prediction))}


def event_interval(df: pd.DataFrame, values: np.ndarray) -> list[float]:
    """Bootstrap event means: resample races rather than dependent driver rows."""
    means = pd.Series(values, index=df.event_id).groupby(level=0).mean().to_numpy()
    rng = np.random.default_rng(RANDOM_STATE)
    samples = rng.choice(means, size=(1000, len(means)), replace=True).mean(axis=1)
    return [float(v) for v in np.quantile(samples, [0.025, 0.975])]


def select_candidate(validation: dict[str, dict[str, float]], task: str) -> str:
    metric = "accuracy" if task == "tyre_strategy" else "mae"
    return sorted(
        validation,
        key=lambda name: (
            -validation[name][metric] if task == "tyre_strategy" else validation[name][metric],
            name,
        ),
    )[0]


def train_task(task: str) -> tuple[dict[str, Any], dict[str, Any]]:
    df = dataset(task)
    train, valid, test = split_seasons(df)
    target = TARGETS[task]
    validation = {}
    for name in ("random_forest", "gradient_boosting"):
        model = build_pipeline(task, name).fit(train[FEATURES], train[target])
        validation[name] = scores(valid[target], model.predict(valid[FEATURES]), task)
    validation["baseline"] = scores(valid[target], baseline_predict(train, valid, task), task)
    # A heuristic is a legitimate winner. Test scores never influence this choice.
    selected = select_candidate(validation, task)
    development = pd.concat([train, valid], ignore_index=True)
    model = (
        None
        if selected == "baseline"
        else build_pipeline(task, selected).fit(development[FEATURES], development[target])
    )
    prediction = baseline_predict(development, test, task) if model is None else model.predict(test[FEATURES])
    baseline = baseline_predict(development, test, task)
    metrics = scores(test[target], prediction, task)
    errors = (
        (prediction == test[target].to_numpy()).astype(float)
        if task == "tyre_strategy"
        else np.abs(prediction - test[target].to_numpy())
    )
    per_event = []
    candidates_test = {"baseline": scores(test[target], baseline, task)}
    for name in ("random_forest", "gradient_boosting"):
        candidate = (
            model
            if selected == name
            else build_pipeline(task, name).fit(development[FEATURES], development[target])
        )
        candidates_test[name] = scores(test[target], candidate.predict(test[FEATURES]), task)
    for event, indices in test.groupby("event_id").groups.items():
        loc = test.index.get_indexer(indices)
        per_event.append(
            {"event_id": event, "rows": len(loc), **scores(test.loc[indices, target], prediction[loc], task)}
        )
    report = {
        "selected": selected,
        "selection_on": "2015 validation only",
        "features": FEATURES,
        "target": target,
        "rows": {"train_2014": len(train), "validation_2015": len(valid), "test_2016": len(test)},
        "events": {
            "train": train.event_id.nunique(),
            "validation": valid.event_id.nunique(),
            "test": test.event_id.nunique(),
        },
        "validation": validation,
        "candidates_test": candidates_test,
        "test": metrics,
        "baseline_test": scores(test[target], baseline, task),
        "event_mean_metric": float(pd.Series(errors, index=test.event_id).groupby(level=0).mean().mean()),
        "event_bootstrap_95_interval": event_interval(test, errors),
        "per_event": per_event,
    }
    if task == "tyre_strategy":
        report["unseen_test_labels"] = sorted(set(test[target]) - set(development[target]))
        report["unseen_test_label_rows"] = int((~test[target].isin(development[target])).sum())
    artifact = {
        "schema_version": 2,
        "task": task,
        "selected": selected,
        "pipeline": model,
        "baseline_data": development[FEATURES + [target]].copy(),
        "report": report,
        "metadata": metadata(),
        "circuits": sorted(development.circuit_id.unique()),
    }
    return artifact, report


def metadata() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "scikit_learn": sklearn.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "joblib": joblib.__version__,
        "seed": RANDOM_STATE,
        "training_seasons": [2014, 2015],
        "evaluation_season": 2016,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (RACE_DATA, LAP_TIME_DATA)
        },
        "pipeline_sha256": {
            name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("data.py", "identities.py", "models.py")
        },
    }


def predict(artifact: dict[str, Any], features: pd.DataFrame) -> np.ndarray:
    if artifact.get("schema_version") != 2:
        raise ValueError("Model format changed. Rebuild with python scripts/train.py.")
    if artifact["metadata"]["scikit_learn"] != sklearn.__version__:
        raise ValueError("Model dependency version differs. Rebuild in this environment.")
    current = metadata()
    if any(artifact["metadata"].get(key) != current[key] for key in ("source_sha256", "pipeline_sha256")):
        raise ValueError("Model data or pipeline changed. Rebuild with python scripts/train.py.")
    return (
        baseline_predict(artifact["baseline_data"], features, artifact["task"])
        if artifact["pipeline"] is None
        else artifact["pipeline"].predict(features[FEATURES])
    )
