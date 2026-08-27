"""Durable memory of manual review decisions, keyed by transaction_id.

When you review an unrecognized transaction — look up what that €38 card
payment actually was, decide it belongs in Saúde/Consulta, and type "physio,
2nd session" into the review note — that decision is real work, and it lives
in exactly one place: the row you edited in transactions.csv. Rebuild the
store from raw exports (scripts/reset_store.py, then re-ingest) and all of it
is gone, because raw bank exports have never heard of your categories.

This module keeps a second copy of just those decisions, outside the store:

    {
      "9f1c2a...": {
        "category": "Saúde", "sub_category": "Consulta", "method": "Cartão",
        "review_note": "physio, 2nd session", "reviewed_at": "2026-03-04T18:22:11",
        "notes": "PAG. SERVICOS 38,00"      # original description, for readability only
      }
    }

`transaction_id` is a hash of (date, description, amount), so it is stable
across rebuilds — re-ingesting the same bank export produces the same id, and
apply_reviews() puts the decision straight back onto it.

The dashboard writes the same file (its "Download review_decisions.json"
button), and re-applies decisions client-side on load, so a review survives
whichever side of the project you do the work on.

This file contains transaction descriptions and personal notes — it is
gitignored alongside transactions.csv, unlike category_overrides.json.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import schema
from . import taxonomy as tx

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "review_decisions.json"

_FIELDS = {
    "category": schema.CATEGORY,
    "sub_category": schema.SUBCATEGORY,
    "method": schema.METHOD,
    "review_note": schema.REVIEW_NOTE,
    "reviewed_at": schema.REVIEWED_AT,
}


def load_reviews(path=DEFAULT_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save_reviews(reviews: dict, path=DEFAULT_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reviews, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record_review(reviews: dict, transaction_id: str, category: str, sub_category: str,
                  method: str, review_note: str = "", notes: str = "",
                  reviewed_at: str = None, derived_from: str = None) -> dict:
    """Return a new dict with one review decision recorded (input untouched).

    `derived_from` marks a decision that was copied from another row's review
    rather than made by looking at this transaction — see apply_by_description.
    """
    entry = {
        "category": category,
        "sub_category": sub_category,
        "method": method,
        "review_note": review_note or "",
        "reviewed_at": reviewed_at or datetime.now().isoformat(timespec="seconds"),
        "notes": notes or "",
    }
    if derived_from:
        entry["derived_from"] = str(derived_from)
    return {**reviews, str(transaction_id): entry}


def _placed(txn_type: str, decision: dict) -> tuple:
    """A decision's (category, sub-category), mapped onto today's taxonomy.

    review_decisions.json outlives the taxonomy. A decision saved before a
    rename — or before taxonomy.py existed at all — still names the pair that
    was correct when someone made it, and re-applying it verbatim writes an
    off-taxonomy pair straight back into the store. That is this module quietly
    undoing the one guarantee the taxonomy exists to provide, months later and
    with no error anywhere.

    So decisions go through the same alias table as everything else. Returns
    None when the pair cannot be placed at all, and the caller then leaves the
    row's current values alone rather than corrupting them — a decision nobody
    can interpret is not a reason to lose what the row already says.
    """
    category = decision.get("category")
    sub_category = decision.get("sub_category")
    if not category:
        return None
    return tx.resolve(txn_type, category, sub_category)


def apply_reviews(df: pd.DataFrame, reviews: dict = None) -> tuple:
    """Re-apply saved review decisions onto a store DataFrame in place-ish.

    Returns (df, n_applied). A decision is only counted as applied when it
    actually changes something, so re-running this on an already-reviewed
    store reports 0 rather than inflating the count.

    Category/Sub-category are mapped onto the current taxonomy on the way in
    (see _placed) — a saved decision is a human answer worth keeping, but not
    worth reintroducing a vocabulary the rest of the system has retired.
    """
    if reviews is None:
        reviews = load_reviews()
    if df.empty or not reviews:
        return df, 0

    df = df.copy()
    for column in schema.REVIEW_COLUMNS:
        if column not in df.columns:
            df[column] = ""
        # An all-empty column read back from CSV arrives as float64 NaN;
        # writing a string into it would be an incompatible-dtype assignment.
        df[column] = df[column].astype(object).where(df[column].notna(), "")

    ids = df[schema.TRANSACTION_ID].astype(str)
    applied = 0
    unplaceable = 0
    for position, transaction_id in zip(df.index, ids):
        decision = reviews.get(transaction_id)
        if not decision:
            continue

        placed = _placed(df.at[position, schema.TYPE], decision)
        if placed is None:
            # The note and timestamp are still worth restoring — they record
            # what the person found out — but the pair is dropped rather than
            # written, leaving whatever the categorizer decided in its place.
            unplaceable += 1
        decision = dict(decision)
        if placed:
            decision["category"], decision["sub_category"] = placed
        else:
            decision.pop("category", None)
            decision.pop("sub_category", None)

        changed = False
        for key, column in _FIELDS.items():
            value = decision.get(key)
            if value in (None, ""):
                continue
            if str(df.at[position, column]) != str(value):
                df.at[position, column] = value
                changed = True
        applied += int(changed)

    if unplaceable:
        print(f"  {unplaceable} saved review decision(s) name a Category/Sub-category that is no "
              f"longer in the taxonomy — their notes were restored, their categories were not.")
    return df, applied


PEER_METHODS = ("MBWay", "Transferência")
DERIVED_MARKER = "↳ auto-applied"


def _normalized_description(notes) -> str:
    return " ".join(str(notes or "").strip().lower().split())


def apply_by_description(df: pd.DataFrame, reviews: dict = None) -> tuple:
    """Fill in unreviewed rows whose description exactly matches one already
    reviewed, and record each as a derived decision.

    This is the CLI half of the dashboard's "also apply to the N other items
    with this exact description": next month's `Uber Rides` rows inherit the
    answer given to last month's, instead of landing back in the queue.

    Two rules keep it honest, and both are deliberate:

    - **Merchants only.** A peer-to-peer transfer's counterparty doesn't
      determine what the money was for — the same person sends €13 one month
      and €263 another — so transfers are never auto-filled here. The
      dashboard offers them as an explicit, unchecked opt-in because a human
      is present to judge; a batch import has nobody to ask.
    - **Exact description match.** Looser keys score better until you notice
      that every peer transfer shares its opening words, at which point one
      review re-files all of them.

    The source review's *note* is never copied — it records what someone
    actually looked at. Derived rows get a provenance marker instead.

    Returns (df, n_filled).
    """
    if reviews is None:
        reviews = load_reviews()
    if df.empty or not reviews:
        return df, 0

    df = df.copy()
    for column in schema.REVIEW_COLUMNS:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].astype(object).where(df[column].notna(), "")

    # Descriptions that already have a human answer, and what that answer was.
    # A derived row is not a source: chaining them would let one review
    # silently spread across descriptions it never matched.
    answers = {}
    for _, row in df.iterrows():
        reviewed_at = str(row[schema.REVIEWED_AT] or "")
        if not reviewed_at:
            continue
        decision = reviews.get(str(row[schema.TRANSACTION_ID])) or {}
        if decision.get("derived_from") or str(row[schema.REVIEW_NOTE] or "").startswith(DERIVED_MARKER):
            continue
        answers.setdefault(_normalized_description(row[schema.NOTES]), {
            "category": row[schema.CATEGORY],
            "sub_category": row[schema.SUBCATEGORY],
            "source_id": str(row[schema.TRANSACTION_ID]),
            "source_date": str(row[schema.DATE]),
        })
    if not answers:
        return df, 0

    filled = 0
    for position in df.index:
        if str(df.at[position, schema.REVIEWED_AT] or ""):
            continue
        # The whole pair, not just the category: Outros/Levantamento and
        # Outros/Transferências Pessoais are settled answers that happen to
        # share a category with the review queue.
        if not schema.is_unclassified(df.at[position, schema.CATEGORY],
                                      df.at[position, schema.SUBCATEGORY]):
            continue
        if df.at[position, schema.METHOD] in PEER_METHODS:
            continue
        answer = answers.get(_normalized_description(df.at[position, schema.NOTES]))
        if not answer:
            continue

        marker = (f"{DERIVED_MARKER} from the review of {answer['source_date']} "
                  f"(same description) — not individually checked")
        stamp = datetime.now().isoformat(timespec="seconds")
        df.at[position, schema.CATEGORY] = answer["category"]
        df.at[position, schema.SUBCATEGORY] = answer["sub_category"]
        df.at[position, schema.REVIEW_NOTE] = marker
        df.at[position, schema.REVIEWED_AT] = stamp
        reviews.update(record_review(
            {}, df.at[position, schema.TRANSACTION_ID],
            category=answer["category"], sub_category=answer["sub_category"],
            method=df.at[position, schema.METHOD], review_note=marker,
            notes=df.at[position, schema.NOTES], reviewed_at=stamp,
            derived_from=answer["source_id"],
        ))
        filled += 1
    return df, filled


def reviews_from_store(df: pd.DataFrame) -> dict:
    """Harvest review decisions out of a store that has them in its columns.

    Useful for backfilling review_decisions.json from a transactions.csv that
    was reviewed before this file existed: every row carrying a Reviewed At
    timestamp is a decision worth keeping.
    """
    if df.empty or schema.REVIEWED_AT not in df.columns:
        return {}
    reviewed = df[df[schema.REVIEWED_AT].astype(str).str.strip().replace("nan", "") != ""]
    out = {}
    for _, row in reviewed.iterrows():
        out[str(row[schema.TRANSACTION_ID])] = {
            "category": row[schema.CATEGORY],
            "sub_category": row[schema.SUBCATEGORY],
            "method": row[schema.METHOD],
            "review_note": str(row.get(schema.REVIEW_NOTE, "") or ""),
            "reviewed_at": str(row[schema.REVIEWED_AT]),
            "notes": str(row.get(schema.NOTES, "") or ""),
        }
    return out
