# From manually cleaned files to an auditable F1 dataset

## My contribution and the evidence

I collected and manually cleaned the datasets for my original F1 project.
I don't have a complete row-by-row log of those manual edits, so I've separated
what I did from what I can now verify directly from the files. This is a
separate public engineering case study; my academic report is not included.

I can verify the files' contents, schemas and relationships. I've added a
reproducible pipeline around my original cleaning work: explicit driver and
event identities, join reconciliation, version hashes, eligibility checks and
chronological evaluation. I haven't reconstructed undocumented edits or dates.

## What the archive actually contains

The [source catalogue](../data/catalogue.json) records 16 CSV files but only
10 distinct byte contents, plus metadata for five private workbooks. More
filenames do not mean more independent observations.

| Family | Verified evidence | Decision |
|---|---|---|
| Lap snapshots | `all_race_data.csv`, `all_race_data_2.csv` and `Lap Time Data.csv` are byte-identical: 59,300 rows | One unchanged public copy in `data/curated/lap_time_data.csv` |
| Race snapshots | `Race Data.csv` and `updated_dataset.csv` are byte-identical: 1,226 rows | One unchanged public copy in `data/curated/race_data.csv` |
| Positioning exports | Four copies of the same 59,300-row, 16-column table | Catalogue as derived exports; do not concatenate |
| One-hot lap export | `LapTime Data.csv`: 59,300 rows, 47 columns | Derived features, not new observations |
| Tyre feature export | `preprocessed_tyre_strategy.csv`: 1,226 rows, 25 columns | Do not reuse the legacy generated `finalPosition` feature |
| Stint extraction subset | `race_data.csv`: 354 rows, seven exact duplicates, no season | Keep separate; the underscore filename is a different dataset |
| Empty cleaned export | `Lap Time/cleaned_lap_time_data.csv`: header only | Exclude from modelling |
| Richer lap table | `F1_data.csv`: 57,273 rows, 8,413 exact duplicates, no season | Assess, but do not integrate until event identity is recovered |
| Monaco telemetry extract | 51,599 rows; only one non-null tyre-compound value | Insufficient standalone evidence for tyre modelling |

I found that an apparently newer version was not automatically an improvement:
`updated_dataset_2.csv` differs from `updated_dataset.csv` in one cell:
the fourth compound for Maldonado, Abu Dhabi 2014, changes from blank to `x`
(physical CSV row 19). I can't establish why that edit was made, and `x` is not
a compound used by the study. I kept the earlier snapshot as canonical and
left both files unchanged.

The catalogue includes SHA-256 checksums and missing-value counts. Workbook
entries contain filenames, file sizes, hashes and sheet counts only—not cell
contents, addresses, formulas or the academic report.

## A reproducible correction: driver identity

Circuit names already had explicit aliases, but driver matching still relied
on exact source strings. That silently dropped eligible lap summaries.

| Before: source variants | Canonical identity | Handling |
|---|---|---|
| `Filipe Nasr`, `Felipe Nasr` | `nasr` | Explicit spelling alias |
| `Kevin Magnessun`, `kevin_magnussen` | `magnussen` | Explicit source-name mapping |
| `Pastor Maldonando`, `maldonado` | `maldonado` | Explicit source-name mapping |
| `ericssson`, `ericsson` | `ericsson` | Explicit spelling alias |
| `Carlos Sainz Jnr`, `Carlos Sainz` | `sainz` | Explicit name variant |

The [registry](../src/f1strategy/identities.py) is restricted to this archive.
Accents, whitespace, underscores and hyphens are normalised. Unknown names
remain visibly unmapped; no nearest-name guess assigns a driver. Original
`DriverId` values remain available beside the canonical `driver_id`.
Historical name checks can be traced to the
[2015 official standings](https://www.formula1.com/en/results/2015/drivers).

Of 1,066 driver–race lap summaries with at least five usable laps:

- 977 joined with exact source names.
- 88 more join using the explicit aliases.
- One remains unmatched: Button at Bahrain 2015. The lap file contains times,
  while the official result records zero laps and DNS. That conflict is
  excluded, not given an invented grid slot or stint record.
  [Official race result](https://www.formula1.com/en/results/2015/races/920/bahrain/race-result).

This raises identity-match coverage from 91.7% to 99.9%. It does **not** verify
the timing content of every matched record. Additional grid/weather eligibility
filters leave 1,057 pace-model rows, including 373 in the final 2016 season.
The expanded test population changes pace MAE from 5.47 to 5.52 seconds;
better coverage is not the same as a better prediction score.

## Source lineage: recovered references, remaining gaps

My original scraping code contains RaceFans tyre-strategy URLs and Pitwall lap
report URLs. I've recorded hashes of those scripts and example public
URLs. This verifies which sites the code references—not an exact per-row
mapping from every CSV to a retrieval response. Some driver entries in the old
Pitwall script also reuse URLs, another reason not to claim a verified feed.

Retrieval dates, a complete record of manual edits and redistribution permissions
are not recoverable from these files alone. Old scraping scripts are not run
by the public pipeline. The code's MIT license does not relicense source data.

```text
Private source archive (preserved)
  ├─ CSV/workbook metadata → data/catalogue.json
  ├─ two selected, byte-identical snapshots → data/curated/
  │    └─ validated identities + eligibility
  │         ├─ chronological models → reports/metrics.json
  │         └─ join audit + stint study → reports/research.json
  │              └─ allowlisted export → public browser demo
  └─ academic report + original experiments → remain private
```

## Why the richer table is not joined yet

`F1_data.csv` includes sectors, lap times, rainfall, track temperature and tyre
compound. However, `Driver + Race + Lap` cannot identify an observation across
seasons. Its 8,413 repeated rows may mix duplication with event-identity issues;
blind deduplication is not a substitute for recovering those identifiers.

Before promotion, recover season/date, session type, source URL or API session
ID, units and retrieval provenance. Then verify the season/event/driver/lap
key, inspect repeated keys, establish compound definitions, and hold out a
genuinely new season. No inferred year or current weather is substituted.

## What the stint study found

The reproducible study accepts only recorded-dry driver–races with contiguous,
positive integer stint lengths, exact agreement between cumulative lengths
and pit markers, and matching observed distance. It excludes the first race
lap and pit-adjacent laps, requires six usable laps per stint, and measures
the median pairwise lap-time slope (Theil–Sen).

799 of 1,226 driver–race records pass alignment checks, yielding 2,078 analysed
stints. The audit reports every driver–race exclusion and 264 short stints.
The study does not claim that pit filtering removes safety-car laps.

| Stint-slope predictor | 2015 validation MAE | 2016 test MAE |
|---|---:|---:|
| Zero drift | 0.1113 | 0.1933 |
| Training-only compound median | 0.1103 | 0.1944 |

Units: seconds per lap of tyre age. Selection used 2015, then the lookup was
refitted on 2014–2015. The final comparison contains 697 stints. The selected
lookup does not improve on zero drift in 2016; no significance claim is made.

Observed slopes can be negative as fuel burns off, and compound names do not
represent identical physical tyres at every event. Fuel, traffic, car/driver
pace and track status remain confounders. These data therefore support a
descriptive pace-trend view in the explorer, **not a causal calibration of tyre
wear**. The simulator's coefficients remain illustrative.

## Reproduce it

From the public checkout, after installing the Python dependencies:

```bash
python scripts/train.py
python scripts/build_research.py
python scripts/export_demo.py
python scripts/export_demo.py --check
python -m pytest
```

The private archive is not needed for these commands. Its metadata catalogue
is a checked-in evidence snapshot. Only the owner can regenerate that snapshot:

```bash
python scripts/catalogue_sources.py --source-dir "PATH_TO_PRIVATE_ARCHIVE" --output data/catalogue.json
```

The catalogue command reads a fixed allowlist, never the report. It writes
outside the preserved archive. All original datasets and workbooks remain intact.
