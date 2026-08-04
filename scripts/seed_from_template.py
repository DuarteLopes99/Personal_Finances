#!/usr/bin/env python3
"""One-time import: convert the historical Expenses/Income sheets of an Excel
tracker (Expenses / Income sheets, same columns as
Personal_Finance_Tracker_With_Formulas.xlsx) into the centralized
data/transactions.csv (unified schema, see finance_tracker/schema.py).

The source workbook is expected to hold personal financial data, so it is
intentionally not bundled in this repo — pass its path explicitly.

Usage:
    python scripts/seed_from_template.py path/to/template.xlsx [path/to/output.csv]
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import schema  # noqa: E402

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def _seed_id(sheet: str, index: int, date, amount: float, notes) -> str:
    key = f"seed|{sheet}|{index}|{date}|{amount:.2f}|{notes}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _clean_str(value, default="") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip()


# Known spelling variants in the original template, normalized to one label
# so category charts don't split the same bucket into multiple slices.
CATEGORY_ALIASES = {
    "Saude": "Saúde",
}


def _clean_category(value, default="") -> str:
    value = _clean_str(value, default)
    return CATEGORY_ALIASES.get(value, value)


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
            schema.CATEGORY: _clean_category(row.get("Category"), "Outros"),
            schema.SUBCATEGORY: _clean_str(row.get("Sub-category")),
            schema.METHOD: _clean_str(row.get("Payment Method"), schema.UNSPECIFIED_METHOD),
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
            schema.CATEGORY: _clean_category(row.get("Category"), "Outro"),
            schema.SUBCATEGORY: _clean_str(row.get("Source")),
            schema.METHOD: _clean_str(row.get("Source"), schema.UNSPECIFIED_METHOD),
            schema.AMOUNT: round(abs(float(row["Amount (€)"])), 2),
            schema.NOTES: notes,
            schema.MONTH: int(row["Month"]),
            schema.YEAR: int(row["Year"]),
            schema.SOURCE_FILE: f"{source_name} (Income)",
        })
    return pd.DataFrame(records, columns=schema.COLUMNS)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    template_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

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
    merged = merged.sort_values([schema.YEAR, schema.MONTH, schema.DATE]).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    print(f"Wrote {len(merged)} transactions to {output_path}")


if __name__ == "__main__":
    main()
