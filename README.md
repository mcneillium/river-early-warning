# River early warning across 671 British catchments

**Status:** done so far: data, metrics and baselines (week 1); the baseline
repair and the unseen-region experiment with a regional boosting model
(week 2); quantile forecasts, conformal calibration and quantile-based
warnings (Experiment 5). The regional LSTM (Experiment 6) has had its first run: it is no better than
regional boosting at any lead time. A like-for-like rescoring is still owed.
Still to come: gaps in the inputs, explanations. A first report is in
`docs/report.md`.

## Question

How far ahead can river flow, and flood or low-flow warnings, be forecast
without knowing future weather, and does that skill (and the model's sense of
its own uncertainty) carry over to places it was not trained on?

<!-- TODO (Paul): rewrite the question in your own words. -->

## What I expected to find

No prediction was written down before the results existed, so none is claimed
here. For the experiments still to come (the neural model, gaps in the
inputs), write a dated prediction before running them.

## The setup in brief

- **Data:** CAMELS-GB v2, daily river flow and weather for 671 catchments,
  October 1970 to September 2022. See `CITATION.md`.
- **Task:** on day t, forecast river flow on day t + 1, t + 3 and t + 7.
- **Honesty rule:** a forecast may use only what is known at the end of day t.
  No future rainfall or temperature. One clearly labelled "perfect forecast"
  variant breaks this rule on purpose, to show how much skill a perfect
  weather forecast would add. It is an upper bound, never the headline.
- **Splits (water years):** train 1 Oct 1970 to 30 Sep 2004, validation to
  30 Sep 2012, test to 30 Sep 2022. Fixed in `splits/splits_v1.json`.
- **Warnings:** a high-flow day is flow above the catchment's 95th percentile;
  a low-flow day is below its 10th. Both percentiles come from the training
  years only.

## Baselines (week 1)

| Model | What it does |
| --- | --- |
| `persistence` | Flow on the target day = flow on the day the forecast is issued |
| `seasonal` | Flow on the target day = the usual flow for that day of the year |
| `gbm` | Gradient boosting, one model per catchment and lead time, 3 seeds |
| `gbm_perfect_forecast` | The same, given observed weather over the forecast window. Upper bound only |

## Scores

- **NSE** and **KGE** (original 2009 form) for the flow forecast itself.
- **Hit rate, false alarm ratio, critical success index** for high-flow and
  low-flow warnings.
- **Onset hit rate:** the same, but only on the first day of each event. This
  is where early warning matters, and where "same as today" cannot help.

All models are scored on exactly the same days. Results are reported as the
median across catchments, never as one pooled score.

## Reproduce

```
conda env create -f environment.yml
conda activate rew
pip install -e .[dev]

python -m rew.download --dest data     # about 790 MB, no login needed
pytest                                 # 91 tests (83 if PyTorch is not installed)
python scripts/run_baselines.py        # week 1: results/table_baselines.*

# week 2 (protocol in docs/protocol_week2.md)
pip install -e .[analysis]
python scripts/run_gbm_variants.py     # results/table_baselines_v2.*
python scripts/run_regional.py         # results/table_regional.*  (then --seed 1, --seed 2)
python scripts/summarise_regional_seeds.py
python scripts/analyse_regional.py     # figures/ and results/table_gap_correlations.csv

# Experiment 5 (protocol in docs/protocol_week3.md). About 3 hours on 2 cores.
# Do not run the next two at the same time on a machine with 8 GB or less.
python scripts/run_quantiles.py        # results/raw_quantiles/
python scripts/score_quantiles.py      # results/table_quantile_warnings.*, table_interval_coverage.*
python scripts/plot_quantiles.py       # figures/warnings_by_lead.png, interval_coverage.png
```

The baseline run is resumable: forecasts are saved per catchment under
`results/raw/`, and a restarted run skips catchments that are already done.

### Experiment 6: the regional LSTM (needs a GPU)

Protocol: `docs/protocol_week4.md`. First run: 14 November 2026, about 11
minutes for three seeds on an RTX 5090.

```bash
# PyTorch built for CUDA 12.8. RTX 50-series cards need this build or newer.
pip install torch --index-url https://download.pytorch.org/whl/cu128
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"

python scripts/run_lstm.py --smoke     # two-minute check of the code, CPU is fine
python scripts/run_lstm.py             # three seeds, all catchments
python scripts/run_lstm.py --unseen    # adds the unseen-region test (five times the cost)
```

The version printed must end in `+cu128` (or a newer CUDA build) and the
second value must be `True`. Run `scripts/run_regional.py` first if
`results/raw_regional/` is missing: the LSTM is then scored beside the
regional boosting model on identical days. Finished models are not trained
again, so the script can be stopped and restarted.

## Results

Week 1 tables are in `results/`:

- `table_baselines.md`: headline medians, readable
- `table_baselines.csv`: every metric with quartiles and seed spread
- `per_catchment_baselines.csv`: one row per catchment, lead, model and seed

Week 2 tables and figures:

- `table_gbm_variants_validation.csv` and `gbm_variant_choice.json`: how the
  repaired baseline was chosen, on validation years only
- `table_baselines_v2.md`: test scores with the chosen variant beside week 1
- `table_regional.md`: the regional model on seen and unseen catchments
- `table_regional_by_region.csv`, `table_wet_to_dry.csv`, `table_regional_seeds.csv`
- `table_gap_correlations.csv`: which catchment descriptors go with a large loss
- `figures/unseen_gap_map.png`, `figures/regions_map.png`

Experiment 5 tables and figures:

- `table_quantile_warnings.md`: warnings from quantiles against three baselines
- `table_interval_coverage.md`: how honest the 90% range is, seen and unseen
- `table_quantile_reliability.csv`, `quantile_tau_choice.json`
- `figures/warnings_by_lead.png`, `figures/interval_coverage.png`

### Experiment 6: a regional LSTM (first run)

Median NSE on the test years, mean of three seeds.

| Model | 1 day | 3 days | 7 days |
| --- | ---: | ---: | ---: |
| Regional boosting (Experiment 3) | 0.763 | 0.375 | 0.235 |
| Regional LSTM | 0.734 | 0.377 | 0.239 |

- Against the rule fixed in the protocol (within 0.01, or below, means "no
  better"), the LSTM is no better at any lead, and is worse at 1 day.
- As a warning system it fails in the same way: high-flow CSI at 7 days is
  0.005 for both models.
- The two rows come from separate scoring runs. Persistence scores the same
  to four decimals in both, so the days almost certainly match, but the
  paired comparison on identical days has not been made yet.
- Validation loss was lowest after 1 or 2 epochs in every seed and rose
  afterwards, so this fixed configuration overfits early. A tuned LSTM
  could do better. Nothing was tuned, and nothing was chosen on test years.

## Where things are

```
configs/splits.yaml      split boundaries and minimum data rules
splits/splits_v1.json    the fixed splits, with a fingerprint
splits/spatial_folds_v1.json  the five regions, with a fingerprint
src/rew/download.py      fetch the data and record checksums
src/rew/load.py          read the daily files into one tidy table
src/rew/splits.py        build the splits once, refuse to overwrite
src/rew/thresholds.py    warning thresholds from training years only
src/rew/features.py      model inputs; the no-future-information rule lives here
src/rew/metrics.py       NSE, KGE and the warning scores
src/rew/evaluate.py      score all models on the same days
src/rew/baselines/       persistence, seasonal average, gradient boosting
src/rew/spatial.py       five geographic regions, saved once
src/rew/regional.py      one boosting model for all catchments
scripts/run_baselines.py one command that produces the week 1 tables
scripts/run_gbm_variants.py   baseline repair, chosen on validation years
scripts/run_regional.py       seen against unseen catchments
scripts/analyse_regional.py   maps and descriptor correlations
src/rew/quantile.py      quantile models, conformal calibration, quantile warnings
scripts/run_quantiles.py      fit the quantile models (slow, resumable)
scripts/score_quantiles.py    score them (fast)
scripts/plot_quantiles.py     the two Experiment 5 figures
docs/protocol_week2.md   the week 2 plan, written before it was run
docs/protocol_week3.md   the Experiment 5 plan, written before it was run
tests/                   hand-worked metric cases, leak tests, data checks
LOG.md                   every decision and run, including what went wrong
```

## Status of this work

Author: Paul McNeill. This is work in progress and has not been peer reviewed.
Choices made during the unattended runs are listed in `LOG.md` (A1 to A13,
B1 to B9, C1 to C8). As of 13 November 2026 I have not yet re-run the study on
my own machine or confirmed those choices.

<!-- TODO (Paul): restore a statement of how any AI tools were used before this goes to anyone else, and keep it accurate. -->
