# Research comparisons and legacy experiment audit

I compare Random Forest, Gradient Boosting and a simple
baseline on identical task-specific records. The full results retain every
candidate's 2015 validation and 2016 test scores, with the selected candidate
fixed by **2015 only**. See [measured results](../reports/metrics.json).

| Task | Validation-selected method | Important final-season finding |
|---|---|---|
| Opening tyre sequence | Gradient Boosting | RF has higher 2016 accuracy, but does not replace the frozen selection |
| Classified finish | Random Forest | GB has lower 2016 MAE, but does not replace the frozen selection |
| Pit-filtered pace | Circuit/condition baseline | RF has lower 2016 MAE, but does not replace the frozen selection |

This is a retrospective chronological evaluation, not a pristine unseen
benchmark. Hyperparameters were not tuned against the final comparison.
All models use grid slot, circuit and assumed conditions. Preprocessing is
fitted inside each training pipeline; finishing position is not a pace feature.

## Why the earlier neural networks are not on the leaderboard

I reviewed selected original scripts without rerunning them. Their file
hashes and audit decisions are in [the catalogue](../data/catalogue.json).
I've kept the original scripts and model files in my private archive. I haven't
relabelled any old metric as a new result.

| Original experiment | Inspection findings | Required redesign |
|---|---|---|
| `Positioning/Positioning LSTM.py` | Tokenisation/scaling precede a random-row split; one-token input is not an ordered lap window | Build real within-driver/event sequences; fit transformations on training seasons only |
| `Tyre Strategy/Tyre Strategy GRU.py` | Randomly generated `finalPosition`; input reshaped to one timestep; tuner consumes the test set; interactive output uses a frequency lookup | Remove fabricated/post-race inputs; separate validation and test; make inference use the evaluated model |
| `Lap Time/GRU Lap Time.py` | Post-race final position feeds pace; full-data scaling before random split; one timestep; test data reused as validation | Define a prediction-time feature contract, ordered windows and a genuine later-event test |

An LSTM/GRU layer alone does not make a model a meaningful time-series
experiment. Retraining these scripts unchanged would reproduce the problems,
not establish a fair neural-versus-tree comparison. TensorFlow and old pickles
are therefore not runtime dependencies of this public rebuild.

## Stint drift: a separate, completed experiment

The [stint study](../src/f1strategy/stints.py) tests a training-only compound
median against zero pace drift, with 2014 training, 2015 selection and 2016
evaluation. It analyses 2,078 alignment-checked stints and reports its
exclusions. The compound lookup narrowly wins validation but loses the final
comparison: 0.1944 versus 0.1933 s/lap slope MAE. It is not promoted to a fitted
tyre-wear model. [Full analysis and limitations](../documentation/data-case-study.md#what-the-stint-study-found).

## A valid next sequence experiment

Use documented season/event/session identities, then create windows within
each driver's event ordered by lap. Inputs must exist by the prediction lap;
targets belong to future laps. Keep whole events and seasons apart, fit all
transformations on training data, tune only on validation, and compare a
last-observed-pace baseline and tree model on exactly the same windows.
Reserve a newly acquired season before looking at outcomes. Publish exclusion
counts, out-of-sample error, a learning curve and runtime—not only the best score.

The richer table currently lacks season identity, so this redesign is a next
experiment, not a completed neural benchmark.
