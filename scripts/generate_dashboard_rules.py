#!/usr/bin/env python3
"""Generate dashboard/rules.js from the Python taxonomy and rule tables.

The dashboard has to categorize client-side (it ingests bank exports in the
browser, offline), so it needs its own copy of the taxonomy and the rules.
Keeping that copy by hand does not work: by the time this script was first
written the two had already drifted by 21 keywords and two whole sub-categories,
so the same file categorized differently depending on which tool you fed it to.
That is the worst kind of divergence, because both answers look right alone.

So: `finance_tracker/taxonomy.py` and `finance_tracker/categorize.py` are the
single source of truth, and the JavaScript is generated from them.

What crosses the boundary
-------------------------
Rule patterns are emitted as **pattern strings**, not as compiled regexes, and
the browser wraps them in the same `[a-z0-9_]` lookarounds Python uses (see
`_compile` in categorize.py). That is why patterns are restricted to ASCII-safe
syntax with no `\\b`, `\\w` or `\\p{...}`: those three are the constructs whose
meaning differs between the two engines, and avoiding them is what makes a
pattern string mean the same thing on both sides.

Usage:
    python3 scripts/generate_dashboard_rules.py           # write dashboard/rules.js
    python3 scripts/generate_dashboard_rules.py --check   # exit 1 if stale (for hooks/CI)

Run it after editing any rule or the taxonomy. The pre-commit hook installed by
scripts/install_git_hooks.py runs --check for you.
"""

import argparse
import importlib.util
import json
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_package_modules(*names):
    """Load finance_tracker submodules without executing the package __init__.

    `from finance_tracker import categorize` would run the package's __init__,
    which imports pandas and cryptography. This script runs from a git
    pre-commit hook under whatever python3 is on PATH — usually not the project
    venv — so depending on those would make the hook fail for a reason that has
    nothing to do with the rules.

    A stub package with a __path__ is registered first so that the modules'
    relative imports (`from . import taxonomy`) resolve against it. taxonomy.py
    imports nothing at all and categorize.py imports only `re` and
    `unicodedata`, so nothing heavy gets pulled in.
    """
    package = types.ModuleType("finance_tracker")
    package.__path__ = [str(REPO_ROOT / "finance_tracker")]
    sys.modules.setdefault("finance_tracker", package)

    loaded = []
    for name in names:
        path = REPO_ROOT / "finance_tracker" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"finance_tracker.{name}", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        loaded.append(module)
    return loaded


taxonomy, categorize = _load_package_modules("taxonomy", "categorize")

OUTPUT = REPO_ROOT / "dashboard" / "rules.js"

HEADER = """// AUTO-GENERATED — DO NOT EDIT BY HAND.
//
// Written by scripts/generate_dashboard_rules.py from finance_tracker/taxonomy.py
// and finance_tracker/categorize.py, which are the single source of truth for
// the taxonomy and the rule tables. Editing this file directly means the
// dashboard and the CLI categorize the same bank export differently — which is
// exactly what happened when these tables were maintained by hand.
//
// To change a rule: edit categorize.py (or taxonomy.py), then re-run
//   python3 scripts/generate_dashboard_rules.py
"""


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _rules_block(name: str, rules) -> str:
    lines = [f"const {name} = ["]
    for patterns, category, sub_category, suggested_method in rules:
        lines.append(f"  [{_js(list(patterns))}, {_js(category)}, "
                     f"{_js(sub_category)}, {_js(suggested_method)}],")
    lines.append("];")
    return "\n".join(lines)


def _legacy_aliases_block() -> str:
    """LEGACY_ALIASES as {"Type|Category|sub": [category, sub]}.

    The browser needs this for the same reason Python does: review decisions
    and loaded stores outlive the taxonomy, and re-applying one verbatim writes
    a retired pair back in. Emitting the table keeps both engines resolving a
    legacy pair to the *same* place — validating on one side and aliasing on
    the other would be a fresh divergence of exactly the kind rules.js exists
    to prevent. The tuple key is flattened to a string because JS objects
    cannot key on arrays.
    """
    flat = {f"{t}|{c}|{sub}": list(target)
            for (t, c, sub), target in taxonomy.LEGACY_ALIASES.items()}
    return f"const LEGACY_ALIASES = {json.dumps(flat, ensure_ascii=False, indent=2)};"


def _taxonomy_block() -> str:
    tree = {
        txn_type: {category: list(subs) for category, subs in categories.items()}
        for txn_type, categories in taxonomy.TAXONOMY.items()
    }
    return f"const TAXONOMY = {json.dumps(tree, ensure_ascii=False, indent=2)};"


def render() -> str:
    parts = [
        HEADER,
        "",
        "// ---- Taxonomy (finance_tracker/taxonomy.py) ----",
        "// The complete list of Category -> Sub-category pairs that may exist.",
        "// The review panel builds its pickers from this and refuses anything",
        "// outside it, exactly like taxonomy.validate() does in Python.",
        _taxonomy_block(),
        "",
        "// ---- Legacy pairs (finance_tracker/taxonomy.py LEGACY_ALIASES) ----",
        "// Keyed \"Type|Category|sub-category\" with the sub-category lowercased;",
        "// a \"*\" sub-category matches any. resolvePair() below mirrors",
        "// taxonomy.resolve().",
        _legacy_aliases_block(),
        "",
        f"const COLUMNS = {_js(schema_columns())};",
        f"const TYPE_INCOME = {_js(taxonomy.TYPE_INCOME)};",
        f"const TYPE_EXPENSE = {_js(taxonomy.TYPE_EXPENSE)};",
        f"const EXPENSE_CATEGORIES = {_js(taxonomy.EXPENSE_CATEGORIES)};",
        f"const INCOME_CATEGORIES = {_js(taxonomy.INCOME_CATEGORIES)};",
        f"const METHODS = {_js(taxonomy.METHODS)};",
        f"const UNSPECIFIED_METHOD = {_js(taxonomy.UNSPECIFIED_METHOD)};",
        f"const MEAL_CARD_METHOD = {_js(taxonomy.MEAL_CARD_METHOD)};",
        f"const SAVINGS_CATEGORY = {_js(taxonomy.SAVINGS_CATEGORY)};",
        f"const UNCLASSIFIED_CATEGORY = {_js(taxonomy.UNCLASSIFIED_CATEGORY)};",
        f"const UNCLASSIFIED_SUB = {_js(taxonomy.UNCLASSIFIED_SUB)};",
        f"const REVIEW_NOTE = {_js('Review Note')};",
        f"const REVIEWED_AT = {_js('Reviewed At')};",
        "",
        "// ---- Rule tables (finance_tracker/categorize.py) ----",
        "// Each rule: [patterns, category, sub_category, suggestedMethod].",
        "// `patterns` are regex fragments matched against the NORMALIZED",
        "// description (lowercased, accents stripped) with word boundaries",
        "// added by compileRule(). The suggested method is a default only —",
        "// the rail is detected separately by overlayMethod() and wins",
        "// whenever the description names one.",
        f"const GATEWAY_PATTERNS = {_js(categorize.GATEWAY_PATTERNS)};",
        "",
        _rules_block("PURPOSE_INCOME_RULES", categorize.PURPOSE_INCOME_RULES),
        "",
        _rules_block("PURPOSE_EXPENSE_RULES", categorize.PURPOSE_EXPENSE_RULES),
        "",
    ]
    return "\n".join(parts)


def schema_columns() -> list:
    """The store's column order.

    Duplicated as a literal rather than imported from schema.py, which imports
    pandas transitively through the package. The store's columns change far
    less often than the taxonomy does, and `--check` in the pre-commit hook
    would fail loudly if this ever fell behind.
    """
    return [
        "transaction_id", "Date", "Type", "Category", "Sub-category", "Method",
        "Amount (€)", "Notes", "Review Note", "Reviewed At", "Month", "Year",
        "Source File",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="Don't write; exit 1 if the file on disk is out of date")
    args = parser.parse_args()

    generated = render()
    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None

    if args.check:
        if current == generated:
            print(f"{OUTPUT.relative_to(REPO_ROOT)} is up to date.")
            return 0
        print(f"{OUTPUT.relative_to(REPO_ROOT)} is STALE — the dashboard would categorize "
              f"differently from the CLI.\nRun: python3 scripts/generate_dashboard_rules.py",
              file=sys.stderr)
        return 1

    if current == generated:
        print(f"{OUTPUT.relative_to(REPO_ROOT)} already up to date.")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(generated, encoding="utf-8")
    n_rules = len(categorize.PURPOSE_EXPENSE_RULES) + len(categorize.PURPOSE_INCOME_RULES)
    n_pairs = sum(len(subs) for tree in taxonomy.TAXONOMY.values() for subs in tree.values())
    print(f"Wrote {OUTPUT.relative_to(REPO_ROOT)} — {n_rules} rules, "
          f"{len(taxonomy.EXPENSE_CATEGORIES) + len(taxonomy.INCOME_CATEGORIES)} categories, "
          f"{n_pairs} valid pairs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
