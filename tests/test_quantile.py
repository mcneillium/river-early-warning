"""Tests for quantile forecasts, conformal calibration and quantile-based warnings."""

import numpy as np
import pandas as pd
import pytest

from rew import quantile, regional


def test_sorting_removes_crossings_and_keeps_ordered_rows():
    values = np.array([[1.0, 3.0, 2.0], [0.1, 0.2, 0.3]])
    out = quantile.sort_quantiles(values)
    assert (np.diff(out, axis=1) >= 0).all()
    assert out[1].tolist() == [0.1, 0.2, 0.3]


def test_coverage_hand_worked():
    lower, upper = np.array([1.0, 1.0, 1.0, 1.0]), np.array([2.0, 2.0, 2.0, 2.0])
    assert quantile.coverage(lower, upper, np.array([1.5, 2.0, 2.5, 0.5])) == pytest.approx(0.5)


def test_conformal_adjustment_hand_worked():
    # Work in log(1 + flow): the range is [log 2, log 4], i.e. flows 1 to 3.
    # Ten observations; nine sit exactly on the upper edge (score 0) and one
    # sits log(8) - log(4) = log 2 above it. With n = 10 and 10% miscoverage the
    # level is ceil(11 * 0.9) / 10 = 1.0, so the adjustment is the largest score.
    lower, upper = np.full(10, 1.0), np.full(10, 3.0)
    obs = np.array([3.0] * 9 + [7.0])
    assert quantile.conformal_adjustment(lower, upper, obs) == pytest.approx(np.log(2.0))


def test_conformal_adjustment_is_negative_when_the_range_is_too_wide():
    rng = np.random.default_rng(0)
    obs = rng.uniform(4.0, 6.0, 5000)
    adjustment = quantile.conformal_adjustment(np.full(5000, 0.5), np.full(5000, 50.0), obs)
    assert adjustment < 0


def test_conformal_step_gives_the_promised_coverage_on_fresh_data():
    # A deliberately overconfident range: it covers about 50%, not 90%.
    rng = np.random.default_rng(1)
    def sample(n):
        obs = np.exp(rng.normal(0.0, 1.0, n))
        return np.full(n, np.exp(-0.674)), np.full(n, np.exp(0.674)), obs
    lower, upper, obs = sample(20000)
    assert quantile.coverage(lower, upper, obs) == pytest.approx(0.5, abs=0.02)
    adjustment = quantile.conformal_adjustment(lower, upper, obs)
    new_lower, new_upper, new_obs = sample(20000)
    wide_lower, wide_upper = quantile.apply_adjustment(new_lower, new_upper, adjustment)
    assert quantile.coverage(wide_lower, wide_upper, new_obs) == pytest.approx(0.9, abs=0.015)


def test_adjusted_range_never_goes_below_zero_or_inverts():
    lower, upper = quantile.apply_adjustment(np.array([0.05, 2.0]), np.array([0.1, 2.5]), 5.0)
    assert (lower >= 0).all() and (upper >= lower).all()
    lower, upper = quantile.apply_adjustment(np.array([1.0]), np.array([1.2]), -3.0)
    assert upper[0] >= lower[0]


def _flow(days=3000, seed=0):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2000-01-01", periods=days, freq="D")
    return pd.Series(np.exp(np.cumsum(rng.normal(0, 0.2, days)) * 0.2 + rng.normal(0, 0.1, days)), index=index)


def test_persistence_band_offsets_use_training_years_only_and_are_ordered():
    flow = _flow()
    start, end = flow.index[0], flow.index[1999]
    offsets = quantile.persistence_band_offsets(flow, 3, start, end)
    assert (np.diff(offsets) >= 0).all()
    altered = flow.copy()
    altered.iloc[2100:] *= 100.0
    assert np.allclose(quantile.persistence_band_offsets(altered, 3, start, end), offsets)


def test_persistence_band_is_centred_on_todays_flow_and_respects_the_lead():
    flow = _flow()
    offsets = np.array([-0.1, 0.0, 0.1])
    dates = flow.index[2500:2510]
    forecast = quantile.persistence_band_forecast(flow, 3, offsets, dates)
    issue_flow = flow.shift(3).reindex(dates).to_numpy()
    assert np.allclose(forecast[:, 1], issue_flow)          # zero offset = plain persistence
    assert (forecast[:, 0] < forecast[:, 1]).all() and (forecast[:, 1] < forecast[:, 2]).all()


def test_persistence_band_covers_roughly_ninety_percent_on_similar_data():
    flow = _flow(days=6000)
    offsets = quantile.persistence_band_offsets(flow, 3, flow.index[0], flow.index[3999], quantile.INTERVAL)
    dates = flow.index[4000:]
    band = quantile.persistence_band_forecast(flow, 3, offsets, dates)
    assert quantile.coverage(band[:, 0], band[:, 1], flow.reindex(dates).to_numpy()) == pytest.approx(0.9, abs=0.04)


def test_warning_scores_use_separate_forecasts_for_high_and_low():
    obs = np.array([1.0, 6.0, 7.0, 1.0, 0.2])
    yesterday = np.array([np.nan, 1.0, 6.0, 7.0, 1.0])
    high_forecast = np.array([1.0, 6.5, 1.0, 9.0, 1.0])     # hit, miss, false alarm
    low_forecast = np.array([1.0, 1.0, 1.0, 1.0, 0.1])      # one hit
    row = quantile.warning_scores(obs, yesterday, high_forecast, low_forecast, high=5.0, low=0.5)
    assert row["high_events"] == 2 and row["high_warnings"] == 2
    assert row["high_hit_rate"] == pytest.approx(0.5)
    assert row["high_far"] == pytest.approx(0.5)
    assert row["high_csi"] == pytest.approx(1 / 3)
    assert row["high_onsets"] == 1 and row["high_onset_hit_rate"] == pytest.approx(1.0)
    assert row["low_csi"] == pytest.approx(1.0)


def test_tau_choice_takes_best_score_and_breaks_ties_towards_the_median():
    assert quantile.choose_tau({0.5: 0.1, 0.75: 0.3, 0.9: 0.2, 0.95: 0.1}, quantile.HIGH_CANDIDATES) == 0.75
    assert quantile.choose_tau({0.5: 0.3, 0.75: 0.3, 0.9: 0.3, 0.95: 0.3}, quantile.HIGH_CANDIDATES) == 0.5
    assert quantile.choose_tau({0.5: 0.2, 0.25: 0.2, 0.1: 0.4, 0.05: 0.4}, quantile.LOW_CANDIDATES) == 0.1


def test_column_names():
    assert [quantile.column(q) for q in quantile.QUANTILES] == ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]


def _toy():
    rng = np.random.default_rng(3)
    frames = {}
    for g in range(6):
        index = pd.date_range("2000-01-01", periods=2500, freq="D", name="date")
        precip = rng.gamma(0.6, 5.0, 2500)
        flow, store = np.empty(2500), 5.0
        for i in range(2500):
            store = 0.5 * store + precip[i]
            flow[i] = 0.5 * store
        frames[str(g)] = pd.DataFrame({"precip": precip, "temp": rng.normal(10, 5, 2500), "pet": 1.0, "flow": flow}, index=index)
    attributes = pd.DataFrame({"gauge_id": list(frames)})
    for j, name in enumerate(regional.STATIC_FEATURES):
        attributes[name] = np.arange(6, dtype=float) + j
    config = {"train": {"start": "2000-01-01", "end": "2004-02-08"},
              "validation": {"start": "2004-02-09", "end": "2005-06-22"},
              "test": {"start": "2005-06-23", "end": "2006-11-04"}}
    return frames, attributes, config


def test_calibration_rows_are_separate_from_training_and_early_stopping():
    frames, attributes, config = _toy()
    start = pd.Timestamp("2004-10-01")
    tables = regional.build_tables(frames, attributes, config, lead=1, calibration_start=start)
    assert tables["calibration"]["date"].min() >= start
    assert tables["validation"]["date"].max() < start
    assert tables["train"]["date"].max() < pd.Timestamp("2004-02-09")
    assert len(tables["calibration"]) == 6 * 265            # every calibration day kept
    without = regional.build_tables(frames, attributes, config, lead=1)
    assert "calibration" not in without                     # earlier experiments unchanged


def test_quantile_models_are_ordered_and_roughly_calibrated_on_a_toy_problem():
    frames, attributes, config = _toy()
    tables = regional.build_tables(frames, attributes, config, lead=1, calibration_start=pd.Timestamp("2004-10-01"))
    everyone = set(frames)
    low, _ = quantile.fit_predict(tables, everyone, everyone, 0.05)
    high, _ = quantile.fit_predict(tables, everyone, everyone, 0.95)
    assert set(low["split"]) == {"calibration", "test"}
    merged = low.merge(high, on=["gauge_id", "date", "split"], suffixes=("_low", "_high"))
    assert (merged["forecast_high"] >= merged["forecast_low"]).mean() > 0.97
    test = merged[merged["split"] == "test"].merge(tables["test"][["gauge_id", "date", "obs"]], on=["gauge_id", "date"])
    covered = quantile.coverage(test["forecast_low"], test["forecast_high"], test["obs"])
    assert 0.75 < covered < 0.98


def test_unseen_quantile_model_forecasts_only_the_held_out_catchments():
    frames, attributes, config = _toy()
    tables = regional.build_tables(frames, attributes, config, lead=1, calibration_start=pd.Timestamp("2004-10-01"))
    train, held_out = {"0", "1", "2", "3"}, {"4", "5"}
    forecast, _ = quantile.fit_predict(tables, train, held_out, 0.95)
    assert set(forecast.loc[forecast["split"] == "test", "gauge_id"]) == held_out
    assert set(forecast.loc[forecast["split"] == "calibration", "gauge_id"]) == train
