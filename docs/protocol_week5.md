# Protocol for Experiment 7: a time-series foundation model with no training

Drafted on 14 November 2026 by the assistant, **before** this experiment was
run. Paul writes the question and the prediction below, in his own words and
with the date, before the full run. `scripts/run_foundation.py` refuses to
start while either section still says "TO BE WRITTEN BY PAUL".

## Background

Sun and Sun (2026), "Zero-shot Forecasting of Streamflow Using Time Series
Foundation Models: Are We There Yet?", tested general forecasting models on
daily flow in 500+ US basins. One (Sundial) came close to a trained LSTM,
best in basins with strong seasonal patterns such as snowmelt. British rivers
are rain-driven, and sub-daily skill was not tested. Chronos-2 (Ansari et
al., 2025) can also take past covariates, such as rainfall, without
training. No benchmark on British catchments was found (search of 14
November 2026; to be confirmed against the reading list).

## Question

TO BE WRITTEN BY PAUL. (A suggestion to rewrite, not to copy: with the same
365 days of history and no future weather, how close does a forecasting model
never trained on rivers come to the trained regional LSTM and boosting model
at 1, 3 and 7 days, and does adding past weather help it?)

## What I expect, and why

TO BE WRITTEN BY PAUL, dated. Say for each lead whether you expect Chronos-2
to be within 0.05 NSE of the LSTM, better than persistence, and whether the
weather covariates will help.

## Models

- `chronos2_flow_only`: Chronos-2 (`amazon/chronos-2`), past 365 days of flow
  in mm/day, missing days left as missing (the model accepts gaps).
- `chronos2_weather`: the same, with the past 365 days of rain, temperature
  and PET as past-only covariates.
- No training, no fine-tuning, no tuning of any setting on these rivers.
- The point forecast is the median (0.5 quantile). The 0.05 and 0.95
  quantiles give a 90% range, with no calibration step.

## Data, splits and scoring

- The saved splits; the test years (water years 2013 to 2022) only. Every
  issue day whose target date at a lead is in the test years, as in
  Experiment 6.
- Scored exactly as in Experiments 1 to 6, beside persistence, the regional
  boosting model and the LSTM (seed 0 of each), on identical days.
- The foundation model is deterministic given its inputs, so there are no
  seeds. The trained models' seed-to-seed spread (Experiments 3 and 6) is the
  yardstick for whether a gap matters.

## What would count as a result, fixed now

- At each lead, the gap is the median, across catchments, of Chronos-2's NSE
  minus the LSTM's NSE, with the share of catchments where Chronos-2 is
  better.
- "Close to the trained model" means a median gap within 0.02 NSE, a
  margin fixed now. The LSTM's seed-to-seed spread is reported beside it.
  Anything else is reported as a gap of that size.
- The weather covariates "help" if `chronos2_weather` beats
  `chronos2_flow_only` by more than 0.01 median NSE.
- Coverage of the 90% range is reported beside Experiment 5's calibrated
  quantile model.

## Stage 2 (not built yet): hourly

CAMELS-GB v2 has hourly files for all 671 catchments (1990 to 2022); how many have usable hourly flow is not yet checked. Hourly
rain comes from two products: CEH-GEAR1hr ends on 31 December 2016 and
GRaD-GB starts in 2006, so the hourly test years would use GRaD-GB. The
hourly files are about 10.6 GB. Stage 2 is designed only after stage 1 has
been read, as a further amendment.

## Limits known in advance

- Chronos-2 may have seen some public river series during pretraining; its
  training data are not fully listed, so "never trained on rivers" means
  never trained on these rivers by this study.
- It cannot use the 35 catchment descriptors, which the LSTM and boosting
  model both use.
- Raw flow in mm/day is given to the model; a log transform might change the
  result and would be a separate amendment.
- One foundation model. TimesFM 2.5 and Sundial are candidates for an
  amendment once their installation on Paul's machine has been checked.
