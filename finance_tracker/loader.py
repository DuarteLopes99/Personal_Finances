"""Read raw monthly bank export files (xlsx or csv) into a normalized DataFrame.

Bank exports vary in exact header names (e.g. "Montante( EUR )" vs "Montante(EUR)"),
so we try a list of known aliases per logical field, same approach as the original
process_bank_files.py prototype.
"""

from pathlib import Path

import pandas as pd

DATE_ALIASES = ["Data Operação", "Data de Operação", "Data", "Date"]
DESCRIPTION_ALIASES = ["Descrição", "Descricao", "Descrição da transação", "Description"]
AMOUNT_ALIASES = ["Montante( EUR )", "Montante(EUR)", "Montante (EUR)", "Montante", "Amount", "Valor"]


class UnrecognizedFileFormat(ValueError):
    pass


def _find_column(columns, aliases):
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def _to_amount(series: "pd.Series") -> "pd.Series":
    """Parse an amount column that may be numeric, or text in either convention.

    Excel exports arrive as floats and need nothing. CSV exports arrive as text,
    and a Portuguese bank writes `1.424,00` — dot for thousands, comma for
    decimals. The previous implementation replaced every comma with a dot,
    turning that into `1.424.00`, which `float()` rejects: **one transaction
    over €999 in a CSV export aborted the entire ingest**, and the error
    ("could not convert string to float") named neither the file nor the row.

    So the separators are worked out per value instead of assumed:
    whichever of `.` or `,` appears last is the decimal point, and the other is
    a thousands separator to be dropped.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    def parse(value):
        text = str(value).strip().replace("\xa0", "").replace(" ", "")
        if not text or text.lower() in ("nan", "none"):
            return float("nan")
        # Trailing sign, as some exports write "12,34-" for a debit.
        negative = text.endswith("-") or text.startswith("-")
        text = text.strip("-+")
        last_dot, last_comma = text.rfind("."), text.rfind(",")
        if last_dot >= 0 and last_comma >= 0:
            decimal = "." if last_dot > last_comma else ","
            thousands = "," if decimal == "." else "."
            text = text.replace(thousands, "").replace(decimal, ".")
        elif last_comma >= 0:
            # A lone comma is a decimal comma ("3,50"), unless it is clearly
            # grouping ("1,424" with exactly three digits after it and no other
            # separator is ambiguous — treat it as decimal, matching the
            # European exports this reads).
            text = text.replace(",", ".")
        try:
            amount = float(text)
        except ValueError:
            return float("nan")
        return -amount if negative and amount > 0 else amount

    return series.map(parse)


def read_raw_bank_file(path) -> pd.DataFrame:
    """Load a raw monthly export and return a DataFrame with normalized
    columns: Date (datetime64), Description (str), Amount (float, signed).
    """
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise UnrecognizedFileFormat(f"Unsupported file type: {path.suffix}")

    date_col = _find_column(df.columns, DATE_ALIASES)
    desc_col = _find_column(df.columns, DESCRIPTION_ALIASES)
    amount_col = _find_column(df.columns, AMOUNT_ALIASES)

    missing = [
        name for name, col in
        [("date", date_col), ("description", desc_col), ("amount", amount_col)]
        if col is None
    ]
    if missing:
        raise UnrecognizedFileFormat(
            f"Could not find column(s) {missing} in {path.name}. "
            f"Available columns: {list(df.columns)}"
        )

    out = pd.DataFrame({
        # errors="coerce" so one malformed date is a dropped row rather than an
        # exception that takes the whole file with it — same reasoning as the
        # amount parser above.
        "Date": pd.to_datetime(df[date_col], dayfirst=True, errors="coerce"),
        "Description": df[desc_col].astype(str),
        "Amount": _to_amount(df[amount_col]),
    })

    unparsed = int(out["Date"].isna().sum() + out["Amount"].isna().sum())
    out = out.dropna(subset=["Date", "Amount"])
    if out.empty:
        raise UnrecognizedFileFormat(
            f"No usable rows in {path.name}: every row had an unreadable date or amount. "
            f"Found columns date={date_col!r}, description={desc_col!r}, amount={amount_col!r}."
        )
    if unparsed:
        # Not fatal, but never silent: a dropped row is a transaction missing
        # from every total on the page, and that must not be discovered later.
        print(f"  {path.name}: skipped {unparsed} row(s) with an unreadable date or amount.")
    return out.reset_index(drop=True)
