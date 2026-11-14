Median across catchments, test period (water years 2013 to 2022). No future weather in any model.
`gbm_local` is the per-catchment model (`log_es100`). `regional_seen` was trained on every catchment.
`regional_unseen` forecasts each region with a model trained on the other four regions only.

**Lead 1 day**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.509 | 0.754 | 0.414 | 0.000 | 0.754 | 0.000 |
| gbm_local | 0.755 | 0.747 | 0.570 | 0.351 | 0.730 | 0.356 |
| regional_seen | 0.762 | 0.758 | 0.566 | 0.347 | 0.731 | 0.323 |
| regional_unseen | 0.723 | 0.718 | 0.517 | 0.343 | 0.708 | 0.286 |

**Lead 3 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.066 | 0.533 | 0.223 | 0.165 | 0.545 | 0.250 |
| gbm_local | 0.360 | 0.360 | 0.093 | 0.009 | 0.256 | 0.023 |
| regional_seen | 0.375 | 0.398 | 0.134 | 0.033 | 0.385 | 0.087 |
| regional_unseen | 0.368 | 0.390 | 0.135 | 0.031 | 0.385 | 0.086 |

**Lead 7 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | -0.235 | 0.385 | 0.138 | 0.143 | 0.389 | 0.325 |
| gbm_local | 0.212 | 0.174 | 0.000 | 0.000 | 0.000 | 0.000 |
| regional_seen | 0.236 | 0.233 | 0.005 | 0.000 | 0.173 | 0.081 |
| regional_unseen | 0.222 | 0.217 | 0.000 | 0.000 | 0.141 | 0.065 |

**Gap for unseen catchments (unseen minus seen, per catchment)**

| Lead (days) | Score | Median gap | Middle half of catchments | Share of catchments worse when unseen |
| ---: | --- | ---: | --- | ---: |
| 1 | high_csi | -0.023 | -0.054 to -0.003 | 78% |
| 1 | low_csi | -0.012 | -0.048 to +0.013 | 61% |
| 1 | nse | -0.019 | -0.040 to -0.006 | 86% |
| 3 | high_csi | +0.000 | -0.021 to +0.013 | 42% |
| 3 | low_csi | +0.000 | -0.036 to +0.032 | 46% |
| 3 | nse | -0.004 | -0.018 to +0.003 | 66% |
| 7 | high_csi | +0.000 | -0.004 to +0.004 | 29% |
| 7 | low_csi | -0.008 | -0.051 to +0.014 | 54% |
| 7 | nse | -0.008 | -0.024 to +0.001 | 73% |
