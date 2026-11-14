"""The headline features must not see the future. These tests would catch it if they did."""

import numpy as np
import pandas as pd
import pytest

from rew.baselines import persistence, seasonal
from rew.features import make_xy
from rew.thresholds import train_thresholds


def toy_frame(days: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2000-01-01", periods=days, freq="D", name="date")
    return pd.DataFrame(
        {
            "precip": rng.gamma(1.0, 3.0, days),
            "temp": rng.normal(10, 5, days),
            "pet": rng.gamma(2.0, 0.5, days),
            "flow": rng.gamma(2.0, 1.0, days),
        },
        index=index,
    )


@pytest.mark.parametrize("lead", [1, 3, 7])
def test_target_and_issue_day_are_aligned(lead):
    frame = toy_frame()
    features, target = make_xy(frame, lead)
    day = features.index[200]
    assert target[day] == frame["flow"][day]
    assert features.loc[day, "flow_t"] == frame["flow"][day - pd.Timedelta(days=lead)]
    assert features.loc[day, "precip_t"] == frame["precip"][day - pd.Timedelta(days=lead)]


@pytest.mark.parametrize("lead", [1, 3, 7])
def test_headline_features_do_not_change_when_the_future_changes(lead):
    frame = toy_frame()
    issue_day = frame.index[250]
    changed = frame.copy()
    changed.loc[changed.index > issue_day] += 1000.0   # rewrite everything after the issue day

    before, _ = make_xy(frame, lead)
    after, _ = make_xy(changed, lead)
    target_day = issue_day + pd.Timedelta(days=lead)
    # Every forecast issued on or before issue_day must be identical.
    pd.testing.assert_frame_equal(before.loc[:target_day], after.loc[:target_day])


@pytest.mark.parametrize("lead", [1, 3, 7])
def test_the_leak_test_can_detect_a_leak(lead):
    # The perfect-forecast variant DOES use the future, so the same check must fail
    # for it. This proves the test above is able to catch leakage.
    frame = toy_frame()
    issue_day = frame.index[250]
    changed = frame.copy()
    changed.loc[changed.index > issue_day] += 1000.0
    before, _ = make_xy(frame, lead, future_weather=True)
    after, _ = make_xy(changed, lead, future_weather=True)
    target_day = issue_day + pd.Timedelta(days=lead)
    assert not before.loc[target_day].equals(after.loc[target_day])


def test_future_weather_window_covers_exactly_the_forecast_days():
    frame = toy_frame()
    lead = 3
    features, _ = make_xy(frame, lead, future_weather=True)
    target_day = features.index[100]
    issue_day = target_day - pd.Timedelta(days=lead)
    window = frame["precip"][issue_day + pd.Timedelta(days=1) : target_day]
    assert len(window) == lead
    assert features.loc[target_day, "fut_precip_sum"] == pytest.approx(window.sum())
    assert features.loc[target_day, "fut_precip_target_day"] == frame["precip"][target_day]


def test_gaps_in_flow_stay_gaps():
    frame = toy_frame()
    frame.loc[frame.index[100:110], "flow"] = np.nan
    features, target = make_xy(frame, 1)
    assert target.loc[frame.index[100:110]].isna().all()
    assert np.isnan(features.loc[frame.index[105], "flow_t"])
    assert np.isnan(features.loc[frame.index[112], "flow_mean_7d"])   # window touches the gap


def test_persistence_is_the_issue_day_flow():
    frame = toy_frame()
    forecast = persistence.predict(frame["flow"], 3)
    day = frame.index[50]
    assert forecast[day] == frame["flow"][day - pd.Timedelta(days=3)]
    assert forecast.iloc[:3].isna().all()


def test_seasonal_average_uses_training_years_only():
    index = pd.date_range("2000-01-01", "2009-12-31", freq="D")
    flow = pd.Series(2.0, index=index)
    flow.loc["2005-01-01":] = 50.0                      # later years are very different
    climatology = seasonal.fit(flow, pd.Timestamp("2000-01-01"), pd.Timestamp("2004-12-31"))
    assert climatology.shape == (366,)
    assert np.allclose(climatology, 2.0)
    forecast = seasonal.predict(climatology, index[-10:])
    assert np.allclose(forecast, 2.0)


def test_seasonal_average_follows_the_yearly_cycle():
    index = pd.date_range("2001-01-01", "2008-12-31", freq="D")
    flow = pd.Series(5 + 3 * np.cos(2 * np.pi * index.dayofyear / 365.25), index=index)
    climatology = seasonal.fit(flow, index[0], index[-1])
    assert climatology[0] > climatology[182]            # winter above summer
    assert abs(climatology[0] - 8.0) < 0.2


def test_thresholds_ignore_everything_outside_the_training_years():
    index = pd.date_range("2000-01-01", "2009-12-31", freq="D")
    flow = pd.Series(np.arange(len(index), dtype=float), index=index)
    start, end = pd.Timestamp("2000-01-01"), pd.Timestamp("2004-12-31")
    high, low = train_thresholds(flow, start, end)

    altered = flow.copy()
    altered.loc["2005-01-01":] = 1e9
    assert train_thresholds(altered, start, end) == (high, low)

    train = flow.loc[start:end].to_numpy()
    assert high == pytest.approx(np.quantile(train, 0.95))
    assert low == pytest.approx(np.quantile(train, 0.10))
