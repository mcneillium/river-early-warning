"""Figures for Experiment 5.

    python scripts/plot_quantiles.py

    figures/warnings_by_lead.png    warning skill of four models at 1, 3 and 7 days
    figures/interval_coverage.png   how honest the 90% range is, catchment by catchment

The numbers behind both figures are in results/table_quantile_warnings.csv and
results/table_interval_coverage.csv.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SURFACE, TEXT, TEXT_QUIET, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
# Fixed colour and marker per model, so identity never rests on colour alone.
MODELS = {
    "persistence": ("Persistence", "#2a78d6", "o"),
    "regional_point": ("Single-number model", "#eb6834", "s"),
    "persistence_band": ("Persistence band", "#1baf7a", "^"),
    "quantile_model": ("Quantile model", "#eda100", "D"),
}
LEADS = [1, 3, 7]


def tidy_axis(axis) -> None:
    axis.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color(GRID)
    axis.tick_params(colors=TEXT_QUIET, labelsize=8.5, length=0)
    axis.yaxis.grid(True, color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)


def spread_labels(values: dict[str, float], gap: float) -> dict[str, float]:
    """Nudge end-of-line labels apart so they do not overlap."""
    placed, last = {}, None
    for name, value in sorted(values.items(), key=lambda item: item[1]):
        position = value if last is None else max(value, last + gap)
        placed[name], last = position, position
    return placed


def warnings_figure(table: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(9.6, 4.3), facecolor=SURFACE, sharey=True)
    for axis, metric, title in zip(axes, ("high_csi", "low_csi"), ("High-flow warnings", "Low-flow warnings")):
        ends = {}
        for model, (label, colour, marker) in MODELS.items():
            rows = table[table["model"] == model].set_index("lead_days").reindex(LEADS)
            axis.plot(range(len(LEADS)), rows[metric], color=colour, linewidth=2, marker=marker,
                      markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.2, label=label)
            ends[model] = float(rows[metric].iloc[-1])
        for model, y in spread_labels(ends, gap=0.045).items():
            axis.annotate(MODELS[model][0], (len(LEADS) - 1, y), xytext=(10, 0), textcoords="offset points",
                          fontsize=8.5, color=TEXT, va="center")
        tidy_axis(axis)
        axis.set_xticks(range(len(LEADS)), [f"{lead} day{'s' if lead > 1 else ''} ahead" for lead in LEADS])
        axis.set_xlim(-0.2, len(LEADS) - 1 + 1.25)
        axis.set_ylim(0, 0.85)
        axis.set_title(title, fontsize=10.5, color=TEXT, loc="left")
    axes[0].set_ylabel("Critical success index, median catchment", fontsize=8.5, color=TEXT_QUIET)
    axes[0].legend(loc="upper right", fontsize=8, frameon=False, labelcolor=TEXT_QUIET)
    figure.suptitle("Warning skill at 1, 3 and 7 days, test years 2013 to 2022",
                    fontsize=12, color=TEXT, x=0.065, ha="left", y=1.0)
    figure.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(figure)


def coverage_figure(table: pd.DataFrame, path: Path) -> None:
    series = [
        ("quantile model, seen", "raw", "Quantile model, before calibration", "#eb6834", "s"),
        ("quantile model, seen", "conformal", "Quantile model, calibrated", "#2a78d6", "o"),
        ("quantile model, unseen", "conformal", "Calibrated, unseen regions", "#1baf7a", "^"),
        ("persistence band", "conformal", "Persistence band, calibrated", "#eda100", "D"),
    ]
    figure, axis = plt.subplots(figsize=(8.4, 4.4), facecolor=SURFACE)
    width = 0.17
    for k, (model, stage, label, colour, marker) in enumerate(series):
        rows = table[(table["model"] == model) & (table["stage"] == stage)].set_index("lead_days").reindex(LEADS)
        x = [i + (k - 1.5) * width for i in range(len(LEADS))]
        axis.vlines(x, rows["coverage_5th_percentile_catchment"], rows["coverage_95th_percentile_catchment"],
                    color=colour, linewidth=2, alpha=0.55)
        axis.scatter(x, rows["coverage_median_catchment"], color=colour, marker=marker, s=58,
                     edgecolor=SURFACE, linewidth=1.2, zorder=3, label=label)
    axis.axhline(0.90, color=TEXT_QUIET, linewidth=1, linestyle=(0, (4, 3)))
    axis.annotate("target 90%", (len(LEADS) - 0.22, 0.90), xytext=(0, 4), textcoords="offset points",
                  fontsize=8.5, color=TEXT_QUIET, ha="right")
    tidy_axis(axis)
    axis.set_xticks(range(len(LEADS)), [f"{lead} day{'s' if lead > 1 else ''} ahead" for lead in LEADS])
    axis.set_xlim(-0.55, len(LEADS) - 0.2)
    plotted = pd.concat([table[(table["model"] == m) & (table["stage"] == st)] for m, st, *_ in series])
    lowest = float(plotted["coverage_5th_percentile_catchment"].min())
    axis.set_ylim(int((lowest - 0.03) * 20) / 20, 1.0)   # round down to the nearest 0.05
    axis.set_ylabel("Share of test days inside the 90% range", fontsize=8.5, color=TEXT_QUIET)
    axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), fontsize=8, frameon=False,
                labelcolor=TEXT_QUIET, ncol=4, columnspacing=1.4, handletextpad=0.3)
    axis.set_title("Is the 90% range honest? Median catchment, with the 5th to 95th percentile of catchments",
                   fontsize=10.5, color=TEXT, loc="left")
    figure.savefig(path, dpi=200, facecolor=SURFACE, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    results, figures = ROOT / "results", ROOT / "figures"
    figures.mkdir(exist_ok=True)
    warnings_figure(pd.read_csv(results / "table_quantile_warnings.csv"), figures / "warnings_by_lead.png")
    coverage_figure(pd.read_csv(results / "table_interval_coverage.csv"), figures / "interval_coverage.png")
    print("Figures written")


if __name__ == "__main__":
    main()
