Median across catchments, test period (water years 2013 to 2022). No future weather.
`regional_point` is the single-number regional model of Experiment 3.
`persistence_band` and `quantile_model` warn when a chosen forecast quantile crosses the threshold;
the quantile was chosen on the calibration half (2009 to 2012) only.
CSI = critical success index; FAR = false alarm ratio (share of warnings that were wrong).

**Lead 1 day** (quantile model warns on 0.75 for high flow, 0.5 for low flow; persistence band on 0.5 and 0.5)

| Model | High CSI | High hit rate | High FAR | High onset hit rate | Low CSI | Low hit rate | Low FAR | Low onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.414 | 0.585 | 0.415 | 0.000 | 0.754 | 0.859 | 0.140 | 0.000 |
| regional_point | 0.566 | 0.683 | 0.215 | 0.343 | 0.728 | 0.830 | 0.120 | 0.316 |
| persistence_band | 0.413 | 0.576 | 0.405 | 0.000 | 0.710 | 0.961 | 0.256 | 0.710 |
| quantile_model | 0.562 | 0.765 | 0.322 | 0.484 | 0.788 | 0.932 | 0.162 | 0.625 |

**Lead 3 days** (quantile model warns on 0.9 for high flow, 0.5 for low flow; persistence band on 0.9 and 0.5)

| Model | High CSI | High hit rate | High FAR | High onset hit rate | Low CSI | Low hit rate | Low FAR | Low onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.223 | 0.365 | 0.635 | 0.165 | 0.545 | 0.705 | 0.292 | 0.250 |
| regional_point | 0.134 | 0.154 | 0.389 | 0.033 | 0.385 | 0.429 | 0.200 | 0.087 |
| persistence_band | 0.229 | 0.592 | 0.721 | 0.387 | 0.541 | 0.887 | 0.402 | 0.571 |
| quantile_model | 0.225 | 0.723 | 0.752 | 0.536 | 0.583 | 0.797 | 0.304 | 0.375 |

**Lead 7 days** (quantile model warns on 0.9 for high flow, 0.25 for low flow; persistence band on 0.9 and 0.5)

| Model | High CSI | High hit rate | High FAR | High onset hit rate | Low CSI | Low hit rate | Low FAR | Low onset hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| persistence | 0.138 | 0.242 | 0.758 | 0.143 | 0.389 | 0.556 | 0.436 | 0.325 |
| regional_point | 0.005 | 0.005 | 0.475 | 0.000 | 0.173 | 0.189 | 0.299 | 0.081 |
| persistence_band | 0.155 | 0.518 | 0.816 | 0.381 | 0.410 | 0.749 | 0.514 | 0.542 |
| quantile_model | 0.175 | 0.632 | 0.802 | 0.492 | 0.426 | 0.867 | 0.540 | 0.700 |
