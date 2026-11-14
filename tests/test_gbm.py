"""The boosting baseline on a small synthetic catchment."""

import numpy as np
import pandas as pd

from rew.baselines import gbm
from rew.features import make_xy


def synthetic_frame(days: int = 2500, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2000-01-01", periods=days, freq="D", name="date")
    precip = rng.gamma(0.6, 5.0, days)
    flow = np.empty(days)
    store = 5.0
    for i in range(days):                      # a leaky bucket that drains fast
        store = 0.5 * store + precip[i]
        flow[i] = 0.5 * store
    return pd.DataFrame(
        {"precip": precip, "temp": rng.normal(10, 5, days), "pet": 1.0, "flow": flow}, index=index
    )


def labels(index: pd.DatetimeIndex) -> pd.Series:
    position = np.arange(len(index))
    split = np.where(position < 1500, "train", np.where(position < 2000, "validation", "test"))
    return pd.Series(split, index=index)


def test_forecasts_cover_the_test_period_only_and_are_never_negative():
    features, target = make_xy(synthetic_frame(), lead=1)
    split = labels(features.index)
    forecast, trees = gbm.fit_predict(features, target, split, seed=0)
    assert forecast.index.equals(features.index[(split == "test").to_numpy()])
    assert (forecast >= 0).all()
    assert 1 <= trees <= gbm.PARAMS["n_estimators"]


def test_same_seed_gives_the_same_forecast_and_seeds_differ():
    features, target = make_xy(synthetic_frame(), lead=1)
    split = labels(features.index)
    first, _ = gbm.fit_predict(features, target, split, seed=0)
    again, _ = gbm.fit_predict(features, target, split, seed=0)
    other, _ = gbm.fit_predict(features, target, split, seed=1)
    pd.testing.assert_series_equal(first, again)
    assert not np.allclose(first, other)


def test_it_beats_persistence_on_a_predictable_catchment():
    # In this bucket tomorrow's flow is half of today's plus new rain, so the best
    # forecast (half of today plus average rain) clearly beats "same as today".
    frame = synthetic_frame()
    features, target = make_xy(frame, lead=1)
    split = labels(features.index)
    forecast, _ = gbm.fit_predict(features, target, split, seed=0)
    observed = target.reindex(forecast.index)
    persistence = frame["flow"].shift(1).reindex(forecast.index)
    assert ((forecast - observed) ** 2).mean() < ((persistence - observed) ** 2).mean()
