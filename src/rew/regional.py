"""One regional boosting model for all catchments.

The per-catchment models of week 1 can only ever forecast the catchment they
were trained on. A regional model is trained on many catchments at once and
is told what kind of catchment each row comes from, through fixed descriptors
(size, relief, climate, land cover, soil, geology). It can therefore be asked
to forecast a catchment that was not in its training data, which is the test
in Experiment 3.

Descriptors that depend on the flow record are deliberately left out. For a
catchment the model has never seen they would be computed from the flows
being forecast. Latitude and longitude are left out too, so the model cannot
memorise regions.
"""

from __future__ import annotations

import warnings
import zlib

import lightgbm as lgb
import numpy as np
import pandas as pd

from rew.baselines import gbm
from rew.features import make_xy
from rew.splits import assign_split

STATIC_FEATURES = [
    # size and relief
    "area", "elev_mean", "elev_min", "elev_max", "dpsbar",
    # long-term climate (from weather records, not from flow)
    "p_mean", "pet_mean", "aridity", "p_seasonality", "frac_snow", "high_prec_freq", "low_prec_freq",
    # land cover, 2015 map
    "dwood_perc_2015", "ewood_perc_2015", "grass_perc_2015", "shrub_perc_2015",
    "crop_perc_2015", "urban_perc_2015", "inwater_perc_2015", "bares_perc_2015",
    # soil
    "sand_perc", "silt_perc", "clay_perc", "organic_perc", "tawc",
    "porosity_cosby", "conductivity_cosby", "soil_depth_pelletier",
    # hydrogeology: share of the catchment over each class of aquifer
    "inter_high_perc", "inter_mod_perc", "inter_low_perc",
    "frac_high_perc", "frac_mod_perc", "frac_low_perc", "no_gw_perc",
]

FLOW_DERIVED = [
    "q_mean", "runoff_ratio", "stream_elas", "slope_fdc", "baseflow_index", "baseflow_index_ceh",
    "hfd_mean", "Q5", "Q95", "high_q_freq", "high_q_dur", "low_q_freq", "low_q_dur", "zero_q_freq",
]
"""Never model inputs. Allowed only when analysing results afterwards."""

PARAMS = {
    "objective": "regression",
    "learning_rate": 0.1,
    "num_leaves": 63,
    "min_child_samples": 200,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "n_estimators": 1000,
    "max_bin": 63,
    "n_jobs": 2,
    "verbose": -1,
}
TRAIN_FRACTION = 0.2
VALIDATION_FRACTION = 0.2


def sample_mask(gauge_id: str, n_rows: int, fraction: float, salt: int = 0) -> np.ndarray:
    """A fixed random subset of a catchment's rows.

    Seeded by the gauge id, so a catchment contributes exactly the same rows to
    every model it appears in, whichever other catchments are present.
    """
    rng = np.random.default_rng([zlib.crc32(gauge_id.encode()), salt])
    return rng.random(n_rows) < fraction


def build_tables(
    frames: dict[str, pd.DataFrame],
    attributes: pd.DataFrame,
    config: dict,
    lead: int,
    calibration_start: pd.Timestamp | None = None,
) -> dict[str, pd.DataFrame]:
    """Stack every catchment's rows into train, validation and test tables.

    Each table has the dynamic features, the static descriptors, and the
    columns gauge_id, date and obs (the target flow in mm/day). Training and
    validation rows are subsampled and exclude missing targets; test rows are
    all kept.

    If `calibration_start` is given, validation rows on or after that date are
    moved to a fourth table, "calibration". Those rows are all kept (not
    sampled), exclude missing targets, and take no part in training or early
    stopping. Experiment 5 uses them to calibrate uncertainty.
    """
    static = attributes.set_index("gauge_id")[STATIC_FEATURES].astype("float32")
    parts: dict[str, list[pd.DataFrame]] = {"train": [], "validation": [], "test": []}
    if calibration_start is not None:
        parts["calibration"] = []
    for gauge_id, frame in frames.items():
        features, target = make_xy(frame, lead)
        split = assign_split(features.index, config).set_axis(features.index)
        features = features.astype("float32")
        for column in STATIC_FEATURES:
            features[column] = static.at[gauge_id, column]
        features["obs"] = target.astype("float32")
        features["gauge_id"] = gauge_id
        features = features.rename_axis("date").reset_index()
        split = split.to_numpy()
        if calibration_start is not None:
            late = (split == "validation") & (features["date"] >= calibration_start).to_numpy()
            split = np.where(late, "calibration", split)
            parts["calibration"].append(features[late & features["obs"].notna().to_numpy()])
        for name, fraction, salt in (("train", TRAIN_FRACTION, 1), ("validation", VALIDATION_FRACTION, 2)):
            rows = features[(split == name) & features["obs"].notna().to_numpy()]
            parts[name].append(rows[sample_mask(gauge_id, len(rows), fraction, salt)])
        parts["test"].append(features[split == "test"])
    return {name: pd.concat(blocks, ignore_index=True) for name, blocks in parts.items()}


def feature_columns(table: pd.DataFrame) -> list[str]:
    return [column for column in table.columns if column not in ("date", "obs", "gauge_id")]


def fit_predict(
    tables: dict[str, pd.DataFrame],
    train_gauges: set[str],
    predict_gauges: set[str],
    target_scale: str,
    patience: int,
    seed: int = 0,
) -> tuple[pd.DataFrame, int]:
    """Train on `train_gauges`, forecast the test years of `predict_gauges`.

    Returns a table of gauge_id, date, forecast (mm/day) and the tree count.
    """
    columns = feature_columns(tables["train"])
    train = tables["train"][tables["train"]["gauge_id"].isin(train_gauges)]
    valid = tables["validation"][tables["validation"]["gauge_id"].isin(train_gauges)]
    test = tables["test"][tables["test"]["gauge_id"].isin(predict_gauges)]
    if set(train["gauge_id"]) & (predict_gauges - train_gauges):
        raise AssertionError("A held-out catchment is in the training rows")

    model = lgb.LGBMRegressor(**PARAMS, random_state=seed)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*eval_set.*")
        model.fit(
            train[columns],
            gbm.to_training_scale(train["obs"], target_scale),
            eval_set=[(valid[columns], gbm.to_training_scale(valid["obs"], target_scale))],
            callbacks=[lgb.early_stopping(patience, verbose=False)],
        )
    forecast = gbm.to_flow(model.predict(test[columns]), target_scale)
    out = test[["gauge_id", "date"]].copy()
    out["forecast"] = forecast.astype("float32")
    return out, int(model.best_iteration_ or PARAMS["n_estimators"])
