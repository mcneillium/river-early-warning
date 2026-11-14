"""Read the CAMELS-GB v2 daily files into one tidy table.

One row per catchment per day, with four variables:

    precip  precipitation, mm/day      (HadUK-Grid)
    temp    air temperature, deg C     (HadUK-Grid)
    pet     potential evapotranspiration, mm/day (Hydro-PE)
    flow    river flow per unit catchment area, mm/day

Why these sources: each file carries two versions of the weather variables.
The CEH-GEAR / CHESS versions stop on 2019-12-31, which is inside the test
period. The HadUK-Grid / Hydro-PE versions run to 2022-09-30, so they are the
only ones that cover every split consistently.

Missing values are kept as NaN. Nothing is filled here: a gap in the flow
record stays a gap, and each later step decides what to do about it.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

SOURCE_COLUMNS = {
    "precipitation_haduk": "precip",
    "temperature_haduk": "temp",
    "pet_hydrope": "pet",
    "discharge_spec": "flow",
}
VARIABLES = list(SOURCE_COLUMNS.values())
RECORD_START = pd.Timestamp("1970-10-01")
RECORD_END = pd.Timestamp("2022-09-30")
_NAME = re.compile(r"camels_gb_v2_hydromet_daily_timeseries_(\d+)_\d{8}-\d{8}\.csv$")


def gauge_id_from_path(path: Path) -> str:
    match = _NAME.search(Path(path).name)
    if not match:
        raise ValueError(f"Not a CAMELS-GB v2 daily file: {path}")
    return match.group(1)


def load_catchment(path: Path) -> pd.DataFrame:
    """Read one catchment's daily file, indexed by date, on a complete calendar."""
    raw = pd.read_csv(path, usecols=["date", *SOURCE_COLUMNS], parse_dates=["date"])
    frame = raw.rename(columns=SOURCE_COLUMNS).set_index("date").sort_index()
    if frame.index.has_duplicates:
        raise ValueError(f"Duplicate dates in {path}")
    calendar = pd.date_range(RECORD_START, RECORD_END, freq="D", name="date")
    if not frame.index.equals(calendar):
        # Put every catchment on the same calendar. Days absent from the file
        # become NaN rows; they are never invented.
        frame = frame.reindex(calendar)
    return frame[VARIABLES].astype("float64")


def load_all(data_dir: Path, use_cache: bool = True) -> pd.DataFrame:
    """Return the tidy table for every catchment: columns gauge_id, date, variables."""
    data_dir = Path(data_dir)
    cache = data_dir / "daily_tidy.parquet"
    if use_cache and cache.exists():
        return pd.read_parquet(cache)

    files = sorted((data_dir / "daily").glob("camels_gb_v2_hydromet_daily_timeseries_*.csv"))
    if not files:
        raise FileNotFoundError(
            f"No daily files under {data_dir / 'daily'}. Run: python -m rew.download"
        )
    parts = []
    for path in files:
        frame = load_catchment(path).reset_index()
        frame.insert(0, "gauge_id", gauge_id_from_path(path))
        parts.append(frame)
    tidy = pd.concat(parts, ignore_index=True)
    tidy["gauge_id"] = tidy["gauge_id"].astype("string")
    if use_cache:
        tidy.to_parquet(cache, index=False)
    return tidy


def _read_attribute_table(path: Path) -> pd.DataFrame:
    """Read one attribute table, tolerating commas inside the last text column.

    The hydrometry table ends with a free-text comment. In two rows (gauges
    27038 and 42010 in the October 2025 release) that comment contains a comma
    that is not quoted, so the row has one field too many and a plain
    `pd.read_csv` fails. Extra fields are joined back into the last column.
    """
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    header, body = rows[0], rows[1:]
    width = len(header)
    fixed = [row[: width - 1] + [",".join(row[width - 1 :])] if len(row) > width else row for row in body]
    table = pd.DataFrame(fixed, columns=header).replace({"NaN": pd.NA, "": pd.NA})
    table["gauge_id"] = table["gauge_id"].astype("string")
    for column in table.columns.drop("gauge_id"):
        try:
            table[column] = pd.to_numeric(table[column])
        except (ValueError, TypeError):
            pass  # a genuine text column, for example the gauge name
    return table


def load_attributes(data_dir: Path) -> pd.DataFrame:
    """Join the catchment attribute tables on gauge_id (one row per catchment)."""
    files = sorted((Path(data_dir) / "attributes").glob("camels_gb_v2_*_attributes.csv"))
    merged: pd.DataFrame | None = None
    for path in files:
        if "groundwaterwell" in path.name:  # keyed by well, not by catchment
            continue
        table = _read_attribute_table(path)
        merged = table if merged is None else merged.merge(table, on="gauge_id", how="outer")
    if merged is None:
        raise FileNotFoundError(f"No attribute tables under {Path(data_dir) / 'attributes'}")
    return merged


def summarise(tidy: pd.DataFrame) -> pd.DataFrame:
    """A small table describing what was loaded, for a quick sanity check."""
    by_gauge = tidy.groupby("gauge_id", observed=True)
    summary = {
        "catchments": tidy["gauge_id"].nunique(),
        "first_date": tidy["date"].min().date(),
        "last_date": tidy["date"].max().date(),
        "rows": len(tidy),
    }
    for name in VARIABLES:
        summary[f"{name}_missing_pct"] = round(100 * tidy[name].isna().mean(), 2)
    summary["median_flow_years"] = round(by_gauge["flow"].count().median() / 365.25, 1)
    summary["min_flow_years"] = round(by_gauge["flow"].count().min() / 365.25, 1)
    return pd.Series(summary).to_frame("value")
