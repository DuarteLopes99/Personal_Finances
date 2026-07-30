#!/usr/bin/env python3
"""Reset the centralized transactions store to empty, so you can rebuild it
from scratch with scripts/seed_from_template.py and/or scripts/ingest_monthly.py.

Never deletes outright: if a store already exists, it's renamed to a
timestamped backup file first (e.g. transactions.backup-20260730T193000.csv),
so resetting is always reversible.

Usage:
    python scripts/reset_store.py [path/to/transactions.csv]
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import schema, pipeline  # noqa: E402

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def main():
    store_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_STORE

    if store_path.exists():
        current = pipeline.load_store(store_path)
        confirm = input(
            f"{store_path} has {len(current)} transactions. This backs it up and replaces it "
            f"with an empty store. Continue? [y/N] "
        )
        if confirm.strip().lower() != "y":
            print("Aborted — nothing changed.")
            return

        backup_path = store_path.with_name(
            f"{store_path.stem}.backup-{datetime.now():%Y%m%dT%H%M%S}{store_path.suffix}"
        )
        store_path.rename(backup_path)
        print(f"Backed up existing store to {backup_path}")

    empty = pd.DataFrame(columns=schema.COLUMNS)
    store_path.parent.mkdir(parents=True, exist_ok=True)
    empty.to_csv(store_path, index=False)
    print(f"Wrote an empty store to {store_path}")
    print(
        "Rebuild it with scripts/seed_from_template.py and/or scripts/ingest_monthly.py — "
        "duplicates across the files you re-add are still detected automatically."
    )


if __name__ == "__main__":
    main()
