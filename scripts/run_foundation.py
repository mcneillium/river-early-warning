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
run restarts where it left off. Each variant is scored beside persistence,
the regional boosting model and the LSTM (seed 0 of each) on identical days.
"""

from __future__ import annotations

import argparse
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
from rew.evaluate import SCORE_COLUMNS  # noqa: E402
from rew.load import VARIABLES, load_all, load_attributes  # noqa: E402
from rew.splits import config_from_splits, load_splits  # noqa: E402

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
        obs = pd.concat([frames[g]["flow"].reindex(pd.DatetimeIndex(b["date"])).reset_index(drop=True)
                         for g, b in block.groupby("gauge_id", sort=False)], ignore_index=True)
        ordered = pd.concat([b for _, b in block.groupby("gauge_id", sort=False)], ignore_index=True)
        ok = obs.notna().to_numpy()
        inside = (obs.to_numpy() >= ordered["q05"].to_numpy()) & (obs.to_numpy() <= ordered["q95"].to_numpy())
        rows.append({"variant": variant, "lead_days": lead, "coverage_all_days": float(inside[ok].mean()),
                     "median_width_mm_day": float((ordered["q95"] - ordered["q05"])[ok].median())})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS))
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--smoke", action="store_true", help="3 catchments, 60 issue days, CPU; not a result")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    protocol = (ROOT / "docs" / "protocol_week5.md").read_text(encoding="utf-8")
    if not args.smoke:
        if UNFILLED in protocol:
            sys.exit("docs/protocol_week5.md still has sections marked 'TO BE WRITTEN BY PAUL'. "
                     "Write the question and prediction first, commit, then run.")
        if args.device == "cpu":
            sys.exit("No GPU found. Use --smoke to check the code.")
    from chronos import Chronos2Pipeline

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = sorted(saved["gauge_ids"])
    tag = ""
    if args.smoke:
        gauges, tag = gauges[:: max(1, len(gauges) // 3)][:3], "_smoke"
    attributes = load_attributes(args.data)
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
    print(f"{len(gauges)} catchments, {len(days)} issue days each, variants {args.variants}", flush=True)

    collected = []
    for variant in args.variants:
        out_dir = args.results / f"raw_foundation{tag}" / variant
        out_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        for i, gauge in enumerate(gauges):
            path = out_dir / f"{gauge}.parquet"
            if not path.exists():
                table = forecast_catchment(pipeline, panel, panel.index_of([gauge])[0], variant, days, args.batch_size)
                table.to_parquet(path.with_suffix(".tmp"), index=False)
                path.with_suffix(".tmp").replace(path)
            if (i + 1) % 50 == 0 or i + 1 == len(gauges):
                print(f"  {variant}: {i + 1}/{len(gauges)} catchments, {(time.time() - started) / 60:.1f} min", flush=True)
        collected.append(pd.concat([pd.read_parquet(out_dir / f"{g}.parquet") for g in gauges],
                                   ignore_index=True).assign(variant=variant))
    foundation = pd.concat(collected, ignore_index=True)

    import run_lstm  # scoring identical to Experiment 6

    forecasts = {v: foundation[foundation["variant"] == v].drop(columns=["variant", "q05", "q95"]) for v in args.variants}
    if not args.smoke:
        lstm_path = args.results / "raw_lstm" / "seed0_seen.parquet"
        if lstm_path.exists():
            forecasts["lstm_seen"] = pd.read_parquet(lstm_path)
        boosting = run_lstm.load_boosting(args.results, 0, "regional_seen")
        if boosting is not None:
            forecasts["regional_seen"] = boosting
    per_catchment = run_lstm.score(forecasts, frames, config, gauges)
    per_catchment.to_csv(args.results / f"per_catchment_foundation{tag}.csv", index=False)
    table = per_catchment.groupby(["model", "lead_days"])[SCORE_COLUMNS].median().round(4).reset_index()
    table.to_csv(args.results / f"table_foundation{tag}.csv", index=False)
    coverage = interval_coverage(foundation, frames)
    coverage.to_csv(args.results / f"table_foundation_coverage{tag}.csv", index=False)

    lines = ["Experiment 7. Median across catchments on the test years. Trained models are seed 0. "
             "All models in a row group are scored on the same days.", "",
             "| Lead | Model | NSE | KGE | High-flow CSI | Low-flow CSI |", "| ---: | --- | ---: | ---: | ---: | ---: |"]
    for _, row in table.sort_values(["lead_days", "model"]).iterrows():
        lines.append(f"| {row['lead_days']} | {row['model']} | {row['nse']:.3f} | {row['kge']:.3f} | "
                     f"{row['high_csi']:.3f} | {row['low_csi']:.3f} |")
    lines += ["", "90% range (0.05 to 0.95 quantiles), no calibration step:", "",
              "| Variant | Lead | Coverage | Median width (mm/day) |", "| --- | ---: | ---: | ---: |"]
    for _, row in coverage.iterrows():
        lines.append(f"| {row['variant']} | {row['lead_days']} | {row['coverage_all_days']:.3f} | {row['median_width_mm_day']:.3f} |")
    (args.results / f"table_foundation{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
