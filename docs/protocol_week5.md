# Protocol for Experiment 7: a time-series foundation model with no training

Drafted on 14 November 2026 by the assistant; the question, the prediction
and the margin were set by Paul the same evening, **before** this experiment
was run. All of it was fixed before any Chronos-2 forecast on the test years
existed (only a 60-day CPU smoke run, which is not a result).

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

Written by Paul on 14 November 2026, before the run:

> How does zero-shot Chronos-2 compare with persistence, regional boosting
> and the regional LSTM when forecasting daily flow in British catchments at
> 1, 3 and 7 days? Does adding past weather improve its performance, and how
> does it compare with wet-trained models on the same 167 dry catchments?

## What I expect, and why

Written by Paul on 14 November 2026, before the run. These are working
hypotheses, not estimates from an existing Chronos-2 run. They were
formulated after seeing the earlier river results (Experiments 1 to 6 and
the wet-to-dry follow-up), with drafting assistance.

**Flow-only Chronos-2 against the seen regional LSTM**

| Lead | Predicted median paired NSE difference |
| ---: | --- |
| 1 day | Between -0.05 and +0.01 |
| 3 days | -0.03 or lower |
| 7 days | -0.05 or lower |

Calculated as follows: each catchment's NSE difference on identical valid
dates, averaged across the three LSTM seeds, then the median across
catchments. Positive means Chronos-2 performs better.

**Chronos-2 with past weather against flow-only Chronos-2:** a median paired
NSE improvement of at least 0.01 at one day, but less than 0.01 at three and
seven days.

**On the 167 dry catchments:** Chronos-2 with past weather will exceed the
wet-trained LSTM by more than 0.01 median paired NSE at one day. All three
leads are reported, but the three- and seven-day dry-subset comparisons are
secondary analyses without directional predictions.

Boundaries as written: "between" includes both ends; "or lower" and "at
least" include the value; "less than" and "more than" exclude it.

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
- Scored exactly as in Experiments 1 to 6 (the same thresholds and score
  functions), as set out below.

## One improvement margin, fixed now

0.01 NSE throughout, applied to a median paired difference (model minus
reference):

- above +0.01: exceeds the predefined improvement margin;
- below -0.01: worse by more than that margin;
- between -0.01 and +0.01, inclusive: within the practical comparison band.

The band does not establish statistical equivalence. The prediction
thresholds above are separate from this interpretation rule. (The draft's
separate 0.02 "close" rule was removed on 14 November 2026, before the run.)

## Paired comparisons

For each trained-model seed s (0, 1, 2): every model in a comparison is
scored on the days where all of them have a forecast and an observation.
For each catchment the NSE difference is computed per seed and averaged over
the three seeds; the median across catchments is reported with the share of
catchments where the model is better. A catchment counts only if it has a
difference for all three seeds. Chronos-2's forecasts are the same in every
seed's comparison; only the trained models change.

All catchments: each Chronos-2 variant against the seen LSTM, the seen
regional boosting model and persistence, and the two variants against each
other.

## The 167 dry catchments

The exact list of the wet-to-dry test (rebuilt by `run_lstm.wet_dry_split`
and checked against the boosting files): Chronos-2 (both variants) against
the wet-trained LSTM, wet-trained boosting, their seen references and
persistence, on common valid dates at each lead. Chronos-2 has no
wet-trained and broadly trained pair, so no transfer cost is computed for it;
the comparison is of absolute performance on the same catchments and dates.

## Scores reported

NSE and KGE, and for high and low flow: CSI, hit rate, false alarm ratio and
onset hit rate. Each score is averaged over seeds per catchment. Zero and
undefined scores are counted separately (undefined: no seed gives a value,
for example no observed or forecast events), and the median is over the
catchments where the score is defined. Median per-catchment denominators are
reported: events (hit rate), warnings (false alarm ratio), events plus false
alarms (CSI) and onsets (onset hit rate), with catchment counts. Coverage
and width of Chronos-2's 90% range are reported; they can be read against
Experiment 5's table, but that range is calibrated and this one is not.

## Repeatability

Chronos-2 has no seed. The first two catchments are forecast twice and the
largest difference is recorded (`results/exp7/repeatability.json`). Its
forecasts are not presented as independent seeds.

## Outputs

Tables in `results/exp7/`; raw forecasts in `results/raw_foundation/`. No
earlier table is written by this experiment.

## Stage 2 (not built yet): hourly

CAMELS-GB v2 has hourly files for all 671 catchments (1990 to 2022); how many have usable hourly flow is not yet checked. Hourly
rain comes from two products: CEH-GEAR1hr ends on 31 December 2016 and
GRaD-GB starts in 2006, so the hourly test years would use GRaD-GB. The
hourly files are about 10.6 GB. Stage 2 is designed only after stage 1 has
been read, as a further amendment.

## Limits known in advance

- Chronos-2 is zero-shot with respect to this study: it is not trained or
  tuned on these data. It may have seen public river series in pretraining;
  that would need an audit of its pretraining sources, which is not done.
- It cannot use the 35 catchment descriptors, which the LSTM and boosting
  model both use.
- Raw flow in mm/day is given to the model; a log transform might change the
  result and would be a separate amendment.
- One foundation model. TimesFM 2.5 and Sundial are candidates for an
  amendment once their installation on Paul's machine has been checked.
