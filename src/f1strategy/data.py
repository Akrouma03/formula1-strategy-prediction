"""Loading and feature engineering for the three prediction tasks.

Every model in this project draws its features from here, so the training and
prediction paths cannot drift apart -- a class of bug that is easy to introduce
when each script does its own preprocessing.

Three corrections relative to the original coursework scripts are applied here
and are worth calling out, because they change what the models learn:

1. ``positionFinish`` is a real column in ``race_data.csv``. The original
   scripts looked for a differently named ``finalPosition``, did not find it,
   and filled it with ``np.random.randint(1, 20)`` -- then trained on it. The
   real column is used instead.
2. ``raceCondition`` (Dry/Mix/Wet) is real and highly relevant to tyre choice.
   It was present in the data but unused; it is now a feature.
3. Race names are one-hot encoded. The original neural nets tokenised the race
   name and truncated to a single token, which collapsed every race to the
   token for "prix" -- so the race name carried no information at all.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import LAP_TIME_DATA, RACE_DATA

# race_data.csv is Latin-1: it carries circuit addresses with accented characters.
RACE_DATA_ENCODING = "latin1"

STINT_COMPOUNDS = [f"Stint_Compound_{i}" for i in range(1, 7)]

#: How many opening stints define the strategy label. The full stint sequence
#: yields 163 classes over 1226 rows (51 of them singletons), which is not
#: learnable. The opening two stints give 31 classes and match the decision a
#: strategist actually commits to before the race.
STRATEGY_STINTS = 2

RACE_FEATURES = ["positionStart", "raceName", "raceCondition", "Year"]


def _to_int_position(value: object) -> float:
    """Parse a finishing/starting position that may be an ordinal or a status.

    Handles ``'1'``, ``'1st'``, and non-finishes such as ``'DNF'`` / ``'PIT'``,
    which become NaN so callers can drop them.
    """
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if text[-2:].lower() in ("st", "nd", "rd", "th"):
        text = text[:-2]
    try:
        return float(text)
    except ValueError:
        return np.nan


def load_race_data() -> pd.DataFrame:
    """Race-level data: one row per driver per race.

    Adds ``tyre_strategy`` (the opening stint compounds) and ``n_stops``, and
    coerces the position columns to numbers, dropping non-finishes.
    """
    df = pd.read_csv(RACE_DATA, encoding=RACE_DATA_ENCODING)

    df["positionStart"] = df["positionStart"].map(_to_int_position)
    df["positionFinish"] = df["positionFinish"].map(_to_int_position)
    df["raceCondition"] = df["raceCondition"].fillna("Dry")
    df["raceName"] = df["raceName"].fillna("Unknown")

    compounds = df[STINT_COMPOUNDS]
    df["n_stops"] = compounds.notna().sum(axis=1).clip(upper=4)
    df["tyre_strategy"] = compounds.apply(_opening_strategy, axis=1)

    # A row with no recorded stints tells us nothing about strategy, and a row
    # without both positions cannot be used for the positioning model.
    df = df[df["tyre_strategy"] != ""]
    df = df.dropna(subset=["positionStart", "positionFinish"])

    return df.reset_index(drop=True)


def _opening_strategy(row: pd.Series) -> str:
    """Join the first ``STRATEGY_STINTS`` non-empty compounds into a label."""
    stints = [
        str(row[col]).strip()
        for col in STINT_COMPOUNDS
        if pd.notna(row[col]) and str(row[col]).strip() != ""
    ]
    return " - ".join(stints[:STRATEGY_STINTS])


def lap_time_to_seconds(value: object) -> float:
    """Convert a ``M:SS.s`` or ``MM:SS.s`` lap time to seconds."""
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    if ":" not in text:
        try:
            return float(text)
        except ValueError:
            return np.nan
    minutes, _, seconds = text.partition(":")
    try:
        return float(minutes) * 60 + float(seconds)
    except ValueError:
        return np.nan


def seconds_to_lap_time(seconds: float) -> str:
    """Format seconds as ``M:SS.mmm`` for display."""
    minutes = int(seconds // 60)
    remainder = seconds % 60
    whole = int(remainder)
    millis = int(round((remainder - whole) * 1000))
    if millis == 1000:  # rounding carried into the next second
        whole += 1
        millis = 0
    return f"{minutes}:{whole:02d}.{millis:03d}"


def load_lap_time_data() -> pd.DataFrame:
    """Per-driver, per-race average green-flag lap time.

    Laps in and around a pit stop are excluded before averaging, so the target
    reflects representative pace rather than pit-lane time.
    """
    df = pd.read_csv(LAP_TIME_DATA)

    df["time_seconds"] = df["Time"].map(lap_time_to_seconds)
    df["position"] = df["Position"].map(_to_int_position)
    df["is_pit_lap"] = df["Pitstop"].notna()
    df = df.dropna(subset=["time_seconds", "position"])

    group = ["Year", "raceName", "DriverId"]
    # A pit stop distorts the lap it happens on and the laps either side.
    pit = df.groupby(group)["is_pit_lap"]
    df["near_pit"] = (
        pit.shift(1).astype("boolean").fillna(False).to_numpy()
        | df["is_pit_lap"].to_numpy()
        | pit.shift(-1).astype("boolean").fillna(False).to_numpy()
    )
    green = df[~df["near_pit"]]

    summary = (
        green.groupby(group)
        .agg(
            avg_lap_time=("time_seconds", "mean"),
            laps=("Lap", "count"),
            finish_position=("position", "last"),
        )
        .reset_index()
    )

    # Drivers who retired early leave too few clean laps to average meaningfully.
    summary = summary[summary["laps"] >= 5]
    return summary.reset_index(drop=True)
