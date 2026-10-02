"""Turn a raw monthly bank export into rows for the centralized transactions
store, and merge them in without duplicating transactions that were already
ingested (e.g. re-uploading the same monthly file is a no-op).
"""

import hashlib
from pathlib import Path

import pandas as pd

from . import schema
from .categorize import categorize_transaction, is_refund
from .loader import read_raw_bank_file
from .overrides import load_overrides


def _make_transaction_id(date, description: str, amount: float) -> str:
    """Stable id from the raw bank fields only, so the same underlying
    transaction always hashes the same way regardless of which file or
    categorization pass produced it.
    """
    key = f"{pd.Timestamp(date).date().isoformat()}|{description.strip().lower()}|{amount:.2f}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def categorize_dataframe(raw: pd.DataFrame, source_file: str, overrides=None) -> pd.DataFrame:
    """Convert a loader.read_raw_bank_file() DataFrame into unified schema rows."""
    records = []
    for _, row in raw.iterrows():
        date, description, amount = row["Date"], row["Description"], row["Amount"]
        category, sub_category, method = categorize_transaction(description, amount, overrides=overrides)
        # A refund is money in that undoes a purchase: stored as a negative
        # expense under the purchase's pair, so every total nets on its own.
        # See REFUNDS in taxonomy.py. The id still hashes the raw signed amount.
        refund = is_refund(description, amount)
        records.append({
            schema.TRANSACTION_ID: _make_transaction_id(date, description, amount),
            schema.DATE: pd.Timestamp(date).date().isoformat(),
            schema.TYPE: schema.TYPE_INCOME if amount > 0 and not refund else schema.TYPE_EXPENSE,
            schema.CATEGORY: category,
            schema.SUBCATEGORY: sub_category,
            schema.METHOD: method,
            schema.AMOUNT: -round(abs(amount), 2) if refund else round(abs(amount), 2),
            schema.NOTES: description,
            # Filled in only by a manual review (dashboard panel or
            # reviews.apply_reviews) — a freshly parsed bank row has no
            # review attached to it yet.
            schema.REVIEW_NOTE: "",
            schema.REVIEWED_AT: "",
            schema.MONTH: pd.Timestamp(date).month,
            schema.YEAR: pd.Timestamp(date).year,
            schema.SOURCE_FILE: source_file,
        })
    return pd.DataFrame(records, columns=schema.COLUMNS)


def ingest_monthly_file(path, overrides=None) -> pd.DataFrame:
    """Read + categorize a raw monthly bank export file into unified schema rows.

    overrides defaults to whatever is in data/category_overrides.json (see
    overrides.py) — pass an explicit list (or []) to override that.
    """
    path = Path(path)
    if overrides is None:
        overrides = load_overrides()
    raw = read_raw_bank_file(path)
    return categorize_dataframe(raw, source_file=path.name, overrides=overrides)


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add any schema column the frame is missing, in the canonical order.

    Stores written before the review columns existed are still perfectly
    valid files; they just need the newer columns filled in as empty rather
    than being rejected or silently losing the ones they do have.
    """
    df = df.copy()
    for column in schema.COLUMNS:
        if column not in df.columns:
            df[column] = ""
    extras = [c for c in df.columns if c not in schema.COLUMNS]
    return df[schema.COLUMNS + extras]


def load_store(csv_path) -> pd.DataFrame:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return pd.DataFrame(columns=schema.COLUMNS)
    df = pd.read_csv(csv_path, dtype={schema.TRANSACTION_ID: str})
    return ensure_columns(df)


def save_store(df: pd.DataFrame, csv_path) -> None:
    df = ensure_columns(df)
    df = df.sort_values([schema.YEAR, schema.MONTH, schema.DATE]).reset_index(drop=True)
    df.to_csv(csv_path, index=False)


def merge_into_store(existing: pd.DataFrame, new_rows: pd.DataFrame):
    """Append new_rows to existing, dropping any transaction_id already present.

    Returns (merged_df, n_added, n_duplicate).
    """
    if existing.empty:
        existing = pd.DataFrame(columns=schema.COLUMNS)

    known_ids = set(existing[schema.TRANSACTION_ID])
    is_new = ~new_rows[schema.TRANSACTION_ID].isin(known_ids)

    # ...and not a repeat of a row earlier in this same batch. Checking only
    # against `existing` catches a file re-uploaded later but not the same
    # transaction appearing twice inside one file, so two identical rows in a
    # single export both landed in the store. The dashboard's mergeIntoStore
    # has always added each id to its seen-set as it goes; this is the Python
    # side catching up, and the two engines now agree.
    is_new &= ~new_rows[schema.TRANSACTION_ID].duplicated(keep="first")

    to_add = new_rows[is_new]
    n_added = len(to_add)
    n_duplicate = len(new_rows) - n_added

    # Concatenating onto a column-only frame is deprecated in pandas (the
    # empty side's all-NA columns muddy the result dtypes), and it's also just
    # a no-op — the new rows already carry the full schema.
    merged = to_add.reset_index(drop=True) if len(existing) == 0 else \
        pd.concat([existing, to_add], ignore_index=True)
    return merged, n_added, n_duplicate
