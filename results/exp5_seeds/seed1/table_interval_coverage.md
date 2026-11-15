The 90% range (0.05 to 0.95 quantile) on the test period. Target coverage: 0.90.
`conformal` = after the calibration step, which uses 2009 to 2012 only.
`unseen` = each region forecast and calibrated by models that never saw it.

| Lead | Model | Stage | Coverage, all days | Median catchment | 5th to 95th percentile of catchments | Catchments under 80% | Median width (mm/day) |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: |
| 1 | quantile model, seen | raw | 0.900 | 0.902 | 0.854 to 0.941 | 1% | 0.432 |
| 1 | quantile model, seen | conformal | 0.903 | 0.904 | 0.856 to 0.943 | 1% | 0.434 |
| 1 | persistence band | raw | 0.895 | 0.895 | 0.867 to 0.930 | 0% | 1.251 |
| 1 | persistence band | conformal | 0.900 | 0.898 | 0.871 to 0.938 | 0% | 1.272 |
| 1 | quantile model, unseen | raw | 0.851 | 0.872 | 0.675 to 0.954 | 17% | 0.474 |
| 1 | quantile model, unseen | conformal | 0.872 | 0.893 | 0.704 to 0.963 | 13% | 0.486 |
| 3 | quantile model, seen | raw | 0.887 | 0.890 | 0.829 to 0.934 | 2% | 1.630 |
| 3 | quantile model, seen | conformal | 0.904 | 0.908 | 0.847 to 0.951 | 0% | 1.656 |
| 3 | persistence band | raw | 0.895 | 0.896 | 0.863 to 0.923 | 0% | 2.192 |
| 3 | persistence band | conformal | 0.899 | 0.899 | 0.867 to 0.930 | 0% | 2.225 |
| 3 | quantile model, unseen | raw | 0.833 | 0.872 | 0.570 to 0.970 | 28% | 1.740 |
| 3 | quantile model, unseen | conformal | 0.865 | 0.899 | 0.661 to 0.979 | 18% | 1.782 |
| 7 | quantile model, seen | raw | 0.883 | 0.884 | 0.827 to 0.932 | 2% | 2.318 |
| 7 | quantile model, seen | conformal | 0.907 | 0.909 | 0.857 to 0.958 | 0% | 2.379 |
| 7 | persistence band | raw | 0.890 | 0.890 | 0.860 to 0.918 | 0% | 2.848 |
| 7 | persistence band | conformal | 0.894 | 0.893 | 0.863 to 0.923 | 0% | 2.885 |
| 7 | quantile model, unseen | raw | 0.837 | 0.865 | 0.566 to 0.968 | 28% | 2.467 |
| 7 | quantile model, unseen | conformal | 0.872 | 0.896 | 0.701 to 0.979 | 16% | 2.539 |
