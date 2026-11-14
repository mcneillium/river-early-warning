"""Forecasts with uncertainty: quantiles, calibrated ranges, and warnings from them.

A quantile forecast answers "what flow will be exceeded with this
probability?" The 0.95 quantile is a level the model thinks the flow will stay
below 95 times in 100. Seven quantiles together sketch the whole range of
outcomes, where the earlier models gave a single number.

Three ideas live here (the protocol is docs/protocol_week3.md):

1. **Quantile models.** The same regional boosting model as Experiment 3, but
   trained with the quantile ("pinball") loss, once per quantile.
2. **Conformal calibration.** A model's 90% range does not automatically
   contain 90% of outcomes. Conformalized quantile regression measures, on
   held-back calibration days, how far outcomes fall outside the range, and
   widens (or narrows) the range by the amount needed.
3. **Warnings from quantiles.** Warn when a chosen quantile, not the central
   forecast, crosses the threshold. That lets the system warn when an event is
   likely enough, without needing it to be the single most probable outcome.

Everything is done on log(1 + flow). Quantiles survive that transform
unchanged, so results convert straight back to mm/day.
"""

from __future__ import annotations

import math
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd

from rew import metrics, regional

QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
INTERVAL = (0.05, 0.95)                     # the 90% range
MISCOVERAGE = 0.10
CALIBRATION_START = pd.Timestamp("2008-10-01")
HIGH_CANDIDATES = (0.50, 0.75, 0.90, 0.95)  # in order of preference for ties
LOW_CANDIDATES = (0.50, 0.25, 0.10, 0.05)
PATIENCE = 100


def column(quantile: float) -> str:
    return f"q{round(100 * quantile):02d}"


def fit_predict(
    tables: dict[str, pd.DataFrame],
    train_gauges: set[str],
    predict_gauges: set[str],
    quantile: float,
    seed: int = 0,
) -> tuple[pd.DataFrame, int]:
    """Train one quantile model and forecast two sets of rows.

    Returns forecasts (mm/day) for the calibration days of `train_gauges` and
    the test days of `predict_gauges`, labelled by a `split` column.
    """
    columns = regional.feature_columns(tables["train"])
    train = tables["train"][tables["train"]["gauge_id"].isin(train_gauges)]
    valid = tables["validation"][tables["validation"]["gauge_id"].isin(train_gauges)]
    calibration = tables["calibration"][tables["calibration"]["gauge_id"].isin(train_gauges)]
    test = tables["test"][tables["test"]["gauge_id"].isin(predict_gauges)]
    if set(train["gauge_id"]) & (predict_gauges - train_gauges):
        raise AssertionError("A held-out catchment is in the training rows")

    params = {**regional.PARAMS, "objective": "quantile", "alpha": quantile}
    model = lgb.LGBMRegressor(**params, random_state=seed)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*eval_set.*")
        model.fit(
            train[columns], np.log1p(train["obs"]),
            eval_set=[(valid[columns], np.log1p(valid["obs"]))],
            callbacks=[lgb.early_stopping(PATIENCE, verbose=False)],
        )
    parts = []
    for name, block in (("calibration", calibration), ("test", test)):
        out = block[["gauge_id", "date"]].copy()
        out["split"] = name
        out["forecast"] = np.clip(np.expm1(model.predict(block[columns])), 0.0, None).astype("float32")
        parts.append(out)
    return pd.concat(parts, ignore_index=True), int(model.best_iteration_ or params["n_estimators"])


def sort_quantiles(values: np.ndarray) -> np.ndarray:
    """Sort each row so that quantile forecasts never cross.

    Each quantile comes from its own model, so on a few days a lower quantile
    can come out above a higher one. Sorting the row is the standard repair.
    """
    return np.sort(np.asarray(values, dtype=float), axis=1)


# ---------- honest ranges ----------

def coverage(lower: np.ndarray, upper: np.ndarray, obs: np.ndarray) -> float:
    """Share of observations inside [lower, upper]."""
    obs = np.asarray(obs, dtype=float)
    if obs.size == 0:
        return float("nan")
    return float(np.mean((obs >= np.asarray(lower)) & (obs <= np.asarray(upper))))


def conformal_adjustment(lower: np.ndarray, upper: np.ndarray, obs: np.ndarray,
                         miscoverage: float = MISCOVERAGE) -> float:
    """How much to widen the range, in log(1 + flow) units.

    For each calibration day the score is how far the observation lies outside
    the range (negative when it is inside). The adjustment is the
    (1 - miscoverage) quantile of the scores, nudged up for the finite sample.
    A negative result means the range was too wide and gets narrowed.
    """
    lower, upper, obs = (np.log1p(np.asarray(a, dtype=float)) for a in (lower, upper, obs))
    scores = np.maximum(lower - obs, obs - upper)
    n = scores.size
    if n == 0:
        raise ValueError("No calibration rows")
    level = min(1.0, math.ceil((n + 1) * (1 - miscoverage)) / n)
    return float(np.quantile(scores, level, method="higher"))


def apply_adjustment(lower: np.ndarray, upper: np.ndarray, adjustment: float) -> tuple[np.ndarray, np.ndarray]:
    """Widen (or narrow) a range by `adjustment` log units and return mm/day."""
    low = np.expm1(np.log1p(np.asarray(lower, dtype=float)) - adjustment)
    high = np.expm1(np.log1p(np.asarray(upper, dtype=float)) + adjustment)
    low = np.clip(low, 0.0, None)
    return low, np.maximum(high, low)


# ---------- the simple baseline ----------

def persistence_band_offsets(flow: pd.Series, lead: int, train_start: pd.Timestamp,
                             train_end: pd.Timestamp, quantiles=QUANTILES) -> np.ndarray:
    """Quantiles of the change in log(1 + flow) over `lead` days, training years only."""
    logged = np.log1p(flow)
    change = (logged - logged.shift(lead)).loc[train_start:train_end].dropna()   # indexed by target date
    if change.empty:
        return np.full(len(quantiles), np.nan)
    return np.quantile(change.to_numpy(), quantiles)


def persistence_band_forecast(flow: pd.Series, lead: int, offsets: np.ndarray,
                              dates: pd.DatetimeIndex) -> np.ndarray:
    """Today's flow shifted by each historical change quantile. Rows are target dates."""
    issue_log = np.log1p(flow.shift(lead).reindex(dates).to_numpy(dtype=float))
    return np.clip(np.expm1(issue_log[:, None] + np.asarray(offsets)[None, :]), 0.0, None)


# ---------- warnings ----------

def warning_scores(obs: np.ndarray, obs_yesterday: np.ndarray, high_forecast: np.ndarray,
                   low_forecast: np.ndarray, high: float, low: float) -> dict[str, float]:
    """Warning scores when one forecast drives high-flow warnings and another low-flow ones."""
    obs = np.asarray(obs, dtype=float)
    yesterday = np.asarray(obs_yesterday, dtype=float)
    row: dict[str, float] = {"n_days": int(obs.size)}
    for label, today, before, forecast in (
        ("high", obs > high, np.where(np.isnan(yesterday), np.nan, (yesterday > high).astype(float)),
         np.asarray(high_forecast) > high),
        ("low", obs < low, np.where(np.isnan(yesterday), np.nan, (yesterday < low).astype(float)),
         np.asarray(low_forecast) < low),
    ):
        table = metrics.contingency(today, forecast)
        onset_rate, onset_count = metrics.onset_hit_rate(today, before, forecast)
        row[f"{label}_events"] = table["hits"] + table["misses"]
        row[f"{label}_warnings"] = table["hits"] + table["false_alarms"]
        row[f"{label}_hit_rate"] = metrics.hit_rate(table)
        row[f"{label}_far"] = metrics.false_alarm_ratio(table)
        row[f"{label}_csi"] = metrics.csi(table)
        row[f"{label}_onsets"] = onset_count
        row[f"{label}_onset_hit_rate"] = onset_rate
    return row


def choose_tau(median_csi: dict[float, float], candidates: tuple[float, ...]) -> float:
    """The candidate quantile with the highest median CSI; ties go to the earliest listed."""
    best = max(candidates, key=lambda tau: (round(median_csi.get(tau, float("-inf")), 6), -candidates.index(tau)))
    return float(best)
