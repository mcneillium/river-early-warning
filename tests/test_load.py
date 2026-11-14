"""Checks on the real data. Skipped automatically if data/ has not been downloaded."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rew import load

DATA = Path(__file__).resolve().parents[1] / "data"
FILES = sorted((DATA / "daily").glob("camels_gb_v2_hydromet_daily_timeseries_*.csv"))

pytestmark = [
    pytest.mark.data,
    pytest.mark.skipif(not FILES, reason="CAMELS-GB v2 not downloaded; run python -m rew.download"),
]


@pytest.fixture(scope="module")
def tidy() -> pd.DataFrame:
    return load.load_all(DATA)


def test_there_are_671_catchments(tidy):
    assert len(FILES) == 671
    assert tidy["gauge_id"].nunique() == 671


def test_every_catchment_has_the_full_daily_calendar(tidy):
    days = (load.RECORD_END - load.RECORD_START).days + 1
    assert days == 18993
    assert (tidy.groupby("gauge_id", observed=True).size() == days).all()
    assert tidy["date"].min() == load.RECORD_START
    assert tidy["date"].max() == load.RECORD_END


def test_missing_flow_is_not_filled(tidy):
    # Compare against the raw file for three catchments: the number of missing
    # flow days must be exactly the same before and after loading.
    for path in (FILES[0], FILES[len(FILES) // 2], FILES[-1]):
        raw = pd.read_csv(path, usecols=["date", "discharge_spec"])
        gauge = load.gauge_id_from_path(path)
        loaded = tidy.loc[tidy["gauge_id"] == gauge, "flow"]
        assert int(loaded.isna().sum()) == int(raw["discharge_spec"].isna().sum())
        assert np.isclose(loaded.sum(skipna=True), raw["discharge_spec"].sum(skipna=True))


def test_weather_covers_the_test_period(tidy):
    # The reason HadUK-Grid / Hydro-PE were chosen over CEH-GEAR / CHESS.
    test = tidy[tidy["date"] >= "2012-10-01"]
    for name in ("precip", "temp", "pet"):
        assert test[name].notna().mean() > 0.999


def test_values_are_physically_plausible(tidy):
    assert (tidy["precip"].dropna() >= 0).all()
    assert (tidy["flow"].dropna() >= 0).all()
    assert tidy["temp"].between(-30, 40).all()


def test_attributes_have_one_row_per_catchment():
    attributes = load.load_attributes(DATA)
    assert attributes["gauge_id"].is_unique
    assert len(attributes) == 671
    assert {"area", "baseflow_index", "aridity"} <= set(attributes.columns)
