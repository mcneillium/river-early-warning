"""Experiment 5, stage 2: score the quantile forecasts.

    python scripts/score_quantiles.py

Reads the forecasts saved by scripts/run_quantiles.py and follows
docs/protocol_week3.md. Nothing is fitted here, so it runs in a few minutes
and can be repeated freely.

Outputs (all in results/)
    quantile_tau_choice.json           the warning quantiles chosen on the calibration half
    table_quantile_warnings.csv / .md  test-period warning scores, four models
    table_interval_coverage.csv / .md  honesty of the 90% range, before and after the conformal step
    table_quantile_reliability.csv     share of observations below each quantile
    per_catchment_quantile.csv         the per-catchment numbers behind the tables
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

import numpy as np
import pandas as pd

from rew import LEAD_DAYS, metrics, quantile
from rew.load import VARIABLES, load_all
from rew.spatial import N_FOLDS, load_folds
from rew.splits import config_from_splits, load_splits
from rew.thresholds import train_thresholds

ROOT = Path(__file__).resolve().parents[1]
Q_COLUMNS = [quantile.column(q) for q in quantile.QUANTILES]
LOW_COL, HIGH_COL = quantile.column(quantile.INTERVAL[0]), quantile.column(quantile.INTERVAL[1])
WARNING_METRICS = ["high_csi", "high_hit_rate", "high_far", "high_onset_hit_rate",
                   "low_csi", "low_hit_rate", "low_far", "low_onset_hit_rate"]


def load_seen(raw_dir: Path, lead: int) -> pd.DataFrame:
    """All seven seen-model quantiles side by side, sorted so they never cross."""
    base = None
    for q in quantile.QUANTILES:
        part = pd.read_parquet(raw_dir / f"lead{lead}_seen_{quantile.column(q)}.parquet")
        if base is None:
            base = part[["gauge_id", "date", "split"]].copy()
        elif not (part["gauge_id"].to_numpy() == base["gauge_id"].to_numpy()).all() or not (
            part["date"].to_numpy() == base["date"].to_numpy()
        ).all():
            raise ValueError("Quantile files are not row-aligned")
        base[quantile.column(q)] = part["forecast"].to_numpy()
    raw = base[Q_COLUMNS].to_numpy(dtype=float)
    steps = np.diff(raw, axis=1)
    crossed = (steps < 0).any(axis=1)
    # Size of the worst crossing on a day, relative to that day's median forecast.
    size = (-steps.min(axis=1))[crossed] / (raw[crossed, Q_COLUMNS.index("q50")] + 1e-6)
    base[Q_COLUMNS] = quantile.sort_quantiles(raw)
    base.attrs["share_rows_with_crossing"] = float(crossed.mean())
    base.attrs["median_crossing_relative_size"] = float(np.median(size)) if size.size else 0.0
    base.attrs["share_rows_crossing_over_5pct"] = float((size > 0.05).sum() / len(raw))
    return base


def load_unseen(raw_dir: Path, lead: int, fold: int) -> pd.DataFrame:
    low = pd.read_parquet(raw_dir / f"lead{lead}_unseen_region{fold}_{LOW_COL}.parquet")
    high = pd.read_parquet(raw_dir / f"lead{lead}_unseen_region{fold}_{HIGH_COL}.parquet")
    merged = low.rename(columns={"forecast": "lower"})
    merged["upper"] = high["forecast"].to_numpy()
    both = np.sort(merged[["lower", "upper"]].to_numpy(), axis=1)
    merged["lower"], merged["upper"] = both[:, 0], both[:, 1]
    return merged


def add_observations(table: pd.DataFrame, frames: dict[str, pd.DataFrame], lead: int) -> pd.DataFrame:
    """Attach the observed flow, yesterday's flow and the issue-day flow to each row."""
    parts = []
    for gauge, block in table.groupby("gauge_id", sort=False):
        flow = frames[gauge]["flow"]
        dates = pd.DatetimeIndex(block["date"])
        block = block.copy()
        block["obs"] = flow.reindex(dates).to_numpy()
        block["obs_yesterday"] = flow.shift(1).reindex(dates).to_numpy()
        block["persistence"] = flow.shift(lead).reindex(dates).to_numpy()
        parts.append(block)
    return pd.concat(parts, ignore_index=True)


def interval_row(label: str, stage: str, lead: int, block: pd.DataFrame, lower: str, upper: str,
                 adjustment: float) -> dict:
    """Coverage and width of one range on the test years, pooled and per catchment."""
    per_catchment = block.groupby("gauge_id").apply(
        lambda g: quantile.coverage(g[lower], g[upper], g["obs"]), include_groups=False
    )
    return {
        "lead_days": lead, "model": label, "stage": stage,
        "coverage_all_days": quantile.coverage(block[lower], block[upper], block["obs"]),
        "coverage_median_catchment": float(per_catchment.median()),
        "coverage_5th_percentile_catchment": float(per_catchment.quantile(0.05)),
        "coverage_95th_percentile_catchment": float(per_catchment.quantile(0.95)),
        "share_catchments_below_80pct": float((per_catchment < 0.80).mean()),
        "median_width_mm_day": float((block[upper] - block[lower]).median()),
        "adjustment_log_units": adjustment,
        "n_catchments": int(per_catchment.size), "n_days": int(len(block)),
    }


def csi_only(event: np.ndarray, forecast: np.ndarray) -> float:
    return metrics.csi(metrics.contingency(event, forecast))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--leads", type=int, nargs="*", default=list(LEAD_DAYS))
    leads = parser.parse_args().leads
    results = ROOT / "results"
    raw_dir = results / "raw_quantiles"
    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = saved["gauge_ids"]
    folds = load_folds(ROOT / "splits" / "spatial_folds_v1.json")
    train_start, train_end = pd.Timestamp(config["train"]["start"]), pd.Timestamp(config["train"]["end"])

    tidy = load_all(ROOT / "data")
    frames = {
        gauge: group.set_index("date")[VARIABLES]
        for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
    }
    del tidy
    thresholds = {g: train_thresholds(frames[g]["flow"], train_start, train_end) for g in gauges}

    choice, warning_rows, interval_rows, reliability_rows, catchment_rows = {}, [], [], [], []
    for lead in leads:
        loaded = load_seen(raw_dir, lead)
        crossing_notes = dict(loaded.attrs)
        seen = add_observations(loaded, frames, lead)

        # The persistence-band baseline, built from each catchment's own training years.
        band = np.full((len(seen), len(Q_COLUMNS)), np.nan)
        for gauge, index in seen.groupby("gauge_id", sort=False).indices.items():
            flow = frames[gauge]["flow"]
            offsets = quantile.persistence_band_offsets(flow, lead, train_start, train_end)
            band[index] = quantile.persistence_band_forecast(
                flow, lead, offsets, pd.DatetimeIndex(seen["date"].to_numpy()[index])
            )
        band_columns = [f"band_{name}" for name in Q_COLUMNS]
        seen[band_columns] = band

        point = pd.read_parquet(results / "raw_regional" / f"lead{lead}_regional_seen.parquet").rename(
            columns={"forecast": "regional_point"}
        )
        seen = seen.merge(point, on=["gauge_id", "date"], how="left")

        calibration = seen[(seen["split"] == "calibration") & seen["obs"].notna()]
        test = seen[(seen["split"] == "test") & seen["obs"].notna()]

        # ----- reliability of every quantile -----
        for q, name in zip(quantile.QUANTILES, Q_COLUMNS):
            reliability_rows.append({
                "lead_days": lead, "quantile": q,
                "share_below_test": float((test["obs"] < test[name]).mean()),
                "share_below_calibration": float((calibration["obs"] < calibration[name]).mean()),
                "share_below_test_persistence_band": float(
                    (test["obs"] < test[f"band_{name}"])[test[f"band_{name}"].notna()].mean()
                ),
            })

        # ----- the 90% range, before and after the conformal step -----
        adjustment = quantile.conformal_adjustment(calibration[LOW_COL], calibration[HIGH_COL], calibration["obs"])
        test = test.copy()
        test["adj_lower"], test["adj_upper"] = quantile.apply_adjustment(test[LOW_COL], test[HIGH_COL], adjustment)
        interval_rows.append(interval_row("quantile model, seen", "raw", lead, test, LOW_COL, HIGH_COL, 0.0))
        interval_rows.append(interval_row("quantile model, seen", "conformal", lead, test, "adj_lower", "adj_upper", adjustment))

        band_cal = calibration[calibration[f"band_{LOW_COL}"].notna()]
        band_test = test[test[f"band_{LOW_COL}"].notna()].copy()
        band_adjustment = quantile.conformal_adjustment(
            band_cal[f"band_{LOW_COL}"], band_cal[f"band_{HIGH_COL}"], band_cal["obs"]
        )
        band_test["band_adj_lower"], band_test["band_adj_upper"] = quantile.apply_adjustment(
            band_test[f"band_{LOW_COL}"], band_test[f"band_{HIGH_COL}"], band_adjustment
        )
        interval_rows.append(interval_row("persistence band", "raw", lead, band_test,
                                          f"band_{LOW_COL}", f"band_{HIGH_COL}", 0.0))
        interval_rows.append(interval_row("persistence band", "conformal", lead, band_test,
                                          "band_adj_lower", "band_adj_upper", band_adjustment))

        # ----- unseen regions: calibrated on the other four regions only -----
        unseen_parts, fold_adjustments = [], []
        for fold in range(N_FOLDS):
            part = add_observations(load_unseen(raw_dir, lead, fold), frames, lead)
            cal = part[(part["split"] == "calibration") & part["obs"].notna()]
            held = part[(part["split"] == "test") & part["obs"].notna()].copy()
            fold_adjustment = quantile.conformal_adjustment(cal["lower"], cal["upper"], cal["obs"])
            held["adj_lower"], held["adj_upper"] = quantile.apply_adjustment(held["lower"], held["upper"], fold_adjustment)
            fold_adjustments.append(fold_adjustment)
            unseen_parts.append(held)
        unseen = pd.concat(unseen_parts, ignore_index=True)
        mean_adjustment = float(np.mean(fold_adjustments))
        interval_rows.append(interval_row("quantile model, unseen", "raw", lead, unseen, "lower", "upper", 0.0))
        interval_rows.append(interval_row("quantile model, unseen", "conformal", lead, unseen,
                                          "adj_lower", "adj_upper", mean_adjustment))

        # ----- choose the warning quantiles on the calibration half -----
        choice[f"lead{lead}"] = {"quantile_crossing": crossing_notes}
        for prefix, label in (("", "quantile_model"), ("band_", "persistence_band")):
            high_scores = {tau: [] for tau in quantile.HIGH_CANDIDATES}
            low_scores = {tau: [] for tau in quantile.LOW_CANDIDATES}
            usable = calibration[calibration[f"{prefix}{LOW_COL}"].notna()]
            for gauge, block in usable.groupby("gauge_id", sort=False):
                high, low = thresholds[gauge]
                obs = block["obs"].to_numpy()
                for tau in quantile.HIGH_CANDIDATES:
                    high_scores[tau].append(csi_only(obs > high, block[f"{prefix}{quantile.column(tau)}"].to_numpy() > high))
                for tau in quantile.LOW_CANDIDATES:
                    low_scores[tau].append(csi_only(obs < low, block[f"{prefix}{quantile.column(tau)}"].to_numpy() < low))
            high_median = {tau: float(np.nanmedian(values)) for tau, values in high_scores.items()}
            low_median = {tau: float(np.nanmedian(values)) for tau, values in low_scores.items()}
            choice[f"lead{lead}"][label] = {
                "tau_high": quantile.choose_tau(high_median, quantile.HIGH_CANDIDATES),
                "tau_low": quantile.choose_tau(low_median, quantile.LOW_CANDIDATES),
                "calibration_median_high_csi": {str(k): v for k, v in high_median.items()},
                "calibration_median_low_csi": {str(k): v for k, v in low_median.items()},
            }

        # ----- test-period warnings, four models on the same days -----
        picked = choice[f"lead{lead}"]
        forecasts = {
            "persistence": ("persistence", "persistence"),
            "regional_point": ("regional_point", "regional_point"),
            "persistence_band": (f"band_{quantile.column(picked['persistence_band']['tau_high'])}",
                                 f"band_{quantile.column(picked['persistence_band']['tau_low'])}"),
            "quantile_model": (quantile.column(picked["quantile_model"]["tau_high"]),
                               quantile.column(picked["quantile_model"]["tau_low"])),
        }
        needed = sorted({name for pair in forecasts.values() for name in pair})
        complete = test[test[needed].notna().all(axis=1)]
        seen_cover = test.groupby("gauge_id").apply(
            lambda g: pd.Series({
                "coverage_seen_raw": quantile.coverage(g[LOW_COL], g[HIGH_COL], g["obs"]),
                "coverage_seen_conformal": quantile.coverage(g["adj_lower"], g["adj_upper"], g["obs"]),
            }), include_groups=False)
        unseen_cover = unseen.groupby("gauge_id").apply(
            lambda g: pd.Series({
                "coverage_unseen_raw": quantile.coverage(g["lower"], g["upper"], g["obs"]),
                "coverage_unseen_conformal": quantile.coverage(g["adj_lower"], g["adj_upper"], g["obs"]),
            }), include_groups=False)
        for gauge, block in complete.groupby("gauge_id", sort=False):
            high, low = thresholds[gauge]
            for model, (high_name, low_name) in forecasts.items():
                row = quantile.warning_scores(block["obs"], block["obs_yesterday"], block[high_name],
                                              block[low_name], high, low)
                catchment_rows.append({
                    "gauge_id": gauge, "region": folds[gauge], "lead_days": lead, "model": model, **row,
                    **(seen_cover.loc[gauge].to_dict() if gauge in seen_cover.index else {}),
                    **(unseen_cover.loc[gauge].to_dict() if gauge in unseen_cover.index else {}),
                })
        print(f"lead {lead}: scored {complete['gauge_id'].nunique()} catchments; "
              f"conformal adjustment {adjustment:+.3f} (seen), {mean_adjustment:+.3f} (unseen, mean of folds)", flush=True)
        # Each lead's tables hold several million rows; release them before the next lead.
        del loaded, seen, band, point, calibration, test, band_cal, band_test, unseen_parts, unseen, complete
        gc.collect()

    per_catchment = pd.DataFrame(catchment_rows)
    per_catchment.to_csv(results / "per_catchment_quantile.csv", index=False)
    grouped = per_catchment.groupby(["lead_days", "model"], observed=True)
    warnings_table = grouped[WARNING_METRICS].median()
    warnings_table["warnings_per_event_high"] = grouped.apply(
        lambda g: g["high_warnings"].sum() / max(g["high_events"].sum(), 1), include_groups=False)
    warnings_table["warnings_per_event_low"] = grouped.apply(
        lambda g: g["low_warnings"].sum() / max(g["low_events"].sum(), 1), include_groups=False)
    warnings_table["n_catchments"] = grouped["gauge_id"].nunique()
    warnings_table = warnings_table.reset_index()
    warnings_table.to_csv(results / "table_quantile_warnings.csv", index=False)
    intervals = pd.DataFrame(interval_rows)
    intervals.to_csv(results / "table_interval_coverage.csv", index=False)
    pd.DataFrame(reliability_rows).to_csv(results / "table_quantile_reliability.csv", index=False)
    (results / "quantile_tau_choice.json").write_text(json.dumps(choice, indent=1))

    order = ["persistence", "regional_point", "persistence_band", "quantile_model"]
    lines = ["Median across catchments, test period (water years 2013 to 2022). No future weather.",
             "`regional_point` is the single-number regional model of Experiment 3.",
             "`persistence_band` and `quantile_model` warn when a chosen forecast quantile crosses the threshold;",
             "the quantile was chosen on the calibration half (2009 to 2012) only.",
             "CSI = critical success index; FAR = false alarm ratio (share of warnings that were wrong).", ""]
    for lead in leads:
        picked = choice[f"lead{lead}"]
        lines += [f"**Lead {lead} day{'s' if lead > 1 else ''}** "
                  f"(quantile model warns on {picked['quantile_model']['tau_high']} for high flow, "
                  f"{picked['quantile_model']['tau_low']} for low flow; "
                  f"persistence band on {picked['persistence_band']['tau_high']} and {picked['persistence_band']['tau_low']})", "",
                  "| Model | High CSI | High hit rate | High FAR | High onset hit rate | Low CSI | Low hit rate | Low FAR | Low onset hit rate |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for model in order:
            row = warnings_table[(warnings_table["lead_days"] == lead) & (warnings_table["model"] == model)].iloc[0]
            lines.append(f"| {model} | " + " | ".join(
                "" if pd.isna(row[m]) else f"{row[m]:.3f}" for m in WARNING_METRICS) + " |")
        lines.append("")
    (results / "table_quantile_warnings.md").write_text("\n".join(lines))

    lines = ["The 90% range (0.05 to 0.95 quantile) on the test period. Target coverage: 0.90.",
             "`conformal` = after the calibration step, which uses 2009 to 2012 only.",
             "`unseen` = each region forecast and calibrated by models that never saw it.", "",
             "| Lead | Model | Stage | Coverage, all days | Median catchment | 5th to 95th percentile of catchments | Catchments under 80% | Median width (mm/day) |",
             "| ---: | --- | --- | ---: | ---: | --- | ---: | ---: |"]
    for _, row in intervals.iterrows():
        lines.append(
            f"| {int(row['lead_days'])} | {row['model']} | {row['stage']} | {row['coverage_all_days']:.3f} | "
            f"{row['coverage_median_catchment']:.3f} | {row['coverage_5th_percentile_catchment']:.3f} to "
            f"{row['coverage_95th_percentile_catchment']:.3f} | {100 * row['share_catchments_below_80pct']:.0f}% | "
            f"{row['median_width_mm_day']:.3f} |")
    (results / "table_interval_coverage.md").write_text("\n".join(lines) + "\n")
    print("Tables written", flush=True)


if __name__ == "__main__":
    main()
