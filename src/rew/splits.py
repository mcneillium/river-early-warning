"""Build the train / validation / test splits once and save them to a file.

The splits are by time. A row belongs to a split according to the date of its
target (the day being forecast), so a forecast issued on 29 September 2004 for
2 October 2004 is a validation row, not a training row.

The saved file also lists which catchments are used and which were excluded
for having too little flow data, and carries a fingerprint of its own content.
`build_splits` refuses to overwrite an existing file: once results depend on a
split, it must not change silently.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

SPLIT_NAMES = ("train", "validation", "test")


def load_config(path: Path) -> dict:
    with Path(path).open() as handle:
        return yaml.safe_load(handle)


def boundaries(config: dict) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    """Start and end date of each split, checked to be in order and not overlapping."""
    spans = {
        name: (pd.Timestamp(config[name]["start"]), pd.Timestamp(config[name]["end"]))
        for name in SPLIT_NAMES
    }
    previous_end = None
    for name in SPLIT_NAMES:
        start, end = spans[name]
        if start > end:
            raise ValueError(f"{name}: start is after end")
        if previous_end is not None and start <= previous_end:
            raise ValueError(f"{name} overlaps the split before it")
        previous_end = end
    return spans


def assign_split(dates: pd.DatetimeIndex | pd.Series, config: dict) -> pd.Series:
    """Label each date 'train', 'validation', 'test', or <NA> if outside all three."""
    dates = pd.Series(pd.DatetimeIndex(dates), index=getattr(dates, "index", None))
    labels = pd.Series(pd.NA, index=dates.index, dtype="string")
    for name, (start, end) in boundaries(config).items():
        labels[(dates >= start) & (dates <= end)] = name
    return labels


def _fingerprint(content: dict) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def build_splits(tidy: pd.DataFrame, config: dict, out_path: Path) -> dict:
    """Decide which catchments are usable, then write the splits file once."""
    out_path = Path(out_path)
    if out_path.exists():
        raise FileExistsError(
            f"{out_path} already exists. Splits are fixed; bump the version and "
            "write a new file if they genuinely need to change."
        )
    labels = assign_split(tidy["date"], config)
    counts = (
        tidy.assign(split=labels.to_numpy())
        .dropna(subset=["flow", "split"])
        .groupby(["gauge_id", "split"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=list(SPLIT_NAMES), fill_value=0)
    )
    counts = counts.reindex(sorted(tidy["gauge_id"].unique()), fill_value=0)
    minimum = config["min_flow_days"]
    enough = pd.concat([counts[name] >= minimum[name] for name in SPLIT_NAMES], axis=1).all(axis=1)

    content = {
        "version": config["version"],
        "boundaries": {
            name: [str(start.date()), str(end.date())]
            for name, (start, end) in boundaries(config).items()
        },
        "min_flow_days": dict(minimum),
        "gauge_ids": [str(g) for g in counts.index[enough]],
        "excluded": {
            str(gauge): {name: int(counts.loc[gauge, name]) for name in SPLIT_NAMES}
            for gauge in counts.index[~enough]
        },
    }
    saved = {**content, "sha256": _fingerprint(content)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(saved, indent=1, sort_keys=True))
    return saved


def load_splits(path: Path) -> dict:
    """Read a splits file and verify it has not been edited since it was built."""
    saved = json.loads(Path(path).read_text())
    content = {key: value for key, value in saved.items() if key != "sha256"}
    if _fingerprint(content) != saved.get("sha256"):
        raise ValueError(f"{path} does not match its fingerprint; it has been altered.")
    return saved


def config_from_splits(saved: dict) -> dict:
    """Rebuild the boundary config from a saved splits file."""
    config = {
        name: {"start": saved["boundaries"][name][0], "end": saved["boundaries"][name][1]}
        for name in SPLIT_NAMES
    }
    config["version"] = saved["version"]
    config["min_flow_days"] = saved["min_flow_days"]
    return config
