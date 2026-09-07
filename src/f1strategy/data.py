"""Validated historical data with stable circuit IDs and task-specific eligibility.

Track status is absent from the source CSVs. Pace excludes pit-adjacent laps;
it must not be described as green-flag pace.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .paths import LAP_TIME_DATA, RACE_DATA

STINT_COMPOUNDS = [f"Stint_Compound_{i}" for i in range(1, 7)]
CONDITIONS = ("Dry", "Mix", "Wet")
CIRCUITS = {
    "abu-dhabi": ("Abu Dhabi",),
    "australia": ("Australia", "Australian"),
    "austria": ("Austria", "Austrian"),
    "azerbaijan": ("European", "Azerbaijan"),
    "bahrain": ("Bahrain",),
    "belgium": ("Belgium", "Belgian"),
    "brazil": ("Brazil", "Brazilian"),
    "britain": ("Britain", "British"),
    "canada": ("Canada", "Canadian"),
    "china": ("China", "Chinese"),
    "germany": ("Germany", "German"),
    "hungary": ("Hungary", "Hungarian"),
    "italy": ("Italy", "Italian"),
    "japan": ("Japan", "Japanese"),
    "malaysia": ("Malaysia", "Malaysian"),
    "mexico": ("Mexico", "Mexican"),
    "monaco": ("Monaco",),
    "russia": ("Russia", "Russian"),
    "singapore": ("Singapore",),
    "spain": ("Spain", "Spanish"),
    "united-states": ("United States",),
}
RACE_NAMES = {key: f"{aliases[-1]} Grand Prix" for key, aliases in CIRCUITS.items()}
ALIASES = {alias.casefold(): key for key, values in CIRCUITS.items() for alias in values}
ALIASES.update({key: key for key in CIRCUITS})


def circuit_id(name: object) -> str:
    """Resolve explicit aliases, never silently choose an ambiguous circuit."""
    text = re.sub(r"\s+", " ", str(name).strip()).casefold()
    text = re.sub(r" grand prix$", "", text)
    if text not in ALIASES:
        raise ValueError(f"Unknown circuit {name!r}. Choose a circuit from the historical calendar.")
    return ALIASES[text]


def _position(value: object) -> float:
    text = str(value).strip()
    if not re.fullmatch(r"\d+(?:\.0+|st|nd|rd|th)?", text, re.IGNORECASE):
        return np.nan
    number = float(re.sub(r"(st|nd|rd|th)$", "", text, flags=re.IGNORECASE))
    return number if 1 <= number <= 22 else np.nan


def _require(df: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {', '.join(sorted(missing))}")


def _identity(df: pd.DataFrame) -> pd.DataFrame:
    df["circuit_id"] = df["raceName"].map(circuit_id)
    years = pd.to_numeric(df["Year"], errors="raise")
    if not years.isin([2014, 2015, 2016]).all():
        raise ValueError("These source datasets must contain seasons 2014–2016 only.")
    df["Year"] = years.astype(int)
    df["event_id"] = df["Year"].astype(str) + ":" + df["circuit_id"]
    df["raceName"] = df["circuit_id"].map(RACE_NAMES)
    if df["DriverId"].isna().any():
        raise ValueError("Every row must have a driver ID.")
    df["DriverId"] = df["DriverId"].astype(str).str.strip()
    if df["DriverId"].eq("").any():
        raise ValueError("Every row must have a driver ID.")
    return df


def load_race_data(path: Path | str = RACE_DATA) -> pd.DataFrame:
    """Keep retirees; each prediction task selects its own eligible records."""
    df = pd.read_csv(path, encoding="latin1")
    _require(
        df,
        [
            "raceName",
            "Year",
            "DriverId",
            "positionStart",
            "positionFinish",
            "raceCondition",
            *STINT_COMPOUNDS,
        ],
        "Race data",
    )
    df = _identity(df)
    if df.duplicated(["event_id", "DriverId"]).any():
        raise ValueError("Race data contains duplicate driver/event records.")
    df["positionStart"] = df["positionStart"].map(_position)
    df["positionFinish"] = df["positionFinish"].map(_position)
    df["raceCondition"] = df["raceCondition"].fillna("Unknown").astype(str).str.strip()
    if not df["raceCondition"].isin([*CONDITIONS, "Unknown"]).all():
        raise ValueError("Race conditions must be Dry, Mix, Wet or Unknown.")
    for col in STINT_COMPOUNDS:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["n_stints"] = df[STINT_COMPOUNDS].ne("").sum(axis=1)
    df["n_stops"] = (df["n_stints"] - 1).clip(lower=0)
    # Require two observed opening stints, rather than shifting later observations.
    df["tyre_strategy"] = df.apply(
        lambda row: (
            " - ".join([row[STINT_COMPOUNDS[0]], row[STINT_COMPOUNDS[1]]])
            if row[STINT_COMPOUNDS[0]] and row[STINT_COMPOUNDS[1]]
            else ""
        ),
        axis=1,
    )
    return df.sort_values(["Year", "circuit_id", "DriverId"]).reset_index(drop=True)


def lap_time_to_seconds(value: object) -> float:
    """Parse positive seconds or M:SS.s; invalid values become NaN."""
    text = str(value).strip()
    try:
        if ":" in text:
            match = re.fullmatch(r"(\d+):(\d{1,2}(?:\.\d+)?)", text)
            if not match or float(match[2]) >= 60:
                return np.nan
            result = int(match[1]) * 60 + float(match[2])
        else:
            result = float(text)
        return result if math.isfinite(result) and result > 0 else np.nan
    except (ValueError, TypeError):
        return np.nan


def seconds_to_lap_time(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Time must be finite and nonnegative.")
    minutes, rest = divmod(round(seconds * 1000), 60_000)
    whole, millis = divmod(rest, 1000)
    return f"{minutes}:{whole:02d}.{millis:03d}"


def load_laps(path: Path | str = LAP_TIME_DATA) -> pd.DataFrame:
    df = pd.read_csv(path)
    _require(df, ["raceName", "Year", "DriverId", "Lap", "Time", "Pitstop"], "Lap data")
    df = _identity(df)
    df["Lap"] = pd.to_numeric(df["Lap"], errors="raise")
    if not ((df["Lap"] > 0) & (df["Lap"] % 1 == 0)).all():
        raise ValueError("Lap numbers must be positive integers.")
    df["Lap"] = df["Lap"].astype(int)
    if df.duplicated(["event_id", "DriverId", "Lap"]).any():
        raise ValueError("Lap data contains duplicate driver/event/lap records.")
    df = df.sort_values(["event_id", "DriverId", "Lap"]).reset_index(drop=True)
    df["time_seconds"] = df["Time"].map(lap_time_to_seconds)
    df["is_pit_lap"] = df["Pitstop"].notna() & df["Pitstop"].astype(str).str.strip().ne("")
    group = df.groupby(["event_id", "DriverId"], sort=False)
    before = group["is_pit_lap"].shift(1, fill_value=False) & (df["Lap"] - group["Lap"].shift(1) == 1)
    after = group["is_pit_lap"].shift(-1, fill_value=False) & (group["Lap"].shift(-1) - df["Lap"] == 1)
    df["near_pit"] = df["is_pit_lap"] | before | after
    return df


def load_lap_time_data(
    lap_path: Path | str = LAP_TIME_DATA,
    race_path: Path | str = RACE_DATA,
) -> pd.DataFrame:
    """Join pit-filtered pace to actual grid position, never finishing position."""
    laps = load_laps(lap_path)
    usable = laps[~laps["near_pit"] & laps["time_seconds"].notna()]
    summary = (
        usable.groupby(["event_id", "DriverId"])
        .agg(
            avg_lap_time=("time_seconds", "mean"),
            laps=("Lap", "count"),
        )
        .reset_index()
    )
    races = load_race_data(race_path)
    summary = summary.merge(
        races[["event_id", "DriverId", "Year", "circuit_id", "raceName", "positionStart", "raceCondition"]],
        on=["event_id", "DriverId"],
        how="inner",
        validate="one_to_one",
    )
    return summary[summary["laps"] >= 5].reset_index(drop=True)
