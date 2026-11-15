"""Check that a quantile model refits to exactly the same forecasts on this machine.

    python scripts/check_quantile_repeat.py --seed 2 --lead 7 --model seen_q05

Refits one model of a re-run (`run_quantiles.py --seed N`) in memory and
compares its forecasts with the saved file in
results/raw_quantiles_rerun_seedN/. Nothing is written except one line to
results/exp5_seeds/repeat_checks.jsonl.

Why: on 14 November two processes fitted seed 2 at the same time, so its
folder holds files from both (LOG.md). That is harmless only if a refit with
the same code, data, seed and thread count gives identical forecasts.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from rew import quantile, regional
from rew.load import VARIABLES, load_all, load_attributes
from rew.spatial import load_folds
from rew.splits import config_from_splits, load_splits

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--lead", type=int, required=True)
    parser.add_argument("--model", required=True, help="for example seen_q05 or unseen_region3_q95")
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    args = parser.parse_args()

    import run_quantiles  # same directory; the job list of the original run

    saved_path = args.results / f"raw_quantiles_rerun_seed{args.seed}" / f"lead{args.lead}_{args.model}.parquet"
    saved = pd.read_parquet(saved_path)
    splits = load_splits(ROOT / "splits" / "splits_v1.json")
    config = config_from_splits(splits)
    gauges = splits["gauge_ids"]
    folds = load_folds(ROOT / "splits" / "spatial_folds_v1.json")
    job = {j[0]: j for j in run_quantiles.jobs_for(gauges, folds)}[args.model]
    tidy = load_all(args.data)
    frames = {g: grp.set_index("date")[VARIABLES]
              for g, grp in tidy[tidy["gauge_id"].isin(gauges)].groupby("gauge_id", observed=True)}
    del tidy
    started = time.time()
    tables = regional.build_tables(frames, load_attributes(args.data), config, args.lead,
                                   calibration_start=quantile.CALIBRATION_START)
    _, train_gauges, predict_gauges, q = job
    forecast, n_trees = quantile.fit_predict(tables, train_gauges, predict_gauges, q, seed=args.seed)

    same_rows = (len(forecast) == len(saved)
                 and (forecast["gauge_id"].astype(str).to_numpy() == saved["gauge_id"].astype(str).to_numpy()).all()
                 and (pd.DatetimeIndex(forecast["date"]) == pd.DatetimeIndex(saved["date"])).all())
    difference = (float(np.nanmax(np.abs(forecast["forecast"].to_numpy() - saved["forecast"].to_numpy())))
                  if same_rows else float("nan"))
    saved_trees = json.loads((saved_path.parent / f"lead{args.lead}_trees.json").read_text()).get(args.model)
    record = {"seed": args.seed, "lead": args.lead, "model": args.model, "same_rows": bool(same_rows),
              "max_abs_difference": difference, "identical": bool(same_rows and difference == 0.0),
              "trees_refit": int(n_trees), "trees_saved": saved_trees,
              "minutes": round((time.time() - started) / 60, 1)}
    out = args.results / "exp5_seeds" / "repeat_checks.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    print(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()
