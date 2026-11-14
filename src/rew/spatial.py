"""Geographic folds: hold out whole regions to test on unseen catchments.

Catchments are grouped into regions by k-means clustering on the gauge's
British National Grid easting and northing. Nearby catchments share weather
and geology, so a random split would leave close neighbours of every test
catchment in the training set and overstate how well the model transfers.
Holding out a whole region is the harder and more honest test.

The grouping is saved once with a fingerprint, like the time splits.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans

N_FOLDS = 5
SEED = 0


def make_folds(attributes: pd.DataFrame, gauge_ids: list[str]) -> dict[str, int]:
    """Assign each catchment to one of N_FOLDS regions. Region 0 is the most northerly."""
    table = attributes.set_index("gauge_id").loc[gauge_ids, ["gauge_easting", "gauge_northing"]]
    labels = KMeans(n_clusters=N_FOLDS, n_init=10, random_state=SEED).fit_predict(table.to_numpy(dtype=float))
    # Renumber regions from north to south so the numbering is stable and readable.
    northing = table["gauge_northing"].groupby(labels).mean().sort_values(ascending=False)
    rename = {old: new for new, old in enumerate(northing.index)}
    return {gauge: int(rename[label]) for gauge, label in zip(table.index, labels)}


def _fingerprint(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_folds(attributes: pd.DataFrame, gauge_ids: list[str], out_path: Path) -> dict:
    out_path = Path(out_path)
    if out_path.exists():
        raise FileExistsError(f"{out_path} already exists. Spatial folds are fixed.")
    content = {
        "version": 1,
        "method": f"k-means on gauge easting and northing, k={N_FOLDS}, seed={SEED}, regions numbered north to south",
        "folds": make_folds(attributes, gauge_ids),
    }
    saved = {**content, "sha256": _fingerprint(content)}
    out_path.write_text(json.dumps(saved, indent=1, sort_keys=True))
    return saved


def load_folds(path: Path) -> dict[str, int]:
    saved = json.loads(Path(path).read_text())
    content = {key: value for key, value in saved.items() if key != "sha256"}
    if _fingerprint(content) != saved.get("sha256"):
        raise ValueError(f"{path} does not match its fingerprint; it has been altered.")
    return saved["folds"]
