"""Turn one catchment's daily series into model inputs and targets.

The rule that matters: a forecast issued at the end of day t may use anything
observed up to and including day t, and nothing after it. The target is the
flow on day t + lead. Every headline feature below is built from trailing
windows only, and tests/test_features.py checks that changing the future does
not change them.

The one deliberate exception is `future_weather_features`. It gives the model
the observed rainfall, temperature and PET over the forecast window, as if a
perfect weather forecast existed. Results that use it are an upper bound and
are always labelled "perfect forecast"; they are never the headline.

Rows are indexed by TARGET date (issue date + lead), because splits are
assigned by target date.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def issue_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Features known at the end of each day t. Indexed by issue date t."""
    flow, precip, temp, pet = frame["flow"], frame["precip"], frame["temp"], frame["pet"]
    out = pd.DataFrame(index=frame.index)

    # Recent river flow: the strongest predictor at short lead times.
    out["flow_t"] = flow
    for lag in (1, 2, 3, 7):
        out[f"flow_lag{lag}"] = flow.shift(lag)
    out["flow_change_1d"] = flow - flow.shift(1)
    for window in (3, 7, 30):
        out[f"flow_mean_{window}d"] = flow.rolling(window, min_periods=window).mean()

    # Recent weather: how wet the catchment is and how fast it is drying.
    out["precip_t"] = precip
    out["precip_lag1"] = precip.shift(1)
    out["precip_lag2"] = precip.shift(2)
    for window in (3, 7, 30, 90):
        out[f"precip_sum_{window}d"] = precip.rolling(window, min_periods=window).sum()
    out["temp_t"] = temp
    for window in (7, 30):
        out[f"temp_mean_{window}d"] = temp.rolling(window, min_periods=window).mean()
        out[f"pet_mean_{window}d"] = pet.rolling(window, min_periods=window).mean()
    return out


def future_weather_features(frame: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Observed weather on days t+1 .. t+lead. PERFECT-FORECAST UPPER BOUND ONLY."""
    out = pd.DataFrame(index=frame.index)
    # rolling(lead) at day t+lead covers t+1 .. t+lead; shift it back to day t.
    out["fut_precip_sum"] = frame["precip"].rolling(lead, min_periods=lead).sum().shift(-lead)
    out["fut_precip_target_day"] = frame["precip"].shift(-lead)
    out["fut_precip_max"] = frame["precip"].rolling(lead, min_periods=lead).max().shift(-lead)
    out["fut_temp_mean"] = frame["temp"].rolling(lead, min_periods=lead).mean().shift(-lead)
    out["fut_pet_mean"] = frame["pet"].rolling(lead, min_periods=lead).mean().shift(-lead)
    return out


def make_xy(
    frame: pd.DataFrame,
    lead: int,
    future_weather: bool = False,
) -> tuple[pd.DataFrame, pd.Series]:
    """Inputs X and target y for one lead time, both indexed by target date.

    `frame` is one catchment on a complete daily calendar with columns
    precip, temp, pet, flow.
    """
    if lead < 1:
        raise ValueError("lead must be at least 1 day")
    features = issue_features(frame)
    if future_weather:
        features = features.join(future_weather_features(frame, lead))

    # Move each row from its issue date t to its target date t + lead.
    features = features.shift(lead, freq="D")
    features = features.loc[features.index.intersection(frame.index)]

    # Season of the target day, as a smooth yearly cycle.
    day = features.index.day_of_year.to_numpy()
    features["doy_sin"] = np.sin(2 * np.pi * day / 365.25)
    features["doy_cos"] = np.cos(2 * np.pi * day / 365.25)

    target = frame["flow"].reindex(features.index).rename("flow_target")
    return features, target
