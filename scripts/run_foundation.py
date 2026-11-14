"""Experiment 7: a general time-series foundation model, used with no training.

    python scripts/run_foundation.py --smoke    a few minutes on a CPU, 3 catchments, not a result
    python scripts/run_foundation.py            all catchments, test years, needs a GPU

Protocol: docs/protocol_week5.md. The full run refuses to start until the
question and the prediction in that protocol have been written.

Chronos-2 (Ansari et al., 2025) forecasts flow 1 to 7 days ahead from the
last 365 days, the same history the LSTM of Experiment 6 reads. It is never
trained or fine-tuned on these rivers. Two variants:

    chronos2_flow_only   past flow only
    chronos2_weather     past flow, with past rain, temperature and PET as covariates

Neither sees weather after the issue day, as for every other model here.
Forecasts are saved per catchment under results/raw_foundation/, so a stopped
run restarts where it left off. Tables go to results/exp7/.

Scoring (protocol_week5.md): for each trained-model seed s in 0, 1, 2, every
model is scored on the days where all models in that comparison have a
forecast. A paired difference is computed per catchment and seed, averaged
over the three seeds, and its median across catchments is reported. Two
comparisons: all 659 catchments against the seen models, and the 167 dry
catchments of the wet-to-dry test against the wet-trained models.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rew import lstm  # noqa: E402
from rew.load import VARIABLES, load_all, load_attributes  # noqa: E402
from rew.splits import config_from_splits, load_splits  # noqa: E402

MARGIN = 0.01  # the single improvement margin of protocol_week5.md
SEEDS = (0, 1, 2)
WARNING_METRICS = ("high_csi", "high_hit_rate", "high_far", "high_onset_hit_rate",
                   "low_csi", "low_hit_rate", "low_far", "low_onset_hit_rate")
CONTEXT = 365
HORIZON = max(lstm.LEADS)
QUANTILES = (0.05, 0.5, 0.95)
VARIANTS = ("chronos2_flow_only", "chronos2_weather")
MODEL_ID = "amazon/chronos-2"
UNFILLED = "TO BE WRITTEN BY PAUL"


def inputs_for(panel: lstm.Panel, catchment: int, days: np.ndarray, variant: str) -> list[dict]:
    """One input per issue day: the CONTEXT days ending on that day, nothing later."""
    flow = np.expm1(panel.dynamic[catchment, :, lstm.FLOW])  # back to mm/day; NaN stays NaN
    weather = {name: panel.dynamic[catchment, :, lstm.DYNAMIC.index(name)] for name in ("precip", "temp", "pet")}
    out = []
    for day in days:
        window = slice(day - CONTEXT + 1, day + 1)
        item = {"target": flow[window].astype(np.float32)}
        if variant == "chronos2_weather":
            item["past_covariates"] = {name: series[window].astype(np.float32) for name, series in weather.items()}
        out.append(item)
    return out


def forecast_catchment(pipeline, panel, catchment, variant, days, batch_size) -> pd.DataFrame:
    quantiles, _ = pipeline.predict_quantiles(
        inputs_for(panel, catchment, days, variant), prediction_length=HORIZON,
        quantile_levels=list(QUANTILES), batch_size=batch_size)
    values = torch.stack([q[0] for q in quantiles]).float().cpu().numpy()  # (issue day, horizon, quantile)
    in_test = lstm.split_mask(panel, "test")
    blocks = []
    for lead in lstm.LEADS:
        keep = in_test[days + lead]
        step = values[keep, lead - 1, :]
        blocks.append(pd.DataFrame({
            "gauge_id": panel.gauges[catchment],
            "date": panel.dates[days[keep] + lead],
            "lead_days": lead,
            "forecast": np.clip(step[:, QUANTILES.index(0.5)], 0.0, None).astype(np.float32),
            "q05": np.clip(step[:, QUANTILES.index(0.05)], 0.0, None).astype(np.float32),
            "q95": np.clip(step[:, QUANTILES.index(0.95)], 0.0, None).astype(np.float32),
        }))
    return pd.concat(blocks, ignore_index=True)


def interval_coverage(forecasts: pd.DataFrame, frames) -> pd.DataFrame:
    rows = []
    for (variant, lead), block in forecasts.groupby(["variant", "lead_days"]):
        obs = np.concatenate([frames[g]["flow"].reindex(pd.DatetimeIndex(b["date"])).to_numpy()
                              for g, b in block.groupby("gauge_id", sort=False)])
        ordered = pd.concat([b for _, b in block.groupby("gauge_id", sort=False)], ignore_index=True)
        ok = np.isfinite(obs)
        inside = (obs >= ordered["q05"].to_numpy()) & (obs <= ordered["q95"].to_numpy())
        rows.append({"variant": variant, "lead_days": lead, "coverage_all_days": float(inside[ok].mean()),
                     "median_width_mm_day": float((ordered["q95"] - ordered["q05"])[ok].median()),
                     "n_observations": int(ok.sum())})
    return pd.DataFrame(rows)


def band(value: float) -> str:
    """The interpretation rule fixed in protocol_week5.md. Not an equivalence test."""
    if value > MARGIN:
        return "exceeds the improvement margin"
    if value < -MARGIN:
        return "worse by more than the margin"
    return "within the practical comparison band"


def paired(per_catchment: pd.DataFrame, model: str, reference: str) -> pd.DataFrame:
    """Median across catchments of (model - reference) NSE, averaged over seeds first.

    Both models were scored in the same call for each seed, so each catchment's
    difference is on identical valid dates. A catchment counts only if it has a
    difference for every seed present.
    """
    wide = per_catchment.pivot_table(index=["seed", "lead_days", "gauge_id"], columns="model", values="nse")
    if model not in wide or reference not in wide:
        return pd.DataFrame()
    difference = (wide[model] - wide[reference]).dropna()
    n_seeds = per_catchment["seed"].nunique()
    counts = difference.groupby(["lead_days", "gauge_id"]).size()
    averaged = difference.groupby(["lead_days", "gauge_id"]).mean()[counts == n_seeds]
    rows = []
    for lead, values in averaged.groupby("lead_days"):
        median = float(values.median())
        rows.append({"model": model, "reference": reference, "lead_days": int(lead),
                     "median_paired_difference": median, "share_model_better": float((values > 0).mean()),
                     "n_catchments": int(values.size), "n_seeds": int(n_seeds), "interpretation": band(median)})
    return pd.DataFrame(rows)


def warning_summary(per_catchment: pd.DataFrame) -> pd.DataFrame:
    """Per model and lead: scores averaged over seeds per catchment, then summarised.

    A catchment's score is "undefined" if no seed gives it a value (for example
    no observed and no forecast events), and "zero" if it is defined and 0.
    Denominators are per catchment, seed 0: events (hit rate), warnings (false
    alarm ratio), events plus false alarms (CSI) and onsets (onset hit rate).
    """
    columns = ["nse", *WARNING_METRICS]
    averaged = per_catchment.groupby(["model", "lead_days", "gauge_id"])[columns].mean()
    first = per_catchment[per_catchment["seed"] == per_catchment["seed"].min()].set_index(
        ["model", "lead_days", "gauge_id"]).sort_index()
    rows = []
    for (model, lead), block in averaged.groupby(level=["model", "lead_days"]):
        row = {"model": model, "lead_days": int(lead), "n_catchments": int(len(block)),
               "nse_median": float(block["nse"].median())}
        for metric in WARNING_METRICS:
            values = block[metric]
            defined = values.dropna()
            row[f"{metric}_median_defined"] = float(defined.median()) if len(defined) else float("nan")
            row[f"{metric}_n_defined"] = int(defined.size)
            row[f"{metric}_n_zero"] = int((defined == 0).sum())
            row[f"{metric}_n_undefined"] = int(values.isna().sum())
        denominators = first.loc[(model, lead)]
        for label in ("high", "low"):
            false_alarms = denominators[f"{label}_warnings"] - denominators[f"{label}_hits"]
            row[f"{label}_events_median"] = float(denominators[f"{label}_events"].median())
            row[f"{label}_warnings_median"] = float(denominators[f"{label}_warnings"].median())
            row[f"{label}_csi_denominator_median"] = float((denominators[f"{label}_events"] + false_alarms).median())
            row[f"{label}_onsets_median"] = float(denominators[f"{label}_onsets"].median())
        rows.append(row)
    return pd.DataFrame(rows)


# Recorded in protocol_week5.md before the run. Each test takes the median paired difference.
PREDICTIONS = [
    ("all", "chronos2_flow_only", "lstm_seen", 1, "between -0.05 and +0.01", lambda d: -0.05 <= d <= 0.01),
    ("all", "chronos2_flow_only", "lstm_seen", 3, "-0.03 or lower", lambda d: d <= -0.03),
    ("all", "chronos2_flow_only", "lstm_seen", 7, "-0.05 or lower", lambda d: d <= -0.05),
    ("all", "chronos2_weather", "chronos2_flow_only", 1, "at least +0.01", lambda d: d >= 0.01),
    ("all", "chronos2_weather", "chronos2_flow_only", 3, "less than +0.01", lambda d: d < 0.01),
    ("all", "chronos2_weather", "chronos2_flow_only", 7, "less than +0.01", lambda d: d < 0.01),
    ("dry", "chronos2_weather", "lstm_wet_only", 1, "more than +0.01", lambda d: d > 0.01),
]

PAIRS = {
    "all": [("chronos2_flow_only", "lstm_seen"), ("chronos2_weather", "lstm_seen"),
            ("chronos2_weather", "chronos2_flow_only"), ("chronos2_flow_only", "regional_seen"),
            ("chronos2_weather", "regional_seen"), ("chronos2_flow_only", "persistence"),
            ("chronos2_weather", "persistence")],
    "dry": [("chronos2_weather", "lstm_wet_only"), ("chronos2_flow_only", "lstm_wet_only"),
            ("chronos2_weather", "regional_wet_only"), ("chronos2_flow_only", "regional_wet_only"),
            ("chronos2_weather", "lstm_seen"), ("chronos2_weather", "regional_seen"),
            ("chronos2_weather", "chronos2_flow_only"), ("chronos2_weather", "persistence")],
}


def score_by_seed(foundation: dict[str, pd.DataFrame], trained: dict[str, str], results: Path, frames, config,
                  gauges, seeds, run_lstm) -> pd.DataFrame:
    """Score the foundation variants beside each seed of the trained models."""
    parts = []
    for seed in seeds:
        forecasts = dict(foundation)
        for name, source in trained.items():
            if source == "lstm":
                path = results / "raw_lstm" / f"seed{seed}_{name.removeprefix('lstm_')}.parquet"
                table = pd.read_parquet(path) if path.exists() else None
            else:
                table = run_lstm.load_boosting(results, seed, name)
            if table is None:
                raise FileNotFoundError(f"{name}, seed {seed}: forecasts not found; run Experiments 3 and 6 first")
            forecasts[name] = table
        scores = run_lstm.score(forecasts, frames, config, gauges)
        scores.insert(0, "seed", seed)
        parts.append(scores)
    return pd.concat(parts, ignore_index=True)


def markdown_tables(name: str, summary: pd.DataFrame, pairs: pd.DataFrame) -> list[str]:
    lines = [f"### {name}", "", "Scores averaged over the three trained-model seeds per catchment, then the median "
             "across catchments. CSI and hit rates: median of the catchments where the score is defined; "
             "zero and undefined counted separately.", "",
             "| Lead | Model | Catchments | NSE | High CSI | High hit rate | High FAR | High onset hit rate "
             "| Low CSI (zero / undefined) | Low hit rate | Low FAR | Low onset hit rate |",
             "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |"]
    def f(value):
        return "" if pd.isna(value) else f"{value:.3f}"
    for _, r in summary.sort_values(["lead_days", "model"]).iterrows():
        lines.append(
            f"| {r['lead_days']} | {r['model']} | {r['n_catchments']} | {f(r['nse_median'])} | "
            f"{f(r['high_csi_median_defined'])} | {f(r['high_hit_rate_median_defined'])} | {f(r['high_far_median_defined'])} | "
            f"{f(r['high_onset_hit_rate_median_defined'])} | {f(r['low_csi_median_defined'])} "
            f"({r['low_csi_n_zero']} / {r['low_csi_n_undefined']}) | {f(r['low_hit_rate_median_defined'])} | "
            f"{f(r['low_far_median_defined'])} | {f(r['low_onset_hit_rate_median_defined'])} |")
    lines += ["", "Paired NSE differences (model minus reference), per catchment on identical valid dates, averaged "
              f"over seeds, median across catchments. Margin {MARGIN}; the band is not an equivalence test.", "",
              "| Lead | Model | Reference | Median difference | Model better in | Catchments | Interpretation |",
              "| ---: | --- | --- | ---: | ---: | ---: | --- |"]
    for _, r in pairs.sort_values(["lead_days"], kind="stable").iterrows():
        lines.append(f"| {r['lead_days']} | {r['model']} | {r['reference']} | {r['median_paired_difference']:+.3f} | "
                     f"{100 * r['share_model_better']:.0f}% | {r['n_catchments']} | {r['interpretation']} |")
    return lines + [""]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--smoke", action="store_true", help="a few catchments, 60 issue days, CPU; not a result")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    protocol = (ROOT / "docs" / "protocol_week5.md").read_text(encoding="utf-8")
    if not args.smoke:
        if UNFILLED in protocol:
            sys.exit("docs/protocol_week5.md still has sections marked 'TO BE WRITTEN BY PAUL'.")
        if args.device == "cpu":
            sys.exit("No GPU found. Use --smoke to check the code.")
    from chronos import Chronos2Pipeline

    import run_lstm  # the split and the scoring of Experiment 6

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = sorted(saved["gauge_ids"])
    attributes = load_attributes(args.data)
    _, _, _, dry = run_lstm.wet_dry_split(attributes, gauges)
    tag = ""
    if args.smoke:
        gauges = sorted(set(gauges[:: max(1, len(gauges) // 3)][:3]) | set(dry[:2]))
        dry, tag = [g for g in dry if g in gauges], "_smoke"
    out_dir = args.results / f"exp7{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    tidy = load_all(args.data)
    frames = {
        gauge: group.set_index("date")[VARIABLES]
        for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
    }
    del tidy
    panel = lstm.build_panel(frames, attributes, config)
    days = lstm.issue_days(panel, "test", CONTEXT)
    if args.smoke:
        days = days[:60]

    pipeline = Chronos2Pipeline.from_pretrained(MODEL_ID, device_map=args.device)
    if args.device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}; torch {torch.__version__}", flush=True)
    print(f"{len(gauges)} catchments ({len(dry)} in the dry subset), {len(days)} issue days each", flush=True)

    collected, repeat = [], {}
    for variant in VARIANTS:
        raw_dir = args.results / f"raw_foundation{tag}" / variant
        raw_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        for i, gauge in enumerate(gauges):
            path = raw_dir / f"{gauge}.parquet"
            if not path.exists():
                table = forecast_catchment(pipeline, panel, panel.index_of([gauge])[0], variant, days, args.batch_size)
                table.to_parquet(path.with_suffix(".tmp"), index=False)
                path.with_suffix(".tmp").replace(path)
            if (i + 1) % 50 == 0 or i + 1 == len(gauges):
                print(f"  {variant}: {i + 1}/{len(gauges)} catchments, {(time.time() - started) / 60:.1f} min", flush=True)
        # Repeatability: forecast the first two catchments again and compare with the saved files.
        differences = []
        for gauge in gauges[:2]:
            again = forecast_catchment(pipeline, panel, panel.index_of([gauge])[0], variant, days, args.batch_size)
            saved_table = pd.read_parquet(raw_dir / f"{gauge}.parquet")
            differences.append(float(np.abs(again["forecast"].to_numpy() - saved_table["forecast"].to_numpy()).max()))
        repeat[variant] = {"catchments": gauges[:2], "max_abs_difference_mm_day": max(differences)}
        collected.append(pd.concat([pd.read_parquet(raw_dir / f"{g}.parquet") for g in gauges],
                                   ignore_index=True).assign(variant=variant))
    (out_dir / "repeatability.json").write_text(json.dumps(repeat, indent=1))
    foundation_all = pd.concat(collected, ignore_index=True)
    foundation = {v: foundation_all[foundation_all["variant"] == v].drop(columns=["variant", "q05", "q95"])
                  for v in VARIANTS}

    seeds = [0] if args.smoke else list(SEEDS)
    trained_all = {} if args.smoke else {"lstm_seen": "lstm", "regional_seen": "boosting"}
    trained_dry = {} if args.smoke else {"lstm_seen": "lstm", "lstm_wet_only": "lstm",
                                         "regional_seen": "boosting", "regional_wet_only": "boosting"}
    per_all = score_by_seed(foundation, trained_all, args.results, frames, config, gauges, seeds, run_lstm)
    per_dry = score_by_seed({v: t[t["gauge_id"].isin(dry)] for v, t in foundation.items()}, trained_dry,
                            args.results, frames, config, dry, seeds, run_lstm)
    per_all.to_csv(out_dir / "per_catchment_all.csv", index=False)
    per_dry.to_csv(out_dir / "per_catchment_dry.csv", index=False)

    summaries, comparisons = {}, {}
    for name, per in (("all", per_all), ("dry", per_dry)):
        summaries[name] = warning_summary(per)
        frames_ = [paired(per, a, b) for a, b in PAIRS[name]]
        comparisons[name] = pd.concat([f for f in frames_ if len(f)], ignore_index=True) if any(len(f) for f in frames_) else pd.DataFrame()
        summaries[name].to_csv(out_dir / f"table_scores_{name}.csv", index=False)
        comparisons[name].to_csv(out_dir / f"table_paired_{name}.csv", index=False)

    checks = []
    for subset, model, reference, lead, wording, test in PREDICTIONS:
        table = comparisons[subset]
        match = table[(table["model"] == model) & (table["reference"] == reference) & (table["lead_days"] == lead)] \
            if len(table) else table
        value = float(match["median_paired_difference"].iloc[0]) if len(match) else float("nan")
        checks.append({"subset": subset, "model": model, "reference": reference, "lead_days": lead,
                       "predicted": wording, "observed": value,
                       "met": (bool(test(value)) if np.isfinite(value) else None)})
    checks = pd.DataFrame(checks)
    checks.to_csv(out_dir / "table_predictions.csv", index=False)
    coverage = interval_coverage(foundation_all, frames)
    coverage.to_csv(out_dir / "table_coverage.csv", index=False)

    lines = ["# Experiment 7 results" + (" (SMOKE RUN: not a result)" if args.smoke else ""), "",
             "## Predictions recorded before the run", "",
             "| Subset | Model | Reference | Lead | Predicted | Observed | Met |", "| --- | --- | --- | ---: | --- | ---: | --- |"]
    for _, r in checks.iterrows():
        observed = "" if not np.isfinite(r["observed"]) else f"{r['observed']:+.3f}"
        met = "not computed" if r["met"] is None else ("yes" if r["met"] else "no")
        lines.append(f"| {r['subset']} | {r['model']} | {r['reference']} | {r['lead_days']} | {r['predicted']} | {observed} | {met} |")
    lines += ["", "Dry subset at 3 and 7 days: secondary, no directional prediction.", ""]
    lines += markdown_tables("All catchments", summaries["all"], comparisons["all"])
    lines += markdown_tables(f"The {len(dry)} dry catchments of the wet-to-dry test", summaries["dry"], comparisons["dry"])
    lines += ["### 90% range of Chronos-2 (0.05 to 0.95 quantiles), all catchments, no calibration step", "",
              "| Variant | Lead | Coverage | Median width (mm/day) | Observations |", "| --- | ---: | ---: | ---: | ---: |"]
    for _, r in coverage.iterrows():
        lines.append(f"| {r['variant']} | {r['lead_days']} | {r['coverage_all_days']:.3f} | "
                     f"{r['median_width_mm_day']:.3f} | {r['n_observations']:,} |")
    lines += ["", f"Repeatability (same inputs forecast twice): {json.dumps(repeat)}"]
    (out_dir / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
