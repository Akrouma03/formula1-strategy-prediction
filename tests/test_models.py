"""Tests that the models learn something and respond to their inputs.

The headline test is ``test_predictions_respond_to_conditions``: in the original
scripts every input returned the same recommendation because the loaded model
was never actually used for the prediction.
"""
import pandas as pd
import pytest

from f1strategy.data import load_race_data
from f1strategy.models import (
    lap_time_dataset,
    positioning_dataset,
    train_lap_time,
    train_positioning,
    train_tyre_strategy,
    tyre_strategy_dataset,
)


class TestDatasets:
    def test_no_target_leakage_into_features(self):
        X_tyre, y_tyre = tyre_strategy_dataset()
        assert "tyre_strategy" not in X_tyre.columns

        X_pos, y_pos = positioning_dataset()
        assert "positionFinish" not in X_pos.columns

        X_lap, y_lap = lap_time_dataset()
        assert "avg_lap_time" not in X_lap.columns

    def test_features_and_targets_align(self):
        for loader in (tyre_strategy_dataset, positioning_dataset, lap_time_dataset):
            X, y = loader()
            assert len(X) == len(y)
            assert len(X) > 100


class TestTraining:
    """Each model must beat the obvious heuristic to justify existing."""

    def test_tyre_strategy_beats_most_frequent(self):
        results = train_tyre_strategy()
        best = max(results, key=lambda r: r.metrics["accuracy"])
        assert best.metrics["accuracy"] > best.baseline["accuracy"]

    def test_positioning_beats_finishing_where_you_started(self):
        results = train_positioning()
        best = min(results, key=lambda r: r.metrics["mae"])
        assert best.metrics["mae"] < best.baseline["mae"]

    def test_lap_time_beats_predicting_the_mean(self):
        results = train_lap_time()
        best = min(results, key=lambda r: r.metrics["mae"])
        assert best.metrics["mae"] < best.baseline["mae"]
        assert best.metrics["r2"] > 0.5


class TestPredictionBehaviour:
    @pytest.fixture(scope="class")
    @classmethod
    def tyre_model(cls):
        results = train_tyre_strategy()
        return max(results, key=lambda r: r.metrics["accuracy"]).estimator

    def test_predictions_respond_to_conditions(self, tyre_model):
        """A wet race must not get the same recommendation as a dry one."""
        def predict(condition):
            row = pd.DataFrame([{
                "positionStart": 5.0,
                "raceName": "Monaco Grand Prix",
                "raceCondition": condition,
                "Year": "2016",
            }])
            return tyre_model.predict(row)[0]

        assert predict("Dry") != predict("Wet")

    def test_wet_race_recommends_a_wet_compound(self, tyre_model):
        row = pd.DataFrame([{
            "positionStart": 1.0,
            "raceName": "Monaco Grand Prix",
            "raceCondition": "Wet",
            "Year": "2016",
        }])
        recommendation = tyre_model.predict(row)[0]
        assert any(c in recommendation for c in ("Wet", "Intermediate"))

    def test_predictions_vary_across_races(self, tyre_model):
        """The circuit must influence the recommendation.

        Checked across the whole calendar rather than a few races: many circuits
        legitimately share the same dominant opening in a given season, so a
        three-race sample can agree by chance.
        """
        races = sorted(load_race_data()["raceName"].unique())
        rows = pd.DataFrame([
            {"positionStart": 5.0, "raceName": race, "raceCondition": "Dry", "Year": "2016"}
            for race in races
        ])
        assert len(set(tyre_model.predict(rows))) > 2
