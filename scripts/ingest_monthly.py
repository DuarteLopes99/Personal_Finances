#!/usr/bin/env python3
"""Ingest a new monthly raw bank export (xlsx/csv) into the centralized
data/transactions.csv, categorizing transactions and skipping any that were
already ingested before (dedup by transaction hash).

Usage:
    python scripts/ingest_monthly.py path/to/monthly_export.xlsx [path/to/transactions.csv]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import pipeline  # noqa: E402

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    monthly_file = Path(sys.argv[1])
    store_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_STORE

    print(f"Reading + categorizing {monthly_file.name}...")
    new_rows = pipeline.ingest_monthly_file(monthly_file)
    print(f"  Parsed {len(new_rows)} transactions")

    existing = pipeline.load_store(store_path)
    merged, n_added, n_duplicate = pipeline.merge_into_store(existing, new_rows)

    pipeline.save_store(merged, store_path)
    print(f"Added {n_added} new transactions, skipped {n_duplicate} already in the store.")
    print(f"Store now has {len(merged)} total transactions -> {store_path}")


if __name__ == "__main__":
    main()
