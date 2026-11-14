"""All models must be scored on exactly the same days."""

import numpy as np
import pandas as pd
import pytest

from rew.evaluate import score_catchment_lead, summarise


def test_a_day_missing_for_one_model_is_dropped_for_all():
    dates = pd.date_range("2020-01-01", periods=6, freq="D")
    predictions = pd.DataFrame(
        {
            "obs": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "b": [1.0, np.nan, 3.0, 4.0, 5.0, 6.0],   # missing on day 2
        },
        index=dates,
    )
    yesterday = predictions["obs"].shift(1)
    scores = score_catchment_lead(predictions, yesterday, high=4.5, low=1.5).set_index("model")
    assert scores.loc["a", "n_days"] == 5
    assert scores.loc["b", "n_days"] == 5
    assert scores.loc["a", "nse"] == pytest.approx(1.0)


def test_warning_scores_use_the_supplied_thresholds():
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    predictions = pd.DataFrame(
        {"obs": [1.0, 5.0, 6.0, 1.0, 7.0], "m": [1.0, 5.5, 1.0, 1.0, 1.0]}, index=dates
    )
    yesterday = predictions["obs"].shift(1)
    row = score_catchment_lead(predictions, yesterday, high=4.0, low=0.5).iloc[0]
    assert row["high_events"] == 3            # days 2, 3 and 5
    assert row["high_hit_rate"] == pytest.approx(1 / 3)
    assert row["high_far"] == pytest.approx(0.0)
    assert row["high_onsets"] == 2            # day 2 and day 5 start events
    assert row["high_onset_hit_rate"] == pytest.approx(0.5)


def test_summary_averages_seeds_within_a_catchment_first():
    rows = []
    for gauge, values in {"g1": (0.2, 0.4, 0.6), "g2": (0.8, 0.8, 0.8), "g3": (0.5, 0.5, 0.5)}.items():
        for seed, value in enumerate(values):
            row = {"gauge_id": gauge, "lead_days": 1, "model": "gbm", "seed": seed}
            row.update({name: value for name in (
                "nse", "kge", "high_hit_rate", "high_far", "high_csi", "high_onset_hit_rate",
                "low_hit_rate", "low_far", "low_csi", "low_onset_hit_rate")})
            rows.append(row)
    summary = summarise(pd.DataFrame(rows))
    nse_row = summary[summary["metric"] == "nse"].iloc[0]
    assert nse_row["median"] == pytest.approx(0.5)      # medians of per-catchment means 0.4, 0.8, 0.5
    assert nse_row["n_catchments"] == 3
    assert nse_row["n_seeds"] == 3
    assert nse_row["seed_sd"] > 0
