# Data

Two datasets covering the 2014–2016 Formula One seasons, scraped from public
race-results sites. Both are committed so results reproduce exactly.

## `raw/race_data.csv` — 1,226 rows, one per driver per race

| Column | Notes |
|---|---|
| `DriverId`, `raceName`, `Year` | Race identity |
| `Stint_Compound_1..6`, `Stint_Laps_1..6` | Tyre stints in order; unused stints are blank |
| `positionStart`, `positionFinish` | Grid and finishing position; non-finishes appear as `DNF`/`PIT` and are dropped |
| `raceCondition` | `Dry`, `Mix` or `Wet` |
| `raceLength`, `raceTurns`, `raceLaps`, `raceAddress` | Circuit metadata (sparsely populated) |

Encoded as Latin-1, not UTF-8 — circuit addresses contain accented characters.

## `raw/lap_time_data.csv` — 59,300 rows, one per driver per lap

| Column | Notes |
|---|---|
| `raceName`, `DriverId`, `Year`, `Lap` | Lap identity |
| `Time` | Lap time as `M:SS.s` |
| `Position` | Ordinal, e.g. `6th` |
| `Pitstop` | Pit duration in seconds, blank on non-pit laps |
| `Delta` | Change from the previous lap; `-` on the first lap |

`src/f1strategy/data.py` aggregates this to one row per driver-race, averaging
green-flag laps only.
