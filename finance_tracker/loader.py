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
        "Date": pd.to_datetime(df[date_col], dayfirst=True),
        "Description": df[desc_col].astype(str),
        "Amount": (
            df[amount_col]
            .astype(str)
            .str.replace(",", ".", regex=False)
            .str.strip()
            .astype(float)
        ),
    })
    out = out.dropna(subset=["Date", "Amount"])
    return out.reset_index(drop=True)
