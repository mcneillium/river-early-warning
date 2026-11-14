"""Warning thresholds for each catchment, from the training years only.

A high-flow warning day is a day when flow is above the catchment's own 95th
percentile; a low-flow warning day is one below its 10th percentile. Both
percentiles are computed from training-period flow only. Using the full record
would let information about the test years leak into the definition of the
event being forecast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HIGH_QUANTILE = 0.95
LOW_QUANTILE = 0.10


def train_thresholds(
    flow: pd.Series,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
) -> tuple[float, float]:
    """Return (high threshold, low threshold) from the training-period flow.

    `flow` is one catchment's daily flow indexed by date. Missing days are
    ignored. Returns NaN for both if there is no training flow at all.
    """
    in_train = flow.loc[train_start:train_end].dropna()
    if in_train.empty:
        return float("nan"), float("nan")
    high, low = np.quantile(in_train.to_numpy(), [HIGH_QUANTILE, LOW_QUANTILE])
    return float(high), float(low)
