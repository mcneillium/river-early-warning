The 90% range (0.05 to 0.95 quantile) on the test period. Target coverage: 0.90.
`conformal` = after the calibration step, which uses 2009 to 2012 only.
`unseen` = each region forecast and calibrated by models that never saw it.

| Lead | Model | Stage | Coverage, all days | Median catchment | 5th to 95th percentile of catchments | Catchments under 80% | Median width (mm/day) |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: |
| 1 | quantile model, seen | raw | 0.899 | 0.902 | 0.856 to 0.941 | 1% | 0.434 |
| 1 | quantile model, seen | conformal | 0.902 | 0.905 | 0.858 to 0.943 | 1% | 0.436 |
| 1 | persistence band | raw | 0.895 | 0.895 | 0.867 to 0.930 | 0% | 1.251 |
| 1 | persistence band | conformal | 0.900 | 0.898 | 0.871 to 0.938 | 0% | 1.272 |
| 1 | quantile model, unseen | raw | 0.849 | 0.871 | 0.663 to 0.954 | 20% | 0.472 |
| 1 | quantile model, unseen | conformal | 0.871 | 0.893 | 0.703 to 0.961 | 14% | 0.484 |
| 3 | quantile model, seen | raw | 0.888 | 0.892 | 0.830 to 0.936 | 1% | 1.639 |
| 3 | quantile model, seen | conformal | 0.905 | 0.908 | 0.848 to 0.950 | 0% | 1.664 |
| 3 | persistence band | raw | 0.895 | 0.896 | 0.863 to 0.923 | 0% | 2.192 |
| 3 | persistence band | conformal | 0.899 | 0.899 | 0.867 to 0.930 | 0% | 2.225 |
| 3 | quantile model, unseen | raw | 0.833 | 0.868 | 0.569 to 0.968 | 28% | 1.710 |
| 3 | quantile model, unseen | conformal | 0.866 | 0.897 | 0.671 to 0.980 | 17% | 1.754 |
| 7 | quantile model, seen | raw | 0.885 | 0.887 | 0.830 to 0.933 | 2% | 2.285 |
| 7 | quantile model, seen | conformal | 0.907 | 0.909 | 0.858 to 0.955 | 0% | 2.341 |
| 7 | persistence band | raw | 0.890 | 0.890 | 0.860 to 0.918 | 0% | 2.848 |
| 7 | persistence band | conformal | 0.894 | 0.893 | 0.863 to 0.923 | 0% | 2.885 |
| 7 | quantile model, unseen | raw | 0.829 | 0.860 | 0.559 to 0.969 | 31% | 2.448 |
| 7 | quantile model, unseen | conformal | 0.870 | 0.896 | 0.690 to 0.978 | 18% | 2.525 |
