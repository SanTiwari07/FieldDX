"""Clear every recorded finding and stored summary for the Niphad demo area, so each demo take starts clean.

    python scripts/reset_demo.py              # the database the app uses (FIELDDX_DB, or backend/fielddx.db)
    python scripts/reset_demo.py --db PATH    # another database, for example a preview copy
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="path to the SQLite file to reset")
    ap.add_argument("--area", default="niphad", help="area id (default: niphad)")
    args = ap.parse_args()
    if args.db:
        os.environ["FIELDDX_DB"] = str(Path(args.db).resolve())
    sys.path.insert(0, str(ROOT / "backend"))
    from app import config, db

    db.reset(args.area)
    print(f"Cleared findings and summaries for '{args.area}' in {config.DB_PATH}")


if __name__ == "__main__":
    main()
