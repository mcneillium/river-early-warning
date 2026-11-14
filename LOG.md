# Log

Every decision and every run, including what went wrong. Newest section last.

---

## 2026-11-13: decisions made by Paul before the build

| # | Decision |
| --- | --- |
| 1 | Separate repository, outside the website folder and outside any client folder |
| 2 | conda environment on Python 3.12 |
| 3 | Splits in water years: train 01/10/1970 to 30/09/2004, validation 01/10/2004 to 30/09/2012, test 01/10/2012 to 30/09/2022. Lagged inputs may cross a boundary; targets may not |
| 4 | Headline results use NO future rainfall or temperature. A "perfect forecast" variant for the boosting model only, labelled as an upper bound |
| 5 | One boosting model per lead time. Leads of 1, 3 and 7 days |
| 6 | KGE in its original 2009 form (Gupta et al.), subject to a check against Lees et al. (2021) |
| 7 | Warning events scored day by day, with thresholds (Q95 and Q10) from the training years only, plus a separate score for onset days |
| 8 | MIT licence for the code |
| 9 | Persistence and the seasonal average run once; only boosting gets 3 seeds |
| 10 | Download only the daily series and the attribute tables |

## 2026-11-13: choices made during the unattended run

Paul asked for week 1 to be run without stopping for approval. These choices
were not in his instructions. **Each one is for Paul to confirm or change.**

| # | Choice | Reason | Alternative |
| --- | --- | --- | --- |
| A1 | Weather from HadUK-Grid (rain, temperature) and Hydro-PE (PET) | The CEH-GEAR / CHESS columns stop on 2019-12-31, inside the test period | Use CEH-GEAR and end the test period in 2019 |
| A2 | Flow variable is `discharge_spec` (mm/day) | Comparable across catchment sizes; same units as rainfall | `discharge_vol` (m3/s) |
| A3 | Forecasts are issued at the end of day t; day t's flow and weather are known | Simplest clear rule | Issue at the start of day t (day t unknown) |
| A4 | The feature list in `features.py` (lags and trailing windows of flow, rain, temperature, PET; season of the target day) | Plain and explainable | Any other set; this was not tuned |
| A5 | Boosting settings in `baselines/gbm.py`, fixed in advance and not tuned. Squared error on raw flow. Trained on training years only; validation years used only for early stopping (30 rounds) | A baseline should be plain | See the open issue below |
| A6 | Boosting forecasts clipped at zero | Negative flow is impossible; one negative forecast appeared in a smoke test | Leave unclipped and report |
| A7 | Seasonal average smoothed with a 15-day window that wraps the year end | Removes day-to-day noise in the 34-year mean | No smoothing, or a different window |
| A8 | A catchment needs 5 years of flow in training, 1 in validation, 2 in test | Enough data to fit and to score | Other minimums |
| A9 | All models scored on the same days: a day counts only if the observation and every model's forecast exist | Otherwise models are scored on different days | Score each model on its own valid days |
| A10 | Events are strict: flow > Q95, flow < Q10 | Needed a rule | Greater-or-equal |
| A11 | Seeds 0, 1, 2 for boosting; the perfect-forecast variant uses seed 0 only | Paul asked for 3 seeds on the headline model; the upper bound is a reference | 3 seeds for both |
| A12 | The attribute loader repairs two rows of the hydrometry table that have an unquoted comma in the last text column (gauges 27038 and 42010) | `pandas.read_csv` fails on them | Report upstream and wait |
| A13 | Target day's season added as sine and cosine features | The time of year of the target is known in advance | Leave out |

## 2026-11-13: check on decision 6 (which KGE)

Lees et al. (2021), "Benchmarking data-driven rainfall-runoff models in Great
Britain", HESS 25, 5517. The first two thirds of the article page were
read (the page was cut off at that point). In that part the paper does not
report KGE at all: it reports NSE, a decomposition of NSE (correlation, bias
error, variability error) and three flow-duration-curve biases. So there is no
published KGE on CAMELS-GB to match from that paper, and the 2009 form stays.

Two further points from the same paper, relevant to how results are compared:

- Its task is simulation: the model sees the weather up to and including the
  target day. It reports a median NSE of 0.88 for an LSTM ensemble on 518
  stations. That is not comparable with the headline forecasts here.
- Its periods differ (training 1988 to 1997, testing 1998 to 2008).

TODO (Paul): read the paper in full and confirm, including the last third.

## 2026-11-13: data

- Source: CAMELS-GB v2 datastore, record 9a46d428-958f-4ac1-86eb-94eee70c0955.
  No login was needed, so the download is scripted.
- Downloaded: 671 daily files and 9 attribute tables, 790 MB. Checksums are in
  `data/MANIFEST.json`.
- Loaded: 671 catchments, 18,993 days each (1970-10-01 to 2022-09-30),
  12,744,303 rows. Rain, temperature and PET have no missing days. Flow is
  missing on 8.84% of catchment-days. Median flow record 51.1 years, shortest
  14.0 years.
- Splits: 659 catchments used, 12 excluded for too little flow in one split
  (listed in `splits/splits_v1.json`). Fingerprint starts `c0acbcaf0bec`.

## 2026-11-13: problems hit during the build

1. **Attribute table would not parse.** Two rows of the hydrometry table have
   an unquoted comma. Fixed in the loader (choice A12). Found by
   `tests/test_load.py`.
2. **A weak test.** The first synthetic test for the boosting model used a
   slowly draining bucket, where "same as today" is already close to the best
   possible forecast, so the test failed for a reason unrelated to the code.
   Replaced with a fast-draining bucket where a better forecast clearly exists.
3. **Negative forecast.** One catchment produced a slightly negative boosting
   forecast in a 4-catchment smoke test. Forecasts are now clipped at zero
   (choice A6).

## 2026-11-13: run 1, week 1 baselines

- Command: `python scripts/run_baselines.py --jobs 2`
- Environment actually used: Python 3.13.18 on Linux (a cloud container), with
  the package versions in `requirements-lock.txt`. NOT the conda Python 3.12
  environment in `environment.yml`. TODO (Paul): re-run locally and confirm
  the tables match.
- 659 catchments, leads 1, 3 and 7 days, 18.7 minutes on 2 cores.
- 7,908 boosting models fitted (659 catchments x 3 leads x 3 seeds, plus one
  perfect-forecast model per catchment and lead).
- Tests: 51 passed.
- Re-running the script skipped all 659 catchments and rewrote byte-identical
  tables, so scoring is reproducible from the saved forecasts. A full refit
  from scratch has not been repeated.
- Outputs: `results/table_baselines.md`, `results/table_baselines.csv`,
  `results/per_catchment_baselines.csv`.

---

## Notes on run 1 (these discuss the results)

**Paul: write your prediction in the README before reading below this line.**

### Open issue: the boosting baseline is not a fair test of low-flow or multi-day warnings

At leads of 3 and 7 days the headline boosting model issues almost no
warnings. Its median low-flow CSI is zero at both leads, and its high-flow CSI
is close to zero at 7 days. Persistence scores far higher on the same days.

This should NOT be read as "these events cannot be forecast". Checks on the
saved forecasts point to how the baseline is trained:

- On observed low-flow days, the boosting forecast is typically about 1.8
  times the observed flow at 3 days and about 2.5 times at 7 days (median
  ratio, sample of 60 catchments). Persistence is within about 15%.
- Early stopping keeps few trees at longer leads: a median of about 67 trees
  at 3 days and 44 at 7 days, against about 175 at 1 day.
- The perfect-forecast variant, which keeps about 150 to 200 trees, is within about
  10 to 16% on the same low-flow days.

This is consistent with two known effects working together. A model trained
on squared error forecasts the average outcome, and with skewed flows the
average sits above the typical value. And early stopping is driven by errors
on large flows, so it ends training before the model has learned to separate
low-flow states. The exact split between the two has not been tested.

**What to do about it (not done, because it would be tuning after seeing
test results):** declare one or two alternatives in advance, for example
training on log-transformed flow, choose between them using validation-period
scores only, and then report the test scores once. The quantile forecasts
planned for week 3 address the same weakness directly.

### Other observations

- **Persistence onset hit rate is exactly zero at 1 day**, as it must be by
  construction. This is the clearest illustration of why onset days are
  scored separately.
- **The seasonal average never issues a warning**, so its false alarm ratio is
  undefined everywhere (shown as 0 catchments for that metric).
- **The test decade is not like the training period.** A median of 6.0% of
  test days are above the training Q95 (5% expected if nothing had changed)
  and 7.2% are below the training Q10 (10% expected). Worth a closer look: it
  is a small, real example of the distribution shift the study is about.
- **Boosting beats persistence on NSE in almost every catchment**: it is worse
  in 5.9% of catchments at 1 day, 4.4% at 3 days and 2.9% at 7 days.
- **Seeds barely matter**: the headline medians move by about 0.001 between
  seeds.
- **The gap to the perfect-forecast variant is large at 3 and 7 days.** Most
  of what is forecastable beyond a day or two comes from knowing the weather.
- About 20 to 27 catchments have no low-flow events on scored test days, so
  low-flow scores are medians over about 632 to 639 catchments, not 659.

---

## 2026-11-13: week 2, part 1 (run unattended at Paul's request)

Paul asked for the work to continue without stopping. The protocol was written
first (`docs/protocol_week2.md`), then the experiments were run. The LSTM was
NOT started: it needs a GPU.

### Choices made during the run, for Paul to confirm or change

| # | Choice | Reason | Alternative |
| --- | --- | --- | --- |
| B1 | Four boosting variants: raw or log(1 + flow) target, patience 30 or 100 | The two suspected causes of the week 1 weakness, in every combination | Other fixes, for example a quantile loss |
| B2 | Selection rule: best average of high-flow and low-flow CSI on the validation years, with NSE allowed to drop by at most 0.02 | Rewards warnings without letting NSE collapse | A different score or tolerance |
| B3 | Regional model settings in `regional.py` (learning rate 0.1, 63 leaves, up to 1,000 trees), not tuned | Plain settings for a first regional model | Tune on validation years |
| B4 | The 35 catchment descriptors in `STATIC_FEATURES`; no flow-derived descriptors, no location | See the protocol | A different list |
| B5 | Five regions by k-means on gauge position, seed 0 | Whole regions held out, simple and repeatable | Hydrometric areas, or more folds |
| B6 | Each catchment contributes a fixed random 20% of its training and validation days to the regional models | Fits the run on 2 CPU cores | Use every row on a larger machine |
| B7 | Wet and dry halves split at the median aridity | Simple | Thirds, or a different descriptor |
| B8 | A control model on a random half of catchments, added after the first results | Separates "fewer training catchments" from "different climate" | None; without it the wet-to-dry result is confounded |
| B9 | Model seeds 1 and 2 added for the regional models after the first run proved cheap | The standard is 3 seeds | Keep one seed |

### Runs

| Run | Command | Time on 2 cores |
| --- | --- | --- |
| 2 | `python scripts/run_gbm_variants.py` | 19.9 min (four variants) plus 11.9 min (two extra seeds) |
| 3 | `python scripts/run_regional.py` (seed 0) | about 12 min for 24 models |
| 4 | `python scripts/run_regional.py --seed 1`, then `--seed 2` | about 13 min each |
| 5 | `python scripts/analyse_regional.py`, `python scripts/summarise_regional_seeds.py` | under 1 min |

Same environment as run 1 (Python 3.13 on Linux, `requirements-lock.txt`).
Tests: 68 passed. Re-running `run_gbm_variants.py` and `run_regional.py` from the
saved forecasts rewrote byte-identical tables. A full refit from scratch has
not been repeated.

---

## Notes on week 2 (these discuss the results)

### Experiment 1b: the baseline repair worked only in part

**The choice.** On the validation years the rule chose `log_es100`.

| Variant | Warning score | Mean NSE | Eligible |
| --- | ---: | ---: | --- |
| `raw_es30` (week 1) | 0.182 | 0.409 | yes |
| `log_es30` | 0.243 | 0.399 | yes |
| `raw_es100` | 0.185 | 0.409 | yes |
| `log_es100` | 0.243 | 0.399 | yes, chosen |

`log_es100` beat `log_es30` by 0.0002. That is far too small to mean anything;
the rule was simply followed.

**A correction to the week 1 notes.** Week 1 suggested that early stopping
ended training too soon. That is not supported. Raising the patience from 30
to 100 changed almost nothing (0.182 to 0.185 on raw flow), and at 3 and 7
days the models still stop after about 70 and 45 trees. The validation error
really does stop improving. What mattered was the target: training on
log(1 + flow).

**On the test years** (median across catchments, 3 seeds, seed spread about 0.002):

| Lead | Score | Week 1 `gbm` | `gbm_selected` | Persistence |
| ---: | --- | ---: | ---: | ---: |
| 1 | NSE | 0.761 | 0.756 | 0.509 |
| 1 | High-flow CSI | 0.566 | 0.571 | 0.414 |
| 1 | Low-flow CSI | 0.543 | 0.729 | 0.754 |
| 3 | NSE | 0.380 | 0.362 | 0.066 |
| 3 | High-flow CSI | 0.148 | 0.091 | 0.223 |
| 3 | Low-flow CSI | 0.000 | 0.250 | 0.545 |
| 7 | NSE | 0.242 | 0.210 | -0.235 |
| 7 | High-flow CSI | 0.002 | 0.000 | 0.138 |
| 7 | Low-flow CSI | 0.000 | 0.000 | 0.389 |

What this says, plainly:

- Low-flow warnings improved a lot at 1 day and somewhat at 3 days.
- High-flow warnings at 3 days got worse, and NSE and KGE fell slightly. That
  is the expected price of training on log flow.
- At 7 days nothing changed: the model still issues no warnings.
- **For warnings at 3 and 7 days, persistence still beats every boosting
  variant.** The boosting models have far better NSE, but a forecast of the
  typical or average flow rarely crosses a rare-event threshold several days
  ahead, when the weather is unknown.

The conclusion to carry forward: a single-number forecast is the wrong tool
for multi-day warnings. The week 3 plan (quantile forecasts, then calibration)
is aimed at exactly this, and these tables are the evidence for why it is
needed.

### Experiment 3: unseen regions cost little; an unseen climate costs a lot

All numbers are means over 3 model seeds unless stated. Seed spread is given
as a standard deviation (sd).

**One regional model matches 659 local ones.** Median NSE of `regional_seen`
is 0.763, 0.375 and 0.235 at 1, 3 and 7 days, against 0.756, 0.362 and 0.210
for the per-catchment models. It also warns better at 3 days (low-flow CSI
0.383 against 0.250; high-flow CSI 0.134 against 0.091).

**Holding out a whole region costs little.** `regional_unseen` scores 0.724,
0.367 and 0.224. Catchment by catchment, the median loss in NSE is 0.019 at 1
day (sd 0.001), 0.005 at 3 days and 0.006 at 7 days. At 1 day, 86% of
catchments are worse when unseen, so the loss is small but consistent.

**The loss is uneven** (seed 0, 1 day). It is largest in region 3, south-east
England (median -0.039, with a quarter of catchments losing more than 0.10),
and region 0, northern Scotland (-0.034). It is smallest in region 1 (-0.008).
See `figures/unseen_gap_map.png`.

**A different climate is much harder than a different place.** On the same
167 dry catchments, none of which the last two models trained on:

| Lead | Score | Seen | Random half (control) | Wet catchments only |
| ---: | --- | ---: | ---: | ---: |
| 1 | NSE | 0.850 | 0.821 | 0.752 |
| 1 | Low-flow CSI | 0.659 | 0.653 | 0.414 |
| 3 | NSE | 0.485 | 0.460 | 0.407 |
| 3 | Low-flow CSI | 0.380 | 0.375 | 0.170 |
| 7 | NSE | 0.317 | 0.310 | 0.245 |
| 7 | Low-flow CSI | 0.184 | 0.173 | 0.000 |

The control shows that halving the number of training catchments costs about
0.03 in NSE at 1 day. Training only on wet catchments costs about 0.10, and
low-flow warning skill roughly halves or disappears. One exception worth
understanding: the wet-trained model has a HIGHER high-flow CSI on dry
catchments at 3 and 7 days (0.306 against 0.278, and 0.169 against 0.070). It
seems to warn of high flows more readily. Whether that is skill or simply more
warnings has not been checked (look at its false alarm ratio).

**What goes with a large loss** (`results/table_gap_correlations.csv`, seed 0,
Spearman rank correlation with the NSE gap; these are associations, not
causes):

- `reservoir_he`, about -0.33 to -0.41 (only 150 catchments have a value; I take it to mean hydro-electric reservoirs, so check the dataset documentation)
- baseflow index, -0.28 at 3 days: catchments fed mainly by groundwater lose more
- share of grassland, +0.28 at 1 day: these lose less

### Limits to state whenever these results are shown

- "Unseen" means the model was not trained on the catchment. The catchment's
  own recent flow is still an input. This is not the ungauged case.
- The regional models used a 20% sample of training days and untuned settings.
- The per-catchment comparison in `table_regional.md` uses seed 0 of the local
  model; the 3-seed local numbers are in `table_baselines_v2.md`.
- Climate descriptors (for example aridity) are long-term averages that
  include the test years. They are weather-based, not flow-based, but this is
  a small leak of test-period information into a model input.
- No regional model was given future weather, so there is no upper bound for
  the regional setting yet.
- Still on Python 3.13 in a cloud container. None of this has been re-run in
  the conda environment.

---

## 2026-11-13 (afternoon): Experiment 5, forecasts with uncertainty (run unattended at Paul's request)

The protocol was written first: `docs/protocol_week3.md`. Gaps in the inputs
(experiment 4), explanations (experiment 6) and the LSTM were not started.

### Choices made during the run, for Paul to confirm or change

| # | Choice | Reason | Alternative |
| --- | --- | --- | --- |
| C1 | Seven quantiles: 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95 | Covers the 90% range plus candidates for warning rules | More quantiles, or a single distributional model |
| C2 | Quantile models reuse the Experiment 3 regional settings unchanged | No tuning | Tune per quantile |
| C3 | Validation years split in two: 2005 to 2008 stop training, 2009 to 2012 calibrate and choose | The same days should not do both jobs | Calibrate on all validation years |
| C4 | Baseline for uncertainty: persistence with the catchment's own historical error bands | A fair, model-free comparison | Climatology quantiles |
| C5 | Warn when a chosen quantile crosses the threshold; the quantile is chosen by median CSI on the calibration half | Simple and transparent | Choose by a cost ratio between misses and false alarms |
| C6 | Conformal step pooled over catchments, one adjustment per lead, in log units | The standard method, and the only one usable for unseen catchments | Per-catchment calibration |
| C7 | Unseen regions: the 0.05 and 0.95 quantiles only; no unseen warnings | Compute cost | All seven quantiles per fold |
| C8 | One model seed | Compute cost: this run took about 3 hours | Three seeds, on a larger machine |

### Run 6

- Commands: `python scripts/run_quantiles.py`, then
  `python scripts/score_quantiles.py`, then `python scripts/plot_quantiles.py`.
- 51 models (21 seen, 30 unseen), about 3 hours on 2 cores. Low quantiles at
  1 and 3 days are slow: about 6 minutes each.
- **12 of the 51 models hit the 1,000-tree limit** (10 of 17 at 1 day, 2 of 17
  at 3 days, none at 7 days). They had not finished improving. The limit was
  fixed in the protocol, so it was left alone, but those models are probably
  slightly less sharp than they could be.
- Tests: 83 passed. Re-running `score_quantiles.py` rewrote byte-identical
  tables. The models themselves have not been refitted from scratch.

### Problems hit

1. **The fitting run was killed part-way.** A trial run of the scoring script
   was started while the models were still training, the machine ran out of
   memory (7 GB), and the training process was killed. No results were lost:
   the run was restarted and resumed from the saved forecasts. Lesson: do not
   run the two scripts at the same time on a small machine.
2. **The scoring script itself ran out of memory** on the second lead time,
   because it kept the first lead's tables. It now releases each lead's tables
   before loading the next.

---

## Notes on Experiment 5 (these discuss the results)

Test years, median across 659 catchments, one seed. Seed spread has not been
measured for these models; in Experiment 3 it was about 0.001 to 0.01.

### Question 1: do quantile-based warnings work?

**They repair the "no warnings" failure.** At 7 days the single-number model
had a high-flow CSI of 0.005 and a low-flow CSI of 0.173. The quantile model
reaches 0.175 and 0.426.

**They edge past persistence, by a small margin.**

| Lead | Warning | Persistence | Single-number model | Persistence band | Quantile model |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | High flow | 0.414 | 0.566 | 0.413 | 0.564 |
| 1 | Low flow | 0.754 | 0.731 | 0.712 | 0.785 |
| 3 | High flow | 0.223 | 0.134 | 0.229 | 0.225 |
| 3 | Low flow | 0.545 | 0.385 | 0.542 | 0.576 |
| 7 | High flow | 0.138 | 0.005 | 0.155 | 0.175 |
| 7 | Low flow | 0.389 | 0.173 | 0.412 | 0.426 |

**The honest reading is modest.** The protocol named a failure case: quantile
warnings no better than the persistence band. Compared catchment by catchment:

- At 1 day the quantile model clearly wins (better in 88% of catchments for
  high flow, median gain 0.11).
- At 3 days, for high flow, it is a tie (better in 54% of catchments, median
  gain 0.002). **By the protocol's own test, the model adds nothing over a
  catchment's own history here.**
- At 7 days, and for low flow at 3 days, it is better in 69 to 76% of
  catchments, but the median gain is only 0.014 to 0.03.

**Where the model does add something is the start of events.** Its onset hit
rate for high flow is 0.54 at 3 days and 0.49 at 7 days, against 0.39 and 0.38
for the persistence band and 0.17 and 0.14 for persistence. For low flow at 7
days it is 0.70 against 0.54.

**The price is false alarms.** At 3 and 7 days, 75 to 80% of the quantile
model's high-flow warnings are wrong, and it issues about 2.7 to 2.9 warnings
for every event. The persistence band is similar. Without a weather forecast,
no method here gives a high-flow warning at 3 or more days that is right more
than about a quarter of the time. This limit should be stated plainly; it is
what the perfect-forecast result in week 1 predicted.

**Quantiles chosen on the calibration half:** 0.75 (1 day) and 0.90 (3 and 7
days) for high flow; 0.50, 0.50 and 0.25 for low flow.

### Question 2: are the ranges honest?

**On catchments the model trained on: yes, and sharper than the baseline.**

| Lead | Coverage before calibration | After | Median width, mm/day | Persistence band width |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.899 | 0.902 | 0.44 | 1.27 |
| 3 | 0.888 | 0.905 | 1.66 | 2.23 |
| 7 | 0.885 | 0.907 | 2.34 | 2.89 |

Coverage holds on a test decade that is known to differ a little from the
training years, and it holds catchment by catchment: 90% of catchments fall
between about 0.85 and 0.95, and at most 1% are below 0.80. The range is about
a third of the baseline's width at 1 day and about 20 to 25% narrower at 3 and
7 days. All seven quantiles are within about 0.02 of their nominal level.

**On unseen regions: not for a sizeable minority.**

| Lead | Coverage, all days | Median catchment | 5th percentile catchment | Catchments below 0.80 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.871 | 0.893 | 0.703 | 14% |
| 3 | 0.866 | 0.897 | 0.671 | 17% |
| 7 | 0.870 | 0.896 | 0.690 | 18% |

(After the conformal step. Before it, 20 to 31% of catchments were below 0.80.)

The typical unseen catchment is fine, but one in six gets a "90% range" that
holds fewer than 80% of outcomes, and the model gives no sign of it: its
ranges are only about 5 to 11% wider than for seen catchments. Calibrating on
other regions does not transfer fully. Region 1 is worst (median coverage
0.84 at 3 and 7 days, 28 to 32% of its catchments below 0.80).

This is the clearest answer so far to the study's question. The model's skill
transfers to unseen regions at small cost (Experiment 3), but its sense of
its own uncertainty does not transfer as well.

### Other observations

- **Crossing quantiles are common but small.** On 19 to 36% of days at least
  two of the seven forecasts are out of order, typically by about 2% of the
  median forecast; on 5 to 7% of days by more than 5%. They are sorted before
  use. A model that produces all quantiles jointly would avoid this.
- The conformal adjustment for seen catchments is tiny (0.000 to 0.010 log
  units): the raw quantile models were already close to calibrated.

### Limits to state whenever these results are shown

- One seed. Twelve models stopped at the tree limit.
- Warning quantiles were chosen to maximise CSI. A different aim (for example,
  missing a flood costs ten times a false alarm) would choose differently.
- The persistence band uses each catchment's own history, so it could not be
  used on a catchment with no record. The quantile model could.
- "Unseen" still means the catchment's recent flow is an input.
- Coverage is an average. A range can cover 90% of days overall and still be
  too narrow in floods, when it matters most. Coverage by flow level has not
  been checked.
- Still Python 3.13 in a cloud container; nothing re-run locally.

## 2026-11-13: ignore rule fixed before the first commit

`.gitignore` listed `results/raw/` only. The later experiments write to
`results/raw_variants/`, `results/raw_regional*/` and `results/raw_quantiles/`
(about 1.5 GB together), and a plain `git add -A` picked all of them up. Found
when preparing the first commit. The rule is now `results/raw*/`. Nothing large
was ever pushed.

## 2026-11-13: question, authorship statement and first report added

At Paul's instruction ("you do everything") the research question, a
status note and
`docs/report.md`. The README says no prediction was recorded in advance.
The report's related-work section is left unwritten because the papers have
not been read in full.

A check made while writing the report found two wrong numbers in a working
summary (the upper bound at 3 and 7 days was
given as 0.809 and 0.763; `results/table_baselines.md` says 0.810 and 0.722)
and one loose claim (that 75 to 80% of multi-day warnings are false alarms
"for every method"; that holds for the quantile model only). They had reached
the portfolio site's Research page and were corrected there the same evening.
The tables in this repository were always correct.

## 2026-11-14: prepared for publication

- Personal study notes (the walkthrough and the report outline) and the working rules file are
  kept out of the public repository, under `notes/`, which git ignores.
- The public history starts from a single commit. The earlier commits are
  kept privately.
- Data licence terms were checked and recorded in `CITATION.md`.

## 2026-11-14: Experiment 6 written, not yet run

The regional LSTM (`src/rew/lstm.py`, `scripts/run_lstm.py`) and its protocol
(`docs/protocol_week4.md`) were written today. No result exists yet: the full
run needs a GPU.

What has been checked:

- Eight new tests (91 in all, passing). One found a real fault before any
  run: forecasts for the last six test days at the 1-day lead and the last
  four at the 3-day lead were never made, because issue days stopped seven
  days before the end of the record for every lead. Fixed by padding the
  targets past the end of the record and letting each lead run to its own
  last day.
- `--smoke` runs end to end on a CPU (12 catchments, 2 short epochs). Its
  scores mean nothing.
- A slightly longer CPU check on 12 catchments (hidden size 48, 6 epochs of
  25,600 windows) learned: median NSE 0.60, 0.28 and 0.17 at 1, 3 and 7 days
  against persistence at 0.39, -0.10 and -0.26 on the same catchments. This
  only shows the code trains. It is not a result and is not reported.

### Choices made in writing it, for Paul to confirm or change

| # | Choice | Reason | Alternative |
| --- | --- | --- | --- |
| E1 | One model with three outputs (1, 3, 7 days) | A third of the training cost | One model per lead, as boosting has |
| E2 | Observed flow up to the issue day is an input | Same information as boosting; this is forecasting, not simulation | No flow input, as in Kratzert et al. (2019), which answers a different question |
| E3 | 365-day window | The usual choice in the literature | 90 days, to match boosting's memory exactly |
| E4 | Hidden size 256, dropout 0.4, learning rate 0.001, not tuned | Follows Kratzert et al. (2019) | Tune on validation years |
| E5 | Batch 2,048 | Uses a large GPU well | 256, as in the literature |
| E6 | Squared error on standardised log flow | Same target scale as the chosen boosting variant | The catchment-weighted NSE loss of Kratzert et al. |
| E7 | Missing inputs set to the training mean, with a flag for missing flow | Keeps every window usable | Drop windows with any gap |
| E8 | An epoch is 2,000,000 random windows; up to 30; stop after 4 without improvement on a fixed 20% validation sample | Bounded cost; about 8 million windows exist | Full passes |
| E9 | Seeds 0, 1, 2 | Matches Experiment 3 | More seeds |
| E10 | "No better" means within 0.01 median NSE of regional boosting, or below | Fixed before the run | A different margin |

## 2026-11-14: Experiment 6, first run (Paul's machine)

Run by Paul on Windows with an NVIDIA RTX 5090, Python 3.14.7 and PyTorch
2.11.0+cu128, from commit `b684425`. All 91 tests passed there first.
`python scripts/run_lstm.py`, seeds 0, 1 and 2, all 659 catchments, 38
seconds per epoch.

| Seed | Epochs run | Best epoch | Validation loss at best |
| ---: | ---: | ---: | ---: |
| 0 | 6 | 2 | 0.2846 |
| 1 | 5 | 1 | 0.2878 |
| 2 | 6 | 2 | 0.2891 |

Median across catchments on the test years, mean over seeds (standard
deviation over seeds in brackets):

| Lead | Model | NSE | KGE | High-flow CSI | Low-flow CSI |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | LSTM | 0.734 (0.010) | 0.718 | 0.529 | 0.616 |
| 1 | persistence | 0.509 | 0.754 | 0.414 | 0.754 |
| 3 | LSTM | 0.377 (0.003) | 0.389 | 0.131 | 0.317 |
| 3 | persistence | 0.066 | 0.533 | 0.223 | 0.545 |
| 7 | LSTM | 0.239 (0.004) | 0.234 | 0.005 | 0.139 |
| 7 | persistence | -0.235 | 0.385 | 0.138 | 0.389 |

### Against the criteria fixed in the protocol

Regional boosting, same three seeds (`results/table_regional_seeds.csv`):
median NSE 0.763, 0.375 and 0.235.

| Lead | LSTM minus boosting | Outcome under the 0.01 rule |
| ---: | ---: | --- |
| 1 | -0.029 | No better (worse) |
| 3 | +0.001 | No better |
| 7 | +0.004 | No better |

A null result at every lead. The warning scores are no better either:
high-flow CSI 0.529, 0.131, 0.005 against 0.566, 0.134, 0.005 for boosting,
and low-flow CSI lower at every lead.

### What limits this

- The comparison is across two scoring runs, not on identical days. The
  boosting forecasts were not on the machine that ran the LSTM. Persistence
  scores identically to four decimals in both runs (0.5093, 0.0657,
  -0.2347), which suggests the days are the same. The paired comparison in
  the protocol is still owed: run weeks 1 and 2 on the same machine, then
  run `scripts/run_lstm.py` again (trained models are reused).
- The best epoch was 1 or 2 in every seed. An epoch is a quarter of the
  training windows, so the model was at its best before seeing most of them
  once, and overfitted after that. The configuration was fixed in advance
  and not tuned, as the protocol says. This is weak evidence about LSTMs in
  general and fair evidence about this one.
- The 1-day result differs across seeds more than boosting does (standard
  deviation 0.010 against 0.003).
- The unseen-region run (`--unseen`) has not been made.

### Not done, on purpose

No setting was changed after seeing these numbers. Any follow-up (a lower
learning rate, a smaller model, weight decay) would be chosen on validation
years only, written as a dated amendment first, and labelled exploratory.

## 2026-11-14: second-machine re-run and the paired LSTM comparison

Paul re-ran `run_baselines.py`, `run_gbm_variants.py` and `run_regional.py`
(seeds 0, 1, 2) on his Windows machine, then `run_lstm.py` again, which
reused the three trained LSTMs and scored them beside the regional boosting
model on identical days.

**Reproduction.** Weeks 1 and 2 reproduce exactly (largest difference in any
median 4e-16). The variant chosen on validation years is `log_es100` again.
The regional models agree to within 0.006 on every median NSE, KGE and
high-flow or low-flow CSI, and within 0.013 for the wet-to-dry tables. No
conclusion changes. Details: `results/reproduction_second_machine.md`. The
first-run tables stay as the published record.

**Paired comparison (protocol, Experiment 6).** NSE per catchment, LSTM
minus regional boosting:

| Lead | Seed 0 | Seed 1 | Seed 2 | Pooled | LSTM better in |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | -0.013 | -0.030 | -0.013 | -0.019 | 16% |
| 3 | +0.003 | +0.002 | +0.003 | +0.002 | 57% |
| 7 | -0.000 | -0.001 | +0.009 | +0.002 | 56% |

Median NSE, mean of seeds: LSTM 0.734, 0.377, 0.239; boosting 0.764, 0.375,
0.235. Under the 0.01 rule the LSTM is no better at any lead. The first of
the limits recorded this morning (no paired comparison) is now closed. The
others stand: one untuned configuration that overfits within two short
epochs, and no unseen-region run.

## 2026-11-14: Experiment 6, unseen regions (Paul's machine)

`python scripts/run_lstm.py --unseen` on the RTX 5090: 15 more trainings
(five regions held out in turn, seeds 0, 1, 2), 38 to 41 seconds per epoch,
best validation loss after 1 or 2 epochs every time, as before. The three
seen-catchment models were reused, and their scores are unchanged to the
last digit. `scripts/summarise_lstm.py` writes the paired table
(`results/table_lstm_paired.md`).

Median NSE, mean over seeds:

| Lead | LSTM, unseen | Boosting, unseen | Paired median difference | LSTM better in |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.708 | 0.723 | -0.010 | 36% |
| 3 | 0.367 | 0.367 | +0.004 | 59% |
| 7 | 0.225 | 0.224 | +0.005 | 59% |

Under the 0.01 rule fixed in the protocol, the LSTM is no better on unseen
regions at any lead. Low-flow CSI is lower at every lead (0.601 against
0.706 at 1 day), as on seen catchments.

**Exploratory, not set in advance.** The cost of holding a region out, per
catchment, at 1 day: -0.009 for the LSTM and -0.019 for boosting. At 3 and
7 days both lose under 0.01. Seed 1's seen LSTM was the weakest (best after
one epoch), which makes its own held-out cost look small (+0.001), so the
1-day contrast is partly an artefact of that seed. Not a claim.

What remains: one untuned configuration; the overfitting within two short
epochs; no LSTM in the wet-to-dry test.

## 2026-11-14: corrections from a review of the logged choices

A review of the choices against the literature found two errors in how they
were written. Neither changes a number.

- **Threshold names (A10, entry 7, protocol week 3).** "Q95" and "Q10" here
  mean the 95th and 10th percentiles of daily flow in the training years: a
  high-flow event is flow above the 95th percentile, a low-flow event flow
  below the 10th. UK hydrology writes flows the other way round, as the flow
  exceeded for a given share of the time, so the National River Flow
  Archive's Q95 is a low flow. In that convention the high threshold here is
  Q5 and the low threshold is Q90. From now on this study writes "the 95th
  percentile" and "the 10th percentile". The CAMELS-GB descriptors named
  `Q5` and `Q95` in `regional.py` keep the dataset's own names.
- **E3 and E4.** Kratzert et al. (2019) used 270-day input sequences, not
  365. They are the source for hidden size 256 and dropout 0.4 only; the
  learning rate was not checked against the paper. See amendment 1 in
  `docs/protocol_week4.md`.
- **E10.** "No better" means the LSTM did not exceed the predefined
  improvement margin of 0.01 median NSE. It is not a test of equivalence.

The review also raised design points (repeated permutations for the leak
demonstration, nested preprocessing inside the inner tuning folds, missing
data flags for every input). They are design changes, not corrections, and
wait for Paul's decision on each logged choice.

## 2026-11-14: decisions on every logged choice (Paul)

Paul reviewed all 40 river choices in a written review dated 14 November
2026, prepared with help from ChatGPT on reasoning, references and editing.
His decisions, summarised:

| # | Decision | Reason, in short |
| --- | --- | --- |
| A1 | Agree | One weather source for the whole period; a mid-record switch could look like a change in the river. About consistency, not accuracy. |
| A2 | Agree | Specific discharge is comparable across catchments and shares rainfall's units. |
| A3 | Agree, with a condition | Workable for a retrospective study. Observation windows that cross day boundaries must be checked before calling it operational. |
| A4 | Agree | Simple, explainable features; every calculation must stop at the issue time. |
| A5 | Agree | Describe as "no hyperparameter search"; validation still acts through early stopping. |
| A6 | Agree | Clipping a negative forecast cannot worsen squared error; record how often it happens. |
| A7 | Agree | Wrap the window at New Year, training data only, one leap-day rule. |
| A8 | Agree | A basic safeguard; counts alone do not ensure seasonal or event coverage. |
| A9 | Agree | Report retained days and each model's availability. |
| A10 | Agree, with the corrected names | 95th and 10th percentiles; terminology only, thresholds unchanged. |
| A11 | Agree | Three seeds for the headline model; one-seed reference labelled as such. |
| A12 | Agree | Keep the raw file; the repair touches only the two known rows. |
| A13 | Agree | The target date is known in advance; not future weather. |
| B1 | Agree | Keep the sequence visible: the follow-up came after the first test results. |
| B2 | Agree | 0.02 is a chosen tolerance, not a standard; report both CSIs and NSE. |
| B3 | Agree | Compares the models as configured, not each family at its best. |
| B4 | Agree, with a check | The 35 descriptors need a provenance and dates check; other variables still carry geography. |
| B5 | Agree | Show the region map and fold sizes; nested catchments can straddle boundaries. |
| B6 | Agree | Report counts and event coverage; 20% does not give equal examples per catchment. |
| B7 | Agree | State the ratio, period and direction; two halves simplify a gradient. |
| B8 | Agree | Label as a later addition; repeated same-size samples would extend it. |
| B9 | Agree | Keep all seeds and their later addition in the record. |
| C1 | Agree | Seven levels are not a full distribution. |
| C2 | Agree | Not shown to suit every quantile. |
| C3 | Agree | Keep stopping and calibration years separate, same date rules. |
| C4 | Agree | Errors from permitted data; scored on matching days. |
| C5 | Agree | Report hit rate and false alarm ratio with CSI; live use needs real costs. |
| C6 | Change the claim | Not "the only option"; split-conformal relies on exchangeability, which river data do not meet automatically. Report coverage by catchment and lead with width. |
| C7 | Agree | State plainly that unseen-region warnings were not tested. |
| C8 | Agree | Small differences not presented as robust across seeds. |
| E1 | Agree | Score each lead separately; state the loss weighting. |
| E2 | Agree | Both models get observed flow up to the issue time. |
| E3 | Agree, with the amendment | Keep 365 days; a matched-history comparison would separate memory from architecture. |
| E4 | Agree | 256 cells and dropout 0.4 match the paper; the rest is documented as used here. |
| E5 | Agree, if training converges | Look at learning curves; never pick a batch size by test score. |
| E6 | Agree | State the scaling rule explicitly. |
| E7 | Change | Add missing-data flags for any input that can be missing; never impute targets. |
| E8 | Agree | Record the sampling rule; call it a sampling epoch. |
| E9 | Agree | Keep individual seed scores as well as the mean. |
| E10 | Change the interpretation | "Did not exceed the improvement margin", not equivalence; report paired differences. |

### What the code shows for the points the review asked to check

- **B5.** Regions are k-means on British National Grid easting and northing,
  a projected grid in metres.
- **C6.** The conformal step uses the finite-sample level
  ceil((n + 1)(1 - alpha)) / n with the higher order statistic. Each
  unseen region is calibrated on the calibration days of the other four
  regions only (`quantile.fit_predict`). Coverage and width are reported
  pooled and per catchment; by season they are not.
- **E1.** The loss is the mean squared error over every target that
  exists, so the three leads have equal weight.
- **E6.** Scaling is global: one mean and standard deviation per variable
  from the training years of the training catchments, not per catchment.
- **E7.** Rain, temperature and PET are never missing in any split (0.0%).
  Flow is missing on 11.7% of training days, 0.5% of validation days and
  1.6% of test days, and already has a flag. Missing targets are masked out
  of the loss and the scores, never filled. The change Paul asked for is
  therefore already met, and no retraining is needed.
- **E8.** Catchments and issue days are drawn uniformly with replacement,
  so a catchment with a short record is drawn as often as one with a long
  record. The validation sample is fixed (seed 20261114).

Still open from the review: A3 and B4 (observation windows, availability
and the dates behind descriptors), C6 coverage by season, E3 a
matched-history LSTM, E5 learning curves.

## 2026-11-14 (evening): follow-ups written, not yet run

Written by the assistant at Paul's request; nothing below has been run on a
GPU yet. Protocols were amended first (`docs/protocol_week4.md` amendment 2,
`docs/protocol_week3.md` amendment 1).

- `src/rew/lstm.py`: two new settings, `window` (default 365) and
  `weight_decay` (default 0, which keeps plain Adam). With the defaults the
  model and training are unchanged; a test pins the Experiment 6 defaults.
- `scripts/tune_lstm.py`: eight candidates, chosen on validation-year NSE.
- `scripts/run_lstm.py`: `--tuned` and `--wet-to-dry`. The wet/dry split is
  rebuilt as in `run_regional.py` and checked against the boosting files
  (328 wet, 331 dry, 167 scored; both checks pass on the real data).
- `scripts/run_quantiles.py` and `scripts/score_quantiles.py`: `--seed`.
- Checks: 90 tests pass on CPU here (6 skipped: they need files not copied over). The scoring path of `--wet-to-dry` was run
  with the boosting forecasts standing in for the LSTM; it reproduces the
  Experiment 3 wet-to-dry table (seed 0) exactly.

### Choices made by the assistant, for Paul to confirm or change

| # | Choice | Why |
| --- | --- | --- |
| F1 | Eight candidates (see amendment 2) | Small enough for an evening on one GPU; covers stopping, learning rate, size, regularisation and memory |
| F2 | Select on median validation NSE averaged over leads | The reported score is NSE; the loss is on log flow |
| F3 | Seed 0 only during selection | Cost; the chosen settings get three seeds on the test years |
| F4 | Weight decay 0.01 with AdamW | A common AdamW default; not searched |
| F5 | Sampling epochs of 500,000 windows, patience 6 | Lets early stopping act about four times as often |
| F6 | The LSTM wet-only and control models forecast only the 167 scored catchments | Saves time; the boosting wet-only model forecasts all 331 dry ones, scored on the same 167 |
| F7 | Transfer measured as wet-only minus seen, per catchment, 0.01 margin | Matches the 0.01 rule used elsewhere |
| F8 | Experiment 5 seeds keep the 1,000-tree limit | One change at a time; tree counts are reported |

## 2026-11-14 (late evening): Experiment 7 drafted, not run

Written by the assistant. `docs/protocol_week5.md` (with the question and
prediction left for Paul), `scripts/run_foundation.py`, one test, and a
`foundation` extra in `pyproject.toml` (chronos-forecasting 2.3).

- Checked on CPU: Chronos-2 loads from Hugging Face, accepts gaps in the
  flow history, and the smoke run (3 catchments, 60 issue days) scores end
  to end. A spot check of one catchment shows the 1-day forecast tracks the
  previous day's flow, so dates are aligned.
- Hourly files checked: 671 files, about 10.6 GB, 1990 to 2022. Hourly rain
  from CEH-GEAR1hr ends on 31 December 2016; GRaD-GB runs from 2006 to 2022.

| # | Choice | Why |
| --- | --- | --- |
| G1 | Chronos-2 only, for now | The one model whose install and API were checked today |
| G2 | 365-day context | The same history as the LSTM |
| G3 | Raw flow in mm/day, not log flow | How a user would call it; the alternative is a later amendment |
| G4 | Median as the point forecast; 0.05 and 0.95 for a 90% range | Matches Experiment 5's interval |
| G5 | Compared with seed 0 of the trained models | The foundation model has no seed |
| G6 | 0.02 NSE margin for "close", 0.01 for "weather helps" | Set before any result; Paul may change them before the run |

## 2026-11-14 (night): results of the Experiment 6 follow-ups

Run by Paul on his RTX 5090 (commit 994e944). Read and checked by the
assistant against the rules in protocol_week4.md, amendment 2.

### A. Settings chosen on the validation years

`results/table_lstm_tuning_validation.md`. None of the seven alternatives
beat the original settings on the validation years (mean median NSE 0.4009;
the others 0.3863 to 0.3940). The rule chose `c0_original`.

- c0 and c1 have identical scores. This is expected, not a bug: with the
  same seed both draw the same training batches, and 4 of c1's epochs
  (4 x 244 steps) equal 1 of c0's (976 steps). c1's best checkpoint (epoch 8)
  is c0's (epoch 2) exactly, and every check in between was worse. So
  finer early stopping finds the same minimum: the overfitting after about
  4 million windows is real, not an artefact of coarse stopping.
- c7 (90-day window) against c2 (the same with 365 days): validation NSE
  0.682 against 0.701 at 1 day, 0.308 against 0.309 at 3 days, 0.174
  against 0.171 at 7 days. The longer memory helps only at 1 day, by about
  0.02, with one seed. The LSTM's 1-day gap to boosting (which sees 90 days)
  is therefore not explained by memory length.
- `run_lstm.py --tuned` retrained the chosen settings, which are the
  original ones. Training losses and every test score match Experiment 6
  exactly, so training is repeatable on this machine. No new result.

### B. The LSTM in the wet-to-dry test

`results/table_lstm_wet_to_dry.md` and `results/table_lstm_transfer_cost.csv`
(167 dry catchments, 3 seeds). On the measure fixed in advance:

| Trained on | Lead | LSTM cost | Boosting cost | Verdict |
| --- | ---: | ---: | ---: | --- |
| wetter half | 1 | -0.106 | -0.050 | LSTM transfers worse |
| wetter half | 3 | -0.076 | -0.007 | LSTM transfers worse |
| wetter half | 7 | -0.062 | -0.014 | LSTM transfers worse |
| random half | 1 | -0.004 | -0.015 | LSTM better, by 0.0101, just over the 0.01 margin |
| random half | 3 | +0.001 | -0.002 | neither |
| random half | 7 | +0.000 | -0.002 | neither |

The per-seed ranges do not overlap for the wet-trained models at any lead.

- Reading: when the training catchments are like the test catchments, the
  LSTM transfers as well as boosting or slightly better. When they are all
  wetter, it loses about 2 to 11 times as much skill (2.1, 10.9 and 4.4
  times at 1, 3 and 7 days).
- Low flows: the wet-trained LSTM's low-flow CSI is zero (or undefined) in
  81%, 92% and 94% of catchment-seed pairs at 1, 3 and 7 days; the
  wet-trained boosting model's in 26%, 43% and 62%; the seen models' in 6%
  to 23%. The wet-trained LSTM almost never warns correctly of low flow in
  the drier catchments.
- Not tested, only a candidate explanation: the scaler and the catchment
  descriptors come from wet catchments only, so dry catchments' descriptors
  (aridity among them) lie outside the training range. Trees hold their
  last value outside the range; a neural network extrapolates.
- Limit: the wet-only LSTMs reached their best validation loss in the
  first sampling epoch in all three seeds, so they had less training than
  the seen LSTM (best at epoch 1 or 2).

### Mistake found and fixed

The `--wet-to-dry` run also rewrote `results/table_lstm.md`,
`results/table_lstm.csv` and `results/per_catchment_lstm.csv` without the
unseen-region rows. The assistant restored them from commit 994e944 (they
match it exactly) and changed `run_lstm.py` so a wet-to-dry run leaves them
alone. The transfer-cost table is now written by `run_lstm.py`
(`transfer_cost`); the table above was produced by that function from the
saved per-catchment scores, with no retraining. One test added (91 pass).
