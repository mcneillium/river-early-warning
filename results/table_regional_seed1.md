Median across catchments, test period (water years 2013 to 2022). No future weather in any model.
`gbm_local` is the per-catchment model (`log_es100`). `regional_seen` was trained on every catchment.
`regional_unseen` forecasts each region with a model trained on the other four regions only.

**Lead 1 day**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.509 | 0.754 | 0.414 | 0.000 | 0.754 | 0.000 |
| gbm_local | 0.755 | 0.747 | 0.570 | 0.351 | 0.730 | 0.356 |
| regional_seen | 0.767 | 0.764 | 0.568 | 0.348 | 0.723 | 0.308 |
| regional_unseen | 0.725 | 0.725 | 0.524 | 0.352 | 0.706 | 0.286 |

**Lead 3 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.066 | 0.533 | 0.223 | 0.165 | 0.545 | 0.250 |
| gbm_local | 0.360 | 0.360 | 0.093 | 0.009 | 0.256 | 0.023 |
| regional_seen | 0.376 | 0.393 | 0.134 | 0.031 | 0.380 | 0.091 |
| regional_unseen | 0.367 | 0.388 | 0.130 | 0.029 | 0.385 | 0.086 |

**Lead 7 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | -0.235 | 0.385 | 0.138 | 0.143 | 0.389 | 0.325 |
| gbm_local | 0.212 | 0.174 | 0.000 | 0.000 | 0.000 | 0.000 |
| regional_seen | 0.237 | 0.226 | 0.000 | 0.000 | 0.155 | 0.070 |
| regional_unseen | 0.225 | 0.217 | 0.000 | 0.000 | 0.141 | 0.068 |

**Gap for unseen catchments (unseen minus seen, per catchment)**

| Lead (days) | Score | Median gap | Middle half of catchments | Share of catchments worse when unseen |
| ---: | --- | ---: | --- | ---: |
| 1 | high_csi | -0.023 | -0.055 to -0.005 | 78% |
| 1 | low_csi | -0.013 | -0.054 to +0.017 | 60% |
| 1 | nse | -0.019 | -0.041 to -0.005 | 87% |
| 3 | high_csi | +0.000 | -0.018 to +0.015 | 40% |
| 3 | low_csi | -0.002 | -0.044 to +0.029 | 51% |
| 3 | nse | -0.004 | -0.017 to +0.004 | 62% |
| 7 | high_csi | +0.000 | +0.000 to +0.005 | 24% |
| 7 | low_csi | +0.000 | -0.033 to +0.025 | 48% |
| 7 | nse | -0.006 | -0.020 to +0.003 | 67% |
