# Experiment 7 results

## Predictions recorded before the run

| Subset | Model | Reference | Lead | Predicted | Observed | Met |
| --- | --- | --- | ---: | --- | ---: | --- |
| all | chronos2_flow_only | lstm_seen | 1 | between -0.05 and +0.01 | -0.129 | no |
| all | chronos2_flow_only | lstm_seen | 3 | -0.03 or lower | -0.073 | yes |
| all | chronos2_flow_only | lstm_seen | 7 | -0.05 or lower | -0.083 | yes |
| all | chronos2_weather | chronos2_flow_only | 1 | at least +0.01 | -0.000 | no |
| all | chronos2_weather | chronos2_flow_only | 3 | less than +0.01 | -0.000 | yes |
| all | chronos2_weather | chronos2_flow_only | 7 | less than +0.01 | -0.001 | yes |
| dry | chronos2_weather | lstm_wet_only | 1 | more than +0.01 | +0.013 | yes |

Dry subset at 3 and 7 days: secondary, no directional prediction.

### All catchments

Scores averaged over the three trained-model seeds per catchment, then the median across catchments. CSI and hit rates: median of the catchments where the score is defined; zero and undefined counted separately.

| Lead | Model | Catchments | NSE | High CSI | High hit rate | High FAR | High onset hit rate | Low CSI (zero / undefined) | Low hit rate | Low FAR | Low onset hit rate |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | chronos2_flow_only | 659 | 0.570 | 0.376 | 0.452 | 0.298 | 0.000 | 0.632 (11 / 23) | 0.762 | 0.176 | 0.244 |
| 1 | chronos2_weather | 659 | 0.577 | 0.403 | 0.500 | 0.331 | 0.014 | 0.593 (16 / 24) | 0.685 | 0.154 | 0.163 |
| 1 | lstm_seen | 659 | 0.736 | 0.528 | 0.628 | 0.218 | 0.291 | 0.606 (23 / 11) | 0.790 | 0.205 | 0.453 |
| 1 | persistence | 659 | 0.509 | 0.414 | 0.585 | 0.415 | 0.000 | 0.754 (4 / 28) | 0.859 | 0.140 | 0.000 |
| 1 | regional_seen | 659 | 0.762 | 0.566 | 0.682 | 0.213 | 0.349 | 0.725 (18 / 17) | 0.830 | 0.121 | 0.320 |
| 3 | chronos2_flow_only | 659 | 0.292 | 0.111 | 0.124 | 0.478 | 0.029 | 0.488 (15 / 23) | 0.645 | 0.305 | 0.278 |
| 3 | chronos2_weather | 659 | 0.294 | 0.125 | 0.146 | 0.500 | 0.036 | 0.450 (18 / 23) | 0.556 | 0.280 | 0.200 |
| 3 | lstm_seen | 659 | 0.376 | 0.129 | 0.145 | 0.382 | 0.027 | 0.312 (39 / 16) | 0.367 | 0.200 | 0.095 |
| 3 | persistence | 659 | 0.066 | 0.223 | 0.365 | 0.635 | 0.165 | 0.545 (6 / 28) | 0.705 | 0.292 | 0.250 |
| 3 | regional_seen | 659 | 0.374 | 0.131 | 0.149 | 0.400 | 0.033 | 0.383 (29 / 20) | 0.436 | 0.201 | 0.090 |
| 7 | chronos2_flow_only | 659 | 0.144 | 0.025 | 0.027 | 0.562 | 0.010 | 0.374 (21 / 19) | 0.542 | 0.440 | 0.326 |
| 7 | chronos2_weather | 659 | 0.147 | 0.028 | 0.029 | 0.601 | 0.012 | 0.338 (21 / 22) | 0.441 | 0.411 | 0.241 |
| 7 | lstm_seen | 659 | 0.240 | 0.007 | 0.008 | 0.437 | 0.000 | 0.147 (69 / 21) | 0.181 | 0.304 | 0.093 |
| 7 | persistence | 659 | -0.235 | 0.138 | 0.242 | 0.758 | 0.143 | 0.389 (9 / 28) | 0.556 | 0.436 | 0.325 |
| 7 | regional_seen | 659 | 0.236 | 0.002 | 0.002 | 0.486 | 0.000 | 0.152 (73 / 23) | 0.170 | 0.298 | 0.072 |

Paired NSE differences (model minus reference), per catchment on identical valid dates, averaged over seeds, median across catchments. Margin 0.01; the band is not an equivalence test.

| Lead | Model | Reference | Median difference | Model better in | Catchments | Interpretation |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | chronos2_flow_only | lstm_seen | -0.129 | 15% | 659 | worse by more than the margin |
| 1 | chronos2_weather | lstm_seen | -0.134 | 14% | 659 | worse by more than the margin |
| 1 | chronos2_weather | chronos2_flow_only | -0.000 | 47% | 659 | within the practical comparison band |
| 1 | chronos2_flow_only | regional_seen | -0.148 | 12% | 659 | worse by more than the margin |
| 1 | chronos2_weather | regional_seen | -0.150 | 11% | 659 | worse by more than the margin |
| 1 | chronos2_flow_only | persistence | +0.062 | 88% | 659 | exceeds the improvement margin |
| 1 | chronos2_weather | persistence | +0.064 | 88% | 659 | exceeds the improvement margin |
| 3 | chronos2_flow_only | lstm_seen | -0.073 | 7% | 659 | worse by more than the margin |
| 3 | chronos2_weather | lstm_seen | -0.076 | 7% | 659 | worse by more than the margin |
| 3 | chronos2_weather | chronos2_flow_only | -0.000 | 50% | 659 | within the practical comparison band |
| 3 | chronos2_flow_only | regional_seen | -0.074 | 10% | 659 | worse by more than the margin |
| 3 | chronos2_weather | regional_seen | -0.075 | 9% | 659 | worse by more than the margin |
| 3 | chronos2_flow_only | persistence | +0.234 | 96% | 659 | exceeds the improvement margin |
| 3 | chronos2_weather | persistence | +0.234 | 96% | 659 | exceeds the improvement margin |
| 7 | chronos2_flow_only | lstm_seen | -0.083 | 5% | 659 | worse by more than the margin |
| 7 | chronos2_weather | lstm_seen | -0.084 | 5% | 659 | worse by more than the margin |
| 7 | chronos2_weather | chronos2_flow_only | -0.001 | 47% | 659 | within the practical comparison band |
| 7 | chronos2_flow_only | regional_seen | -0.082 | 8% | 659 | worse by more than the margin |
| 7 | chronos2_weather | regional_seen | -0.084 | 8% | 659 | worse by more than the margin |
| 7 | chronos2_flow_only | persistence | +0.374 | 96% | 659 | exceeds the improvement margin |
| 7 | chronos2_weather | persistence | +0.378 | 97% | 659 | exceeds the improvement margin |

### The 167 dry catchments of the wet-to-dry test

Scores averaged over the three trained-model seeds per catchment, then the median across catchments. CSI and hit rates: median of the catchments where the score is defined; zero and undefined counted separately.

| Lead | Model | Catchments | NSE | High CSI | High hit rate | High FAR | High onset hit rate | Low CSI (zero / undefined) | Low hit rate | Low FAR | Low onset hit rate |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| 1 | chronos2_flow_only | 167 | 0.706 | 0.533 | 0.614 | 0.214 | 0.018 | 0.650 (4 / 10) | 0.827 | 0.221 | 0.310 |
| 1 | chronos2_weather | 167 | 0.703 | 0.537 | 0.644 | 0.237 | 0.027 | 0.627 (5 / 11) | 0.764 | 0.191 | 0.211 |
| 1 | lstm_seen | 167 | 0.799 | 0.614 | 0.718 | 0.176 | 0.359 | 0.484 (8 / 7) | 0.775 | 0.310 | 0.517 |
| 1 | lstm_wet_only | 167 | 0.638 | 0.500 | 0.647 | 0.239 | 0.315 | 0.000 (114 / 11) | 0.000 | 0.060 | 0.000 |
| 1 | persistence | 167 | 0.673 | 0.530 | 0.693 | 0.307 | 0.000 | 0.717 (2 / 12) | 0.834 | 0.162 | 0.000 |
| 1 | regional_seen | 167 | 0.850 | 0.660 | 0.763 | 0.175 | 0.420 | 0.656 (7 / 8) | 0.825 | 0.191 | 0.349 |
| 1 | regional_wet_only | 167 | 0.752 | 0.574 | 0.765 | 0.251 | 0.493 | 0.405 (36 / 6) | 0.523 | 0.227 | 0.091 |
| 3 | chronos2_flow_only | 167 | 0.405 | 0.204 | 0.237 | 0.380 | 0.037 | 0.503 (6 / 10) | 0.693 | 0.333 | 0.333 |
| 3 | chronos2_weather | 167 | 0.401 | 0.243 | 0.297 | 0.402 | 0.043 | 0.480 (5 / 10) | 0.637 | 0.307 | 0.256 |
| 3 | lstm_seen | 167 | 0.483 | 0.279 | 0.326 | 0.325 | 0.057 | 0.306 (13 / 7) | 0.397 | 0.264 | 0.159 |
| 3 | lstm_wet_only | 167 | 0.314 | 0.215 | 0.300 | 0.414 | 0.056 | 0.000 (139 / 11) | 0.000 | 0.120 | 0.000 |
| 3 | persistence | 167 | 0.234 | 0.300 | 0.462 | 0.538 | 0.153 | 0.525 (3 / 12) | 0.686 | 0.311 | 0.271 |
| 3 | regional_seen | 167 | 0.486 | 0.279 | 0.337 | 0.347 | 0.061 | 0.379 (11 / 9) | 0.452 | 0.248 | 0.120 |
| 3 | regional_wet_only | 167 | 0.408 | 0.304 | 0.464 | 0.506 | 0.160 | 0.188 (59 / 11) | 0.216 | 0.244 | 0.044 |
| 7 | chronos2_flow_only | 167 | 0.254 | 0.071 | 0.077 | 0.500 | 0.020 | 0.397 (8 / 8) | 0.593 | 0.436 | 0.400 |
| 7 | chronos2_weather | 167 | 0.256 | 0.080 | 0.087 | 0.523 | 0.027 | 0.375 (6 / 10) | 0.507 | 0.405 | 0.314 |
| 7 | lstm_seen | 167 | 0.333 | 0.076 | 0.086 | 0.413 | 0.023 | 0.178 (16 / 10) | 0.264 | 0.340 | 0.130 |
| 7 | lstm_wet_only | 167 | 0.194 | 0.063 | 0.085 | 0.525 | 0.027 | 0.000 (141 / 11) | 0.000 | 0.334 | 0.000 |
| 7 | persistence | 167 | -0.060 | 0.190 | 0.320 | 0.682 | 0.162 | 0.394 (4 / 12) | 0.559 | 0.430 | 0.360 |
| 7 | regional_seen | 167 | 0.317 | 0.078 | 0.085 | 0.459 | 0.028 | 0.184 (25 / 10) | 0.216 | 0.332 | 0.098 |
| 7 | regional_wet_only | 167 | 0.245 | 0.169 | 0.295 | 0.627 | 0.140 | 0.000 (87 / 11) | 0.000 | 0.245 | 0.000 |

Paired NSE differences (model minus reference), per catchment on identical valid dates, averaged over seeds, median across catchments. Margin 0.01; the band is not an equivalence test.

| Lead | Model | Reference | Median difference | Model better in | Catchments | Interpretation |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | chronos2_weather | lstm_wet_only | +0.013 | 52% | 167 | exceeds the improvement margin |
| 1 | chronos2_flow_only | lstm_wet_only | +0.010 | 52% | 167 | exceeds the improvement margin |
| 1 | chronos2_weather | regional_wet_only | -0.100 | 35% | 167 | worse by more than the margin |
| 1 | chronos2_flow_only | regional_wet_only | -0.094 | 36% | 167 | worse by more than the margin |
| 1 | chronos2_weather | lstm_seen | -0.114 | 25% | 167 | worse by more than the margin |
| 1 | chronos2_weather | regional_seen | -0.137 | 20% | 167 | worse by more than the margin |
| 1 | chronos2_weather | chronos2_flow_only | -0.000 | 46% | 167 | within the practical comparison band |
| 1 | chronos2_weather | persistence | +0.026 | 80% | 167 | exceeds the improvement margin |
| 3 | chronos2_weather | lstm_wet_only | +0.005 | 53% | 167 | within the practical comparison band |
| 3 | chronos2_flow_only | lstm_wet_only | +0.005 | 52% | 167 | within the practical comparison band |
| 3 | chronos2_weather | regional_wet_only | -0.059 | 32% | 167 | worse by more than the margin |
| 3 | chronos2_flow_only | regional_wet_only | -0.061 | 31% | 167 | worse by more than the margin |
| 3 | chronos2_weather | lstm_seen | -0.070 | 12% | 167 | worse by more than the margin |
| 3 | chronos2_weather | regional_seen | -0.070 | 14% | 167 | worse by more than the margin |
| 3 | chronos2_weather | chronos2_flow_only | +0.000 | 52% | 167 | within the practical comparison band |
| 3 | chronos2_weather | persistence | +0.175 | 95% | 167 | exceeds the improvement margin |
| 7 | chronos2_weather | lstm_wet_only | -0.013 | 46% | 167 | worse by more than the margin |
| 7 | chronos2_flow_only | lstm_wet_only | -0.013 | 45% | 167 | worse by more than the margin |
| 7 | chronos2_weather | regional_wet_only | -0.063 | 34% | 167 | worse by more than the margin |
| 7 | chronos2_flow_only | regional_wet_only | -0.062 | 35% | 167 | worse by more than the margin |
| 7 | chronos2_weather | lstm_seen | -0.079 | 9% | 167 | worse by more than the margin |
| 7 | chronos2_weather | regional_seen | -0.077 | 14% | 167 | worse by more than the margin |
| 7 | chronos2_weather | chronos2_flow_only | +0.001 | 52% | 167 | within the practical comparison band |
| 7 | chronos2_weather | persistence | +0.288 | 94% | 167 | exceeds the improvement margin |

### 90% range of Chronos-2 (0.05 to 0.95 quantiles), all catchments, no calibration step

| Variant | Lead | Coverage | Median width (mm/day) | Observations |
| --- | ---: | ---: | ---: | ---: |
| chronos2_flow_only | 1 | 0.899 | 0.972 | 2,367,293 |
| chronos2_flow_only | 3 | 0.876 | 1.435 | 2,367,293 |
| chronos2_flow_only | 7 | 0.843 | 2.053 | 2,367,293 |
| chronos2_weather | 1 | 0.898 | 1.105 | 2,367,293 |
| chronos2_weather | 3 | 0.883 | 1.648 | 2,367,293 |
| chronos2_weather | 7 | 0.854 | 2.488 | 2,367,293 |

Repeatability (same inputs forecast twice): {"chronos2_flow_only": {"catchments": ["10002", "10003"], "max_abs_difference_mm_day": 0.0}, "chronos2_weather": {"catchments": ["10002", "10003"], "max_abs_difference_mm_day": 0.0}}
