"""Experiment 6 follow-up: choose LSTM settings on the validation years only.

    python scripts/tune_lstm.py            eight candidate settings, seed 0, needs a GPU
    python scripts/tune_lstm.py --smoke    a two-minute check of the code on a CPU

Protocol: docs/protocol_week4.md, amendment 2, written before this was run.

Each candidate is trained once (seed 0) on the training years of every
catchment, stopped on the validation loss as in Experiment 6, and then
forecasts the validation years (2005 to 2012). The candidate with the highest
median validation NSE, averaged over the three leads, is written to
results/lstm_tuning_choice.json. The test years are never read here.

Then run `python scripts/run_lstm.py --tuned` to train the chosen settings
with three seeds and score them on the test years.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rew import lstm, metrics  # noqa: E402
from rew.load import VARIABLES, load_all, load_attributes  # noqa: E402
from rew.splits import config_from_splits, load_splits  # noqa: E402

# Fixed in amendment 2 before any of these was run. "fine" means shorter
# sampling epochs, so early stopping can act before the model overfits:
# in Experiment 6 the best validation loss came at epoch 1 or 2 of 2,000,000
# windows in every run.
FINE = {"windows_per_epoch": 500_000, "epochs": 60, "patience": 6}
CANDIDATES: dict[str, dict] = {
    "c0_original": {},
    "c1_fine_stopping": {**FINE},
    "c2_lr3e-4": {**FINE, "learning_rate": 3e-4},
    "c3_lr1e-4": {**FINE, "learning_rate": 1e-4},
    "c4_hidden128": {**FINE, "learning_rate": 3e-4, "hidden": 128},
    "c5_hidden64": {**FINE, "learning_rate": 3e-4, "hidden": 64},
    "c6_weight_decay": {**FINE, "learning_rate": 3e-4, "weight_decay": 1e-2},
    "c7_window90": {**FINE, "learning_rate": 3e-4, "window": 90},
}
SMOKE = {"hidden": 16, "batch": 128, "epochs": 2, "windows_per_epoch": 2048, "validation_fraction": 0.01}


def validation_nse(forecast: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """NSE per catchment and lead on the validation target dates."""
    rows = []
    for (gauge, lead), block in forecast.groupby(["gauge_id", "lead_days"], observed=True):
        obs = frames[gauge]["flow"].reindex(pd.DatetimeIndex(block["date"])).to_numpy(dtype=float)
        sim = block["forecast"].to_numpy(dtype=float)
        keep = np.isfinite(obs) & np.isfinite(sim)
        if keep.sum() < 365:
            continue
        rows.append({"gauge_id": gauge, "lead_days": int(lead), "nse": metrics.nse(obs[keep], sim[keep])})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--only", nargs="*", help="run only these candidates")
    parser.add_argument("--smoke", action="store_true", help="tiny run to check the code, not a result")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()
    if args.device == "cpu" and not args.smoke:
        sys.exit("No GPU found. Use --smoke to check the code.")

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = sorted(saved["gauge_ids"])
    tag = ""
    if args.smoke:
        gauges, tag = gauges[:: max(1, len(gauges) // 12)][:12], "_smoke"
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
    index = panel.index_of(gauges)
    scaler = lstm.fit_scaler(panel, index)
    tensors = lstm.to_tensors(panel, scaler, args.device)
    out_dir = args.results / f"raw_lstm_tuning{tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    names = args.only or list(CANDIDATES)
    for name in names:
        path = out_dir / f"{name}.json"
        if path.exists():
            print(f"{name}: already done", flush=True)
            continue
        overrides = {**CANDIDATES[name], **(SMOKE if args.smoke else {})}
        settings = lstm.Settings(**overrides)
        print(f"{name}: {settings}", flush=True)
        started = time.time()
        model, history = lstm.train(panel, tensors, index, settings, 0, print)
        forecast = lstm.predict(panel, tensors, scaler, model, index, split="validation", window=settings.window)
        scores = validation_nse(forecast, frames)
        medians = scores.groupby("lead_days")["nse"].median()
        best = min(history, key=lambda row: row["validation_loss"])
        record = {
            "name": name,
            "settings": dataclasses.asdict(settings),
            "best_epoch": best["epoch"],
            "epochs_run": len(history),
            "best_validation_loss": best["validation_loss"],
            "validation_median_nse": {str(lead): float(value) for lead, value in medians.items()},
            "validation_median_nse_mean": float(medians.mean()),
            "catchments_scored": int(scores["gauge_id"].nunique()),
            "minutes": round((time.time() - started) / 60, 1),
            "history": history,
        }
        path.write_text(json.dumps(record, indent=1))
        print(f"{name}: median validation NSE {record['validation_median_nse']} "
              f"(mean {record['validation_median_nse_mean']:.4f}), best epoch {best['epoch']}, "
              f"{record['minutes']} min", flush=True)
        del model
        if args.device == "cuda":
            torch.cuda.empty_cache()

    records = [json.loads((out_dir / f"{name}.json").read_text())
               for name in CANDIDATES if (out_dir / f"{name}.json").exists()]
    table = pd.DataFrame([{
        "candidate": r["name"],
        **{f"nse_lead{lead}": r["validation_median_nse"].get(str(lead)) for lead in lstm.LEADS},
        "nse_mean": r["validation_median_nse_mean"],
        "best_validation_loss": r["best_validation_loss"],
        "best_epoch": r["best_epoch"],
        "epochs_run": r["epochs_run"],
        "minutes": r["minutes"],
    } for r in records])
    table.to_csv(args.results / f"table_lstm_tuning_validation{tag}.csv", index=False)
    lines = ["Validation years only (2005 to 2012), seed 0, median NSE across catchments. "
             "The test years were not used.", "",
             "| Candidate | NSE 1 day | NSE 3 days | NSE 7 days | Mean | Best validation loss | Best epoch | Epochs run |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for _, row in table.iterrows():
        lines.append(f"| {row['candidate']} | {row['nse_lead1']:.3f} | {row['nse_lead3']:.3f} | {row['nse_lead7']:.3f} | "
                     f"{row['nse_mean']:.4f} | {row['best_validation_loss']:.4f} | {row['best_epoch']} | {row['epochs_run']} |")
    if len(records) == len(CANDIDATES):
        # Highest mean validation NSE; ties go to the lower validation loss.
        winner = sorted(records, key=lambda r: (-round(r["validation_median_nse_mean"], 4), r["best_validation_loss"]))[0]
        choice = {"chosen": winner["name"], "settings": winner["settings"],
                  "rule": "highest median validation NSE averaged over leads 1, 3, 7; tie to lower validation loss",
                  "smoke": bool(args.smoke)}
        if args.smoke:
            choice["settings"] = dataclasses.asdict(lstm.Settings(**CANDIDATES[winner["name"]]))
        (args.results / f"lstm_tuning_choice{tag}.json").write_text(json.dumps(choice, indent=1))
        lines += ["", f"Chosen: **{winner['name']}**."]
    else:
        lines += ["", f"{len(records)} of {len(CANDIDATES)} candidates done; no choice written yet."]
    (args.results / f"table_lstm_tuning_validation{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
