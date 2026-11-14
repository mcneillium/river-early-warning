"""Checks on the LSTM data handling. They run on a CPU in a few seconds."""

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from rew import lstm  # noqa: E402
from rew.load import RECORD_END, RECORD_START  # noqa: E402
from rew.regional import STATIC_FEATURES  # noqa: E402

CONFIG = {
    "train": {"start": "1970-10-01", "end": "2004-09-30"},
    "validation": {"start": "2004-10-01", "end": "2012-09-30"},
    "test": {"start": "2012-10-01", "end": "2022-09-30"},
}


def make_panel(n_catchments: int = 3) -> lstm.Panel:
    """Each variable holds its own day number, so any slip in time is visible."""
    dates = pd.date_range(RECORD_START, RECORD_END, freq="D")
    day_number = np.arange(len(dates), dtype=np.float32)
    dynamic = np.repeat(day_number[None, :, None], n_catchments, axis=0).repeat(len(lstm.DYNAMIC), axis=2)
    static = np.arange(n_catchments * len(STATIC_FEATURES), dtype=np.float32).reshape(n_catchments, -1)
    split = np.full(len(dates), "", dtype=object)
    for name, limits in CONFIG.items():
        split[(dates >= limits["start"]) & (dates <= limits["end"])] = name
    return lstm.Panel([f"g{i}" for i in range(n_catchments)], dates, dynamic.copy(), static, split)


def identity_tensors(panel: lstm.Panel) -> lstm.Tensors:
    """Tensors with no scaling, so values can be read back as day numbers."""
    scaler = lstm.Scaler(
        np.zeros(len(lstm.DYNAMIC), np.float32), np.ones(len(lstm.DYNAMIC), np.float32),
        np.zeros(panel.static.shape[1], np.float32), np.ones(panel.static.shape[1], np.float32),
    )
    return lstm.to_tensors(panel, scaler, "cpu")


def test_window_ends_on_the_issue_day_and_holds_nothing_later():
    panel = make_panel()
    tensors = identity_tensors(panel)
    day = torch.tensor([400, 9000])
    window = lstm.cut_windows(tensors, torch.tensor([0, 1]), day)
    assert window.shape == (2, lstm.WINDOW, len(lstm.DYNAMIC) + 1)
    assert window[:, -1, 0].tolist() == [400.0, 9000.0]
    assert window[:, 0, 0].tolist() == [400.0 - 364, 9000.0 - 364]
    assert float(window[..., 0].max()) == 9000.0


def test_targets_are_the_flow_on_the_lead_days():
    panel = make_panel()
    tensors = identity_tensors(panel)
    everywhere = torch.ones(len(panel.dates) + max(lstm.LEADS), dtype=torch.bool)
    y, mask = lstm.cut_targets(tensors, everywhere, torch.tensor([2]), torch.tensor([500]))
    assert y[0].tolist() == [501.0, 503.0, 507.0]
    assert mask.all()


def test_a_target_outside_the_split_or_missing_is_not_used():
    panel = make_panel()
    last_train_day = int(np.flatnonzero(panel.split == "train")[-1])
    panel.dynamic[0, 600, lstm.FLOW] = np.nan
    tensors = identity_tensors(panel)
    in_train = torch.from_numpy(lstm.split_mask(panel, "train"))
    # Issued two days before the split ends: only the 1-day target is a training target.
    _, mask = lstm.cut_targets(tensors, in_train, torch.tensor([1]), torch.tensor([last_train_day - 2]))
    assert mask[0].tolist() == [True, False, False]
    # A missing flow on the 1-day target date switches that target off.
    _, mask = lstm.cut_targets(tensors, in_train, torch.tensor([0]), torch.tensor([599]))
    assert mask[0].tolist() == [False, True, True]


def test_missing_flow_becomes_zero_with_a_flag():
    panel = make_panel()
    panel.dynamic[1, 700, lstm.FLOW] = np.nan
    tensors = identity_tensors(panel)
    assert float(tensors.x[1, 700, lstm.FLOW]) == 0.0
    assert float(tensors.x[1, 700, -1]) == 1.0
    assert float(tensors.x[1, 701, -1]) == 0.0
    assert torch.isnan(tensors.target[1, 700])


def test_issue_days_cover_every_test_target_and_fit_the_record():
    panel = make_panel()
    days = lstm.issue_days(panel, "test")
    assert days.min() >= lstm.WINDOW - 1
    # The last day of the record is still forecast at the shortest lead.
    assert days.max() + min(lstm.LEADS) == len(panel.dates) - 1
    first_test_day = int(np.flatnonzero(panel.split == "test")[0])
    # The first test target at a 7-day lead is issued 7 days before the test years.
    assert days.min() == first_test_day - 7


def test_scaler_ignores_test_years_and_held_out_catchments():
    panel = make_panel()
    before = lstm.fit_scaler(panel, np.array([0, 1]))
    panel.dynamic[:, panel.split == "test"] += 1000.0
    panel.dynamic[2] += 1000.0
    panel.static[2] += 1000.0
    after = lstm.fit_scaler(panel, np.array([0, 1]))
    assert np.allclose(before.dynamic_mean, after.dynamic_mean)
    assert np.allclose(before.dynamic_std, after.dynamic_std)
    assert np.allclose(before.static_mean, after.static_mean)


def test_training_never_draws_a_held_out_catchment(monkeypatch):
    panel = make_panel()
    scaler = lstm.fit_scaler(panel, np.array([0, 1]))
    tensors = lstm.to_tensors(panel, scaler, "cpu")
    seen = set()
    original = lstm.cut_windows

    def spy(tensors, catchment, day, *args):
        seen.update(catchment.tolist())
        return original(tensors, catchment, day, *args)

    monkeypatch.setattr(lstm, "cut_windows", spy)
    settings = lstm.Settings(hidden=4, batch=16, epochs=1, windows_per_epoch=32, validation_fraction=0.001)
    lstm.train(panel, tensors, np.array([0, 1]), settings, seed=0, log=lambda _: None)
    assert seen == {0, 1}


def test_forecasts_are_in_flow_units_on_test_dates_only():
    panel = make_panel()
    panel.dynamic[..., lstm.FLOW] = np.log1p(2.0)
    scaler = lstm.fit_scaler(panel, np.array([0, 1, 2]))
    tensors = lstm.to_tensors(panel, scaler, "cpu")
    model = lstm.FlowLSTM(tensors.x.shape[-1], tensors.static.shape[-1], hidden=4)
    forecast = lstm.predict(panel, tensors, scaler, model, np.array([1]))
    assert set(forecast["gauge_id"]) == {"g1"}
    assert sorted(forecast["lead_days"].unique()) == list(lstm.LEADS)
    assert forecast["date"].min() == pd.Timestamp(CONFIG["test"]["start"])
    assert forecast["date"].max() == pd.Timestamp(CONFIG["test"]["end"])
    assert (forecast["forecast"] >= 0).all()
    n_test_days = int((panel.split == "test").sum())
    assert len(forecast) == n_test_days * len(lstm.LEADS)


def test_default_settings_are_those_of_experiment_6():
    settings = lstm.Settings()
    assert (settings.hidden, settings.dropout, settings.learning_rate, settings.batch) == (256, 0.4, 1e-3, 2048)
    assert (settings.window, settings.weight_decay, settings.windows_per_epoch) == (365, 0.0, 2_000_000)


def test_a_shorter_window_holds_only_that_many_days_ending_on_the_issue_day():
    panel = make_panel()
    tensors = lstm.to_tensors(panel, lstm.fit_scaler(panel, np.array([0, 1])), "cpu")
    day = torch.tensor([400, 500])
    short = lstm.cut_windows(tensors, torch.tensor([0, 1]), day, 90)
    full = lstm.cut_windows(tensors, torch.tensor([0, 1]), day)
    assert short.shape[1] == 90
    assert torch.equal(short, full[:, -90:])
    assert lstm.issue_days(panel, "train", 90).min() >= 89


def _load_script(name):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wet_to_dry_split_keeps_the_scored_catchments_out_of_both_training_sets():
    import pandas as pd

    run_lstm = _load_script("run_lstm")
    gauges = [f"g{i:02d}" for i in range(20)]
    attributes = pd.DataFrame({"gauge_id": gauges, "aridity": np.linspace(0.1, 1.0, 20)})
    wet, dry, half, dry_control = run_lstm.wet_dry_split(attributes, gauges)
    assert set(wet) | set(dry) == set(gauges) and not set(wet) & set(dry)
    assert len(half) == len(wet)
    assert set(dry_control) == set(dry) - set(half)
    assert not set(dry_control) & set(wet) and not set(dry_control) & set(half)


def test_tuning_candidates_are_valid_settings_and_include_the_original():
    tune = _load_script("tune_lstm")
    assert tune.CANDIDATES["c0_original"] == {}
    for overrides in tune.CANDIDATES.values():
        lstm.Settings(**overrides)


def test_foundation_inputs_end_on_the_issue_day_and_carry_no_later_weather():
    run_foundation = _load_script("run_foundation")
    panel = make_panel()
    # make_panel stores each day's number; store flow as log1p of it, as build_panel does.
    panel.dynamic[..., lstm.FLOW] = np.log1p(panel.dynamic[..., lstm.FLOW])
    day = 1000
    (item,) = run_foundation.inputs_for(panel, 0, np.array([day]), "chronos2_weather")
    assert len(item["target"]) == run_foundation.CONTEXT
    assert np.isclose(item["target"][-1], day, rtol=1e-4)
    assert np.isclose(item["target"][0], day - run_foundation.CONTEXT + 1, rtol=1e-4)
    for series in item["past_covariates"].values():
        assert len(series) == run_foundation.CONTEXT and series[-1] == day
    (plain,) = run_foundation.inputs_for(panel, 0, np.array([day]), "chronos2_flow_only")
    assert "past_covariates" not in plain
