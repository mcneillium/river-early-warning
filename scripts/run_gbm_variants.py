"""Experiment 1b: repair the boosting baseline, choosing on validation years only.

    python scripts/run_gbm_variants.py

Follows docs/protocol_week2.md exactly.

Stage 1  Fit the four declared variants (seed 0) for every catchment and lead,
         and save their forecasts for the validation AND test years.
Stage 2  Score the VALIDATION years, apply the selection rule, write the choice.
Stage 3  Fit the chosen variant with seeds 1 and 2.
Stage 4  Score the test years once: week 1 models beside the chosen variant.

Outputs
    results/table_gbm_variants_validation.csv   what the choice was based on
    results/gbm_variant_choice.json             the choice and the rule's numbers
    results/table_baselines_v2.csv / .md        test scores including the chosen variant
    results/per_catchment_baselines_v2.csv
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

from rew import LEAD_DAYS
from rew.baselines import gbm, persistence
from rew.evaluate import score_catchment_lead, summarise
from rew.features import make_xy
from rew.load import VARIABLES, load_all
from rew.splits import assign_split, config_from_splits, load_splits
from rew.thresholds import train_thresholds

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "raw_es30"
NSE_TOLERANCE = 0.02
EXTRA_SEEDS = (1, 2)


def fit_variants(gauge_id: str, frame: pd.DataFrame, config: dict, out_dir: Path) -> str:
    """Stage 1 for one catchment: all four variants, validation and test forecasts."""
    out_path = out_dir / f"{gauge_id}.parquet"
    if out_path.exists():
        return "skipped"
    parts, trees = [], {}
    for lead in LEAD_DAYS:
        features, target = make_xy(frame, lead)
        split = assign_split(features.index, config).set_axis(features.index)
        keep = split.isin(["validation", "test"]).to_numpy()
        block = pd.DataFrame(index=features.index[keep])
        block["split"] = split[keep].to_numpy()
        block["obs"] = target[keep]
        block["persistence"] = persistence.predict(frame["flow"], lead).reindex(block.index)
        for name, settings in gbm.VARIANTS.items():
            forecast, n_trees = gbm.fit_predict(
                features, target, split, seed=0,
                target_scale=settings["target"], patience=settings["patience"],
                predict_splits=("validation", "test"),
            )
            block[name] = forecast
            trees[f"lead{lead}_{name}"] = n_trees
        block.insert(0, "lead_days", lead)
        parts.append(block.rename_axis("date").reset_index())
    temporary = out_path.with_suffix(".tmp")
    pd.concat(parts, ignore_index=True).to_parquet(temporary, index=False)
    temporary.replace(out_path)
    (out_dir / f"{gauge_id}.trees.json").write_text(json.dumps(trees))
    return "done"


def fit_extra_seeds(gauge_id: str, frame: pd.DataFrame, config: dict, out_dir: Path, variant: str) -> str:
    """Stage 3 for one catchment: the chosen variant with seeds 1 and 2, test years."""
    out_path = out_dir / f"{gauge_id}.{variant}.seeds.parquet"
    if out_path.exists():
        return "skipped"
    settings = gbm.VARIANTS[variant]
    parts = []
    for lead in LEAD_DAYS:
        features, target = make_xy(frame, lead)
        split = assign_split(features.index, config).set_axis(features.index)
        block = pd.DataFrame(index=features.index[(split == "test").to_numpy()])
        for seed in EXTRA_SEEDS:
            forecast, _ = gbm.fit_predict(
                features, target, split, seed=seed,
                target_scale=settings["target"], patience=settings["patience"],
            )
            block[f"seed{seed}"] = forecast
        block.insert(0, "lead_days", lead)
        parts.append(block.rename_axis("date").reset_index())
    temporary = out_path.with_suffix(".tmp")
    pd.concat(parts, ignore_index=True).to_parquet(temporary, index=False)
    temporary.replace(out_path)
    return "done"


def score_split(gauge_id: str, frame: pd.DataFrame, config: dict, out_dir: Path, which: str) -> pd.DataFrame:
    """Score every variant for one catchment on the validation or the test years."""
    raw = pd.read_parquet(out_dir / f"{gauge_id}.parquet")
    raw = raw[raw["split"] == which].drop(columns="split")
    high, low = train_thresholds(
        frame["flow"], pd.Timestamp(config["train"]["start"]), pd.Timestamp(config["train"]["end"])
    )
    yesterday = frame["flow"].shift(1)
    rows = []
    for lead, block in raw.groupby("lead_days"):
        scores = score_catchment_lead(block.set_index("date").drop(columns="lead_days"), yesterday, high, low)
        scores.insert(0, "lead_days", int(lead))
        rows.append(scores)
    out = pd.concat(rows, ignore_index=True)
    out.insert(0, "gauge_id", gauge_id)
    out["seed"] = 0
    return out


def choose_variant(validation_summary: pd.DataFrame) -> dict:
    """Apply the selection rule from the protocol to validation-period medians."""
    medians = validation_summary.pivot_table(index=["model", "lead_days"], columns="metric", values="median")
    record = {}
    for name in gbm.VARIANTS:
        rows = medians.loc[name]
        record[name] = {
            "warning_score": float(rows[["high_csi", "low_csi"]].to_numpy().mean()),
            "mean_nse": float(rows["nse"].mean()),
        }
    floor = record[BASELINE]["mean_nse"] - NSE_TOLERANCE
    for name in record:
        record[name]["eligible"] = bool(record[name]["mean_nse"] >= floor)
    eligible = [name for name in gbm.VARIANTS if record[name]["eligible"]]
    # max() returns the first of equal values, and VARIANTS is in order of simplicity
    chosen = max(eligible, key=lambda name: round(record[name]["warning_score"], 6))
    return {"chosen": chosen, "nse_floor": floor, "variants": record}


def test_table(gauges, frames, config, week1_raw: Path, variant_dir: Path, chosen: str) -> pd.DataFrame:
    """Stage 4: week 1 forecasts plus the chosen variant (3 seeds), scored on the same test days."""
    rows = []
    for gauge in gauges:
        frame = frames[gauge]
        week1 = pd.read_parquet(week1_raw / f"{gauge}.parquet")
        variants = pd.read_parquet(variant_dir / f"{gauge}.parquet")
        variants = variants[variants["split"] == "test"][["date", "lead_days", chosen]]
        extra = pd.read_parquet(variant_dir / f"{gauge}.{chosen}.seeds.parquet")
        merged = week1.merge(variants, on=["date", "lead_days"]).merge(extra, on=["date", "lead_days"])
        merged = merged.rename(
            columns={chosen: "gbm_selected_seed0", "seed1": "gbm_selected_seed1", "seed2": "gbm_selected_seed2"}
        )
        high, low = train_thresholds(
            frame["flow"], pd.Timestamp(config["train"]["start"]), pd.Timestamp(config["train"]["end"])
        )
        yesterday = frame["flow"].shift(1)
        for lead, block in merged.groupby("lead_days"):
            scores = score_catchment_lead(block.set_index("date").drop(columns="lead_days"), yesterday, high, low)
            scores.insert(0, "lead_days", int(lead))
            scores.insert(0, "gauge_id", gauge)
            rows.append(scores)
    out = pd.concat(rows, ignore_index=True)
    seed = out["model"].str.extract(r"_seed(\d+)$")[0]
    out["seed"] = seed.fillna("0").astype(int)
    out["model"] = out["model"].str.replace(r"_seed\d+$", "", regex=True)
    return out


def to_markdown(summary: pd.DataFrame, chosen: str) -> str:
    order = ["persistence", "seasonal", "gbm", "gbm_selected", "gbm_perfect_forecast"]
    labels = {
        "nse": "NSE", "kge": "KGE",
        "high_csi": "High-flow CSI", "high_onset_hit_rate": "High-flow onset hit rate",
        "low_csi": "Low-flow CSI", "low_onset_hit_rate": "Low-flow onset hit rate",
    }
    lines = [
        "Median across catchments, test period (water years 2013 to 2022).",
        f"`gbm` is the week 1 baseline. `gbm_selected` is the variant `{chosen}`, chosen on validation years only.",
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
                hit = summary[(summary["model"] == model) & (summary["lead_days"] == lead) & (summary["metric"] == metric)]
                cells.append("" if hit.empty else f"{hit['median'].iloc[0]:.3f}")
            lines.append(f"| {model} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = saved["gauge_ids"][: args.limit] if args.limit else saved["gauge_ids"]
    tidy = load_all(args.data)
    frames = {
        gauge: group.set_index("date")[VARIABLES]
        for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
    }
    del tidy
    variant_dir = args.results / "raw_variants"
    variant_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_first{args.limit}" if args.limit else ""

    started = time.time()
    status = Parallel(n_jobs=args.jobs, verbose=1)(
        delayed(fit_variants)(gauge, frames[gauge], config, variant_dir) for gauge in gauges
    )
    print(f"Stage 1: {status.count('done')} fitted, {status.count('skipped')} present, {(time.time() - started) / 60:.1f} min")

    validation = pd.concat(
        [score_split(gauge, frames[gauge], config, variant_dir, "validation") for gauge in gauges], ignore_index=True
    )
    validation_summary = summarise(validation)
    validation_summary.to_csv(args.results / f"table_gbm_variants_validation{suffix}.csv", index=False)
    choice = choose_variant(validation_summary)
    (args.results / f"gbm_variant_choice{suffix}.json").write_text(json.dumps(choice, indent=1))
    chosen = choice["chosen"]
    print(f"Stage 2: chosen variant = {chosen}")

    started = time.time()
    status = Parallel(n_jobs=args.jobs, verbose=1)(
        delayed(fit_extra_seeds)(gauge, frames[gauge], config, variant_dir, chosen) for gauge in gauges
    )
    print(f"Stage 3: {status.count('done')} fitted, {status.count('skipped')} present, {(time.time() - started) / 60:.1f} min")

    per_catchment = test_table(gauges, frames, config, args.results / "raw", variant_dir, chosen)
    summary = summarise(per_catchment)
    per_catchment.to_csv(args.results / f"per_catchment_baselines_v2{suffix}.csv", index=False)
    summary.to_csv(args.results / f"table_baselines_v2{suffix}.csv", index=False)
    (args.results / f"table_baselines_v2{suffix}.md").write_text(to_markdown(summary, chosen))
    print("Stage 4: test tables written")


if __name__ == "__main__":
    main()
