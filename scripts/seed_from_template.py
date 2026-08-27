#!/usr/bin/env python3
"""One-time import: convert the historical Expenses/Income sheets of an Excel
tracker (Expenses / Income sheets, same columns as
Personal_Finance_Tracker_With_Formulas.xlsx) into the centralized
data/transactions.csv (unified schema, see finance_tracker/schema.py).

The source workbook is expected to hold personal financial data, so it is
intentionally not bundled in this repo — pass its path explicitly.

Usage:
    python3 scripts/seed_from_template.py path/to/template.xlsx [path/to/output.csv]
"""

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import categorize, pipeline, reviews, schema, taxonomy  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def _seed_id(sheet: str, index: int, date, amount: float, notes) -> str:
    key = f"seed|{sheet}|{index}|{date}|{amount:.2f}|{notes}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _clean_str(value, default="") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip()


# Known spelling variants in the original template, normalized before the
# taxonomy lookup below so "Saude" and "Saúde" don't miss each other.
CATEGORY_ALIASES = {
    "Saude": "Saúde",
    "Investimento": "Investimentos",
    "Poupança/Investimento": "Investimentos",
}


def _resolve_method(value) -> str:
    """Force a template row's payment method onto the known rails.

    Same reasoning as _resolve_pair: the Payment Method column (and, for
    income, Source) is free text somebody typed into a spreadsheet, and this
    script used to copy it through untouched. A Method of
    "cartão de crédito do Pingo Doce" is not a rail — it is a new bar in the
    payment-method chart that nothing else in the system will ever produce
    again, which is the Category problem in a different column.

    Unrecognized values become "Não especificado" rather than being dropped:
    the row is real, only the rail is unknown, and a labelled bucket keeps it
    visible in the charts instead of blank.
    """
    method = _clean_str(value)
    if method in taxonomy.METHODS:
        return method
    # Case and accents differ between the sheet and the taxonomy far more often
    # than the actual word does ("cartao" / "Cartão", "MBWAY" / "MBWay"), so
    # compare through categorize.normalize() — the same lowercase/unaccented
    # form the rule engine matches on, rather than a second implementation of
    # it that could disagree.
    folded = {categorize.normalize(m): m for m in taxonomy.METHODS}
    return folded.get(categorize.normalize(method), taxonomy.UNSPECIFIED_METHOD)


def _resolve_pair(txn_type: str, category, sub_category) -> tuple:
    """Force a template row's (Category, Sub-category) onto the taxonomy.

    The template is a spreadsheet: its Category column is whatever the user
    typed into it over two years, and this script used to copy that through
    verbatim. That is exactly how the store acquired `Gasoleo` next to
    `Combustível` and 71 sub-categories that were people's names — the seeder
    was a writer that nothing validated.

    Legacy pairs are mapped through taxonomy.LEGACY_ALIASES; anything with no
    mapping keeps as much as is still true (the category, if it exists) and
    drops what isn't (the sub-category), rather than inventing a bucket.
    """
    category = CATEGORY_ALIASES.get(_clean_str(category), _clean_str(category))
    sub_category = _clean_str(sub_category)

    resolved = taxonomy.resolve(txn_type, category, sub_category)
    if resolved:
        return resolved
    # Same guard as recategorize._fallback: a row whose category was already
    # "Outros" knew nothing, so it belongs in the review queue, not in the
    # settled Outros/Outros bucket.
    if (category != taxonomy.UNCLASSIFIED_CATEGORY
            and taxonomy.is_valid(txn_type, category, taxonomy.CATCH_ALL_SUB)):
        return category, taxonomy.CATCH_ALL_SUB
    return taxonomy.unclassified(txn_type)


def _convert_expenses(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.dropna(subset=["Date", "Amount (€)"]).reset_index(drop=True)
    records = []
    for i, row in df.iterrows():
        date = pd.Timestamp(row["Date"])
        notes = _clean_str(row.get("Notes"))
        records.append({
            schema.TRANSACTION_ID: _seed_id("Expenses", i, date.date(), row["Amount (€)"], notes),
            schema.DATE: date.date().isoformat(),
            schema.TYPE: schema.TYPE_EXPENSE,
            **dict(zip((schema.CATEGORY, schema.SUBCATEGORY),
                       _resolve_pair(schema.TYPE_EXPENSE, row.get("Category"),
                                     row.get("Sub-category")))),
            schema.METHOD: _resolve_method(row.get("Payment Method")),
            schema.AMOUNT: round(abs(float(row["Amount (€)"])), 2),
            schema.NOTES: notes,
            schema.MONTH: int(row["Month"]),
            schema.YEAR: int(row["Year"]),
            schema.SOURCE_FILE: f"{source_name} (Expenses)",
        })
    return pd.DataFrame(records, columns=schema.COLUMNS)


def _convert_income(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.dropna(subset=["Date", "Amount (€)"]).reset_index(drop=True)
    records = []
    for i, row in df.iterrows():
        date = pd.Timestamp(row["Date"])
        notes = _clean_str(row.get("Notes"))
        records.append({
            schema.TRANSACTION_ID: _seed_id("Income", i, date.date(), row["Amount (€)"], notes),
            schema.DATE: date.date().isoformat(),
            schema.TYPE: schema.TYPE_INCOME,
            **dict(zip((schema.CATEGORY, schema.SUBCATEGORY),
                       _resolve_pair(schema.TYPE_INCOME, row.get("Category"),
                                     row.get("Source")))),
            schema.METHOD: _resolve_method(row.get("Source")),
            schema.AMOUNT: round(abs(float(row["Amount (€)"])), 2),
            schema.NOTES: notes,
            schema.MONTH: int(row["Month"]),
            schema.YEAR: int(row["Year"]),
            schema.SOURCE_FILE: f"{source_name} (Income)",
        })
    return pd.DataFrame(records, columns=schema.COLUMNS)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("template", type=Path, help="Excel tracker with Expenses/Income sheets")
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT,
                        help="Where to write the store (default: data/transactions.csv)")
    args = parser.parse_args()
    template_path, output_path = args.template, args.output

    if not template_path.exists():
        print(f"{template_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading historical data from {template_path.name}...")
    expenses_raw = pd.read_excel(template_path, sheet_name="Expenses")
    income_raw = pd.read_excel(template_path, sheet_name="Income")

    expenses = _convert_expenses(expenses_raw, template_path.name)
    income = _convert_income(income_raw, template_path.name)
    print(f"  Expenses: {len(expenses)} rows, Income: {len(income)} rows")

    merged = pd.concat([expenses, income], ignore_index=True)

    # Re-seeding is the case where manual review work is most at risk of being
    # thrown away, so saved decisions are put back on the way out (see
    # finance_tracker/reviews.py). Seed ids are deterministic, so a row that
    # was reviewed before comes back already reviewed.
    merged, n_reviewed = reviews.apply_reviews(merged)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline.save_store(merged, output_path)
    print(f"Wrote {len(merged)} transactions to {output_path}")
    if n_reviewed:
        print(f"Re-applied {n_reviewed} saved review decision(s) from data/review_decisions.json.")


if __name__ == "__main__":
    main()
