"""Experiment 6: train the regional LSTM and score it on the test years.

    python scripts/run_lstm.py                 three seeds, all catchments
    python scripts/run_lstm.py --unseen        also hold out each region in turn
    python scripts/run_lstm.py --smoke         a two-minute check on a CPU
    python scripts/run_lstm.py --wet-to-dry    train on wet catchments, forecast dry ones
    python scripts/run_lstm.py --tuned         use the settings chosen by scripts/tune_lstm.py

Protocol: docs/protocol_week4.md (amendment 2 covers --tuned and --wet-to-dry). Each trained model's forecasts are saved
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
    forecast = lstm.predict(panel, tensors, scaler, model, panel.index_of(predict_gauges), window=settings.window)
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


def wet_dry_split(attributes: pd.DataFrame, gauges: list[str]) -> tuple[list[str], list[str], list[str], list[str]]:
    """The wet-to-dry split of scripts/run_regional.py, rebuilt the same way.

    Returns wet, dry, the fixed random half (control) and the dry catchments
    outside that half, which are the catchments every model is scored on.
    """
    aridity = attributes.set_index("gauge_id").loc[gauges, "aridity"].astype(float)
    wet = list(aridity.index[aridity < aridity.median()])
    dry = list(aridity.index[aridity >= aridity.median()])
    half = list(np.random.default_rng(0).choice(sorted(gauges), size=len(wet), replace=False))
    dry_control = [g for g in dry if g not in set(half)]
    return wet, dry, half, dry_control


def write_tables(per_catchment: pd.DataFrame, seeds, prefix: str, reference: str, out_csv: Path, out_md: Path,
                 per_catchment_csv: Path, title: str) -> None:
    per_catchment.to_csv(per_catchment_csv, index=False)
    by_seed = per_catchment.groupby(["model", "lead_days", "seed"])[SCORE_COLUMNS].median()
    table = by_seed.groupby(["model", "lead_days"]).agg(["mean", "std"]).round(4)
    table.columns = [f"{column}_{stat}" for column, stat in table.columns]
    table.reset_index().to_csv(out_csv, index=False)
    lines = [f"{title} Median across catchments on the test years, then the mean over seeds "
             f"(seeds {list(seeds)}). All models in a row group are scored on the same days.", ""]
    lines += ["| Lead | Model | NSE | KGE | High-flow CSI | Low-flow CSI |", "| ---: | --- | ---: | ---: | ---: | ---: |"]
    for (model, lead), row in table.reset_index().set_index(["model", "lead_days"]).sort_index(level=1).iterrows():
        lines.append(f"| {lead} | {model} | {row['nse_mean']:.3f} | {row['kge_mean']:.3f} | "
                     f"{row['high_csi_mean']:.3f} | {row['low_csi_mean']:.3f} |")
    models = set(per_catchment["model"])
    if reference in models and prefix in models:
        wide = per_catchment.pivot_table(index=["seed", "lead_days", "gauge_id"], columns="model", values="nse")
        gap = (wide[prefix] - wide[reference]).groupby("lead_days")
        lines += ["", f"{prefix} minus {reference}, NSE per catchment (all seeds pooled):", "",
                  f"| Lead | Median difference | Share of catchments where {prefix} is better |", "| ---: | ---: | ---: |"]
        for lead, values in gap:
            lines.append(f"| {lead} | {values.median():+.3f} | {100 * (values > 0).mean():.0f}% |")
    out_md.write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


def transfer_cost(per_catchment: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """The measure fixed in protocol_week4.md, amendment 2B.

    Cost of transfer per catchment and seed: NSE of the model trained on fewer
    catchments minus NSE of the seen model of the same family. The median is
    over catchments and seeds pooled, with the range of per-seed medians. The
    LSTM "transfers better" if its median cost is smaller than boosting's by
    more than 0.01, "worse" if larger by more than 0.01, otherwise neither.
    """
    wide = per_catchment.pivot_table(index=["seed", "lead_days", "gauge_id"], columns="model", values="nse")
    rows = []
    for kind in ("wet_only", "random_half"):
        lstm_name, boost_name = f"{prefix}_{kind}", f"regional_{kind}"
        if not {lstm_name, f"{prefix}_seen", boost_name, "regional_seen"} <= set(wide.columns):
            continue
        lstm_cost = wide[lstm_name] - wide[f"{prefix}_seen"]
        boost_cost = wide[boost_name] - wide["regional_seen"]
        for lead in sorted(wide.index.get_level_values("lead_days").unique()):
            lc, bc = lstm_cost.xs(lead, level="lead_days"), boost_cost.xs(lead, level="lead_days")
            difference = lc.median() - bc.median()
            verdict = "better" if difference > 0.01 else "worse" if difference < -0.01 else "neither"
            rows.append({
                "trained_on": kind, "lead_days": lead,
                "lstm_cost": lc.median(), "lstm_cost_seed_min": lc.groupby("seed").median().min(),
                "lstm_cost_seed_max": lc.groupby("seed").median().max(),
                "boosting_cost": bc.median(), "boosting_cost_seed_min": bc.groupby("seed").median().min(),
                "boosting_cost_seed_max": bc.groupby("seed").median().max(),
                "lstm_minus_boosting": difference,
                "share_lstm_loses_less": float(((lc - bc) > 0).mean()),
                "lstm_transfers": verdict,
            })
    return pd.DataFrame(rows)


def append_transfer_markdown(costs: pd.DataFrame, path: Path) -> None:
    lines = ["", "Cost of transfer (protocol amendment 2B): per catchment, NSE of the model trained on fewer "
             "catchments minus the seen model of the same family; median over catchments and seeds, "
             "per-seed range in brackets.", "",
             "| Trained on | Lead | LSTM cost | Boosting cost | LSTM minus boosting | LSTM loses less in | LSTM transfers |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for _, r in costs.iterrows():
        lines.append(f"| {r['trained_on']} | {r['lead_days']} | {r['lstm_cost']:+.3f} ({r['lstm_cost_seed_min']:+.3f} to "
                     f"{r['lstm_cost_seed_max']:+.3f}) | {r['boosting_cost']:+.3f} ({r['boosting_cost_seed_min']:+.3f} to "
                     f"{r['boosting_cost_seed_max']:+.3f}) | {r['lstm_minus_boosting']:+.3f} | "
                     f"{100 * r['share_lstm_loses_less']:.0f}% | {r['lstm_transfers']} |")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--seeds", type=int, nargs="*", default=[0, 1, 2])
    parser.add_argument("--unseen", action="store_true", help="also hold out each region in turn")
    parser.add_argument("--wet-to-dry", action="store_true", help="also train on wet catchments, forecast dry ones")
    parser.add_argument("--tuned", action="store_true", help="settings from results/lstm_tuning_choice.json")
    parser.add_argument("--smoke", action="store_true", help="tiny run to check the code, not a result")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = sorted(saved["gauge_ids"])
    settings = lstm.Settings()
    tag, prefix = "", "lstm"
    if args.tuned:
        choice_path = args.results / "lstm_tuning_choice.json"
        if not choice_path.exists():
            sys.exit("results/lstm_tuning_choice.json not found. Run scripts/tune_lstm.py first.")
        settings = lstm.Settings(**json.loads(choice_path.read_text())["settings"])
        tag, prefix = "_tuned", "lstm_tuned"
    if args.smoke:
        gauges = gauges[:: max(1, len(gauges) // 12)][:12]
        settings = lstm.Settings(hidden=16, batch=128, epochs=2, windows_per_epoch=2048, validation_fraction=0.01,
                                 window=settings.window)
        args.seeds, tag = [0], tag + "_smoke"
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
    wet, dry, half, dry_control = wet_dry_split(attributes, gauges)
    if args.wet_to_dry:
        print(f"wet-to-dry: {len(wet)} wet, {len(dry)} dry, control half {len(half)}, "
              f"scored on {len(dry_control)} dry catchments outside the half", flush=True)
    all_scores, dry_scores = [], []
    for seed in args.seeds:
        seen = fit_and_forecast(panel, gauges, gauges, settings, seed, args.device,
                                raw_dir / f"seed{seed}_seen.parquet", print)
        forecasts = {f"{prefix}_seen": seen}
        if args.tuned and not args.smoke:
            original = args.results / "raw_lstm" / f"seed{seed}_seen.parquet"
            if original.exists():
                forecasts["lstm_seen"] = pd.read_parquet(original)
        if args.unseen:
            parts = []
            for fold in sorted(set(folds.values())):
                held_out = [g for g in gauges if folds[g] == fold]
                kept = [g for g in gauges if folds[g] != fold]
                parts.append(fit_and_forecast(
                    panel, kept, held_out, settings, seed, args.device,
                    raw_dir / f"seed{seed}_unseen_region{fold}.parquet", print))
            forecasts[f"{prefix}_unseen"] = pd.concat(parts, ignore_index=True)
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

        if args.wet_to_dry:
            dry_forecasts = {
                f"{prefix}_seen": seen,
                f"{prefix}_wet_only": fit_and_forecast(panel, wet, dry_control, settings, seed, args.device,
                                                       raw_dir / f"seed{seed}_wet_only.parquet", print),
                f"{prefix}_random_half": fit_and_forecast(panel, half, dry_control, settings, seed, args.device,
                                                          raw_dir / f"seed{seed}_random_half.parquet", print),
            }
            for name in ("regional_seen", "regional_wet_only", "regional_random_half"):
                boosting = None if args.smoke else load_boosting(args.results, seed, name)
                if boosting is not None:
                    # run_regional.py forecasts every dry catchment from the wet model and the dry
                    # catchments outside the half from the control. Check the rebuilt split agrees.
                    expected = {"regional_wet_only": set(dry), "regional_random_half": set(dry_control)}.get(name)
                    if expected is not None and set(boosting["gauge_id"]) != expected:
                        raise AssertionError(f"{name}: boosting forecasts cover different catchments than the "
                                             "rebuilt wet-to-dry split")
                    dry_forecasts[name] = boosting
            dry_block = score(dry_forecasts, frames, config, dry_control)
            dry_block.insert(0, "seed", seed)
            dry_scores.append(dry_block)

    if args.wet_to_dry and not args.unseen:
        # A wet-to-dry run has no unseen-region models, so writing the main tables here
        # would replace Experiment 6's full tables with a shorter version.
        print("Wet-to-dry run: Experiment 6's main tables left unchanged.", flush=True)
    else:
        write_tables(pd.concat(all_scores, ignore_index=True), args.seeds, f"{prefix}_seen",
                     "regional_seen", args.results / f"table_lstm{tag}.csv", args.results / f"table_lstm{tag}.md",
                     args.results / f"per_catchment_lstm{tag}.csv", "Experiment 6.")
    if args.wet_to_dry:
        write_tables(pd.concat(dry_scores, ignore_index=True), args.seeds, f"{prefix}_wet_only",
                     "regional_wet_only", args.results / f"table_lstm_wet_to_dry{tag}.csv",
                     args.results / f"table_lstm_wet_to_dry{tag}.md",
                     args.results / f"per_catchment_lstm_wet_to_dry{tag}.csv",
                     f"Wet-to-dry test, scored on the {len(dry_control)} dry catchments outside the control half.")
        costs = transfer_cost(pd.concat(dry_scores, ignore_index=True), prefix)
        costs.round(4).to_csv(args.results / f"table_lstm_transfer_cost{tag}.csv", index=False)
        append_transfer_markdown(costs, args.results / f"table_lstm_wet_to_dry{tag}.md")


if __name__ == "__main__":
    main()
