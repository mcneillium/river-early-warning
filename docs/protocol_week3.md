# Protocol for Experiment 5: forecasts with honest uncertainty

Written on 13 November 2026 **before** this experiment was run.

## Why

Weeks 1 and 2 showed that a single-number forecast rarely crosses a
rare-event threshold several days ahead, so it makes a poor warning system
even when its NSE is good. A forecast that says how uncertain it is can warn
when an event is merely likely. Two questions follow:

1. Do warnings based on forecast quantiles beat persistence and the
   single-number model at 3 and 7 days?
2. Are the stated uncertainty ranges honest, and do they stay honest on
   catchments the model has never seen?

## Models

A regional boosting model per lead time and per quantile, trained with the
quantile (pinball) loss on log(1 + flow). Quantiles are unchanged by the log
transform, so the forecast is converted straight back to mm/day.

- **Quantiles:** 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95.
- **Settings:** the same as the regional model of Experiment 3 (same inputs,
  same 35 catchment descriptors, same 20% sample of training days, learning
  rate 0.1, 63 leaves, up to 1,000 trees, patience 100). Not tuned.
- **No future weather.**
- **Crossing quantiles:** each quantile is a separate model, so two can
  occasionally cross. The seven forecasts for a day are sorted before use.
- **Seed:** 0. More seeds are owed.

## A stricter use of the validation years

In earlier experiments the validation years decided when to stop training.
Here they must also calibrate the uncertainty and choose the warning rule, and
the same days should not do both. So the validation period is split:

- **Early-stopping half:** 1 October 2004 to 30 September 2008.
- **Calibration half:** 1 October 2008 to 30 September 2012. Never used in
  training or early stopping.

## Baseline for uncertainty: persistence with error bands

Every result needs a simple baseline. For each catchment and lead, take the
training-years distribution of the change in log(1 + flow) over the lead time.
The forecast quantile is today's flow shifted by the matching quantile of that
change. It needs no model, only the catchment's own history.

## Question 1: warnings

- **Rule.** Warn of high flow when the forecast quantile tau_high is above the
  catchment's Q95 threshold. Warn of low flow when the forecast quantile
  tau_low is below its Q10 threshold.
- **Choosing tau.** On the calibration half only, for each lead time, choose
  tau_high from {0.50, 0.75, 0.90, 0.95} and tau_low from {0.50, 0.25, 0.10,
  0.05} to give the highest median CSI across catchments. Ties go to the
  quantile nearest 0.50. The same procedure is applied separately to the
  persistence-band baseline.
- **Then, once,** score the test years: persistence, the single-number
  regional model from Experiment 3 (seed 0), the persistence-band baseline and
  the quantile model, all on the same days. Report CSI, hit rate, false alarm
  ratio and onset hit rate. A higher CSI bought with many more false alarms
  must be visible in the table.

## Question 2: honest ranges

- **The range.** The 90% range runs from the 0.05 to the 0.95 quantile.
- **Conformal step** (conformalized quantile regression, Romano et al., 2019).
  On the calibration half, for each day compute how far the observation falls
  outside the range, in log(1 + flow) units (negative if it is inside). Take
  the 90th percentile of those values, with the usual finite-sample
  correction, and widen (or narrow) both ends of every test range by that
  amount. One adjustment per lead time, pooled over catchments.
- **Reported on the test years:** the share of observations inside the range
  (target 90%) before and after the conformal step, the median width of the
  range, and how coverage varies from catchment to catchment.
- **All seven quantiles** are also checked: for each one, the share of
  observations that fall below it should equal the quantile.

## Unseen regions

For each of the five regions, models for the 0.05 and 0.95 quantiles are
trained on the other four regions, early-stopped and conformally calibrated
on those four regions only, and applied to the held-out region's test years.
Coverage and width are compared with the seen case on the same catchments.

Warnings for unseen regions are **not** part of this experiment: choosing tau
without touching the held-out region would need all seven quantiles for every
fold, which is too costly here.

## What would count as a failure

- Quantile warnings no better than the persistence-band baseline: then the
  model adds nothing over a catchment's own history.
- Coverage well below 90% on the test years even after the conformal step:
  then the calibration years are not representative of the test years, which
  would itself be a finding about distribution shift.

## Amendment 1, 14 November 2026 (after the results; changes no setting)

Experiment 5 was run with one model seed. It is repeated with model seeds
1 and 2 (`scripts/run_quantiles.py --seed N`, then
`scripts/score_quantiles.py --seed N`), with the same row sample, the same
settings and the same tree limit. Seed 0 is also re-run on a second machine.

- Seeds 1 and 2 are scored against the regional point model of the same seed
  (`results/raw_regional_seedN/`).
- What is reported: each finding of Experiment 5 per seed, and whether it
  holds in all three. A finding that does not hold in all three seeds is
  described as not robust to the model seed.
- The tree limit (1,000) is kept, so the 12 models that reached it in the
  first run may reach it again. How many do, per seed, is reported from the
  saved tree counts. Raising the limit would be a further amendment.
