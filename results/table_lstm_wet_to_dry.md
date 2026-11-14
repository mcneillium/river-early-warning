Wet-to-dry test, scored on the 167 dry catchments outside the control half. Median across catchments on the test years, then the mean over seeds (seeds [0, 1, 2]). All models in a row group are scored on the same days.

| Lead | Model | NSE | KGE | High-flow CSI | Low-flow CSI |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | lstm_random_half | 0.791 | 0.770 | 0.608 | 0.350 |
| 1 | lstm_seen | 0.807 | 0.794 | 0.615 | 0.503 |
| 1 | lstm_wet_only | 0.637 | 0.542 | 0.497 | 0.000 |
| 1 | persistence | 0.673 | 0.836 | 0.530 | 0.717 |
| 1 | regional_random_half | 0.821 | 0.806 | 0.635 | 0.655 |
| 1 | regional_seen | 0.851 | 0.853 | 0.656 | 0.660 |
| 1 | regional_wet_only | 0.752 | 0.729 | 0.577 | 0.409 |
| 3 | lstm_random_half | 0.482 | 0.502 | 0.280 | 0.135 |
| 3 | lstm_seen | 0.481 | 0.499 | 0.285 | 0.317 |
| 3 | lstm_wet_only | 0.316 | 0.311 | 0.213 | 0.000 |
| 3 | persistence | 0.234 | 0.617 | 0.300 | 0.525 |
| 3 | regional_random_half | 0.461 | 0.513 | 0.273 | 0.375 |
| 3 | regional_seen | 0.485 | 0.515 | 0.278 | 0.380 |
| 3 | regional_wet_only | 0.407 | 0.511 | 0.306 | 0.170 |
| 7 | lstm_random_half | 0.318 | 0.368 | 0.090 | 0.070 |
| 7 | lstm_seen | 0.331 | 0.348 | 0.072 | 0.182 |
| 7 | lstm_wet_only | 0.199 | 0.187 | 0.061 | 0.000 |
| 7 | persistence | -0.060 | 0.470 | 0.190 | 0.394 |
| 7 | regional_random_half | 0.311 | 0.349 | 0.067 | 0.173 |
| 7 | regional_seen | 0.317 | 0.350 | 0.070 | 0.184 |
| 7 | regional_wet_only | 0.245 | 0.351 | 0.169 | 0.000 |

lstm_wet_only minus regional_wet_only, NSE per catchment (all seeds pooled):

| Lead | Median difference | Share of catchments where lstm_wet_only is better |
| ---: | ---: | ---: |
| 1 | -0.083 | 16% |
| 3 | -0.061 | 9% |
| 7 | -0.038 | 21% |

Cost of transfer (protocol amendment 2B): per catchment, NSE of the model trained on fewer catchments minus the seen model of the same family; median over catchments and seeds, per-seed range in brackets.

| Trained on | Lead | LSTM cost | Boosting cost | LSTM minus boosting | LSTM loses less in | LSTM transfers |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| wet_only | 1 | -0.106 (-0.111 to -0.094) | -0.050 (-0.051 to -0.047) | -0.056 | 25% | worse |
| wet_only | 3 | -0.076 (-0.085 to -0.067) | -0.007 (-0.008 to -0.006) | -0.069 | 10% | worse |
| wet_only | 7 | -0.062 (-0.079 to -0.052) | -0.014 (-0.022 to -0.011) | -0.047 | 21% | worse |
| random_half | 1 | -0.004 (-0.006 to +0.001) | -0.015 (-0.016 to -0.012) | +0.010 | 66% | better |
| random_half | 3 | +0.001 (-0.002 to +0.002) | -0.002 (-0.004 to -0.002) | +0.003 | 58% | neither |
| random_half | 7 | +0.000 (-0.007 to +0.004) | -0.002 (-0.003 to -0.000) | +0.002 | 53% | neither |
