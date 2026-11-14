"""Combine the regional results from model seeds 0, 1 and 2.

    python scripts/summarise_regional_seeds.py

Writes results/table_regional_seeds.csv: for each headline number, its value
under each seed, then the mean and standard deviation across seeds. A finding
is only worth reporting if it is much larger than the seed-to-seed spread.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (0, 1, 2)
SCORES = ("nse", "high_csi", "low_csi")


def tag(seed: int) -> str:
    return "" if seed == 0 else f"_seed{seed}"


def main() -> None:
    results = ROOT / "results"
    rows = []
    for seed in SEEDS:
        medians = pd.read_csv(results / f"table_regional{tag(seed)}.csv")
        for _, row in medians[medians["model"].isin(["regional_seen", "regional_unseen"])].iterrows():
            for score in SCORES:
                rows.append({"quantity": f"median {score}", "model": row["model"],
                             "lead_days": int(row["lead_days"]), "seed": seed, "value": row[score]})
        gaps = pd.read_csv(results / f"table_regional_gap{tag(seed)}.csv")
        for _, row in gaps.iterrows():
            rows.append({"quantity": f"median gap in {row['metric']}", "model": "unseen minus seen",
                         "lead_days": int(row["lead_days"]), "seed": seed, "value": row["median_gap"]})
            rows.append({"quantity": f"share worse when unseen ({row['metric']})", "model": "unseen minus seen",
                         "lead_days": int(row["lead_days"]), "seed": seed, "value": row["share_worse_unseen"]})
        dry = pd.read_csv(results / f"table_wet_to_dry{tag(seed)}.csv")
        for _, row in dry.iterrows():
            for score in SCORES:
                rows.append({"quantity": f"dry catchments, median {score}", "model": row["model"],
                             "lead_days": int(row["lead_days"]), "seed": seed, "value": row[score]})
    long = pd.DataFrame(rows)
    wide = long.pivot_table(index=["quantity", "model", "lead_days"], columns="seed", values="value")
    wide.columns = [f"seed{seed}" for seed in wide.columns]
    wide["mean"] = wide.mean(axis=1)
    wide["sd"] = wide[[f"seed{seed}" for seed in SEEDS]].std(axis=1, ddof=1)
    wide.reset_index().to_csv(results / "table_regional_seeds.csv", index=False)
    print(wide.round(4).to_string())


if __name__ == "__main__":
    main()
