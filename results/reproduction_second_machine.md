# Reproduction on a second machine, 14 November 2026

The tables in this folder come from the first run (Linux, 2 CPU cores,
Python 3.13). On 14 November 2026 Paul McNeill re-ran weeks 1 and 2 and all
three seeds of Experiment 3 on a second machine (Windows, Python 3.14.7,
LightGBM 4.7.0, NumPy 2.5.4, pandas 3.1.1) from commit `b684425`, with the
same saved splits. The first-run tables are kept as the published record.
This file states how far the second run agrees with them.

| Part | Compared | Largest difference |
| --- | --- | --- |
| Week 1 baselines (persistence, climatology, per-catchment boosting, upper bound) | Every median in `table_baselines.csv` | 4e-16 (identical) |
| Week 2 boosting variants | Every median in `table_baselines_v2.csv` | 4e-16 (identical) |
| Per-catchment boosting inside Experiment 3 | NSE of each catchment and lead | 0 (identical) |
| Regional boosting, seen and unseen | Median NSE, KGE, high-flow and low-flow CSI, each seed and lead | 0.006 |
| Wet-to-dry transfer and its control | The same four medians, each seed and lead | 0.013 (one low-flow CSI); 0.007 otherwise |

The regional models are not bit-for-bit repeatable across the two machines.
For single catchments the NSE of the regional model differs by less than
0.011 in 99% of cases; the largest single difference is 0.27 (one unseen
catchment). The cause has not been investigated.

Headline numbers, mean of three seeds, first run then second run:

| Quantity | First run | Second run |
| --- | ---: | ---: |
| Regional, seen catchments, NSE at 1 / 3 / 7 days | 0.763 / 0.375 / 0.235 | 0.764 / 0.375 / 0.235 |
| Regional, unseen regions, NSE at 1 / 3 / 7 days | 0.724 / 0.367 / 0.224 | 0.723 / 0.367 / 0.224 |
| Trained on all catchments, tested on dry, NSE at 1 day | 0.850 | 0.849 |
| Trained on wet only, tested on dry, NSE at 1 day | 0.752 | 0.752 |
| Trained on a random half, tested on dry, NSE at 1 day | 0.821 | 0.821 |
| Low-flow CSI, all catchments then wet only, 1 day | 0.659 then 0.414 | 0.660 then 0.409 |

No conclusion changes. Experiment 5 (quantiles and intervals) has not been
re-run on the second machine.

The LSTM tables (`table_lstm.*`, `per_catchment_lstm.csv`) come from the
second machine only. The regional boosting row in them is the second-machine
fit, which is why it reads 0.764 where `table_regional_seeds.csv` gives
0.763.
