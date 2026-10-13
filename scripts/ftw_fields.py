"""Predict real field boundaries with the Fields of the World (FTW) model.

Wraps the official `ftw` CLI (https://github.com/fieldsoftheworld/ftw-baselines): it picks two Sentinel-2
L2A scenes from the crop calendar (an early and a late window), downloads them from Microsoft Planetary
Computer, runs the PRUE EfficientNet segmentation model and polygonizes the result.

The published FTW global vectors are too sparse over smallholder Nashik (about 170 polygons in a 55 x 38 km
box), so the model is run directly on the area. B5 with the CC-BY weights keeps the output citable.

Needs the CLI in its own environment, because ftw-tools pins heavy dependencies:

    python -m venv ftwenv --system-site-packages
    ftwenv/Scripts/python -m pip install "git+https://github.com/fieldsoftheworld/ftw-baselines.git"

Run:  python scripts/ftw_fields.py --bbox 74.07 20.04 74.16 20.12 --year 2025 --out data/areas/niphad/raw/ftw_b5
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("LON0", "LAT0", "LON1", "LAT1"))
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--model", default="FTW_PRUE_EFNET_B5_CCBY")
    ap.add_argument("--ftw", default="ftw", help="path to the ftw executable")
    ap.add_argument("--out", required=True, help="folder for polygons.parquet")
    a = ap.parse_args()

    OUT = Path(a.out)
    work = OUT / "work"
    work.mkdir(parents=True, exist_ok=True)
    cmd = [
        a.ftw, "inference", "all", f"--bbox={','.join(map(str, a.bbox))}", f"--year={a.year}", f"--out={work}",
        f"--model={a.model}", "--cloud_cover_max=30", "--buffer_days=20", "--resize_factor=2", "--overwrite",
    ]
    print(" ".join(cmd), file=sys.stderr, flush=True)
    subprocess.run(cmd, check=True)
    shutil.copy(work / "polygons.parquet", OUT / "polygons.parquet")
    shutil.rmtree(work)
    print(f"wrote {OUT / 'polygons.parquet'}", file=sys.stderr)


if __name__ == "__main__":
    main()
