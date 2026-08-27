#!/usr/bin/env python3
"""Ingest one or more monthly raw bank exports (xlsx/csv) into the centralized
data/transactions.csv, categorizing transactions and skipping any that were
already ingested before (dedup by transaction hash).

Files are processed in order into the same running store, so a transaction
appearing in more than one of the files you pass (or already present from an
earlier run) is caught the same way a duplicate re-run of one file always
was — no separate "cross-file" dedup step is needed.

Usage:
    python scripts/ingest_monthly.py path/to/monthly_export.xlsx
    python scripts/ingest_monthly.py nov.xlsx dec.xlsx jan.xlsx --store data/transactions.csv
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import pipeline, reviews  # noqa: E402

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path, help="One or more raw monthly bank export files (xlsx/csv)")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help="Path to the centralized transactions.csv")
    args = parser.parse_args()

    store = pipeline.load_store(args.store)
    total_added = total_duplicate = 0

    for monthly_file in args.files:
        print(f"Reading + categorizing {monthly_file.name}...")
        new_rows = pipeline.ingest_monthly_file(monthly_file)
        store, n_added, n_duplicate = pipeline.merge_into_store(store, new_rows)
        total_added += n_added
        total_duplicate += n_duplicate
        print(f"  Parsed {len(new_rows)} transactions — {n_added} added, {n_duplicate} already known.")

    # Manual review decisions live outside the store (see reviews.py) so that
    # rebuilding it from raw exports doesn't discard the work of working out
    # what an unrecognized transaction actually was. Re-applying them here
    # means a re-ingested row comes back already reviewed.
    saved_reviews = reviews.load_reviews()
    store, n_reviewed = reviews.apply_reviews(store, saved_reviews)

    # Then fill in anything whose description exactly matches a row already
    # reviewed — next month's "Uber Rides" inherits last month's answer rather
    # than landing back in the queue. Merchants only; see apply_by_description.
    store, n_derived = reviews.apply_by_description(store, saved_reviews)
    if n_derived:
        reviews.save_reviews(saved_reviews)

    pipeline.save_store(store, args.store)
    print(f"\nAdded {total_added} new transactions, skipped {total_duplicate} duplicates across "
          f"{len(args.files)} file(s).")
    if n_reviewed:
        print(f"Re-applied {n_reviewed} saved review decision(s) from data/review_decisions.json.")
    if n_derived:
        print(f"Auto-filled {n_derived} transaction(s) whose description exactly matches one you "
              f"already reviewed (marked as auto-applied, not individually checked).")
    print(f"Store now has {len(store)} total transactions -> {args.store}")


if __name__ == "__main__":
    main()
