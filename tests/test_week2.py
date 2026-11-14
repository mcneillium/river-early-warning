"""Tests for the week 2 additions: target variants, spatial folds, the regional model."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rew import regional, spatial
from rew.baselines import gbm
from rew.features import make_xy

ROOT = Path(__file__).resolve().parents[1]


# ---------- target variants ----------

def test_log_target_round_trip_recovers_the_flow():
    flow = np.array([0.0, 0.01, 1.0, 25.0, 300.0])
    assert np.allclose(gbm.to_flow(np.asarray(gbm.to_training_scale(flow, "log")), "log"), flow)
    assert np.allclose(gbm.to_flow(np.asarray(gbm.to_training_scale(flow, "raw")), "raw"), flow)


def test_converted_forecasts_are_never_negative():
    assert (gbm.to_flow(np.array([-3.0, -0.5, 0.2]), "raw") >= 0).all()
    assert (gbm.to_flow(np.array([-3.0, -0.5, 0.2]), "log") >= 0).all()


def test_unknown_target_is_rejected():
    with pytest.raises(ValueError):
        gbm.to_training_scale(np.array([1.0]), "sqrt")
    with pytest.raises(ValueError):
        gbm.to_flow(np.array([1.0]), "sqrt")


def test_the_four_declared_variants_and_the_week1_default():
    assert list(gbm.VARIANTS) == ["raw_es30", "log_es30", "raw_es100", "log_es100"]
    assert gbm.VARIANTS["raw_es30"] == {"target": "raw", "patience": gbm.EARLY_STOPPING_ROUNDS}


def _bucket(days=2500, seed=1):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2000-01-01", periods=days, freq="D", name="date")
    precip = rng.gamma(0.6, 5.0, days)
    flow, store = np.empty(days), 5.0
    for i in range(days):
        store = 0.5 * store + precip[i]
        flow[i] = 0.5 * store
    return pd.DataFrame({"precip": precip, "temp": rng.normal(10, 5, days), "pet": 1.0, "flow": flow}, index=index)


def _labels(index):
    position = np.arange(len(index))
    return pd.Series(np.where(position < 1500, "train", np.where(position < 2000, "validation", "test")), index=index)


def test_default_arguments_reproduce_the_week1_model():
    features, target = make_xy(_bucket(), lead=1)
    split = _labels(features.index)
    default, _ = gbm.fit_predict(features, target, split, seed=0)
    explicit, _ = gbm.fit_predict(features, target, split, seed=0, target_scale="raw", patience=30)
    pd.testing.assert_series_equal(default, explicit)


def test_log_target_forecasts_sit_lower_than_raw_target_forecasts():
    # A log-trained model aims near the typical outcome; a raw-trained one at the
    # average. For skewed flows the typical outcome is below the average.
    features, target = make_xy(_bucket(), lead=3)
    split = _labels(features.index)
    raw, _ = gbm.fit_predict(features, target, split, seed=0, target_scale="raw")
    log, _ = gbm.fit_predict(features, target, split, seed=0, target_scale="log")
    assert log.mean() < raw.mean()


def test_validation_forecasts_can_be_requested():
    features, target = make_xy(_bucket(), lead=1)
    split = _labels(features.index)
    forecast, _ = gbm.fit_predict(features, target, split, seed=0, predict_splits=("validation", "test"))
    assert len(forecast) == int(split.isin(["validation", "test"]).sum())


# ---------- spatial folds ----------

def _toy_attributes(n=60, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "gauge_id": [str(1000 + i) for i in range(n)],
        "gauge_easting": rng.uniform(100_000, 600_000, n),
        "gauge_northing": rng.uniform(0, 1_000_000, n),
    })


def test_folds_cover_every_catchment_exactly_once():
    attributes = _toy_attributes()
    folds = spatial.make_folds(attributes, list(attributes["gauge_id"]))
    assert set(folds) == set(attributes["gauge_id"])
    assert set(folds.values()) == set(range(spatial.N_FOLDS))


def test_folds_are_geographic_and_numbered_north_to_south():
    attributes = _toy_attributes(200)
    folds = spatial.make_folds(attributes, list(attributes["gauge_id"]))
    northing = attributes.set_index("gauge_id")["gauge_northing"].groupby(folds).mean()
    assert northing.is_monotonic_decreasing


def test_folds_are_repeatable_and_tamper_evident(tmp_path):
    attributes = _toy_attributes()
    gauges = list(attributes["gauge_id"])
    assert spatial.make_folds(attributes, gauges) == spatial.make_folds(attributes, gauges)
    path = tmp_path / "folds.json"
    spatial.build_folds(attributes, gauges, path)
    with pytest.raises(FileExistsError):
        spatial.build_folds(attributes, gauges, path)
    path.write_text(path.read_text().replace('"1000": ', '"1000": 9'))
    with pytest.raises(ValueError):
        spatial.load_folds(path)


def test_committed_spatial_folds_are_intact_if_present():
    path = ROOT / "splits" / "spatial_folds_v1.json"
    if not path.exists():
        pytest.skip("spatial folds not built yet")
    folds = spatial.load_folds(path)
    assert set(folds.values()) == set(range(spatial.N_FOLDS))


# ---------- regional model ----------

def test_no_flow_derived_or_location_descriptor_is_a_model_input():
    assert not set(regional.STATIC_FEATURES) & set(regional.FLOW_DERIVED)
    assert not [name for name in regional.STATIC_FEATURES if "lat" in name or "lon" in name
                or "easting" in name or "northing" in name]


def test_row_sampling_depends_only_on_the_catchment():
    first = regional.sample_mask("27001", 5000, 0.2, salt=1)
    again = regional.sample_mask("27001", 5000, 0.2, salt=1)
    other = regional.sample_mask("27002", 5000, 0.2, salt=1)
    assert (first == again).all()
    assert not (first == other).all()
    assert 0.15 < first.mean() < 0.25


def _toy_setup(n_gauges=6):
    frames = {str(i): _bucket(days=2500, seed=i) for i in range(n_gauges)}
    attributes = pd.DataFrame({"gauge_id": list(frames)})
    for j, name in enumerate(regional.STATIC_FEATURES):
        attributes[name] = np.arange(n_gauges, dtype=float) + j
    config = {
        "train": {"start": "2000-01-01", "end": "2004-02-08"},
        "validation": {"start": "2004-02-09", "end": "2005-06-22"},
        "test": {"start": "2005-06-23", "end": "2006-11-04"},
    }
    return frames, attributes, config


def test_tables_keep_all_test_rows_and_subsample_training_rows():
    frames, attributes, config = _toy_setup()
    tables = regional.build_tables(frames, attributes, config, lead=1)
    assert set(tables["test"]["gauge_id"]) == set(frames)
    assert len(tables["test"]) == 6 * 500
    assert len(tables["train"]) < 0.3 * 6 * 1500
    assert tables["train"]["obs"].notna().all()
    assert set(regional.STATIC_FEATURES) <= set(regional.feature_columns(tables["train"]))
    assert "obs" not in regional.feature_columns(tables["train"])


def test_held_out_catchments_never_reach_training_and_are_the_only_ones_forecast():
    frames, attributes, config = _toy_setup()
    tables = regional.build_tables(frames, attributes, config, lead=1)
    train, held_out = {"0", "1", "2", "3"}, {"4", "5"}
    forecast, trees = regional.fit_predict(tables, train, held_out, "log", patience=10)
    assert set(forecast["gauge_id"]) == held_out
    assert (forecast["forecast"] >= 0).all()
    assert trees >= 1


# ---------- selection rule ----------

def _load_variant_script():
    spec = importlib.util.spec_from_file_location("run_gbm_variants", ROOT / "scripts" / "run_gbm_variants.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(values: dict) -> pd.DataFrame:
    rows = []
    for name, (nse, csi) in values.items():
        for lead in (1, 3, 7):
            for metric, value in (("nse", nse), ("high_csi", csi), ("low_csi", csi)):
                rows.append({"model": name, "lead_days": lead, "metric": metric, "median": value})
    return pd.DataFrame(rows)


def test_selection_rule_picks_best_warning_score_among_eligible_variants():
    script = _load_variant_script()
    choice = script.choose_variant(_summary({
        "raw_es30": (0.50, 0.20), "log_es30": (0.49, 0.30),
        "raw_es100": (0.51, 0.21), "log_es100": (0.40, 0.90),   # best warnings but NSE too low
    }))
    assert choice["chosen"] == "log_es30"
    assert not choice["variants"]["log_es100"]["eligible"]


def test_selection_rule_breaks_ties_towards_the_simpler_variant():
    script = _load_variant_script()
    choice = script.choose_variant(_summary({
        "raw_es30": (0.50, 0.30), "log_es30": (0.50, 0.30),
        "raw_es100": (0.50, 0.30), "log_es100": (0.50, 0.30),
    }))
    assert choice["chosen"] == "raw_es30"
