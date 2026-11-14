"""Gradient boosting baseline: one small LightGBM model per catchment and lead.

Training uses rows whose target day is in the training period. The validation
period is used only to decide when to stop adding trees (early stopping); it
never contributes training rows. Predictions are then made for the test
period.

The settings are deliberately plain and are the same for every catchment and
lead time. They were fixed before any test result was seen and were not tuned.
Row and column subsampling are switched on so that the random seed changes the
model; that is what the 3 seeds measure.

Forecasts are clipped at zero. A tree model can extrapolate slightly below the
smallest flow it has seen, and a negative river flow is physically impossible.

Two switches were added in week 2 (docs/protocol_week2.md). Their defaults
reproduce the week 1 baseline exactly.

    target        "raw": train on flow in mm/day (squared error rewards
                  getting large flows right).
                  "log": train on log(1 + flow) and convert the forecast back.
                  Errors then count in proportion to the flow, so low flows
                  matter as much as high ones. The converted forecast sits
                  nearer the typical outcome than the average outcome.
    patience      how many rounds without improvement on the validation years
                  before training stops.
"""

from __future__ import annotations

import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd

PARAMS = {
    "objective": "regression",   # squared error on the training target
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 50,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "n_estimators": 600,         # upper limit; early stopping usually ends sooner
    "n_jobs": 1,
    "verbose": -1,
}
EARLY_STOPPING_ROUNDS = 30

VARIANTS = {
    "raw_es30": {"target": "raw", "patience": 30},
    "log_es30": {"target": "log", "patience": 30},
    "raw_es100": {"target": "raw", "patience": 100},
    "log_es100": {"target": "log", "patience": 100},
}
"""The four variants declared in docs/protocol_week2.md. raw_es30 is week 1."""


def to_training_scale(flow: pd.Series | np.ndarray, target: str):
    if target == "raw":
        return flow
    if target == "log":
        return np.log1p(flow)
    raise ValueError(f"Unknown target '{target}'")


def to_flow(values: np.ndarray, target: str) -> np.ndarray:
    """Convert model output back to flow in mm/day, never below zero."""
    if target == "log":
        values = np.expm1(values)
    elif target != "raw":
        raise ValueError(f"Unknown target '{target}'")
    return np.clip(values, 0.0, None)


def fit_predict(
    features: pd.DataFrame,
    target: pd.Series,
    split: pd.Series,
    seed: int,
    target_scale: str = "raw",
    patience: int = EARLY_STOPPING_ROUNDS,
    predict_splits: tuple[str, ...] = ("test",),
    params: dict | None = None,
) -> tuple[pd.Series, int]:
    """Train on 'train' rows, stop on 'validation' rows, predict the requested splits.

    `features`, `target` and `split` share one index of target dates.
    Returns the forecast (in mm/day) and the number of trees kept.
    """
    has_target = target.notna()
    train = ((split == "train") & has_target).to_numpy()
    valid = ((split == "validation") & has_target).to_numpy()
    wanted = split.isin(list(predict_splits)).to_numpy()
    if not train.any() or not valid.any():
        raise ValueError("Need both training and validation rows with observed flow")

    y = to_training_scale(target, target_scale)
    model = lgb.LGBMRegressor(**(params or PARAMS), random_state=seed)
    with warnings.catch_warnings():
        # LightGBM 4.7 warns that `eval_set` will be renamed; it still works.
        warnings.filterwarnings("ignore", message=".*eval_set.*")
        model.fit(
            features[train],
            y[train],
            eval_set=[(features[valid], y[valid])],
            callbacks=[lgb.early_stopping(patience, verbose=False)],
        )
    values = to_flow(model.predict(features[wanted]), target_scale)
    forecast = pd.Series(values, index=features.index[wanted], name="gbm")
    return forecast, int(model.best_iteration_ or (params or PARAMS)["n_estimators"])
