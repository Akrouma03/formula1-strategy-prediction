"""Tests for the shared data layer.

Several of these lock in fixes for real bugs found in the original coursework
scripts, so a regression would fail loudly rather than silently degrade a model.
"""
import numpy as np
import pandas as pd
import pytest

from f1strategy.data import (
    lap_time_to_seconds,
    load_lap_time_data,
    load_race_data,
    seconds_to_lap_time,
)


@pytest.fixture(scope="module")
def race_df():
    return load_race_data()


@pytest.fixture(scope="module")
def lap_df():
    return load_lap_time_data()


class TestLapTimeConversion:
    @pytest.mark.parametrize(
        "text,expected",
        [("1:38.6", 98.6), ("01:38.6", 98.6), ("2:05.520", 125.52), ("95.5", 95.5)],
    )
    def test_parses_lap_times(self, text, expected):
        assert lap_time_to_seconds(text) == pytest.approx(expected)

    def test_missing_becomes_nan(self):
        assert np.isnan(lap_time_to_seconds(None))
        assert np.isnan(lap_time_to_seconds("-"))

    def test_formats_with_real_milliseconds(self):
        # The original truncated to int before computing milliseconds, so this
        # always rendered as ".000".
        assert seconds_to_lap_time(98.6) == "1:38.600"
        assert seconds_to_lap_time(125.52) == "2:05.520"

    def test_round_trip(self):
        for text in ("1:38.600", "2:05.520", "1:10.807"):
            assert seconds_to_lap_time(lap_time_to_seconds(text)) == text

    def test_millisecond_rounding_carries(self):
        assert seconds_to_lap_time(59.9996) == "0:60.000" or seconds_to_lap_time(
            59.9996
        ) == "1:00.000"


class TestRaceData:
    def test_uses_the_real_finish_column(self, race_df):
        """The original fabricated finishing position with np.random.randint."""
        assert "positionFinish" in race_df
        assert race_df["positionFinish"].notna().all()
        assert race_df["positionFinish"].between(1, 25).all()

    def test_no_fabricated_column(self, race_df):
        assert "finalPosition" not in race_df.columns

    def test_race_condition_is_a_real_feature(self, race_df):
        assert set(race_df["raceCondition"].unique()) <= {"Dry", "Mix", "Wet"}
        assert race_df["raceCondition"].nunique() > 1

    def test_strategy_labels_are_non_empty(self, race_df):
        assert (race_df["tyre_strategy"].str.len() > 0).all()

    def test_strategy_cardinality_is_learnable(self, race_df):
        # The full stint sequence gave 163 classes over ~1000 rows.
        assert race_df["tyre_strategy"].nunique() < 40

    def test_positions_are_numeric(self, race_df):
        for col in ("positionStart", "positionFinish"):
            assert pd.api.types.is_numeric_dtype(race_df[col])


class TestLapTimeData:
    def test_average_lap_times_are_physically_plausible(self, lap_df):
        """F1 laps run roughly 65-210s including wet and safety-car races."""
        assert lap_df["avg_lap_time"].between(60, 220).all()

    def test_excludes_short_stints(self, lap_df):
        assert (lap_df["laps"] >= 5).all()

    def test_one_row_per_driver_race(self, lap_df):
        assert not lap_df.duplicated(["Year", "raceName", "DriverId"]).any()
