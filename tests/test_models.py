"""Test evaluation boundaries and useful baselines, not flattering scores."""

import joblib
import numpy as np
import pandas as pd
import pytest

from f1strategy import models
from f1strategy.models import FEATURES, TASKS, TARGETS


@pytest.fixture(scope="module")
def datasets():
    return {task: models.dataset(task) for task in TASKS}


@pytest.mark.parametrize("task", TASKS)
def test_features_are_pre_race_scenario_inputs(datasets, task):
    frame = datasets[task]
    assert FEATURES == ["positionStart", "circuit_id", "raceCondition"]
    assert frame[FEATURES + [TARGETS[task]]].notna().all().all()
    assert not set(FEATURES) & set(TARGETS.values())


@pytest.mark.parametrize("task", TASKS)
def test_whole_events_and_seasons_are_disjoint(datasets, task):
    parts = models.split_seasons(datasets[task])
    for part, year in zip(parts, [2014, 2015, 2016]):
        assert set(part.Year) == {year}
    assert not set(parts[0].event_id) & set(parts[1].event_id)
    assert not set(parts[2].event_id) & set(pd.concat(parts[:2]).event_id)


def test_missing_season_is_an_error(datasets):
    with pytest.raises(ValueError, match="nonempty"):
        models.split_seasons(datasets["positioning"].query("Year < 2016"))


def test_retirees_are_eligible_for_tyres_but_not_finish(datasets):
    assert datasets["tyre_strategy"].positionFinish.isna().any()
    assert datasets["positioning"].positionFinish.notna().all()


def test_baseline_uses_training_only_with_circuit_then_global_fallback():
    train = pd.DataFrame(
        [
            dict(circuit_id="bahrain", raceCondition="Dry", avg_lap_time=90),
            dict(circuit_id="bahrain", raceCondition="Dry", avg_lap_time=100),
            dict(circuit_id="monaco", raceCondition="Wet", avg_lap_time=120),
        ]
    )
    test = pd.DataFrame(
        [
            dict(circuit_id="bahrain", raceCondition="Wet", avg_lap_time=-999),
            dict(circuit_id="unseen", raceCondition="Dry", avg_lap_time=-999),
        ]
    )
    np.testing.assert_equal(models.baseline_predict(train, test, "lap_time"), [95, 100])
    test.avg_lap_time = 9999
    np.testing.assert_equal(models.baseline_predict(train, test, "lap_time"), [95, 100])


def test_validation_can_select_baseline_and_ties_are_deterministic():
    scores = {"random_forest": {"mae": 5}, "gradient_boosting": {"mae": 4}, "baseline": {"mae": 3}}
    assert models.select_candidate(scores, "lap_time") == "baseline"
    scores["gradient_boosting"]["mae"] = 3
    assert models.select_candidate(scores, "lap_time") == "baseline"


def test_event_bootstrap_weights_races_not_driver_counts():
    frame = pd.DataFrame({"event_id": ["large"] * 20 + ["small"]})
    values = np.array([0.0] * 20 + [1.0])
    interval = models.event_interval(frame, values)
    assert interval == [0, 1]
    assert models.event_interval(frame, values) == interval


@pytest.mark.parametrize("task", TASKS)
def test_training_artifact_roundtrip_and_score_reproduction(task, datasets, tmp_path):
    artifact, report = models.train_task(task)
    _, _, test = models.split_seasons(datasets[task])
    assert report["selected"] == models.select_candidate(report["validation"], task)
    assert set(report["candidates_test"]) == {"baseline", "random_forest", "gradient_boosting"}
    assert report["candidates_test"][report["selected"]] == report["test"]
    assert artifact["metadata"]["training_seasons"] == [2014, 2015]
    assert report["rows"]["test_2016"] == len(test)
    path = tmp_path / "model.joblib"
    joblib.dump(artifact, path)
    result = models.predict(joblib.load(path), test[FEATURES])
    assert report["test"] == models.scores(test[TARGETS[task]], result, task)
    assert len(report["per_event"]) == test.event_id.nunique()
    if task == "tyre_strategy":
        development = pd.concat(models.split_seasons(datasets[task])[:2])
        assert report["unseen_test_labels"] == sorted(
            set(test.tyre_strategy) - set(development.tyre_strategy)
        )


def test_artifact_rejects_old_schema_and_incompatible_versions():
    with pytest.raises(ValueError, match="format changed"):
        models.predict({}, pd.DataFrame())
    with pytest.raises(ValueError, match="version differs"):
        models.predict({"schema_version": 2, "metadata": {"scikit_learn": "old"}}, pd.DataFrame())


def test_test_targets_cannot_change_selected_method(monkeypatch, datasets):
    # A real training run, then corrupt ONLY final-season labels. Choice and
    # fitted predictions must stay fixed while final error changes.
    frame = datasets["positioning"].copy()
    monkeypatch.setattr(models, "dataset", lambda task: frame)
    first, _ = models.train_task("positioning")
    frame.loc[frame.Year == 2016, "positionFinish"] += 100
    second, _ = models.train_task("positioning")
    assert first["selected"] == second["selected"]
    assert first["report"]["validation"] == second["report"]["validation"]
    np.testing.assert_equal(models.predict(first, frame[FEATURES]), models.predict(second, frame[FEATURES]))
    assert first["report"]["test"]["mae"] != second["report"]["test"]["mae"]
