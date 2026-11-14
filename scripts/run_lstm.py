"""Experiment 6: train the regional LSTM and score it on the test years.

    python scripts/run_lstm.py                 three seeds, all catchments
    python scripts/run_lstm.py --unseen        also hold out each region in turn
    python scripts/run_lstm.py --smoke         a two-minute check on a CPU

Protocol: docs/protocol_week4.md. Each trained model's forecasts are saved
under results/raw_lstm/, and a finished model is not trained again, so the
script can be stopped and restarted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rew import lstm  # noqa: E402
from rew.evaluate import SCORE_COLUMNS, score_catchment_lead  # noqa: E402
from rew.load import VARIABLES, load_all, load_attributes  # noqa: E402
from rew.spatial import load_folds  # noqa: E402
from rew.splits import config_from_splits, load_splits  # noqa: E402
from rew.thresholds import train_thresholds  # noqa: E402


def fit_and_forecast(panel, train_gauges, predict_gauges, settings, seed, device, out_path, log) -> pd.DataFrame:
    """Train on `train_gauges` and forecast the test years of `predict_gauges`."""
    if out_path.exists():
        log(f"{out_path.name}: already done")
        return pd.read_parquet(out_path)
    if set(predict_gauges) - set(train_gauges) and set(predict_gauges) & set(train_gauges):
        raise AssertionError("Forecast catchments must be all seen or all held out")
    train_index = panel.index_of(train_gauges)
    scaler = lstm.fit_scaler(panel, train_index)
    tensors = lstm.to_tensors(panel, scaler, device)
    log(f"{out_path.name}: training on {len(train_gauges)} catchments, seed {seed}")
    model, history = lstm.train(panel, tensors, train_index, settings, seed, log)
    forecast = lstm.predict(panel, tensors, scaler, model, panel.index_of(predict_gauges))
    temporary = out_path.with_suffix(".tmp")
    forecast.to_parquet(temporary, index=False)
    temporary.replace(out_path)
    out_path.with_suffix(".history.json").write_text(json.dumps(history, indent=2))
    return forecast


def score(forecasts: dict[str, pd.DataFrame], frames, config, gauges) -> pd.DataFrame:
    """Score every model column on the days where all of them have a forecast."""
    start, end = pd.Timestamp(config["train"]["start"]), pd.Timestamp(config["train"]["end"])
    test_start, test_end = pd.Timestamp(config["test"]["start"]), pd.Timestamp(config["test"]["end"])
    by_gauge = {name: dict(tuple(table.groupby("gauge_id"))) for name, table in forecasts.items()}
    rows = []
    for gauge in gauges:
        flow = frames[gauge]["flow"]
        high, low = train_thresholds(flow, start, end)
        for lead in lstm.LEADS:
            block = pd.DataFrame({"obs": flow, "persistence": flow.shift(lead)}).loc[test_start:test_end]
            for name, tables in by_gauge.items():
                if gauge not in tables:
                    continue
                table = tables[gauge]
                table = table[table["lead_days"] == lead]
                block[name] = table.set_index("date")["forecast"].reindex(block.index)
            scores = score_catchment_lead(block, flow.shift(1), high, low)
            scores.insert(0, "lead_days", lead)
            scores.insert(0, "gauge_id", gauge)
            rows.append(scores)
    return pd.concat(rows, ignore_index=True)


def load_boosting(results: Path, seed: int, name: str) -> pd.DataFrame | None:
    """Raw forecasts of the regional boosting model for the same seed, if present."""
    raw = results / ("raw_regional" if seed == 0 else f"raw_regional_seed{seed}")
    parts = []
    for lead in lstm.LEADS:
        if name == "regional_unseen":
            paths = sorted(raw.glob(f"lead{lead}_regional_unseen_region*.parquet"))
        else:
            paths = [raw / f"lead{lead}_{name}.parquet"]
        if not paths or not all(path.exists() for path in paths):
            return None
        parts.append(pd.concat([pd.read_parquet(path) for path in paths]).assign(lead_days=lead))
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2])
    parser.add_argument("--unseen", action="store_true", help="also hold out each region in turn")
    parser.add_argument("--smoke", action="store_true", help="tiny run to check the code, not a result")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = sorted(saved["gauge_ids"])
    settings = lstm.Settings()
    tag = ""
    if args.smoke:
        gauges = gauges[:: max(1, len(gauges) // 12)][:12]
        settings = lstm.Settings(hidden=16, batch=128, epochs=2, windows_per_epoch=2048, validation_fraction=0.01)
        args.seeds, tag = [0], "_smoke"
    elif args.device == "cpu":
        sys.exit("No GPU found. Use --smoke to check the code, or see README for the PyTorch install.")
    print(f"device {args.device}; {len(gauges)} catchments; seeds {args.seeds}; {settings}", flush=True)
    if args.device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}; torch {torch.__version__}", flush=True)
        torch.backends.cudnn.benchmark = True

    attributes = load_attributes(args.data)
    tidy = load_all(args.data)
    frames = {
        gauge: group.set_index("date")[VARIABLES]
        for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
    }
    del tidy
    panel = lstm.build_panel(frames, attributes, config)
    raw_dir = args.results / f"raw_lstm{tag}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    folds = load_folds(ROOT / "splits" / "spatial_folds_v1.json") if args.unseen else {}
    all_scores = []
    for seed in args.seeds:
        forecasts = {"lstm_seen": fit_and_forecast(
            panel, gauges, gauges, settings, seed, args.device, raw_dir / f"seed{seed}_seen.parquet", print)}
        if args.unseen:
            parts = []
            for fold in sorted(set(folds.values())):
                held_out = [g for g in gauges if folds[g] == fold]
                kept = [g for g in gauges if folds[g] != fold]
                parts.append(fit_and_forecast(
                    panel, kept, held_out, settings, seed, args.device,
                    raw_dir / f"seed{seed}_unseen_region{fold}.parquet", print))
            forecasts["lstm_unseen"] = pd.concat(parts, ignore_index=True)
        for name in ("regional_seen", "regional_unseen"):
            boosting = None if args.smoke else load_boosting(args.results, seed, name)
            if boosting is not None and (name == "regional_seen" or args.unseen):
                forecasts[name] = boosting
        if "regional_seen" not in forecasts and not args.smoke:
            print("results/raw_regional not found: the LSTM is scored beside persistence only. "
                  "Run scripts/run_regional.py for a like-for-like comparison.", flush=True)
        scores = score(forecasts, frames, config, gauges)
        scores.insert(0, "seed", seed)
        all_scores.append(scores)

    per_catchment = pd.concat(all_scores, ignore_index=True)
    per_catchment.to_csv(args.results / f"per_catchment_lstm{tag}.csv", index=False)
    by_seed = per_catchment.groupby(["model", "lead_days", "seed"])[SCORE_COLUMNS].median()
    table = by_seed.groupby(["model", "lead_days"]).agg(["mean", "std"]).round(4)
    table.columns = [f"{column}_{stat}" for column, stat in table.columns]
    table.reset_index().to_csv(args.results / f"table_lstm{tag}.csv", index=False)

    lines = ["Median across catchments on the test years, then the mean over seeds "
             f"(seeds {args.seeds}). All models in a row group are scored on the same days.", ""]
    lines += ["| Lead | Model | NSE | KGE | High-flow CSI | Low-flow CSI |", "| ---: | --- | ---: | ---: | ---: | ---: |"]
    for (model, lead), row in table.reset_index().set_index(["model", "lead_days"]).sort_index(level=1).iterrows():
        lines.append(f"| {lead} | {model} | {row['nse_mean']:.3f} | {row['kge_mean']:.3f} | "
                     f"{row['high_csi_mean']:.3f} | {row['low_csi_mean']:.3f} |")
    if "regional_seen" in set(per_catchment["model"]):
        wide = per_catchment.pivot_table(index=["seed", "lead_days", "gauge_id"], columns="model", values="nse")
        gap = (wide["lstm_seen"] - wide["regional_seen"]).groupby("lead_days")
        lines += ["", "LSTM minus regional boosting, NSE per catchment (all seeds pooled):", "",
                  "| Lead | Median difference | Share of catchments where the LSTM is better |", "| ---: | ---: | ---: |"]
        for lead, values in gap:
            lines.append(f"| {lead} | {values.median():+.3f} | {100 * (values > 0).mean():.0f}% |")
    (args.results / f"table_lstm{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
