# Historical data snapshots

The two CSVs were inherited from the original 2014–2016 coursework project.
They are preserved byte-for-byte in this rebuild. They are not a live feed or
a verified, complete official classification.

## Provenance and reuse

The earlier project describes these as scraped public race-results data.
Per-row source URLs, retrieval dates and redistribution permissions were not
preserved with the CSVs. No stronger provenance claim is made here. The MIT
license covers this repository's code, not third-party data or website material.
Verify permissions with the original providers before reuse or redistribution.

The evaluation records SHA-256 hashes of both snapshots. No report, secrets,
personal user information or model pickles are included in the browser export.
Driver names and historical race observations are explicitly allowlisted.

## race_data.csv

1,226 raw rows, read as Latin-1.

| Fields | Interpretation |
|---|---|
| DriverId, raceName, Year | Source identity, normalised to driver/event keys |
| Stint_Compound_1..6, Stint_Laps_1..6 | Recorded ordered stints; absent values stay absent |
| positionStart, positionFinish | Numeric/ordinal positions or source statuses |
| raceCondition | Dry, Mix, Wet; missing becomes Unknown |
| raceLength, raceTurns, raceLaps, raceAddress | Sparse inherited circuit metadata, not model inputs |

Non-numeric finishing statuses remain missing. Retirees can still contribute
observed tyre sequences and usable pace; they are excluded only from
finishing-position regression. Non-numeric starts are excluded from tasks
requiring a grid feature.

The archive contains inconsistent grid values: for example, two 2016 Bahrain
records use grid slot 8. The explorer flags repeated numeric slots and displays
the records as supplied; it does not invent corrections.

## lap_time_data.csv

59,300 raw rows.

| Fields | Interpretation |
|---|---|
| raceName, DriverId, Year, Lap | Lap identity |
| Time | Positive seconds or M:SS.s |
| Position | Recorded running position, not a model input |
| Pitstop | Recorded pit marker/duration; nonempty means pit lap |
| Delta | Inherited timing delta, not a model input |

There is no track-status field. Filtering pit laps and their physical
neighbours does not remove all safety-car/slow laps. The target is
**pit-filtered average pace**, never “green-flag pace.”

The demo’s race length comes from observed laps. Stint bars use recorded
lengths without stretching a retired driver's race to the full distance.
Unknown lengths are marked; source rows may be incomplete or inconsistent.

## Reproduction

`python scripts/train.py` validates and evaluates the snapshots.
`python scripts/export_demo.py` exports 2016 driver stints, lap medians,
data-quality indicators and measured results. Read the
[methodology](../documentation/methodology.md) for task eligibility and caveats.
