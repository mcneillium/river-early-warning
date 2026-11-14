# Protocol for Experiment 6: a regional LSTM

Written on 14 November 2026 **before** this experiment was run.

## Why

Every model so far is gradient boosting on hand-built summaries of the last
90 days. The standard data-driven model in hydrology is an LSTM that reads
the raw daily series itself (Kratzert et al., 2019; Lees et al., 2021 for
Great Britain). A reader will ask whether the conclusions of Experiments 1
to 3 are about forecasting without future weather, or only about boosting.
One question:

1. With the same information and the same splits, does a regional LSTM
   forecast flow better than the regional boosting model at 1, 3 and 7 days?

A second run, described at the end, repeats the unseen-region test.

## Model

One LSTM for all catchments and all three lead times.

- **Inputs, each day of a 365-day window ending on the issue day t:**
  precipitation, temperature, potential evapotranspiration, observed flow,
  and a flag that is 1 where the flow is missing. Flow is log(1 + flow).
  The 35 catchment descriptors of Experiment 3 are appended to every day.
- **No future weather.** The window ends on day t. This is the same
  information the boosting model has, apart from the longer memory (365
  days against 90).
- **Outputs:** log(1 + flow) on days t + 1, t + 3 and t + 7, from one linear
  layer on the last hidden state. One model for three leads, where boosting
  used one model per lead.
- **Size and training:** one layer, hidden size 256, dropout 0.4 before the
  output layer, Adam with learning rate 0.001, batch 2,048, gradients
  clipped at norm 1. These follow Kratzert et al. (2019) except the batch
  size. Not tuned.
- **Loss:** mean squared error on standardised log flow, over the targets
  that exist.
- **Scaling:** every input and the target are standardised with the mean and
  standard deviation of the training years of the training catchments only.
  Missing inputs are set to zero after scaling, which is the training mean.

## Data and splits

- The saved splits (`splits/splits_v1.json`), by target date: train to water
  year 2004, validation 2005 to 2012, test 2013 to 2022. A target counts
  towards the training loss only if its own date is in the training years.
- An epoch is 2,000,000 windows drawn at random from the training windows,
  not a full pass (there are about 8 million). Up to 30 epochs.
- **Stopping:** the validation loss is computed after each epoch on a fixed
  20% sample of validation windows. Training stops after 4 epochs without
  improvement and the best epoch's weights are kept. The test years take no
  part in this.
- **Seeds:** 0, 1 and 2. Results are reported per seed and as the mean.

## Scoring

Exactly as in Experiments 1 to 3: NSE, KGE, the warning scores, thresholds
from the training years, medians across catchments. Each model is scored on
the days where every model in the comparison has a forecast. If the raw
forecasts of the regional boosting model are present
(`results/raw_regional/`), it is scored beside the LSTM on identical days.
If they are not, the LSTM is scored beside persistence only, and the
comparison with boosting is across tables and is weaker.

## What would count as a negative result

Fixed now:

- The LSTM is "no better" at a lead time if its median NSE, averaged over
  the three seeds, is within 0.01 of the regional boosting model's, or below
  it.
- The paired comparison is the median, across catchments, of the difference
  in NSE, with the share of catchments where the LSTM is better.

Either outcome is reported. A null result here would mean the ceiling found
in Experiment 1 belongs to the information, not to the model.

## Second run: unseen regions

`--unseen` trains five more models per seed, each with one of the five saved
regions (`splits/spatial_folds_v1.json`) held out, and scores each region
with the model that never saw it. Scaling statistics come from the training
catchments of each fold. This is five times the cost and is run only after
the first run has been read.

## Limits known in advance

- One fixed configuration. A tuned LSTM could do better, and a tuned
  boosting model could too.
- The LSTM sees 365 days and boosting sees 90, so a gain could come from
  memory length and not from the model class.
- Squared error on log flow favours the middle of the range, as it did for
  boosting, so the warning scores are expected to stay poor.
- Exact reproduction is not guaranteed: results on a GPU are not
  bit-for-bit repeatable across machines or library versions.

## Amendment 1, 14 November 2026 (after the run)

Correction to the justification under "Size and training", made after the
results existed and changing no setting. Kratzert et al. (2019) used input
sequences of 270 time steps, 256 memory cells and dropout 0.4. This study
uses a 365-day window, so it follows that paper for hidden size and dropout
only. The learning rate of 0.001 was not checked against the paper. The
365-day window remains a design choice made before the run; "follows
Kratzert et al. (2019)" should not be read as covering it.

Interpretation of the 0.01 rule: a result inside the margin means the LSTM
did not exceed the predefined improvement margin. It does not show that the
two models are equivalent.

## Amendment 2, 14 November 2026 (before these runs; after Experiment 6's results were seen)

Two follow-ups. Both were planned after the Experiment 6 test results
existed, so they are exploratory and are reported as such. Neither changes
any result already reported.

### A. Settings chosen on the validation years (`scripts/tune_lstm.py`)

Why: in every Experiment 6 run the best validation loss came at sampling
epoch 1 or 2 (of 2,000,000 windows each) and rose after that, so early
stopping acted late and coarsely. Review item E5 asked for learning curves;
item E3 asked for a matched-history comparison.

Eight candidates, fixed now, each trained once with seed 0 on every
catchment:

| Candidate | Change from Experiment 6 |
| --- | --- |
| c0_original | none (the Experiment 6 settings) |
| c1_fine_stopping | sampling epochs of 500,000 windows, up to 60, patience 6 |
| c2_lr3e-4 | c1, learning rate 0.0003 |
| c3_lr1e-4 | c1, learning rate 0.0001 |
| c4_hidden128 | c2, hidden size 128 |
| c5_hidden64 | c2, hidden size 64 |
| c6_weight_decay | c2, AdamW with weight decay 0.01 |
| c7_window90 | c2, a 90-day window, the history the boosting model sees (item E3) |

- **Selection rule:** the highest median NSE across catchments on the
  validation years (2005 to 2012), averaged over leads 1, 3 and 7; a tie
  (to 4 decimals) goes to the lower validation loss. The same validation
  years also drive early stopping, through the fixed 20% sample. The test
  years are not read by the tuning script.
- **Then:** the chosen settings are trained with seeds 0, 1 and 2 and scored
  on the test years (`run_lstm.py --tuned`), beside the original LSTM and the
  regional boosting model on identical days, with the same 0.01 rule as
  above.
- **c7 is reported whatever is chosen.** Its validation score against c2
  separates memory length from the model class, which is the limit stated
  in advance above.
- Limits: one seed per candidate; a small grid; boosting is not tuned to the
  same degree, so a gain for the tuned LSTM is not a fair contest win.

### B. The LSTM in the wet-to-dry test (`run_lstm.py --wet-to-dry`)

The split is the one in Experiment 3 (`scripts/run_regional.py`), rebuilt
the same way and checked against the boosting forecasts at run time: 328
wetter catchments (aridity below the median) and 331 drier ones; a control
of 328 catchments drawn at random (seed 0); scoring on the 167 dry
catchments outside the control half.

Per seed, two more LSTMs with the Experiment 6 settings: trained on the wet
half (`lstm_wet_only`) and on the random half (`lstm_random_half`), both
forecasting the 167 catchments. They are scored beside the seen LSTM and
the three boosting models on identical days.

- **Question:** does the LSTM lose more or less skill than boosting when it
  has seen only wetter catchments?
- **Measure, fixed now:** the cost of transfer per catchment is NSE of the
  wet-only model minus NSE of the seen model, for each family. The LSTM
  "transfers better" at a lead if the median of its cost is smaller than
  boosting's by more than 0.01, and "worse" if larger by more than 0.01;
  otherwise neither. The random-half control is read the same way.
- If `--tuned` is also given, the same test is run with the tuned settings
  and reported separately.
