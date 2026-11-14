Experiment 6. Median across catchments on the test years, then the mean over seeds (seeds [0, 1, 2]). All models in a row group are scored on the same days.

| Lead | Model | NSE | KGE | High-flow CSI | Low-flow CSI |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | lstm_seen | 0.734 | 0.718 | 0.529 | 0.616 |
| 1 | lstm_tuned_seen | 0.734 | 0.718 | 0.529 | 0.616 |
| 1 | persistence | 0.509 | 0.754 | 0.414 | 0.754 |
| 1 | regional_seen | 0.764 | 0.761 | 0.568 | 0.724 |
| 3 | lstm_seen | 0.377 | 0.389 | 0.131 | 0.317 |
| 3 | lstm_tuned_seen | 0.377 | 0.389 | 0.131 | 0.317 |
| 3 | persistence | 0.066 | 0.533 | 0.223 | 0.545 |
| 3 | regional_seen | 0.375 | 0.394 | 0.134 | 0.383 |
| 7 | lstm_seen | 0.239 | 0.234 | 0.005 | 0.139 |
| 7 | lstm_tuned_seen | 0.239 | 0.234 | 0.005 | 0.139 |
| 7 | persistence | -0.235 | 0.385 | 0.138 | 0.389 |
| 7 | regional_seen | 0.235 | 0.226 | 0.002 | 0.158 |

lstm_tuned_seen minus regional_seen, NSE per catchment (all seeds pooled):

| Lead | Median difference | Share of catchments where lstm_tuned_seen is better |
| ---: | ---: | ---: |
| 1 | -0.019 | 16% |
| 3 | +0.002 | 57% |
| 7 | +0.002 | 56% |
