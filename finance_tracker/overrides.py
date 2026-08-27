"""User-taught category overrides for transactions the built-in keyword rules
in categorize.py don't recognize.

Each override is a small JSON object:
    {"keywords": ["sould park bowling"], "type": "expense",
     "category": "Lazer", "sub_category": "Outros", "method": "Cartão"}

`type` is "income", "expense", or "both". Merchant overrides are checked
before the built-in rules in categorize.categorize_transaction, so a user
correction always wins.

The Category/Sub-category pair must exist in taxonomy.py — `add_override`
refuses anything else. An override is a correction, and a correction that
invents a bucket no chart knows about is not one.

Two kinds of override
---------------------
**Merchant overrides** (the default, `"peer": false`) are the safe case: a
company's purpose doesn't change from transaction to transaction, so "this
name -> this category" generalizes. They win outright, ahead of everything.

**Peer overrides** (`"peer": true`) are the opt-in case, for a recurring MBWay
or bank transfer with a *named counterparty* — the gym buddy you pay for the
weekly court booking, the colleague who fronts the office lunch. The default
answer for peer-to-peer transfers is still "don't learn this": the same person
can send rent one month and a birthday gift the next, and a name-based rule
would silently mis-file that. But when the user knows a given counterparty
really is always the same thing, refusing to remember it means re-typing the
same correction every single month, and that is its own kind of data loss.

So peer overrides exist, are never offered by default, and are deliberately
weaker than merchant ones:

- they are only consulted in the *fallback* path — i.e. when no purpose
  keyword matched at all — so "Mbway - Cinemas" is still
  Lazer/Cinema-Espetáculos, never the peer rule's category;
- they never change the detected Method: the rail stays MBWay/Transferência,
  which is a fact about the transaction, not a guess;
- they are matched against the extracted counterparty name where there is one,
  so "MB WAY para Ana Silva" learns *Ana Silva*, not the words around her.

See categorize.categorize_transaction for the resulting precedence, and the
dashboard's "Needs Review" panel for how each kind is offered.
"""

import json
from pathlib import Path

from . import taxonomy as tx

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "category_overrides.json"

VALID_TYPES = ("income", "expense", "both")

_TXN_TYPES = {"income": (tx.TYPE_INCOME,), "expense": (tx.TYPE_EXPENSE,),
              "both": (tx.TYPE_INCOME, tx.TYPE_EXPENSE)}


def load_overrides(path=DEFAULT_PATH) -> list:
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def save_overrides(overrides: list, path=DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_peer(override: dict) -> bool:
    return bool(override.get("peer"))


def add_override(overrides: list, keywords: list, txn_type: str, category: str,
                 sub_category: str, method: str, peer: bool = False) -> list:
    """Return a new list with one override added (does not mutate the input).

    An override whose keywords, type and peer flag match an existing entry
    replaces it rather than stacking a second, shadowed rule behind it —
    correcting the same merchant twice should leave one rule, not two.
    """
    if txn_type not in VALID_TYPES:
        raise ValueError(f"txn_type must be one of {VALID_TYPES}, got {txn_type!r}")
    keywords = [k.strip().lower() for k in keywords if k and k.strip()]
    if not keywords:
        raise ValueError("at least one non-empty keyword is required")

    # The taxonomy is strict, and an override is a writer like any other. A
    # correction that invents "Saúde/Ginásio" when the taxonomy says
    # "Desporto/Ginásio" doesn't fix a miscategorization — it creates a second
    # one that no chart adds up, which is exactly what the store filled up with
    # before taxonomy.py existed.
    for resolved_type in _TXN_TYPES[txn_type]:
        tx.validate(resolved_type, category, sub_category,
                    where=f"override {keywords[0]!r}: ")
    if method and method not in tx.METHODS:
        raise ValueError(f"override {keywords[0]!r}: {method!r} is not a known Method. "
                         f"Valid: {', '.join(tx.METHODS)}")

    entry = {
        "keywords": keywords,
        "type": txn_type,
        "category": category,
        "sub_category": sub_category,
        "method": method,
        "peer": bool(peer),
    }
    kept = [
        o for o in overrides
        if not (sorted(k.lower() for k in o.get("keywords", [])) == sorted(keywords)
                and o.get("type") == txn_type
                and is_peer(o) == bool(peer))
    ]
    return [*kept, entry]
