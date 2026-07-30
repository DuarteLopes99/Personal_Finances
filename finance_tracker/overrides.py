"""User-taught category overrides for commercial/merchant transactions that
the built-in keyword rules in categorize.py don't recognize.

Each override is a small JSON object:
    {"keywords": ["sould park bowling"], "type": "expense",
     "category": "Lazer", "sub_category": "Desporto e Diversão", "method": "Cartão"}

`type` is "income", "expense", or "both". Overrides are checked before the
built-in rules in categorize.categorize_transaction, so a user correction
always wins.

Deliberately NOT meant for peer-to-peer transfers (MBWay / named bank
transfers, Category == "Transferências Pessoais") — the same person can send
or receive money for a completely different reason each month (rent one
month, a gift the next), so learning "this name -> this category" would
silently mis-categorize future, unrelated transactions from them. Overrides
are for the case a name-based rule actually works well: a merchant or company
whose purpose doesn't change transaction to transaction. The dashboard's
"Needs Review" panel only offers to save an override for "Outros"/"Outro"
rows for exactly this reason — see dashboard/index.html.
"""

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "category_overrides.json"


def load_overrides(path=DEFAULT_PATH) -> list:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_overrides(overrides: list, path=DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_override(overrides: list, keywords: list, txn_type: str, category: str, sub_category: str, method: str) -> list:
    """Return a new list with one override appended (does not mutate the input)."""
    if txn_type not in ("income", "expense", "both"):
        raise ValueError(f"txn_type must be 'income', 'expense', or 'both', got {txn_type!r}")
    return [*overrides, {
        "keywords": keywords,
        "type": txn_type,
        "category": category,
        "sub_category": sub_category,
        "method": method,
    }]
