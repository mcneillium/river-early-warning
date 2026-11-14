"""Paired comparisons for Experiment 6, from results/per_catchment_lstm.csv.

    python scripts/summarise_lstm.py

Writes results/table_lstm_paired.md. Every difference is taken per
catchment, lead and seed on identical days, then summarised.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAIRS = [
    ("lstm_seen", "regional_seen", "LSTM minus boosting, seen catchments"),
    ("lstm_unseen", "regional_unseen", "LSTM minus boosting, unseen regions"),
    ("lstm_unseen", "lstm_seen", "Cost of an unseen region, LSTM"),
    ("regional_unseen", "regional_seen", "Cost of an unseen region, boosting"),
]


def main() -> None:
    scores = pd.read_csv(ROOT / "results" / "per_catchment_lstm.csv")
    wide = scores.pivot_table(index=["seed", "lead_days", "gauge_id"], columns="model", values="nse")
    seeds = sorted(scores["seed"].unique())

    lines = [
        "NSE differences per catchment on the test years (Experiment 6).",
        f"Seeds {', '.join(str(s) for s in seeds)}. Each column is the median across catchments.",
        "",
        "| Comparison | Lead | " + " | ".join(f"Seed {s}" for s in seeds) + " | Pooled | Share above zero |",
        "| --- | ---: | " + " | ".join("---:" for _ in seeds) + " | ---: | ---: |",
    ]
    for first, second, label in PAIRS:
        if first not in wide or second not in wide:
            continue
        difference = (wide[first] - wide[second]).dropna()
        for lead, values in difference.groupby(level="lead_days"):
            per_seed = values.groupby(level="seed").median()
            cells = " | ".join(f"{per_seed.get(s, float('nan')):+.3f}" for s in seeds)
            lines.append(f"| {label} | {lead} | {cells} | {values.median():+.3f} | {100 * (values > 0).mean():.0f}% |")

    out = ROOT / "results" / "table_lstm_paired.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
