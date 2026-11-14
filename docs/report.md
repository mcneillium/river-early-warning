# River early warning across 671 British catchments: report

**Author.** Paul McNeill. Written on 13 November 2026 from the logged results in this repository; not yet peer reviewed. Every number below comes from a table in `results/`.

<!-- TODO (Paul): restore a statement of how any AI tools were used before this goes to anyone else, and keep it accurate. -->

## 1. Question

How far ahead can river flow, and flood or low-flow warnings, be forecast
without knowing future weather, and does that skill carry over to places the
model was not trained on?

No prediction was recorded before the results existed.

## 2. Data and setup

- **Data.** CAMELS-GB v2: daily flow and weather for 671 British catchments,
  October 1970 to September 2022. 659 catchments had enough data to use.
- **Task.** On day t, forecast flow on day t + 1, t + 3 and t + 7. This is
  forecasting, not simulation: the model does not see the weather between
  day t and the target day.
- **Splits.** Train on water years to 2004, choose settings on 2005 to 2012,
  test on 2013 to 2022. The splits are saved with a fingerprint.
- **Warnings.** A high-flow day is flow above the catchment's 95th
  percentile; a low-flow day is below its 10th. Both come from training years.
- **Scores.** NSE and KGE for the flow forecast. Critical success index
  (CSI), hit rate and false alarm ratio for warnings, plus the hit rate on
  the first day of each event. All are reported as the median across
  catchments, on the same days for every model.

## 3. Methods

1. **Baselines.** "Same as today" (persistence), the seasonal average, and
   gradient boosting with one model per catchment. A version given the
   weather that actually happened is an upper bound only.
2. **A regional model.** One boosting model for all catchments, with 35
   catchment descriptors that do not come from the flow record.
3. **Unseen regions.** The catchments were split into five geographic
   regions. Each region was forecast by a model trained on the other four.
4. **An unseen climate.** A model trained on the wetter half of catchments
   was tested on the drier half, beside a control trained on a random half.
5. **Uncertainty.** Seven quantile models per lead time, adjusted with
   conformalized quantile regression on years 2009 to 2012. Warnings were
   then issued when a chosen quantile crossed the threshold. A model-free
   band around today's flow is the baseline for this step.

## 4. Results

**The flow forecast (NSE, test years).**

| Model | 1 day | 3 days | 7 days |
| --- | ---: | ---: | ---: |
| Persistence | 0.509 | 0.066 | -0.235 |
| Boosting, one model per catchment | 0.761 | 0.380 | 0.242 |
| Upper bound: weather known | 0.865 | 0.810 | 0.722 |

- Boosting beats persistence at every lead.
- Most of the skill beyond one day depends on knowing the weather. At 7 days
  the gap to the upper bound is about 0.5 NSE.

**As a warning system, the single-number forecast fails.** At 7 days the
regional model's high-flow CSI is 0.005, far below persistence at 0.138. A
model that minimises squared error learns to predict the middle, and the
middle rarely crosses a 95th-percentile threshold.

**One regional model matches 659 local ones** (NSE 0.762 against 0.755 at
1 day).

**Unseen regions cost little.** Holding out a whole region lowers median NSE
from 0.762 to 0.723 at 1 day, and by less at longer leads. The median loss
per catchment is 0.019.

**An unseen climate costs much more.** On the drier catchments, the model
trained only on wetter ones scores NSE 0.752 where the model trained on
everything scores 0.850. The random-half control loses about 0.03. Low-flow
CSI falls from 0.659 to 0.414.

**Warnings from quantiles repair the failure, narrowly.**

| 7 days ahead | High-flow CSI | Low-flow CSI |
| --- | ---: | ---: |
| Persistence | 0.138 | 0.389 |
| Single-number model | 0.005 | 0.173 |
| Persistence band | 0.155 | 0.412 |
| Quantile model | 0.175 | 0.426 |

- At 3 days the quantile model and the persistence band tie for high flow
  (0.225 and 0.229).
- The clearer gain is at the start of events: at 3 days the quantile model
  catches 54% of high-flow onsets against 39% for the band.
- Most multi-day high-flow warnings are false alarms: 75 to 80% for the
  quantile model, and 64% to 82% for the two persistence baselines.

**The 90% range is honest where the model was trained, less so elsewhere.**
After calibration, coverage on seen catchments is 0.90 to 0.91 at every lead.
On unseen regions the median catchment is close to target (0.89 to 0.90), but
14 to 18% of catchments get a range that covers under 80% of days.

## 5. What failed, and what is uncertain

- The first explanation for a weak baseline (training stopped too early) was
  wrong. A controlled comparison on validation years showed the target scale
  was the cause. Both are in `LOG.md`.
- Twelve of 51 quantile models hit the 1,000-tree limit and are
  under-trained.
- The uncertainty experiment used one random seed.
- The first ignore rule would have committed about 1.5 GB of raw outputs. It
  was caught before the first commit.

## 6. Limitations

- "Unseen" is not "ungauged". Recent flow at the catchment is still an
  input, so this does not show the model works where there is no gauge.
- The regional and quantile models use a 20% sample of training days and
  settings that were not tuned.
- Coverage during floods specifically has not been checked. An interval can
  be right on average and wrong when it matters.
- No comparison with a neural sequence model, which is the standard method in
  this field. That needs a GPU and has not been run.
- The results come from one run in one environment.

## 7. Related work

Not written. It needs the papers to be read in full first. Only two sources
were consulted while building this study: the CAMELS-GB v2 dataset record,
and part of Lees et al. (2021), which reports simulation (weather known up to
the target day) and so is not directly comparable with the forecasts here.

## 8. What would come next

- The neural sequence model, on the same splits and scores.
- Gaps in the inputs: how forecasts and intervals degrade when recent flow or
  weather is missing.
- Coverage by flow level, and intervals that widen on unfamiliar catchments.
- Real weather forecasts as inputs, in place of the perfect-forecast bound.
