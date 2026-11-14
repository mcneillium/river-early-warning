Median across catchments, test period (water years 2013 to 2022). No future weather in any model.
`gbm_local` is the per-catchment model (`log_es100`). `regional_seen` was trained on every catchment.
`regional_unseen` forecasts each region with a model trained on the other four regions only.

**Lead 1 day**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.509 | 0.754 | 0.414 | 0.000 | 0.754 | 0.000 |
| gbm_local | 0.755 | 0.747 | 0.570 | 0.351 | 0.730 | 0.356 |
| regional_seen | 0.761 | 0.764 | 0.566 | 0.349 | 0.726 | 0.300 |
| regional_unseen | 0.725 | 0.716 | 0.514 | 0.343 | 0.702 | 0.264 |

**Lead 3 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.066 | 0.533 | 0.223 | 0.165 | 0.545 | 0.250 |
| gbm_local | 0.360 | 0.360 | 0.093 | 0.009 | 0.256 | 0.023 |
| regional_seen | 0.375 | 0.392 | 0.133 | 0.028 | 0.385 | 0.083 |
| regional_unseen | 0.367 | 0.388 | 0.134 | 0.029 | 0.383 | 0.087 |

**Lead 7 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | -0.235 | 0.385 | 0.138 | 0.143 | 0.389 | 0.325 |
| gbm_local | 0.212 | 0.174 | 0.000 | 0.000 | 0.000 | 0.000 |
| regional_seen | 0.232 | 0.218 | 0.000 | 0.000 | 0.147 | 0.062 |
| regional_unseen | 0.224 | 0.217 | 0.000 | 0.000 | 0.145 | 0.071 |

**Gap for unseen catchments (unseen minus seen, per catchment)**

| Lead (days) | Score | Median gap | Middle half of catchments | Share of catchments worse when unseen |
| ---: | --- | ---: | --- | ---: |
| 1 | high_csi | -0.025 | -0.054 to -0.003 | 78% |
| 1 | low_csi | -0.010 | -0.054 to +0.014 | 60% |
| 1 | nse | -0.018 | -0.041 to -0.006 | 84% |
| 3 | high_csi | +0.000 | -0.014 to +0.015 | 36% |
| 3 | low_csi | -0.001 | -0.040 to +0.028 | 51% |
| 3 | nse | -0.005 | -0.016 to +0.003 | 66% |
| 7 | high_csi | +0.000 | +0.000 to +0.009 | 20% |
| 7 | low_csi | +0.000 | -0.015 to +0.030 | 35% |
| 7 | nse | -0.004 | -0.019 to +0.005 | 62% |
