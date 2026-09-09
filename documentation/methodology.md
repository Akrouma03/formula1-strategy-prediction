# Methodology

## Scope

There are two independent systems: a deterministic strategy simulator in
`docs/simulator.js`, and three historical supervised-learning tasks in Python.
The simulator does not consume model predictions. Its time gains must not be
interpreted as learned recommendations, validated forecasts or counterfactual
race outcomes.

## Data contract and eligibility

Source snapshots cover 2014–2016. Circuit aliases map to explicit canonical IDs:
“Australia” and “Australian Grand Prix” are one identity. The European Grand
Prix label in this archive maps to Azerbaijan. This mapping is intentionally
restricted to these seasons; it is not a universal historical event resolver.
Event identity is season plus circuit. Driver identity uses the explicit
2014–2016 registry in `identities.py`; source `DriverId` values remain intact.
Unknown names are visibly unmapped, never fuzzy-guessed. The pace join records
all eligible keys and reports unmatched rows instead of silently dropping them.
See [join reconciliation](data-case-study.md#a-reproducible-correction-driver-identity).

Missing schema columns, unknown circuit names, out-of-scope years, duplicate
driver/event records and duplicate lap keys fail explicitly. Non-numeric grid
and finish statuses become missing values, not random or inferred positions.
Weather is Dry/Mix/Wet/Unknown; Unknown does not silently become Dry.

| Task | Target | Eligibility beyond recognised weather and numeric grid |
|---|---|---|
| Tyres | Exact first two observed stint compounds | Both opening stints present; retirees remain eligible |
| Finish | Recorded numeric finishing position | Numeric source finish; conditioned on being classified |
| Pace | Mean of available pit-filtered lap times | At least five usable laps and a matching race/grid record |

Tyre labels are not folded into a common class using their full-data frequency.
Missing opening stints are not replaced with later stints. Stints and stops
are different: six observed stints imply five stops, not six or a capped four.

Lap data are sorted by event, driver and lap before filtering. A marked pit lap
and its physically adjacent lap numbers are excluded. A missing lap does not
make the next retained row “adjacent.” Filtering never crosses a driver/event
boundary. Invalid times are removed after adjacency has been determined.
Track-status flags are absent; safety-car laps and other disruptions can remain.

## Features and chronological evaluation

All tasks consume exactly:

```text
positionStart + circuit_id + raceCondition
```

Official or predicted finishing position is never a pace feature. Driver identity,
team, year and post-race timing are not features. Weather is observed in the
archive, so this is conditional scenario evaluation—not a pre-race weather
forecast.

1. Train candidates on 2014. Fit categorical encoding on these rows only.
2. Score Random Forest, Gradient Boosting and the task baseline on 2015.
3. Select maximum accuracy (tyres) or minimum MAE (regression), with a
   deterministic alphabetical tie break that favours the baseline.
4. Refit the selected method on 2014–2015.
5. Evaluate on 2016. Keep the artifact trained only on development seasons.

For transparent research comparison, the two other candidates are also refitted
on the same development rows and evaluated on the same final-season rows.
Those scores never change the validation-selected method.

Random seed: 42. One-hot encoding tolerates previously unseen categories.
Candidate settings are fixed in `models.py`; the test season never selects
a candidate or supplies baseline lookup values. A regression test changes
only 2016 targets and verifies that the chosen method, validation scores and
fitted predictions stay unchanged.

This is a **retrospective chronological evaluation**. Earlier project versions
used random-row splits and this archive has been inspected during development.
It is not an untouched, prospective lockbox. There is only one final-season
split; a new independently collected season is needed for stronger validation.

### Baselines

- Tyres: training-only most common opening sequence for circuit/conditions.
- Pace: training-only median driver-average pace for circuit/conditions.
- Finish: predict the starting grid slot.

Lookups fall back to circuit, then global training values. Baselines refit on the
same development rows as learned models. If the baseline wins validation,
the saved artifact uses it directly.

### Reporting

Accuracy, macro-F1 and weighted-F1 are retained for tyres; MAE and R² for
regression. Headline scores weight driver records equally. Per-event scores
make weak races visible. Unseen test tyre labels are reported, not merged away.

The uncertainty calculation first reduces errors/correctness to one mean per
event, then bootstraps those event means with 1,000 seeded draws. The 2.5th and
97.5th percentiles form the displayed interval. This weights races equally,
unlike the driver-weighted headline. It is a descriptive small-sample interval,
not a calibrated driver-level prediction interval or a guarantee about future
seasons. No claim of statistically significant baseline improvement is made.

Source and pipeline SHA-256 hashes, dependency versions, seed, split counts, candidates and
per-race results accompany each artifact/report. Partial retraining refuses to
mix different source or dependency metadata. Export refuses incomplete or
source- or pipeline-stale reports. CI regenerates research and models, then
checks that the committed browser data matches, ignoring runtime-version
metadata and floating-point differences below 1e-9.

## Measured stint study

The explorer now shows descriptive, robust stint-pace slopes alongside the
recorded stints. It requires exact recorded pit-boundary agreement and observed
distance, dry conditions, valid contiguous stint definitions and six usable
laps. First race laps and pit-adjacent laps are excluded. Compound spelling
`Super Soft` is normalised to `Super soft` in this study only; the original
classification labels and source CSVs are unchanged.

Theil–Sen slope is the median pairwise change in time per lap of tyre age.
It is robust to some isolated slow laps, but cannot distinguish fuel burn,
traffic, safety cars, car/driver pace or tyre wear. The compound-median lookup
is fitted on training stints, selected against zero drift on 2015, refitted on
2014–2015 and assessed on 2016. Its worse final-season error does not justify
promoting it to simulator coefficients. No physical wear calibration is claimed.

The [case study](data-case-study.md#what-the-stint-study-found) documents the
counts and findings; `reports/research.json` records every first-failing
driver–race exclusion, short-stint count, compound summary and event summary.

## Strategy simulator

For race lap `l` and tyre age `a` (zero on a stint's first lap):

```text
lap seconds =
  historical reference pace
  + compound offset
  + base degradation × compound wear factor × a
  − fuel gain × (l − 1)
  + scenario safety-car slowdown
  + pit loss, when stopping after this lap
```

| Dry compound | Offset (s) | Wear factor |
|---|---:|---:|
| Soft | 0.00 | 1.35 |
| Medium | 0.45 | 0.85 |
| Hard | 0.90 | 0.55 |

These are illustrative constants, not estimates fitted to measured tyre wear.
The UI lets visitors choose degradation (0–0.30 s/lap), pit loss (10–40 s),
one/two stops, compounds and increasing pit laps. The shared engine supports
zero to three stops for testing and reuse. Stops cannot occur after the final
lap or share a lap; age resets on the next lap.

Reference pace is the median of eligible driver-average pit-filtered pace for
the chosen 2016 event. Race length is the maximum observed lap number, not a
claim about a complete official schedule. Fuel gain is fixed at 0.03 s per
elapsed lap. The safety-car scenario starts on a chosen lap, adds 15 seconds
to each car for up to three remaining laps, and halves pit loss within that
window. It does not model bunching or track position.

The plotted gap is cumulative **B minus A**: positive means A leads. Sensitivity
reruns the same plans at 70%, 100% and 130% of chosen wear. Its min/max range is
**not a confidence interval**. Generic dry compounds are assumed available,
including when the reference event's recorded conditions were wet.

No traffic, overtaking, driver/car differences, warm-up, tyre allocation,
sporting-rule checks, uncertainty calibration or optimisation search is
implemented. The purpose is to make a simple trade-off inspectable.

## Browser architecture

The static application imports the same pure JavaScript engine tested by Node.
Python exports an explicit field allowlist for the archive and measured report;
browsers do not load joblib, raw CSVs, credentials or academic documents.
No external fonts, libraries, analytics or API requests run in the page.

The HTML entrypoints and fetched JSON use a release query (`v=2.1.0`) to avoid
mixing cached scripts/data with a newer page. Bump the query in `index.html`
and `app.js` together when releasing changed browser assets or data. The
browser suite checks that the app works when unversioned resources are unavailable.

Start with `python -m http.server 8000 --directory docs`.
For deployment, choose **GitHub Actions** in the repository's Pages settings.
The CI workflow publishes only `docs/`, only from `main`, and only after
Python and browser checks pass. This follows the
[GitHub Pages custom-workflow requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
