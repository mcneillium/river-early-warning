"""Where does the regional model fail on unseen catchments, and what predicts it?

    python scripts/analyse_regional.py

Reads results/per_catchment_regional.csv and writes

    figures/regions_map.png              the five held-out regions
    figures/unseen_gap_map.png           NSE gap (unseen minus seen) for each catchment
    results/table_gap_correlations.csv   Spearman rank correlation of the gap with
                                         every numeric catchment descriptor

Flow-derived descriptors (baseflow index and so on) are included in the
correlation table. They are never model inputs, but they are fair to use when
explaining results afterwards.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from scipy.stats import spearmanr

from rew.load import load_attributes

ROOT = Path(__file__).resolve().parents[1]

# Colours: a neutral surface, quiet text, and a red-grey-blue diverging scale
# (red = worse when unseen, blue = better, grey = no difference).
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_QUIET = "#52514e"
RED, NEUTRAL, BLUE = "#e34948", "#f0efec", "#2a78d6"
DIVERGING = LinearSegmentedColormap.from_list("red_grey_blue", [RED, NEUTRAL, BLUE])
REGION_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#6250d6"]


def style(axis) -> None:
    axis.set_aspect("equal")
    axis.set_xticks([])
    axis.set_yticks([])
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.set_facecolor(SURFACE)


def regions_map(table: pd.DataFrame, path: Path) -> None:
    figure, axis = plt.subplots(figsize=(4.6, 6.4), facecolor=SURFACE)
    for region, block in table.groupby("region"):
        colour = REGION_COLOURS[int(region)]
        axis.scatter(block["x"], block["y"], s=16, color=colour, edgecolor=SURFACE, linewidth=0.4)
        # Label each region beside its catchments so colour is not the only cue.
        # The south-west region is labelled on its seaward (left) side; the
        # others on the right, where there is open space.
        on_left = block["x"].mean() < table["x"].median() and block["y"].mean() < table["y"].quantile(0.3)
        anchor = (block["x"].min() - 25, block["y"].mean() + 40) if on_left else (block["x"].max() + 25, block["y"].mean())
        axis.annotate(
            f"Region {int(region)}\n{len(block)} catchments", anchor, fontsize=8, color=TEXT,
            va="center", ha="right" if on_left else "left",
        )
    style(axis)
    axis.set_xlim(table["x"].min() - 250, table["x"].max() + 260)
    axis.set_title("Five held-out regions", fontsize=11, color=TEXT, loc="left")
    figure.text(0.02, 0.02, "Each dot is a gauge. Regions from k-means on gauge position.",
                fontsize=7.5, color=TEXT_QUIET)
    figure.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(figure)


def gap_map(gaps: pd.DataFrame, path: Path) -> float:
    leads = sorted(gaps["lead_days"].unique())
    limit = float(np.nanpercentile(np.abs(gaps["gap"]), 95))
    limit = max(round(limit, 2), 0.05)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    figure, axes = plt.subplots(1, len(leads), figsize=(3.3 * len(leads), 5.6), facecolor=SURFACE)
    for axis, lead in zip(np.atleast_1d(axes), leads):
        block = gaps[gaps["lead_days"] == lead].dropna(subset=["gap"])
        block = block.reindex(block["gap"].abs().sort_values().index)   # largest gaps drawn last
        points = axis.scatter(
            block["x"], block["y"], c=block["gap"].clip(-limit, limit), cmap=DIVERGING, norm=norm,
            s=15, edgecolor=SURFACE, linewidth=0.3,
        )
        style(axis)
        worse = 100 * (block["gap"] < 0).mean()
        axis.set_title(f"Lead {lead} day{'s' if lead > 1 else ''}", fontsize=10, color=TEXT, loc="left")
        axis.text(0.0, -0.02, f"median gap {block['gap'].median():+.3f}\n{worse:.0f}% of catchments worse",
                  transform=axis.transAxes, fontsize=8, color=TEXT_QUIET, va="top")
    bar = figure.colorbar(points, ax=axes, orientation="horizontal", fraction=0.035, pad=0.12, aspect=40)
    bar.set_label(f"NSE when unseen minus NSE when seen (colour scale stops at ±{limit:.2f})",
                  fontsize=8, color=TEXT_QUIET)
    bar.ax.tick_params(labelsize=7.5, colors=TEXT_QUIET, length=0)
    bar.outline.set_visible(False)
    figure.suptitle("What it costs to forecast a catchment the model never trained on",
                    fontsize=11.5, color=TEXT, x=0.125, ha="left", y=0.97)
    figure.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(figure)
    return limit


def correlations(gaps: pd.DataFrame, attributes: pd.DataFrame) -> pd.DataFrame:
    numeric = attributes.set_index("gauge_id").select_dtypes("number")
    numeric = numeric.drop(columns=[c for c in numeric.columns if c.endswith("_missing")], errors="ignore")
    rows = []
    for lead, block in gaps.groupby("lead_days"):
        gap = block.set_index("gauge_id")["gap"].dropna()
        for name in numeric.columns:
            values = numeric[name].reindex(gap.index)
            ok = values.notna()
            if ok.sum() < 100 or values[ok].nunique() < 10:
                continue
            rho, p_value = spearmanr(values[ok], gap[ok])
            rows.append({"lead_days": lead, "descriptor": name, "spearman_rho": rho,
                         "p_value": p_value, "n_catchments": int(ok.sum())})
    table = pd.DataFrame(rows)
    table["abs_rho"] = table["spearman_rho"].abs()
    return table.sort_values(["lead_days", "abs_rho"], ascending=[True, False]).drop(columns="abs_rho")


def main() -> None:
    results = ROOT / "results"
    figures = ROOT / "figures"
    figures.mkdir(exist_ok=True)
    scores = pd.read_csv(results / "per_catchment_regional.csv", dtype={"gauge_id": "string"})
    attributes = load_attributes(ROOT / "data")
    position = attributes.set_index("gauge_id")[["gauge_easting", "gauge_northing"]] / 1000.0  # km

    wide = scores.pivot_table(index=["gauge_id", "region", "lead_days"], columns="model", values="nse")
    gaps = (wide["regional_unseen"] - wide["regional_seen"]).rename("gap").reset_index()
    gaps["x"] = gaps["gauge_id"].map(position["gauge_easting"])
    gaps["y"] = gaps["gauge_id"].map(position["gauge_northing"])

    regions_map(gaps[gaps["lead_days"] == gaps["lead_days"].min()], figures / "regions_map.png")
    limit = gap_map(gaps, figures / "unseen_gap_map.png")
    table = correlations(gaps, attributes)
    table.to_csv(results / "table_gap_correlations.csv", index=False)
    print(f"Figures written; colour scale limit {limit:.2f}")
    print(table.groupby("lead_days").head(8).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
