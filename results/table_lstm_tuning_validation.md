Validation years only (2005 to 2012), seed 0, median NSE across catchments. The test years were not used.

| Candidate | NSE 1 day | NSE 3 days | NSE 7 days | Mean | Best validation loss | Best epoch | Epochs run |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| c0_original | 0.720 | 0.310 | 0.172 | 0.4009 | 0.2846 | 2 | 6 |
| c1_fine_stopping | 0.720 | 0.310 | 0.172 | 0.4009 | 0.2846 | 8 | 14 |
| c2_lr3e-4 | 0.701 | 0.309 | 0.171 | 0.3940 | 0.2874 | 15 | 21 |
| c3_lr1e-4 | 0.694 | 0.308 | 0.173 | 0.3916 | 0.2874 | 31 | 37 |
| c4_hidden128 | 0.690 | 0.304 | 0.169 | 0.3875 | 0.2856 | 22 | 28 |
| c5_hidden64 | 0.686 | 0.302 | 0.170 | 0.3863 | 0.2866 | 31 | 37 |
| c6_weight_decay | 0.701 | 0.309 | 0.171 | 0.3939 | 0.2874 | 15 | 21 |
| c7_window90 | 0.682 | 0.308 | 0.174 | 0.3881 | 0.2871 | 13 | 19 |

Chosen: **c0_original**.
