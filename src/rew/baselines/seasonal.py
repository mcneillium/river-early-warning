"""Seasonal average: the usual flow for the time of year.

For each catchment, average the training-period flow by day of the year, then
smooth that curve with a 15-day centred window that wraps around the year end.
The forecast for any target day is the smoothed value for its day of the year,
whatever the lead time. It knows nothing about current conditions, so it is
weak at short lead times, but it is the natural reference for long ones.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SMOOTHING_DAYS = 15


def fit(flow: pd.Series, train_start: pd.Timestamp, train_end: pd.Timestamp) -> np.ndarray:
    """Return the smoothed day-of-year climatology (length 366, index 0 = 1 January)."""
    train = flow.loc[train_start:train_end].dropna()
    by_day = train.groupby(train.index.day_of_year).mean().reindex(range(1, 367))
    # 29 February in leap years is day 60 and shifts later days by one; with a
    # 15-day smoother that one-day offset is negligible. Day 366 has few
    # samples, so borrow from its neighbours before smoothing.
    by_day = by_day.interpolate(limit_direction="both")
    values = by_day.to_numpy()
    half = SMOOTHING_DAYS // 2
    wrapped = np.concatenate([values[-half:], values, values[:half]])
    kernel = np.ones(SMOOTHING_DAYS) / SMOOTHING_DAYS
    return np.convolve(wrapped, kernel, mode="valid")


def predict(climatology: np.ndarray, dates: pd.DatetimeIndex) -> pd.Series:
    """Forecast for each target date from the fitted climatology."""
    return pd.Series(climatology[dates.day_of_year.to_numpy() - 1], index=dates, name="seasonal")
