"""Experiment 3: catchments the model has never seen.

    python scripts/run_regional.py

Follows docs/protocol_week2.md. For each lead time it trains

    regional_seen      on the training years of all catchments
    regional_unseen    five times, each time leaving one region out, and
                       forecasting only the region that was left out
    regional_wet_only  on the wetter half of catchments, forecasting the drier half
    regional_random_half  a control: a random half of the catchments, forecasting
                       the dry catchments it was not trained on

and scores them on the test years, beside persistence and the per-catchment
model chosen in Experiment 1b. Every model's forecasts are saved separately
under results/raw_regional/, so an interrupted run can be restarted.

Outputs
    results/per_catchment_regional.csv   scores per catchment, lead and model
    results/table_regional.csv / .md     medians, and the seen-to-unseen gap
    results/table_regional_by_region.csv the gap in each held-out region
    results/table_wet_to_dry.csv         wet-trained model on dry catchments
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from rew import LEAD_DAYS
from rew import regional
from rew.baselines import gbm
from rew.evaluate import SCORE_COLUMNS, score_catchment_lead
from rew.load import VARIABLES, load_all, load_attributes
from rew.spatial import N_FOLDS, build_folds, load_folds
from rew.splits import config_from_splits, load_splits
from rew.thresholds import train_thresholds

ROOT = Path(__file__).resolve().parents[1]


def run_models(lead, tables, gauges, folds, wet, dry, half, settings, raw_dir, seed) -> dict[str, int]:
    """Fit every model for one lead time, skipping any whose forecasts exist."""
    trees = {}
    jobs = [("regional_seen", set(gauges), set(gauges))]
    for fold in range(N_FOLDS):
        held_out = {g for g in gauges if folds[g] == fold}
        jobs.append((f"regional_unseen_region{fold}", set(gauges) - held_out, held_out))
    jobs.append(("regional_wet_only", set(wet), set(dry)))
    # Control for the wet-to-dry test: the same number of training catchments,
    # but drawn at random, forecasting the dry catchments it was not trained on.
    jobs.append(("regional_random_half", set(half), set(dry) - set(half)))
    for name, train_gauges, predict_gauges in jobs:
        out_path = raw_dir / f"lead{lead}_{name}.parquet"
        if out_path.exists():
            continue
        started = time.time()
        forecast, n_trees = regional.fit_predict(
            tables, train_gauges, predict_gauges, settings["target"], settings["patience"], seed=seed
        )
        temporary = out_path.with_suffix(".tmp")
        forecast.to_parquet(temporary, index=False)
        temporary.replace(out_path)
        trees[name] = n_trees
        print(f"  lead {lead} {name}: {n_trees} trees, {len(train_gauges)} training catchments, "
              f"{(time.time() - started) / 60:.1f} min", flush=True)
    if trees:
        path = raw_dir / f"lead{lead}_trees.json"
        previous = json.loads(path.read_text()) if path.exists() else {}
        path.write_text(json.dumps({**previous, **trees}))
    return trees


def collect(lead, gauges, raw_dir, variant_dir, chosen) -> pd.DataFrame:
    """One table per lead: observation plus every model's test forecast."""
    seen = pd.read_parquet(raw_dir / f"lead{lead}_regional_seen.parquet").rename(columns={"forecast": "regional_seen"})
    unseen = pd.concat(
        [pd.read_parquet(raw_dir / f"lead{lead}_regional_unseen_region{fold}.parquet") for fold in range(N_FOLDS)],
        ignore_index=True,
    ).rename(columns={"forecast": "regional_unseen"})
    wet_only = pd.read_parquet(raw_dir / f"lead{lead}_regional_wet_only.parquet").rename(
        columns={"forecast": "regional_wet_only"}
    )
    random_half = pd.read_parquet(raw_dir / f"lead{lead}_regional_random_half.parquet").rename(
        columns={"forecast": "regional_random_half"}
    )
    local = []
    for gauge in gauges:
        block = pd.read_parquet(variant_dir / f"{gauge}.parquet")
        block = block[(block["split"] == "test") & (block["lead_days"] == lead)]
        block = block[["date", "obs", "persistence", chosen]].rename(columns={chosen: "gbm_local"})
        block.insert(0, "gauge_id", gauge)
        local.append(block)
    merged = pd.concat(local, ignore_index=True)
    for other in (seen, unseen, wet_only, random_half):
        merged = merged.merge(other, on=["gauge_id", "date"], how="left")
    return merged


def score(merged, frames, config, columns, gauges, lead) -> pd.DataFrame:
    rows = []
    start, end = pd.Timestamp(config["train"]["start"]), pd.Timestamp(config["train"]["end"])
    for gauge, block in merged[merged["gauge_id"].isin(gauges)].groupby("gauge_id"):
        flow = frames[gauge]["flow"]
        high, low = train_thresholds(flow, start, end)
        scores = score_catchment_lead(block.set_index("date")[["obs", *columns]], flow.shift(1), high, low)
        scores.insert(0, "lead_days", lead)
        scores.insert(0, "gauge_id", gauge)
        rows.append(scores)
    return pd.concat(rows, ignore_index=True)


def median_table(per_catchment: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    wanted = ["nse", "kge", "high_csi", "high_onset_hit_rate", "low_csi", "low_onset_hit_rate"]
    table = per_catchment.groupby(by, observed=True)[wanted].median()
    table["n_catchments"] = per_catchment.groupby(by, observed=True)["gauge_id"].nunique()
    return table.reset_index()


def gap_table(per_catchment: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Per-catchment difference, unseen minus seen, then summarised."""
    wide = per_catchment.pivot_table(index=["gauge_id", "region", "lead_days"], columns="model", values=SCORE_COLUMNS)
    rows = []
    for metric in ("nse", "high_csi", "low_csi"):
        gap = (wide[(metric, "regional_unseen")] - wide[(metric, "regional_seen")]).rename("gap").reset_index()
        for key, block in gap.groupby(by):
            key = key if isinstance(key, tuple) else (key,)
            values = block["gap"].dropna()
            rows.append({
                **dict(zip(by, key)), "metric": metric,
                "median_gap": values.median(), "q25": values.quantile(0.25), "q75": values.quantile(0.75),
                "share_worse_unseen": float((values < 0).mean()), "n_catchments": int(len(values)),
            })
    return pd.DataFrame(rows)


def to_markdown(medians: pd.DataFrame, gaps: pd.DataFrame, chosen: str) -> str:
    order = ["persistence", "gbm_local", "regional_seen", "regional_unseen"]
    labels = {"nse": "NSE", "kge": "KGE", "high_csi": "High-flow CSI",
              "high_onset_hit_rate": "High-flow onset hit rate", "low_csi": "Low-flow CSI",
              "low_onset_hit_rate": "Low-flow onset hit rate"}
    lines = [
        "Median across catchments, test period (water years 2013 to 2022). No future weather in any model.",
        f"`gbm_local` is the per-catchment model (`{chosen}`). `regional_seen` was trained on every catchment.",
        "`regional_unseen` forecasts each region with a model trained on the other four regions only.",
        "",
    ]
    for lead in sorted(medians["lead_days"].unique()):
        lines += [f"**Lead {lead} day{'s' if lead > 1 else ''}**", "",
                  "| Model | " + " | ".join(labels.values()) + " |",
                  "| --- | " + " | ".join("---:" for _ in labels) + " |"]
        for model in order:
            row = medians[(medians["model"] == model) & (medians["lead_days"] == lead)]
            if not row.empty:
                lines.append(f"| {model} | " + " | ".join(f"{row[m].iloc[0]:.3f}" for m in labels) + " |")
        lines.append("")
    lines += ["**Gap for unseen catchments (unseen minus seen, per catchment)**", "",
              "| Lead (days) | Score | Median gap | Middle half of catchments | Share of catchments worse when unseen |",
              "| ---: | --- | ---: | --- | ---: |"]
    for _, row in gaps.sort_values(["lead_days", "metric"]).iterrows():
        lines.append(f"| {int(row['lead_days'])} | {row['metric']} | {row['median_gap']:+.3f} | "
                     f"{row['q25']:+.3f} to {row['q75']:+.3f} | {100 * row['share_worse_unseen']:.0f}% |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--leads", type=int, nargs="*", default=list(LEAD_DAYS))
    parser.add_argument("--seed", type=int, default=0, help="model seed; row sampling does not change")
    args = parser.parse_args()

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = saved["gauge_ids"]
    choice = json.loads((args.results / "gbm_variant_choice.json").read_text())
    chosen = choice["chosen"]
    settings = gbm.VARIANTS[chosen]

    attributes = load_attributes(args.data)
    folds_path = ROOT / "splits" / "spatial_folds_v1.json"
    if not folds_path.exists():
        build_folds(attributes, gauges, folds_path)
    folds = load_folds(folds_path)

    aridity = attributes.set_index("gauge_id").loc[gauges, "aridity"].astype(float)
    wet = list(aridity.index[aridity < aridity.median()])
    dry = list(aridity.index[aridity >= aridity.median()])
    # A fixed random half of the catchments, the same size as the wet half.
    half = list(np.random.default_rng(0).choice(sorted(gauges), size=len(wet), replace=False))
    dry_control = [g for g in dry if g not in set(half)]
    print(f"{len(gauges)} catchments; regions {np.bincount(list(folds.values())).tolist()}; "
          f"{len(wet)} wet, {len(dry)} dry; settings from {chosen}", flush=True)

    tidy = load_all(args.data)
    frames = {
        gauge: group.set_index("date")[VARIABLES]
        for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
    }
    del tidy
    tag = "" if args.seed == 0 else f"_seed{args.seed}"
    raw_dir = args.results / f"raw_regional{tag}"
    raw_dir.mkdir(parents=True, exist_ok=True)

    main_scores, dry_scores = [], []
    for lead in args.leads:
        expected = ["regional_seen", "regional_wet_only", "regional_random_half",
                    *[f"regional_unseen_region{f}" for f in range(N_FOLDS)]]
        if not all((raw_dir / f"lead{lead}_{name}.parquet").exists() for name in expected):
            started = time.time()
            tables = regional.build_tables(frames, attributes, config, lead)
            print(f"lead {lead}: tables built in {(time.time() - started) / 60:.1f} min "
                  f"({len(tables['train']):,} training rows)", flush=True)
            run_models(lead, tables, gauges, folds, wet, dry, half, settings, raw_dir, args.seed)
            del tables
        merged = collect(lead, gauges, raw_dir, args.results / "raw_variants", chosen)
        main_scores.append(score(merged, frames, config,
                                 ["persistence", "gbm_local", "regional_seen", "regional_unseen"], gauges, lead))
        dry_scores.append(score(merged, frames, config,
                                ["regional_seen", "regional_wet_only", "regional_random_half"], dry_control, lead))

    per_catchment = pd.concat(main_scores, ignore_index=True)
    per_catchment.insert(1, "region", per_catchment["gauge_id"].map(folds))
    per_catchment.to_csv(args.results / f"per_catchment_regional{tag}.csv", index=False)
    medians = median_table(per_catchment, ["model", "lead_days"])
    gaps = gap_table(per_catchment, ["lead_days"])
    medians.to_csv(args.results / f"table_regional{tag}.csv", index=False)
    gap_table(per_catchment, ["lead_days", "region"]).to_csv(args.results / f"table_regional_by_region{tag}.csv", index=False)
    gaps.to_csv(args.results / f"table_regional_gap{tag}.csv", index=False)
    (args.results / f"table_regional{tag}.md").write_text(to_markdown(medians, gaps, chosen))
    median_table(pd.concat(dry_scores, ignore_index=True), ["model", "lead_days"]).to_csv(
        args.results / f"table_wet_to_dry{tag}.csv", index=False
    )
    print("Tables written", flush=True)


if __name__ == "__main__":
    main()
