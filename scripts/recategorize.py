#!/usr/bin/env python3
"""Bring the store back in line with today's taxonomy and rules.

Categorization normally happens once, at ingest. So teaching the pipeline
something new — a rule in categorize.py, an entry in category_overrides.json, a
sub-category in taxonomy.py — helps every future import and does nothing at all
for the transactions already in the store. Knowledge you added five minutes ago
can be looking straight at fifteen rows it would classify perfectly and not
touch them. This script closes that gap.

Two passes, in this order:

1. **Normalize** — a row whose Category/Sub-category isn't in the taxonomy is
   mapped through `taxonomy.LEGACY_ALIASES`. This is the pass that preserves
   human work: `Poupança/Investimento + PPR` is a correct answer that only
   needs its new name, and re-deriving it from "Golden Sgf Soc Gestora Fundo
   Pensoes Sa" would throw it away. It is also what a taxonomy rename needs —
   add the alias, run this.
2. **Re-classify** — rows still awaiting an answer (`Outros / Por Classificar`,
   or a pair no alias could place) go back through today's rules and overrides
   using their original description.

What it will not touch:

- **A row with `Reviewed At`.** A manual review is the top of the ladder and a
  regex does not get to overrule a human answer. Reviewed rows are normalized
  through the alias table, never re-derived.
- **`Outros / Levantamento` and `Outros / Transferências Pessoais`.** They share
  a category with the review queue but are settled facts — cash withdrawn,
  money sent to a named person — not unanswered questions.
- **A row it would demote.** If today's rules can't do better than the review
  bucket for a row that already has a real category, the real category stays.
  This fills in blanks; it does not overwrite answers with shrugs.

Dry run by default: nothing is written unless you pass --apply, and --apply
backs the store up first.

Usage:
    python3 scripts/recategorize.py                 # show what would change
    python3 scripts/recategorize.py --apply         # back up, then write
    python3 scripts/recategorize.py --limit 60      # show more of the diff
"""

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from finance_tracker import overrides as overrides_mod  # noqa: E402
from finance_tracker import pipeline, schema  # noqa: E402
from finance_tracker import taxonomy as tx  # noqa: E402
from finance_tracker.categorize import categorize_transaction, extract_counterparty  # noqa: E402

DEFAULT_STORE = Path(__file__).resolve().parent.parent / "data" / "transactions.csv"


def _is_reviewed(row) -> bool:
    return str(row.get(schema.REVIEWED_AT, "") or "").strip() not in ("", "nan")


def _clean_method(row) -> str:
    method = str(row[schema.METHOD] or "").strip()
    return method if method in tx.METHODS else tx.UNSPECIFIED_METHOD


def plan_row(row, overrides):
    """Return (category, sub_category, method, how) for one store row.

    `how` is why the row moved, and "unchanged" when it shouldn't.
    """
    txn_type = row[schema.TYPE]
    category = str(row[schema.CATEGORY] or "").strip()
    sub_category = str(row[schema.SUBCATEGORY] or "").strip()
    method = _clean_method(row)
    valid = schema.is_valid(txn_type, category, sub_category)

    # Pass 1 — normalize. An exact (category, sub-category) alias wins over the
    # category-wide "*" one, so `Refeição/Padaria` reaches Café/Padaria while
    # every other Refeição sub-category lands on Alimentação/Outros.
    #
    # An alias that lands on a *catch-all* is only half an answer: it says "this
    # was Investimentos" and gives up on the sub-category. That is worth keeping
    # as a floor, but it must not block pass 2 from doing better — the old
    # `Investimento/ETF` rows aliased to Investimentos/Outros while the rules
    # can read "Degiro" and say ETFs/DEGIRO. So a catch-all alias falls through,
    # and pass 2's answer is taken only if it agrees on the category (a more
    # specific sub-category is an improvement; a different category would be
    # overruling a human's judgement with a regex).
    floor = None
    if not valid:
        aliased = tx.resolve(txn_type, category, sub_category)
        if aliased and aliased[1] != tx.CATCH_ALL_SUB:
            return aliased[0], aliased[1], method, "normalized"
        if aliased:
            floor = aliased
    elif sub_category == tx.CATCH_ALL_SUB:
        # A row already sitting on a catch-all is in the same half-answered
        # state, whether it got there by alias or by an earlier run. Teaching
        # the rules a new sub-category should reach it, so it becomes a floor
        # too — same guarantees: same category only, never a demotion.
        floor = (category, sub_category)

    # A reviewed row keeps its human answer. It is normalized through the alias
    # table above and never re-derived below.
    if _is_reviewed(row):
        if valid:
            return category, sub_category, method, "unchanged"
        if floor:
            return floor[0], floor[1], method, "normalized"
        return (*_fallback(txn_type, category, method, row), "reviewed-unplaceable")

    # Settled answers are left alone — except a catch-all, which pass 2 may
    # still refine within the same category.
    if valid and not floor and not tx.is_unclassified(category, sub_category):
        return category, sub_category, method, "unchanged"

    # Pass 2 — re-classify from the original description.
    amount = float(row[schema.AMOUNT])
    signed = amount if txn_type == schema.TYPE_INCOME else -amount
    new_category, new_sub, new_method = categorize_transaction(
        row[schema.NOTES], signed, overrides=overrides)

    if tx.is_unclassified(new_category, new_sub) or (floor and new_category != floor[0]):
        # Never demote: if today's rules have nothing better to say about a row
        # that already carries a real category, leave the real category alone.
        if floor:
            return floor[0], floor[1], method, "normalized"
        if valid and not tx.is_unclassified(category, sub_category):
            return category, sub_category, method, "unchanged"
        return (*_fallback(txn_type, category, method, row), "unclassified")

    # Keep the recorded rail when the description carries no rail word of its
    # own — seed rows like "Frigorificio" were recorded as MBWay by a human, and
    # re-deriving would silently turn them into bank transfers.
    if method != tx.UNSPECIFIED_METHOD and new_method in ("Cartão", "Transferência"):
        new_method = method
    # Income personal transfers are split by rail, so the sub-category has to
    # follow the rail we just decided to keep.
    if new_category == "Transferências Pessoais":
        new_sub = "MBWay" if new_method == "MBWay" else "Transferência"

    how = "re-classified" if (new_category, new_sub) != (category, sub_category) else "unchanged"
    return new_category, new_sub, new_method, how


def _fallback(txn_type, category, method, row) -> tuple:
    """The honest landing spot for a row nothing could place.

    A transfer with a named counterparty is a real fact worth keeping — it just
    isn't a spending category, so the name stays in Notes and the row gets the
    taxonomy's bucket for exactly that.
    """
    if method in ("MBWay", "Transferência") and extract_counterparty(row[schema.NOTES]):
        peer_category, peer_sub = tx.LEGACY_PEER_CATEGORIES[txn_type]
        if txn_type == schema.TYPE_INCOME:
            peer_sub = "MBWay" if method == "MBWay" else "Transferência"
        return peer_category, peer_sub, method
    # Keep the category, drop the sub-category — but only when the category was
    # a real answer. `Outros` now has a catch-all of its own, and without this
    # guard every unclassified row would land on Outros/Outros: the review queue
    # quietly emptying itself into "settled, miscellaneous". Outros/Outros is a
    # deliberate human choice, never somewhere a regex puts things.
    if category != tx.UNCLASSIFIED_CATEGORY and schema.is_valid(txn_type, category, tx.CATCH_ALL_SUB):
        return category, tx.CATCH_ALL_SUB, method
    return (*tx.unclassified(txn_type), method)


def plan_changes(df, overrides):
    changes = []
    for position in df.index:
        row = df.loc[position]
        category, sub_category, method, how = plan_row(row, overrides)
        current = (str(row[schema.CATEGORY]), str(row[schema.SUBCATEGORY]), str(row[schema.METHOD]))
        if how == "unchanged" and (category, sub_category, method) == current:
            continue
        if (category, sub_category, method) == current:
            continue
        changes.append({
            "position": position, "how": how, "type": row[schema.TYPE],
            "date": row[schema.DATE], "notes": str(row[schema.NOTES])[:42],
            "amount": float(row[schema.AMOUNT]),
            "from": f"{row[schema.CATEGORY]}/{row[schema.SUBCATEGORY]}",
            "to": f"{category}/{sub_category}",
            "category": category, "sub_category": sub_category, "method": method,
        })
    return changes


def _count_invalid(df) -> int:
    return sum(
        1 for p in df.index
        if not schema.is_valid(df.at[p, schema.TYPE], str(df.at[p, schema.CATEGORY]),
                               str(df.at[p, schema.SUBCATEGORY]))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--apply", action="store_true", help="Actually write (backs up first)")
    parser.add_argument("--limit", type=int, default=25, help="Rows of the diff to print")
    args = parser.parse_args()

    df = pipeline.load_store(args.store)
    if df.empty:
        print("Store is empty — nothing to do.")
        return 0

    overrides = overrides_mod.load_overrides()
    changes = plan_changes(df, overrides)

    reviewed = sum(1 for p in df.index if _is_reviewed(df.loc[p]))
    queued = sum(1 for p in df.index
                 if tx.is_unclassified(df.at[p, schema.CATEGORY], df.at[p, schema.SUBCATEGORY]))
    print(f"{len(df)} transactions — {reviewed} reviewed by hand (never re-derived), "
          f"{queued} awaiting an answer, {_count_invalid(df)} outside the taxonomy.")
    print(f"{len(overrides)} override entr(ies) loaded from data/category_overrides.json.")

    if not changes:
        print("\nToday's taxonomy and rules agree with the store. Nothing to change.")
        return 0

    print(f"\n{len(changes)} row(s) would change:")
    for how, count in Counter(c["how"] for c in changes).most_common():
        print(f"  {count:>4}  {how}")

    by_target = {}
    for c in changes:
        by_target.setdefault(c["to"], []).append(c)
    print("\nDestinations:")
    for target, group in sorted(by_target.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(group):>4}  -> {target}  (€{sum(g['amount'] for g in group):.2f})")

    print()
    for c in changes[:args.limit]:
        print(f"  {c['date']}  {c['type'][:3]}  {c['amount']:8.2f}  "
              f"{c['notes']:<44} {c['from']}  ->  {c['to']}")
    if len(changes) > args.limit:
        print(f"  ... and {len(changes) - args.limit} more (raise --limit to see them)")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply to make these changes.")
        return 0

    backup = args.store.with_name(
        f"{args.store.stem}.backup-{datetime.now():%Y%m%dT%H%M%S}{args.store.suffix}")
    backup.write_bytes(args.store.read_bytes())
    print(f"\nBacked up the current store to {backup.name}")

    for c in changes:
        df.at[c["position"], schema.CATEGORY] = c["category"]
        df.at[c["position"], schema.SUBCATEGORY] = c["sub_category"]
        df.at[c["position"], schema.METHOD] = c["method"]
    pipeline.save_store(df, args.store)

    remaining = _count_invalid(df)
    print(f"Updated {len(changes)} row(s) in {args.store}.")
    print(f"{remaining} row(s) outside the taxonomy "
          f"({'clean' if remaining == 0 else 'investigate these'}).")
    print("Manual reviews were left untouched. Reload the dashboard to see the result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
