"""Hand-worked cases for every score. Each expected value can be checked on paper."""

import math

import numpy as np
import pytest

from rew import metrics


def test_nse_is_one_for_a_perfect_forecast():
    obs = np.array([1.0, 2.0, 3.0, 4.0])
    assert metrics.nse(obs, obs.copy()) == 1.0


def test_nse_is_zero_when_forecasting_the_observed_mean():
    obs = np.array([1.0, 2.0, 3.0, 6.0])
    assert metrics.nse(obs, np.full(4, obs.mean())) == pytest.approx(0.0)


def test_nse_hand_worked():
    # squared error = 1; spread of obs about its mean (2) = 1 + 0 + 1 = 2; NSE = 1 - 1/2
    assert metrics.nse(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 4.0])) == pytest.approx(0.5)


def test_nse_is_negative_when_worse_than_the_mean():
    assert metrics.nse(np.array([1.0, 2.0, 3.0]), np.array([3.0, 2.0, 1.0])) < 0


def test_nse_undefined_for_constant_observations():
    assert math.isnan(metrics.nse(np.ones(5), np.ones(5)))


def test_kge_is_one_for_a_perfect_forecast():
    obs = np.array([1.0, 2.0, 4.0, 8.0])
    assert metrics.kge_2009(obs, obs.copy()) == pytest.approx(1.0)


def test_kge_hand_worked_doubling():
    # sim = 2 * obs: correlation 1, variability ratio 2, bias ratio 2
    # KGE = 1 - sqrt(0 + 1 + 1) = 1 - sqrt(2)
    obs = np.array([1.0, 2.0, 4.0, 8.0])
    assert metrics.kge_2009(obs, 2 * obs) == pytest.approx(1 - math.sqrt(2))


def test_kge_hand_worked_constant_offset():
    # sim = obs + 1: correlation 1, variability ratio 1, bias ratio (2 + 1) / 2 = 1.5
    # KGE = 1 - 0.5
    obs = np.array([1.0, 2.0, 3.0])
    assert metrics.kge_2009(obs, obs + 1) == pytest.approx(0.5)


def test_scores_refuse_missing_values():
    with pytest.raises(ValueError):
        metrics.nse(np.array([1.0, np.nan]), np.array([1.0, 2.0]))
    with pytest.raises(ValueError):
        metrics.kge_2009(np.array([1.0, 2.0]), np.array([np.nan, 2.0]))


def test_contingency_and_warning_scores_hand_worked():
    observed = np.array([1, 1, 0, 0, 1], dtype=bool)
    forecast = np.array([1, 0, 1, 0, 1], dtype=bool)
    table = metrics.contingency(observed, forecast)
    assert table == {"hits": 2, "misses": 1, "false_alarms": 1, "correct_negatives": 1}
    assert metrics.hit_rate(table) == pytest.approx(2 / 3)
    assert metrics.false_alarm_ratio(table) == pytest.approx(1 / 3)
    assert metrics.csi(table) == pytest.approx(2 / 4)


def test_warning_scores_are_undefined_without_events_or_warnings():
    table = metrics.contingency(np.zeros(4, dtype=bool), np.zeros(4, dtype=bool))
    assert math.isnan(metrics.hit_rate(table))
    assert math.isnan(metrics.false_alarm_ratio(table))
    assert math.isnan(metrics.csi(table))


def test_onset_is_first_day_of_an_event():
    today = np.array([0, 1, 1, 0, 1], dtype=bool)
    yesterday = np.array([np.nan, 0, 1, 1, 0])
    assert metrics.onset_mask(today, yesterday).tolist() == [False, True, False, False, True]


def test_a_gap_yesterday_never_creates_an_onset():
    today = np.array([1, 1], dtype=bool)
    yesterday = np.array([np.nan, np.nan])
    assert not metrics.onset_mask(today, yesterday).any()


def test_onset_hit_rate_hand_worked():
    today = np.array([0, 1, 1, 0, 1], dtype=bool)
    yesterday = np.array([0.0, 0, 1, 1, 0])
    forecast = np.array([0, 1, 1, 0, 0], dtype=bool)   # catches the first onset, misses the second
    rate, count = metrics.onset_hit_rate(today, yesterday, forecast)
    assert count == 2
    assert rate == pytest.approx(0.5)


def test_persistence_can_never_catch_an_onset_at_one_day_lead():
    # At lead 1 persistence forecasts yesterday's flow. On an onset day yesterday
    # was below the threshold by definition, so the forecast is always "no event".
    rng = np.random.default_rng(0)
    flow = rng.gamma(2.0, 1.0, size=500)
    threshold = np.quantile(flow, 0.9)
    today = flow[1:] > threshold
    yesterday = (flow[:-1] > threshold).astype(float)
    persistence_forecast = flow[:-1] > threshold
    rate, count = metrics.onset_hit_rate(today, yesterday, persistence_forecast)
    assert count > 0
    assert rate == 0.0
