"""Run the three baselines and write the week 1 results tables.

    python scripts/run_baselines.py

Stage 1 (slow, resumable): for every catchment, make test-period forecasts at
each lead time and save them under results/raw/. A catchment whose file
already exists is skipped, so an interrupted run can simply be restarted.

Stage 2 (fast): score every forecast and write
    results/per_catchment_baselines.csv   one row per catchment, lead, model, seed
    results/table_baselines.csv           medians and quartiles across catchments
    results/table_baselines.md            the same headline numbers, readable

Models
    persistence          flow on the issue day
    seasonal             day-of-year average from the training years
    gbm                  gradient boosting, NO future weather (headline), 3 seeds
    gbm_perfect_forecast gradient boosting given observed weather over the
                         forecast window. An UPPER BOUND, not a real forecast. 1 seed
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

from rew import LEAD_DAYS
from rew.baselines import gbm, persistence, seasonal
from rew.evaluate import score_catchment_lead, summarise
from rew.features import make_xy
from rew.load import VARIABLES, load_all
from rew.splits import assign_split, build_splits, config_from_splits, load_config, load_splits
from rew.thresholds import train_thresholds

SEEDS = (0, 1, 2)
ROOT = Path(__file__).resolve().parents[1]


def predict_catchment(gauge_id: str, frame: pd.DataFrame, config: dict, raw_dir: Path) -> str:
    """Stage 1 for one catchment. Writes results/raw/<gauge_id>.parquet."""
    out_path = raw_dir / f"{gauge_id}.parquet"
    if out_path.exists():
        return "skipped"
    train_start = pd.Timestamp(config["train"]["start"])
    train_end = pd.Timestamp(config["train"]["end"])
    flow = frame["flow"]
    climatology = seasonal.fit(flow, train_start, train_end)

    parts = []
    trees = {}
    for lead in LEAD_DAYS:
        features, target = make_xy(frame, lead, future_weather=False)
        split = assign_split(features.index, config).set_axis(features.index)
        test_dates = features.index[(split == "test").to_numpy()]

        block = pd.DataFrame(index=test_dates)
        block["obs"] = target.reindex(test_dates)
        block["persistence"] = persistence.predict(flow, lead).reindex(test_dates)
        block["seasonal"] = seasonal.predict(climatology, test_dates)
        for seed in SEEDS:
            forecast, n_trees = gbm.fit_predict(features, target, split, seed)
            block[f"gbm_seed{seed}"] = forecast
            trees[f"lead{lead}_seed{seed}"] = n_trees

        features_pf, target_pf = make_xy(frame, lead, future_weather=True)
        split_pf = assign_split(features_pf.index, config).set_axis(features_pf.index)
        forecast, n_trees = gbm.fit_predict(features_pf, target_pf, split_pf, SEEDS[0])
        block["gbm_perfect_forecast"] = forecast.reindex(test_dates)
        trees[f"lead{lead}_perfect"] = n_trees

        block.insert(0, "lead_days", lead)
        parts.append(block.rename_axis("date").reset_index())

    result = pd.concat(parts, ignore_index=True)
    result.attrs = {}
    temporary = out_path.with_suffix(".tmp")
    result.to_parquet(temporary, index=False)
    temporary.replace(out_path)
    (raw_dir / f"{gauge_id}.trees.json").write_text(json.dumps(trees))
    return "done"


def score_catchment(gauge_id: str, frame: pd.DataFrame, config: dict, raw_dir: Path) -> pd.DataFrame:
    """Stage 2 for one catchment: score its saved forecasts."""
    raw = pd.read_parquet(raw_dir / f"{gauge_id}.parquet")
    flow = frame["flow"]
    high, low = train_thresholds(
        flow, pd.Timestamp(config["train"]["start"]), pd.Timestamp(config["train"]["end"])
    )
    obs_yesterday_all = flow.shift(1)
    rows = []
    for lead, block in raw.groupby("lead_days"):
        block = block.set_index("date").drop(columns="lead_days")
        scores = score_catchment_lead(block, obs_yesterday_all, high, low)
        scores.insert(0, "lead_days", int(lead))
        rows.append(scores)
    out = pd.concat(rows, ignore_index=True)
    # Split "gbm_seed1" into model "gbm" and seed 1; other models have seed 0.
    seed = out["model"].str.extract(r"_seed(\d+)$")[0]
    out["seed"] = seed.fillna("0").astype(int)
    out["model"] = out["model"].str.replace(r"_seed\d+$", "", regex=True)
    out.insert(0, "gauge_id", gauge_id)
    out["threshold_high"] = high
    out["threshold_low"] = low
    return out


def to_markdown(summary: pd.DataFrame) -> str:
    """A readable version of the headline medians."""
    order = ["persistence", "seasonal", "gbm", "gbm_perfect_forecast"]
    labels = {
        "nse": "NSE",
        "kge": "KGE",
        "high_csi": "High-flow CSI",
        "high_onset_hit_rate": "High-flow onset hit rate",
        "low_csi": "Low-flow CSI",
        "low_onset_hit_rate": "Low-flow onset hit rate",
    }
    lines = [
        "Median across catchments, test period (water years 2013 to 2022).",
        "`gbm_perfect_forecast` sees observed weather over the forecast window: an upper bound, not a forecast.",
        "",
    ]
    for lead in sorted(summary["lead_days"].unique()):
        lines += [f"**Lead {lead} day{'s' if lead > 1 else ''}**", ""]
        lines.append("| Model | " + " | ".join(labels.values()) + " |")
        lines.append("| --- | " + " | ".join("---:" for _ in labels) + " |")
        for model in order:
            cells = []
            for metric in labels:
                hit = summary[
                    (summary["model"] == model)
                    & (summary["lead_days"] == lead)
                    & (summary["metric"] == metric)
                ]
                cells.append("" if hit.empty else f"{hit['median'].iloc[0]:.3f}")
            lines.append(f"| {model} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the week 1 baselines")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None, help="only the first N catchments (smoke test)")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    tidy = load_all(args.data)
    splits_path = ROOT / "splits" / "splits_v1.json"
    if not splits_path.exists():
        build_splits(tidy, load_config(ROOT / "configs" / "splits.yaml"), splits_path)
    saved = load_splits(splits_path)
    config = config_from_splits(saved)
    gauges = saved["gauge_ids"][: args.limit] if args.limit else saved["gauge_ids"]
    print(f"{len(gauges)} catchments, leads {LEAD_DAYS}, splits {saved['sha256'][:12]}")

    raw_dir = args.results / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    frames = {
        gauge: group.set_index("date")[VARIABLES]
        for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
    }
    del tidy

    started = time.time()
    statuses = Parallel(n_jobs=args.jobs, verbose=5)(
        delayed(predict_catchment)(gauge, frames[gauge], config, raw_dir) for gauge in gauges
    )
    print(f"Stage 1: {statuses.count('done')} fitted, {statuses.count('skipped')} already present, "
          f"{(time.time() - started) / 60:.1f} min")

    per_catchment = pd.concat(
        [score_catchment(gauge, frames[gauge], config, raw_dir) for gauge in gauges],
        ignore_index=True,
    )
    summary = summarise(per_catchment)
    suffix = f"_first{args.limit}" if args.limit else ""
    per_catchment.to_csv(args.results / f"per_catchment_baselines{suffix}.csv", index=False)
    summary.to_csv(args.results / f"table_baselines{suffix}.csv", index=False)
    (args.results / f"table_baselines{suffix}.md").write_text(to_markdown(summary))
    print(f"Wrote results to {args.results}")


if __name__ == "__main__":
    main()
