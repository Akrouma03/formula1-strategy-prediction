"""Regression checks for identities, missing observations and pit filtering."""

import numpy as np
import pandas as pd
import pytest

from f1strategy.data import (
    STINT_COMPOUNDS,
    circuit_id,
    lap_time_to_seconds,
    load_lap_time_data,
    load_laps,
    load_race_data,
    seconds_to_lap_time,
)


def race_row(**changes):
    row = dict(
        raceName="Bahrain",
        Year=2016,
        DriverId="driver",
        positionStart="3rd",
        positionFinish="Ret",
        raceCondition="Dry",
    )
    row.update(dict.fromkeys(STINT_COMPOUNDS, ""))
    row.update(Stint_Compound_1="Soft", Stint_Compound_2="Medium")
    return row | changes


def write_csv(tmp_path, rows, name="race.csv"):
    path = tmp_path / name
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


@pytest.mark.parametrize("name", ["Australia", "Australian Grand Prix", " AUSTRALIAN  grand prix "])
def test_aliases_share_identity(name):
    assert circuit_id(name) == "australia"


@pytest.mark.parametrize("name", ["", None, "B", "Silverstone", "not a race"])
def test_unknown_names_do_not_silently_match(name):
    with pytest.raises(ValueError, match="Unknown circuit"):
        circuit_id(name)


@pytest.mark.parametrize("text,seconds", [("1:38.6", 98.6), ("01:38.6", 98.6), ("95.5", 95.5)])
def test_lap_parser(text, seconds):
    assert lap_time_to_seconds(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", [None, "-", "NaN", "inf", "-10", "0", "1:60", "1:02:03"])
def test_bad_lap_times_are_missing(text):
    assert np.isnan(lap_time_to_seconds(text))


def test_rounding_carries_to_next_minute():
    assert seconds_to_lap_time(59.9996) == "1:00.000"
    assert seconds_to_lap_time(98.6) == "1:38.600"


@pytest.mark.parametrize("seconds", [-1, float("nan"), float("inf")])
def test_bad_format_input(seconds):
    with pytest.raises(ValueError):
        seconds_to_lap_time(seconds)


def test_retiree_remains_and_stops_are_not_stints(tmp_path):
    frame = load_race_data(write_csv(tmp_path, [race_row(**dict.fromkeys(STINT_COMPOUNDS, "Soft"))]))
    row = frame.iloc[0]
    assert pd.isna(row.positionFinish)
    assert row.positionStart == 3
    assert row.tyre_strategy == "Soft - Soft"
    assert row.n_stints == 6
    assert row.n_stops == 5


def test_missing_opening_stint_is_not_filled_from_later_stints(tmp_path):
    row = race_row(Stint_Compound_1="", Stint_Compound_3="Hard", raceCondition=None)
    frame = load_race_data(write_csv(tmp_path, [row]))
    assert frame.iloc[0].tyre_strategy == ""
    assert frame.iloc[0].raceCondition == "Unknown"


def test_duplicate_alias_events_rejected(tmp_path):
    rows = [race_row(raceName="Australia"), race_row(raceName="Australian Grand Prix")]
    with pytest.raises(ValueError, match="duplicate"):
        load_race_data(write_csv(tmp_path, rows))


def test_missing_columns_rejected(tmp_path):
    with pytest.raises(ValueError, match="missing columns"):
        load_race_data(write_csv(tmp_path, [{"raceName": "Bahrain"}]))


def lap_row(lap, driver="driver", pit=None, time="1:30"):
    return dict(raceName="Bahrain", Year=2016, DriverId=driver, Lap=lap, Pitstop=pit, Time=time)


def test_pit_filter_sorts_and_respects_gaps_and_driver_boundaries(tmp_path):
    rows = [
        lap_row(10),
        lap_row(5),
        lap_row(3, pit="P"),
        lap_row(2),
        lap_row(1, driver="other"),
        lap_row(4),
        lap_row(1),
    ]
    frame = load_laps(write_csv(tmp_path, rows, "laps.csv"))
    filtered = set(zip(frame.loc[frame.near_pit, "DriverId"], frame.loc[frame.near_pit, "Lap"]))
    assert filtered == {("driver", 2), ("driver", 3), ("driver", 4)}
    # A pit on lap 3 with missing laps 2/4 must not remove laps 1/5.
    frame = load_laps(write_csv(tmp_path, [lap_row(1), lap_row(3, pit="P"), lap_row(5)], "gaps.csv"))
    assert frame.loc[frame.near_pit, "Lap"].tolist() == [3]


def test_duplicate_lap_rejected(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_laps(write_csv(tmp_path, [lap_row(1), lap_row(1)]))


def test_pace_joins_actual_grid_and_requires_five_usable_laps(tmp_path):
    race_path = write_csv(tmp_path, [race_row(positionFinish="19th"), race_row(DriverId="short")])
    laps_path = write_csv(
        tmp_path,
        [lap_row(i) for i in range(1, 6)] + [lap_row(i, driver="short") for i in range(1, 5)],
        "laps.csv",
    )
    frame = load_lap_time_data(laps_path, race_path)
    assert frame.DriverId.tolist() == ["driver"]
    assert frame.iloc[0].positionStart == 3
    assert frame.iloc[0].avg_lap_time == 90
    assert "positionFinish" not in frame.columns
