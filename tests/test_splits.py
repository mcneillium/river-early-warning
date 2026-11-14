"""The splits must not overlap, must not leave gaps, and must not change silently."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rew import splits

ROOT = Path(__file__).resolve().parents[1]
CONFIG = splits.load_config(ROOT / "configs" / "splits.yaml")


def test_boundaries_are_ordered_and_do_not_overlap():
    spans = splits.boundaries(CONFIG)
    assert spans["train"][1] < spans["validation"][0]
    assert spans["validation"][1] < spans["test"][0]


def test_no_day_is_lost_between_splits():
    spans = splits.boundaries(CONFIG)
    one_day = pd.Timedelta(days=1)
    assert spans["train"][1] + one_day == spans["validation"][0]
    assert spans["validation"][1] + one_day == spans["test"][0]


def test_splits_are_whole_water_years():
    for start, end in splits.boundaries(CONFIG).values():
        assert (start.month, start.day) == (10, 1)
        assert (end.month, end.day) == (9, 30)


def test_every_date_gets_exactly_one_label():
    dates = pd.date_range("1970-10-01", "2022-09-30", freq="D")
    labels = splits.assign_split(dates, CONFIG)
    assert labels.notna().all()
    assert set(labels.unique()) == set(splits.SPLIT_NAMES)
    assert labels.iloc[0] == "train"
    assert labels[dates == pd.Timestamp("2004-09-30")].iloc[0] == "train"
    assert labels[dates == pd.Timestamp("2004-10-01")].iloc[0] == "validation"
    assert labels[dates == pd.Timestamp("2012-09-30")].iloc[0] == "validation"
    assert labels[dates == pd.Timestamp("2012-10-01")].iloc[0] == "test"


def test_overlapping_config_is_rejected():
    bad = json.loads(json.dumps(CONFIG))
    bad["validation"]["start"] = "2004-09-30"
    with pytest.raises(ValueError):
        splits.boundaries(bad)


def _toy_table() -> pd.DataFrame:
    dates = pd.date_range("1970-10-01", "2022-09-30", freq="D")
    full = pd.DataFrame({"gauge_id": "1", "date": dates, "flow": 1.0})
    short = pd.DataFrame({"gauge_id": "2", "date": dates, "flow": np.nan})
    short.loc[short["date"] >= "2015-01-01", "flow"] = 1.0   # no training flow at all
    return pd.concat([full, short], ignore_index=True)


def test_build_excludes_catchments_with_too_little_flow(tmp_path):
    saved = splits.build_splits(_toy_table(), CONFIG, tmp_path / "s.json")
    assert saved["gauge_ids"] == ["1"]
    assert list(saved["excluded"]) == ["2"]
    assert saved["excluded"]["2"]["train"] == 0


def test_build_refuses_to_overwrite(tmp_path):
    path = tmp_path / "s.json"
    splits.build_splits(_toy_table(), CONFIG, path)
    with pytest.raises(FileExistsError):
        splits.build_splits(_toy_table(), CONFIG, path)


def test_an_edited_splits_file_is_detected(tmp_path):
    path = tmp_path / "s.json"
    splits.build_splits(_toy_table(), CONFIG, path)
    assert splits.load_splits(path)["gauge_ids"] == ["1"]
    edited = json.loads(path.read_text())
    edited["boundaries"]["test"][0] = "2010-10-01"
    path.write_text(json.dumps(edited))
    with pytest.raises(ValueError):
        splits.load_splits(path)


def test_committed_splits_file_is_intact_if_present():
    path = ROOT / "splits" / "splits_v1.json"
    if not path.exists():
        pytest.skip("splits_v1.json not built yet")
    saved = splits.load_splits(path)
    assert splits.config_from_splits(saved)["train"] == CONFIG["train"]
    assert len(saved["gauge_ids"]) + len(saved["excluded"]) == 671
