"""Score every model on the same days, one catchment and lead time at a time.

Fairness rule: for a given catchment and lead, a day is scored only if the
observation and EVERY model's forecast exist for it. Otherwise one model could
look better simply because it was scored on easier days.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rew import metrics


def score_catchment_lead(
    predictions: pd.DataFrame,
    obs_yesterday: pd.Series,
    high: float,
    low: float,
) -> pd.DataFrame:
    """Score all model columns in `predictions` for one catchment and lead.

    predictions    indexed by target date; column 'obs' plus one column per model
    obs_yesterday  observed flow on the day before each target date (may be NaN)
    high, low      the catchment's warning thresholds from the training years

    Returns one row per model.
    """
    models = [column for column in predictions.columns if column != "obs"]
    complete = predictions.notna().all(axis=1)
    scored = predictions[complete]
    yesterday = obs_yesterday.reindex(scored.index).to_numpy(dtype=float)
    obs = scored["obs"].to_numpy()

    high_today = obs > high
    low_today = obs < low
    # 1.0 = event yesterday, 0.0 = no event, NaN = flow unknown yesterday
    high_yesterday = np.where(np.isnan(yesterday), np.nan, (yesterday > high).astype(float))
    low_yesterday = np.where(np.isnan(yesterday), np.nan, (yesterday < low).astype(float))

    rows = []
    for model in models:
        sim = scored[model].to_numpy()
        row = {
            "model": model,
            "n_days": int(len(scored)),
            "nse": metrics.nse(obs, sim) if len(scored) else np.nan,
            "kge": metrics.kge_2009(obs, sim) if len(scored) else np.nan,
        }
        for label, today, before, forecast in (
            ("high", high_today, high_yesterday, sim > high),
            ("low", low_today, low_yesterday, sim < low),
        ):
            table = metrics.contingency(today, forecast)
            onset_rate, onset_count = metrics.onset_hit_rate(today, before, forecast)
            row[f"{label}_events"] = table["hits"] + table["misses"]
            row[f"{label}_hit_rate"] = metrics.hit_rate(table)
            row[f"{label}_far"] = metrics.false_alarm_ratio(table)
            row[f"{label}_csi"] = metrics.csi(table)
            row[f"{label}_onsets"] = onset_count
            row[f"{label}_onset_hit_rate"] = onset_rate
        rows.append(row)
    return pd.DataFrame(rows)


SCORE_COLUMNS = [
    "nse",
    "kge",
    "high_hit_rate",
    "high_far",
    "high_csi",
    "high_onset_hit_rate",
    "low_hit_rate",
    "low_far",
    "low_csi",
    "low_onset_hit_rate",
]


def summarise(per_catchment: pd.DataFrame) -> pd.DataFrame:
    """Median and quartiles across catchments, per model and lead.

    `per_catchment` has one row per gauge, lead, model and seed. Models run
    with several seeds are first averaged over seeds within each catchment.
    `seed_sd` is the standard deviation, across seeds, of the across-catchment
    median: how much the headline number moves when only the seed changes.
    """
    keys = ["model", "lead_days"]
    seed_mean = per_catchment.groupby([*keys, "gauge_id"], observed=True)[SCORE_COLUMNS].mean()
    grouped = seed_mean.groupby(keys, observed=True)
    median = grouped.median()
    q25 = grouped.quantile(0.25)
    q75 = grouped.quantile(0.75)
    count = grouped.count()

    by_seed = per_catchment.groupby([*keys, "seed"], observed=True)[SCORE_COLUMNS].median()
    seed_sd = by_seed.groupby(keys, observed=True).std(ddof=1)
    n_seeds = per_catchment.groupby(keys, observed=True)["seed"].nunique()

    long = []
    for (model, lead), _ in median.iterrows():
        for score in SCORE_COLUMNS:
            long.append(
                {
                    "model": model,
                    "lead_days": lead,
                    "metric": score,
                    "median": median.loc[(model, lead), score],
                    "q25": q25.loc[(model, lead), score],
                    "q75": q75.loc[(model, lead), score],
                    "n_catchments": int(count.loc[(model, lead), score]),
                    "n_seeds": int(n_seeds.loc[(model, lead)]),
                    "seed_sd": seed_sd.loc[(model, lead), score]
                    if n_seeds.loc[(model, lead)] > 1
                    else np.nan,
                }
            )
    return pd.DataFrame(long)
