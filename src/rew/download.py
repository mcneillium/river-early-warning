"""Download the parts of CAMELS-GB v2 this study uses, and record checksums.

CAMELS-GB v2 (Coxon et al., 2025) is published by the NERC Environmental
Information Data Centre. Its datastore is a plain web directory that needs no
login, so the download can be scripted.

Only two parts are fetched:
  * the daily hydro-meteorological series (671 files, about 790 MB)
  * the catchment attribute tables (9 small files)

The hourly series (about 10 GB), groundwater series and boundary shapefile are
not needed for week 1 and are skipped.

Usage:
    python -m rew.download --dest data
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RECORD_ID = "9a46d428-958f-4ac1-86eb-94eee70c0955"
BASE = f"https://catalogue.ceh.ac.uk/datastore/eidchub/{RECORD_ID}"
PARTS = {
    "attributes": "Catchment_Attributes/",
    "daily": "Catchment_Timeseries/hydro-meteorological/daily/",
}
EXPECTED_CATCHMENTS = 671

# One line of the directory index looks like:
#   <a href="name.csv">name.csv</a>     21-Oct-2025 10:47     1172490
_INDEX_LINE = re.compile(r'<a href="([^"/]+\.csv)">[^<]*</a>\s+\S+\s+\S+\s+(\d+)')


def list_index(url: str) -> list[tuple[str, int]]:
    """Return (file name, size in bytes) for every CSV in a directory index."""
    with urllib.request.urlopen(url, timeout=60) as response:
        html = response.read().decode("utf-8", errors="replace")
    return [(name, int(size)) for name, size in _INDEX_LINE.findall(html)]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, target: Path, size: int, retries: int = 4) -> None:
    """Download one file unless a complete copy is already there."""
    if target.exists() and target.stat().st_size == size:
        return
    partial = target.with_suffix(target.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                partial.write_bytes(response.read())
            if partial.stat().st_size != size:
                raise OSError(f"size mismatch for {target.name}")
            partial.replace(target)
            return
        except Exception:  # noqa: BLE001 - retry any network error
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def download(dest: Path, workers: int = 8) -> dict:
    """Download both parts into `dest` and write `dest/MANIFEST.json`."""
    manifest = {"record": RECORD_ID, "base_url": BASE, "files": {}}
    for part, subdir in PARTS.items():
        out_dir = dest / part
        out_dir.mkdir(parents=True, exist_ok=True)
        index = list_index(f"{BASE}/{subdir}")
        if not index:
            raise RuntimeError(f"No files listed at {BASE}/{subdir}")
        print(f"{part}: {len(index)} files, {sum(s for _, s in index) / 1e6:.0f} MB")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = [
                pool.submit(fetch, f"{BASE}/{subdir}{name}", out_dir / name, size)
                for name, size in index
            ]
            for job in jobs:
                job.result()
        for name, size in index:
            manifest["files"][f"{part}/{name}"] = {
                "bytes": size,
                "sha256": sha256_of(out_dir / name),
            }

    n_daily = sum(1 for key in manifest["files"] if key.startswith("daily/"))
    if n_daily != EXPECTED_CATCHMENTS:
        raise RuntimeError(f"Expected {EXPECTED_CATCHMENTS} daily files, found {n_daily}")
    (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dest", type=Path, default=Path("data"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    manifest = download(args.dest, args.workers)
    print(f"Done: {len(manifest['files'])} files. Checksums in {args.dest / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
