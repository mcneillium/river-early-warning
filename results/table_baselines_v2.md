Median across catchments, test period (water years 2013 to 2022).
`gbm` is the week 1 baseline. `gbm_selected` is the variant `log_es100`, chosen on validation years only.
`gbm_perfect_forecast` sees observed weather over the forecast window: an upper bound, not a forecast.

**Lead 1 day**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.509 | 0.754 | 0.414 | 0.000 | 0.754 | 0.000 |
| seasonal | 0.167 | 0.133 | 0.000 | 0.000 | 0.000 | 0.000 |
| gbm | 0.761 | 0.779 | 0.566 | 0.394 | 0.543 | 0.172 |
| gbm_selected | 0.756 | 0.745 | 0.571 | 0.345 | 0.729 | 0.359 |
| gbm_perfect_forecast | 0.865 | 0.868 | 0.665 | 0.640 | 0.692 | 0.565 |

**Lead 3 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.066 | 0.533 | 0.223 | 0.165 | 0.545 | 0.250 |
| seasonal | 0.167 | 0.133 | 0.000 | 0.000 | 0.000 | 0.000 |
| gbm | 0.380 | 0.408 | 0.148 | 0.043 | 0.000 | 0.000 |
| gbm_selected | 0.362 | 0.354 | 0.091 | 0.010 | 0.250 | 0.026 |
| gbm_perfect_forecast | 0.810 | 0.829 | 0.588 | 0.547 | 0.598 | 0.400 |

**Lead 7 days**

| Model | NSE | KGE | High-flow CSI | High-flow onset hit rate | Low-flow CSI | Low-flow onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | -0.235 | 0.385 | 0.138 | 0.143 | 0.389 | 0.325 |
| seasonal | 0.167 | 0.133 | 0.000 | 0.000 | 0.000 | 0.000 |
| gbm | 0.242 | 0.238 | 0.002 | 0.000 | 0.000 | 0.000 |
| gbm_selected | 0.210 | 0.173 | 0.000 | 0.000 | 0.000 | 0.000 |
| gbm_perfect_forecast | 0.722 | 0.757 | 0.481 | 0.462 | 0.500 | 0.306 |
