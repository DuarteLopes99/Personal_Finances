#!/usr/bin/env python3
"""Reset the centralized transactions store to empty, so you can rebuild it
from scratch with scripts/seed_from_template.py and/or scripts/ingest_monthly.py.

Never deletes outright: if a store already exists, it's renamed to a
timestamped backup file first (e.g. transactions.backup-20260730T193000.csv),
so resetting is always reversible.

Usage:
    python3 scripts/reset_store.py [path/to/transactions.csv]
    python3 scripts/reset_store.py --yes          # skip the confirmation prompt
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import schema, pipeline, reviews  # noqa: E402

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def main():
    # argparse rather than sys.argv[1], which took *any* first argument as a
    # path — so `reset_store.py --help` cheerfully wrote an empty store to a
    # file named "--help" instead of printing usage.
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("store", nargs="?", type=Path, default=DEFAULT_STORE,
                        help="Store to reset (default: data/transactions.csv)")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the confirmation prompt")
    args = parser.parse_args()
    store_path = args.store

    if store_path.exists():
        current = pipeline.load_store(store_path)
        if not args.yes:
            confirm = input(
                f"{store_path} has {len(current)} transactions. This backs it up and replaces it "
                f"with an empty store. Continue? [y/N] "
            )
            if confirm.strip().lower() != "y":
                print("Aborted — nothing changed.")
                return

        # Harvest any manual review decisions out of the store before it goes
        # away. The backup file preserves them too, but only as a file nobody
        # reads again — in review_decisions.json they're re-applied
        # automatically as the rebuilt store fills back up.
        harvested = reviews.reviews_from_store(current)
        if harvested:
            existing = reviews.load_reviews()
            merged = {**harvested, **existing}   # existing wins: it may be newer
            reviews.save_reviews(merged)
            print(f"Saved {len(harvested)} review decision(s) to data/review_decisions.json — "
                  f"they'll be re-applied automatically as you rebuild.")

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
