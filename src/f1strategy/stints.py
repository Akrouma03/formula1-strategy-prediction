"""Retrospective stint-pace drift, not an estimate of causal tyre degradation."""

from collections import Counter

import numpy as np
import pandas as pd
from scipy.stats import theilslopes

from .data import STINT_COMPOUNDS, load_laps, load_race_data

DRY_COMPOUNDS = {"Ultra soft", "Super soft", "Super Soft", "Soft", "Medium", "Hard"}
COLUMNS = ["event_id", "Year", "circuit_id", "driver_id", "stint", "compound", "laps", "slope"]


def extract_stints(races: pd.DataFrame, laps: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Require exact pit-boundary agreement; exclude ambiguous driver-races.

    Age zero is the first lap of each recorded stint. At least six timed laps
    must remain after excluding pit neighbours and the race's opening lap.
    Theil–Sen uses the median pairwise slope; no outcome-tuned outlier threshold.
    """
    groups = {key: group for key, group in laps.groupby(["event_id", "driver_id"])}
    exclusions = Counter()
    records = []
    aligned = 0
    short = 0
    for row in races.itertuples():
        group = groups.get((row.event_id, row.driver_id))
        if group is None:
            exclusions["no_laps"] += 1
            continue
        if row.raceCondition != "Dry":
            exclusions["not_recorded_dry"] += 1
            continue
        compounds = [getattr(row, col) for col in STINT_COMPOUNDS]
        count = sum(bool(c) for c in compounds)
        lengths = pd.to_numeric(
            pd.Series([getattr(row, f"Stint_Laps_{i}", None) for i in range(1, count + 1)]),
            errors="coerce",
        ).to_numpy(dtype=float)
        if (
            not count
            or not all(compounds[:count])
            or any(compounds[count:])
            or not set(compounds[:count]) <= DRY_COMPOUNDS
            or not np.isfinite(lengths).all()
            or (lengths <= 0).any()
            or (lengths % 1 != 0).any()
        ):
            exclusions["invalid_stint_definition"] += 1
            continue
        boundaries = np.cumsum(lengths).astype(int)
        pits = group.loc[group.is_pit_lap, "Lap"].to_numpy()
        if not np.array_equal(boundaries[:-1], pits):
            exclusions["pit_boundaries_disagree"] += 1
            continue
        if boundaries[-1] != group.Lap.max():
            exclusions["recorded_distance_disagrees"] += 1
            continue
        aligned += 1
        start = 0
        for index, end in enumerate(boundaries):
            usable = group[
                (group.Lap > start)
                & (group.Lap <= end)
                & (group.Lap > 1)
                & ~group.near_pit
                & group.time_seconds.notna()
            ]
            if len(usable) < 6:
                short += 1
            else:
                age = usable.Lap.to_numpy() - start - 1
                slope = float(theilslopes(usable.time_seconds.to_numpy(), age).slope)
                records.append(
                    dict(
                        event_id=row.event_id,
                        Year=int(row.Year),
                        circuit_id=row.circuit_id,
                        driver_id=row.driver_id,
                        stint=index + 1,
                        compound=compounds[index].replace("Super Soft", "Super soft"),
                        laps=len(usable),
                        slope=slope,
                    )
                )
            start = end
    return pd.DataFrame(records, columns=COLUMNS), {
        "race_records": len(races),
        "aligned_driver_races": aligned,
        "excluded_driver_races": dict(sorted(exclusions.items())),
        "short_stints_excluded": short,
        "analysed_stints": len(records),
    }


def summaries(frame: pd.DataFrame) -> list[dict]:
    return [
        dict(
            compound=compound,
            stints=len(rows),
            events=rows.event_id.nunique(),
            median=float(rows.slope.median()),
            q25=float(rows.slope.quantile(0.25)),
            q75=float(rows.slope.quantile(0.75)),
        )
        for compound, rows in frame.groupby("compound")
    ]


def predict_drift(train: pd.DataFrame, target: pd.DataFrame, method: str) -> np.ndarray:
    if method == "zero_drift":
        return np.zeros(len(target))
    if method != "compound_median" or train.empty:
        raise ValueError("Compound drift needs nonempty training stints and a known method.")
    medians = train.groupby("compound").slope.median()
    return target.compound.map(medians).fillna(train.slope.median()).to_numpy()


def evaluate_drift(frame: pd.DataFrame) -> dict:
    parts = [frame[frame.Year == year] for year in (2014, 2015, 2016)]
    if any(part.empty for part in parts):
        return {"status": "insufficient_seasons"}
    train, valid, test = parts
    methods = ("zero_drift", "compound_median")
    validation = {
        name: float(np.abs(predict_drift(train, valid, name) - valid.slope).mean()) for name in methods
    }
    selected = min(methods, key=lambda name: (validation[name], name))
    development = pd.concat([train, valid])
    results = {
        name: float(np.abs(predict_drift(development, test, name) - test.slope).mean()) for name in methods
    }
    return {
        "status": "evaluated",
        "metric": "MAE of stint slope, seconds/lap of tyre age",
        "selection_on": "2015 only",
        "selected": selected,
        "validation": validation,
        "test": results,
        "rows": dict(zip(["train_2014", "validation_2015", "test_2016"], map(len, parts))),
    }


def build_study() -> dict:
    frame, audit = extract_stints(load_race_data(), load_laps())
    return {
        "audit": audit,
        "evaluation": evaluate_drift(frame),
        "development": summaries(frame[frame.Year < 2016]),
        "test": summaries(frame[frame.Year == 2016]),
        "events": {event: summaries(rows) for event, rows in frame.groupby("event_id")},
        "decision": "Descriptive pace drift only; simulator wear coefficients remain illustrative.",
        "limitations": [
            "Exact recorded pit boundaries and distance required; this selects a cleaner subset, not all drivers.",
            "Six usable laps minimum; exclude first race lap, pit laps and physical neighbours.",
            "Median pairwise slope limits outlier influence but does not identify safety-car laps.",
            "Fuel burn, traffic, car/driver pace and track status confound tyre wear; no causal calibration.",
            "Compound names are not a fixed physical specification across seasons or events.",
            "Quartiles show spread across stints, not confidence intervals. Archive inspected retrospectively.",
        ],
    }
