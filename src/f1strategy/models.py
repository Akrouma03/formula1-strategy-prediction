"""Model definitions and training for the three prediction tasks.

Each task is a scikit-learn ``Pipeline`` so that preprocessing travels with the
estimator. That means a saved model cannot be fed differently-shaped features
than it was trained on, and prediction needs no separate preprocessing code.

Every task is evaluated against a baseline, because on a dataset this small
(~1000 rows, three seasons) a model that cannot beat the obvious heuristic is
not worth shipping. The baselines are reported in ``reports/metrics.json``
alongside the model scores.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import load_lap_time_data, load_race_data

RANDOM_STATE = 42
TEST_SIZE = 0.2


@dataclass
class TaskResult:
    """Scores for one trained model, next to its baseline."""

    task: str
    model: str
    metrics: dict[str, float]
    baseline: dict[str, float]
    n_train: int
    n_test: int
    estimator: Any = field(default=None, repr=False)


def _build_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ]
    )


# --------------------------------------------------------------------------
# Task 1: tyre strategy (classification)
# --------------------------------------------------------------------------

TYRE_NUMERIC = ["positionStart"]
TYRE_CATEGORICAL = ["raceName", "raceCondition", "Year"]


def tyre_strategy_dataset() -> tuple[pd.DataFrame, pd.Series]:
    df = load_race_data()
    X = df[TYRE_NUMERIC + TYRE_CATEGORICAL].copy()
    X["Year"] = X["Year"].astype(str)
    return X, df["tyre_strategy"]


def train_tyre_strategy() -> list[TaskResult]:
    X, y = tyre_strategy_dataset()
    # Rare strategies cannot be stratified or learned; fold them into "Other"
    # so the split stays valid and the reported accuracy stays honest.
    counts = y.value_counts()
    y = y.where(y.map(counts) >= 10, "Other")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    candidates = {
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=2, random_state=RANDOM_STATE
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=200, max_depth=3, random_state=RANDOM_STATE
        ),
    }

    baseline = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
    baseline_metrics = _classification_metrics(y_test, baseline.predict(X_test))

    results = []
    for name, estimator in candidates.items():
        pipeline = Pipeline(
            [
                ("preprocessor", _build_preprocessor(TYRE_NUMERIC, TYRE_CATEGORICAL)),
                ("classifier", estimator),
            ]
        )
        pipeline.fit(X_train, y_train)
        metrics = _classification_metrics(y_test, pipeline.predict(X_test))
        metrics["cv_accuracy"] = float(
            cross_val_score(pipeline, X, y, cv=5, scoring="accuracy").mean()
        )
        results.append(
            TaskResult(
                task="tyre_strategy",
                model=name,
                metrics=metrics,
                baseline=baseline_metrics,
                n_train=len(X_train),
                n_test=len(X_test),
                estimator=pipeline,
            )
        )
    return results


def _classification_metrics(y_true, y_pred) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }


# --------------------------------------------------------------------------
# Task 2: finishing position (regression)
# --------------------------------------------------------------------------

POSITION_NUMERIC = ["positionStart"]
POSITION_CATEGORICAL = ["raceName", "raceCondition", "Year"]


def positioning_dataset() -> tuple[pd.DataFrame, pd.Series]:
    df = load_race_data()
    X = df[POSITION_NUMERIC + POSITION_CATEGORICAL].copy()
    X["Year"] = X["Year"].astype(str)
    return X, df["positionFinish"]


def train_positioning() -> list[TaskResult]:
    X, y = positioning_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    # The honest baseline here is "you finish where you started".
    grid_baseline = _regression_metrics(y_test, X_test["positionStart"].to_numpy())

    candidates = {
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=2, random_state=RANDOM_STATE
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, random_state=RANDOM_STATE
        ),
    }

    results = []
    for name, estimator in candidates.items():
        pipeline = Pipeline(
            [
                ("preprocessor", _build_preprocessor(POSITION_NUMERIC, POSITION_CATEGORICAL)),
                ("regressor", estimator),
            ]
        )
        pipeline.fit(X_train, y_train)
        metrics = _regression_metrics(y_test, pipeline.predict(X_test))
        results.append(
            TaskResult(
                task="positioning",
                model=name,
                metrics=metrics,
                baseline=grid_baseline,
                n_train=len(X_train),
                n_test=len(X_test),
                estimator=pipeline,
            )
        )
    return results


# --------------------------------------------------------------------------
# Task 3: average lap time (regression)
# --------------------------------------------------------------------------

LAP_NUMERIC = ["finish_position"]
LAP_CATEGORICAL = ["raceName", "Year"]


def lap_time_dataset() -> tuple[pd.DataFrame, pd.Series]:
    df = load_lap_time_data()
    X = df[LAP_NUMERIC + LAP_CATEGORICAL].copy()
    X["Year"] = X["Year"].astype(str)
    return X, df["avg_lap_time"]


def train_lap_time() -> list[TaskResult]:
    X, y = lap_time_dataset()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    baseline = DummyRegressor(strategy="mean").fit(X_train, y_train)
    baseline_metrics = _regression_metrics(y_test, baseline.predict(X_test))

    candidates = {
        "random_forest": RandomForestRegressor(
            n_estimators=300, min_samples_leaf=2, random_state=RANDOM_STATE
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, random_state=RANDOM_STATE
        ),
    }

    results = []
    for name, estimator in candidates.items():
        pipeline = Pipeline(
            [
                ("preprocessor", _build_preprocessor(LAP_NUMERIC, LAP_CATEGORICAL)),
                ("regressor", estimator),
            ]
        )
        pipeline.fit(X_train, y_train)
        metrics = _regression_metrics(y_test, pipeline.predict(X_test))
        results.append(
            TaskResult(
                task="lap_time",
                model=name,
                metrics=metrics,
                baseline=baseline_metrics,
                n_train=len(X_train),
                n_test=len(X_test),
                estimator=pipeline,
            )
        )
    return results


def _regression_metrics(y_true, y_pred) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, np.asarray(y_pred, dtype=float))),
    }


TRAINERS = {
    "tyre_strategy": train_tyre_strategy,
    "positioning": train_positioning,
    "lap_time": train_lap_time,
}
