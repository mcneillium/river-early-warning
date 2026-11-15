The 90% range (0.05 to 0.95 quantile) on the test period. Target coverage: 0.90.
`conformal` = after the calibration step, which uses 2009 to 2012 only.
`unseen` = each region forecast and calibrated by models that never saw it.

| Lead | Model | Stage | Coverage, all days | Median catchment | 5th to 95th percentile of catchments | Catchments under 80% | Median width (mm/day) |
| ---: | --- | --- | ---: | ---: | --- | ---: | ---: |
| 1 | quantile model, seen | raw | 0.901 | 0.904 | 0.855 to 0.941 | 1% | 0.438 |
| 1 | quantile model, seen | conformal | 0.903 | 0.905 | 0.857 to 0.943 | 1% | 0.439 |
| 1 | persistence band | raw | 0.895 | 0.895 | 0.867 to 0.930 | 0% | 1.251 |
| 1 | persistence band | conformal | 0.900 | 0.898 | 0.871 to 0.938 | 0% | 1.272 |
| 1 | quantile model, unseen | raw | 0.856 | 0.875 | 0.687 to 0.956 | 17% | 0.472 |
| 1 | quantile model, unseen | conformal | 0.876 | 0.894 | 0.725 to 0.964 | 12% | 0.485 |
| 3 | quantile model, seen | raw | 0.888 | 0.892 | 0.830 to 0.934 | 2% | 1.619 |
| 3 | quantile model, seen | conformal | 0.905 | 0.908 | 0.849 to 0.950 | 0% | 1.645 |
| 3 | persistence band | raw | 0.895 | 0.896 | 0.863 to 0.923 | 0% | 2.192 |
| 3 | persistence band | conformal | 0.899 | 0.899 | 0.867 to 0.930 | 0% | 2.225 |
| 3 | quantile model, unseen | raw | 0.836 | 0.869 | 0.571 to 0.970 | 27% | 1.717 |
| 3 | quantile model, unseen | conformal | 0.869 | 0.899 | 0.670 to 0.979 | 16% | 1.761 |
| 7 | quantile model, seen | raw | 0.882 | 0.884 | 0.825 to 0.930 | 2% | 2.310 |
| 7 | quantile model, seen | conformal | 0.907 | 0.910 | 0.856 to 0.955 | 0% | 2.373 |
| 7 | persistence band | raw | 0.890 | 0.890 | 0.860 to 0.918 | 0% | 2.848 |
| 7 | persistence band | conformal | 0.894 | 0.893 | 0.863 to 0.923 | 0% | 2.885 |
| 7 | quantile model, unseen | raw | 0.833 | 0.867 | 0.571 to 0.967 | 30% | 2.442 |
| 7 | quantile model, unseen | conformal | 0.869 | 0.897 | 0.686 to 0.979 | 17% | 2.516 |
