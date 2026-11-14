"""Experiment 5, stage 1: fit the quantile models and save their forecasts.

    python scripts/run_quantiles.py              seed 0, as first reported
    python scripts/run_quantiles.py --seed 1     a further model seed (protocol_week3.md, amendment 1)

Follows docs/protocol_week3.md. For each lead time:

    seen     seven quantile models trained on all catchments
    unseen   for each of the five regions, the 0.05 and 0.95 quantile models
             trained on the other four regions

Each model's forecasts go to results/raw_quantiles/ as soon as it finishes, so
an interrupted run can be restarted. Scoring is a separate, fast script:
scripts/score_quantiles.py.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from rew import LEAD_DAYS, quantile, regional
from rew.load import VARIABLES, load_all, load_attributes
from rew.spatial import N_FOLDS, load_folds
from rew.splits import config_from_splits, load_splits

ROOT = Path(__file__).resolve().parents[1]


def jobs_for(gauges: list[str], folds: dict[str, int]) -> list[tuple[str, set[str], set[str], float]]:
    jobs = [(f"seen_{quantile.column(q)}", set(gauges), set(gauges), q) for q in quantile.QUANTILES]
    for fold in range(N_FOLDS):
        held_out = {g for g in gauges if folds[g] == fold}
        for q in quantile.INTERVAL:
            jobs.append((f"unseen_region{fold}_{quantile.column(q)}", set(gauges) - held_out, held_out, q))
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--leads", type=int, nargs="*", default=list(LEAD_DAYS))
    parser.add_argument("--seed", type=int, default=0, help="model seed; the row sample does not change")
    args = parser.parse_args()

    saved = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(saved)
    gauges = saved["gauge_ids"]
    folds = load_folds(ROOT / "splits" / "spatial_folds_v1.json")
    attributes = load_attributes(args.data)
    raw_dir = args.results / ("raw_quantiles" if args.seed == 0 else f"raw_quantiles_seed{args.seed}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    jobs = jobs_for(gauges, folds)

    frames = None
    for lead in args.leads:
        todo = [job for job in jobs if not (raw_dir / f"lead{lead}_{job[0]}.parquet").exists()]
        if not todo:
            print(f"lead {lead}: all {len(jobs)} models present", flush=True)
            continue
        if frames is None:
            tidy = load_all(args.data)
            frames = {
                gauge: group.set_index("date")[VARIABLES]
                for gauge, group in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)
            }
            del tidy
        tables = regional.build_tables(frames, attributes, config, lead,
                                       calibration_start=quantile.CALIBRATION_START)
        print(f"lead {lead}: {len(todo)} models to fit; "
              f"{len(tables['train']):,} training rows, {len(tables['calibration']):,} calibration rows", flush=True)
        trees_path = raw_dir / f"lead{lead}_trees.json"
        trees = json.loads(trees_path.read_text()) if trees_path.exists() else {}
        for name, train_gauges, predict_gauges, q in todo:
            started = time.time()
            forecast, n_trees = quantile.fit_predict(tables, train_gauges, predict_gauges, q, seed=args.seed)
            out_path = raw_dir / f"lead{lead}_{name}.parquet"
            temporary = out_path.with_suffix(".tmp")
            forecast.to_parquet(temporary, index=False)
            temporary.replace(out_path)
            trees[name] = n_trees
            trees_path.write_text(json.dumps(trees))
            print(f"  lead {lead} {name}: {n_trees} trees, {(time.time() - started) / 60:.1f} min", flush=True)
        del tables
    print("Stage 1 complete", flush=True)


if __name__ == "__main__":
    main()
