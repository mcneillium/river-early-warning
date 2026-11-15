The 90% range (0.05 to 0.95 quantile) on the test period. Target coverage: 0.90.
`conformal` = after the calibration step, which uses 2009 to 2012 only.
`unseen` = each region forecast and calibrated by models that never saw it.

| Lead | Model | Stage | Coverage, all days | Median catchment | 5th to 95th percentile of catchments | Catchments under 80% | Median width (mm/day) |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: |
| 1 | quantile model, seen | raw | 0.900 | 0.902 | 0.855 to 0.942 | 1% | 0.437 |
| 1 | quantile model, seen | conformal | 0.902 | 0.905 | 0.857 to 0.943 | 1% | 0.438 |
| 1 | persistence band | raw | 0.895 | 0.895 | 0.867 to 0.930 | 0% | 1.251 |
| 1 | persistence band | conformal | 0.900 | 0.898 | 0.871 to 0.938 | 0% | 1.272 |
| 1 | quantile model, unseen | raw | 0.852 | 0.875 | 0.680 to 0.953 | 19% | 0.474 |
| 1 | quantile model, unseen | conformal | 0.872 | 0.893 | 0.714 to 0.962 | 14% | 0.486 |
| 3 | quantile model, seen | raw | 0.888 | 0.892 | 0.830 to 0.935 | 1% | 1.639 |
| 3 | quantile model, seen | conformal | 0.904 | 0.907 | 0.847 to 0.948 | 0% | 1.663 |
| 3 | persistence band | raw | 0.895 | 0.896 | 0.863 to 0.923 | 0% | 2.192 |
| 3 | persistence band | conformal | 0.899 | 0.899 | 0.867 to 0.930 | 0% | 2.225 |
| 3 | quantile model, unseen | raw | 0.836 | 0.870 | 0.583 to 0.969 | 28% | 1.721 |
| 3 | quantile model, unseen | conformal | 0.868 | 0.898 | 0.668 to 0.980 | 17% | 1.764 |
| 7 | quantile model, seen | raw | 0.883 | 0.885 | 0.830 to 0.933 | 2% | 2.282 |
| 7 | quantile model, seen | conformal | 0.908 | 0.909 | 0.858 to 0.955 | 0% | 2.344 |
| 7 | persistence band | raw | 0.890 | 0.890 | 0.860 to 0.918 | 0% | 2.848 |
| 7 | persistence band | conformal | 0.894 | 0.893 | 0.863 to 0.923 | 0% | 2.885 |
| 7 | quantile model, unseen | raw | 0.828 | 0.859 | 0.544 to 0.970 | 32% | 2.447 |
| 7 | quantile model, unseen | conformal | 0.870 | 0.896 | 0.687 to 0.979 | 17% | 2.527 |
