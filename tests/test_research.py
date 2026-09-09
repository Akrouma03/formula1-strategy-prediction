"""Reconciliation, conservative stint alignment and private-catalogue boundaries."""

import json
import numpy as np
import pandas as pd
import pytest

from f1strategy.data import STINT_COMPOUNDS, lap_time_data_with_audit, load_race_data
from f1strategy.identities import driver_id
from f1strategy.models import metadata, predict
from f1strategy.paths import ROOT, RACE_DATA
from f1strategy.stints import evaluate_drift, extract_stints, predict_drift
from test_scripts import script


@pytest.mark.parametrize(
    "name,identity",
    [
        ("Filipe Nasr", "nasr"),
        ("Felipe Nasr", "nasr"),
        ("Kevin Magnessun", "magnussen"),
        ("kevin_magnussen", "magnussen"),
        ("Pastor Maldonando", "maldonado"),
        ("ericssson", "ericsson"),
        ("Carlos Sainz Jnr", "sainz"),
        ("Kimi Räikkönen", "raikkonen"),
    ],
)
def test_explicit_driver_aliases(name, identity):
    assert driver_id(name) == identity


def test_no_fuzzy_driver_guessing():
    assert driver_id("hamilto") == "unmapped:hamilto"
    assert driver_id("hamilto") != driver_id("hamilton")
    with pytest.raises(ValueError):
        driver_id(" ")


def test_real_archive_reconciles_every_eligible_record():
    rows, audit = lap_time_data_with_audit()
    assert len(rows) == audit["matched_driver_races"] == 1065
    assert audit["eligible_driver_races"] == len(rows) + len(audit["unmatched_records"])
    assert audit["recovered_by_aliases"] == 88
    assert audit["unmatched_records"] == [
        dict(event_id="2015:bahrain", driver_id="button", source_driver="button", laps=49)
    ]
    assert audit["unmapped_names"] == []
    races = load_race_data()
    original = pd.read_csv(RACE_DATA, encoding="latin1")
    assert sorted(races.DriverId) == sorted(original.DriverId.str.strip())
    assert not rows.duplicated(["event_id", "driver_id"]).any()


def fixture_stints():
    row = dict(
        event_id="2014:bahrain", Year=2014, circuit_id="bahrain", driver_id="button", raceCondition="Dry"
    )
    row.update(dict.fromkeys(STINT_COMPOUNDS, ""))
    row.update(Stint_Compound_1="Soft", Stint_Compound_2="Medium", Stint_Laps_1=10, Stint_Laps_2=10)
    laps = pd.DataFrame({"Lap": range(1, 21)})
    laps["event_id"], laps["driver_id"] = "2014:bahrain", "button"
    laps["time_seconds"] = [90 + 0.2 * (i % 10) for i in range(20)]
    laps["is_pit_lap"] = laps.Lap.eq(10)
    laps["near_pit"] = laps.Lap.isin([9, 10, 11])
    return pd.DataFrame([row]), laps


def test_stint_age_resets_and_boundaries_exclude_adjacent_laps():
    races, laps = fixture_stints()
    frame, audit = extract_stints(races, laps)
    assert frame.stint.tolist() == [1, 2]
    assert frame.laps.tolist() == [7, 9]
    np.testing.assert_allclose(frame.slope, 0.2)
    assert audit["aligned_driver_races"] == 1
    assert audit["excluded_driver_races"] == {}


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"Stint_Laps_1": 9}, "pit_boundaries_disagree"),
        ({"Stint_Laps_2": 11}, "recorded_distance_disagrees"),
        ({"Stint_Laps_2": None}, "invalid_stint_definition"),
        ({"Stint_Compound_1": "x"}, "invalid_stint_definition"),
        ({"raceCondition": "Wet"}, "not_recorded_dry"),
    ],
)
def test_ambiguous_stints_are_excluded_not_forced(change, reason):
    races, laps = fixture_stints()
    for key, value in change.items():
        races[key] = value
    frame, audit = extract_stints(races, laps)
    assert frame.empty
    assert audit["excluded_driver_races"] == {reason: 1}


def test_short_stints_never_produce_estimates():
    races, laps = fixture_stints()
    laps.loc[laps.Lap < 16, "time_seconds"] = np.nan
    frame, audit = extract_stints(races, laps)
    assert frame.empty and audit["short_stints_excluded"] == 2


def test_drift_selection_and_lookup_do_not_use_test_targets():
    frame = pd.DataFrame(dict(Year=[2014, 2015, 2016], compound=["Soft"] * 3, slope=[0.1, 0.15, 0.2]))
    first = evaluate_drift(frame)
    frame.loc[frame.Year == 2016, "slope"] = 999
    second = evaluate_drift(frame)
    assert first["selected"] == second["selected"]
    assert first["validation"] == second["validation"]
    assert first["test"] != second["test"]
    assert predict_drift(frame[frame.Year < 2016], pd.DataFrame({"compound": ["Hard"]}), "compound_median")[
        0
    ] == pytest.approx(0.125)


def test_catalogue_only_reads_allowlisted_data_and_keeps_sources_unchanged(tmp_path):
    catalogue = script("catalogue_sources")
    source = tmp_path / "source"
    source.mkdir()
    csv = source / "all_race_data.csv"
    csv.write_text("Year,Lap\n2016,1\n")
    original = csv.read_bytes()
    (source / "private-report.pdf").write_text("Never copy this")
    (source / "unlisted.csv").write_text("private,content\n")
    result = catalogue.build_catalogue(source)
    assert result["summary"]["csv_files"] == 1
    encoded = json.dumps(result)
    assert "Never copy" not in encoded and "unlisted" not in encoded and str(tmp_path) not in encoded
    assert csv.read_bytes() == original


def test_richer_data_without_seasons_cannot_be_marked_ready():
    result = script("catalogue_sources").readiness(
        {"columns": ["Race", "Driver", "Lap"], "exact_duplicate_rows": 5}
    )
    assert result["status"] == "not_integrated"
    assert "Year" in result["issues"][0]
    assert "duplicate" in result["issues"][1]


def test_canonical_catalogue_hashes_match_published_snapshots():
    catalogue = json.loads((ROOT / "data" / "catalogue.json").read_text(encoding="utf-8"))
    for file in catalogue["files"]:
        if "public_copy" in file:
            assert script("catalogue_sources").sha(ROOT / file["public_copy"]) == file["sha256"]
    assert catalogue["summary"] == {"csv_files": 16, "distinct_csv_contents": 10, "workbooks": 5}


def test_pipeline_changes_invalidate_saved_artifacts():
    old = metadata()
    old["pipeline_sha256"] = {}
    with pytest.raises(ValueError, match="pipeline changed"):
        predict({"schema_version": 2, "metadata": old}, pd.DataFrame())
