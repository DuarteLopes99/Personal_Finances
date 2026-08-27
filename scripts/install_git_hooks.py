#!/usr/bin/env python3
"""Install a pre-commit hook that makes leaking the plaintext store impossible.

`.gitignore` is a convention, not a guarantee. `git add -f data/transactions.csv`
bypasses it silently, and this repo has a live remote — one forced add and a
year of real transaction data is on GitHub, in history, forever. Rewriting
that out of a pushed repo is painful and never fully reliable.

So the hook refuses the commit outright. It blocks:

- **Plaintext financial data** — data/*.csv, data/review_decisions.json, and
  any .xlsx/.xls bank export, wherever it appears in the tree. These are the
  files that must only ever leave this machine encrypted.
- **A notebook with its outputs still in it.** This one was found the hard way:
  `pipeline_walkthrough.ipynb` is tracked, and running it embeds whatever it
  printed — real descriptions, counterparty names, salary amounts — straight
  into a committed file. .gitignore never covered it because the leak is inside
  a file that genuinely belongs in git. Clear the outputs and commit the code.
- **A stale dashboard/rules.js** — if the generated taxonomy and rules don't
  match taxonomy.py/categorize.py, the dashboard and the CLI categorize the
  same bank export differently. Committing that ships a silent inconsistency.

It also warns (without blocking) when data/transactions.csv.enc is older than
the plaintext store, i.e. you have changes that exist nowhere encrypted.

Usage:
    python3 scripts/install_git_hooks.py            # install
    python3 scripts/install_git_hooks.py --remove
"""

import argparse
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_MARKER = "# personal_finances pre-commit guard"

HOOK = r'''#!/bin/sh
# personal_finances pre-commit guard
# Installed by scripts/install_git_hooks.py — see that file for the rationale.
# Bypass in a genuine emergency with --no-verify, but understand that the
# things this blocks are exactly the things that cannot be un-leaked.

repo_root=$(git rev-parse --show-toplevel)
staged=$(git diff --cached --name-only --diff-filter=ACM)
blocked=""

for f in $staged; do
  case "$f" in
    data/*.csv|data/*.dec|data/review_decisions.json|*.xlsx|*.xls)
      blocked="$blocked  $f\n" ;;
  esac
done

if [ -n "$blocked" ]; then
  printf "\n\033[31mCOMMIT BLOCKED — plaintext financial data is staged:\033[0m\n"
  printf "$blocked"
  printf "\nOnly the encrypted store belongs in git. To fix:\n"
  printf "  git restore --staged <file>\n"
  printf "  python3 scripts/encrypt_store.py     # then commit data/transactions.csv.enc\n\n"
  exit 1
fi

# A notebook carries its outputs inside it, so "the file is fine to commit" and
# "the contents are fine to commit" are different questions. Executed cells hold
# real transaction descriptions; the source does not.
for f in $staged; do
  case "$f" in
    *.ipynb)
      if python3 - "$repo_root/$f" <<'PYEOF'
import json, sys
nb = json.load(open(sys.argv[1], encoding="utf-8"))
cells = [c for c in nb.get("cells", [])
         if c.get("cell_type") == "code" and (c.get("outputs") or c.get("execution_count"))]
sys.exit(0 if cells else 1)
PYEOF
      then
        printf "\n\033[31mCOMMIT BLOCKED — %s still has cell outputs.\033[0m\n" "$f"
        printf "Executed cells embed real transaction descriptions in a tracked file.\n"
        printf "Clear them, then re-stage:\n"
        printf "  python3 scripts/strip_notebook_outputs.py && git add %s\n\n" "$f"
        exit 1
      fi
      ;;
  esac
done

# A committed rules.js that no longer matches the taxonomy or the rules means
# the dashboard and the CLI disagree about how to categorize the same file.
if echo "$staged" | grep -qE '^(finance_tracker/(taxonomy|categorize|schema)\.py|dashboard/rules\.js)$'; then
  check_output=$(python3 "$repo_root/scripts/generate_dashboard_rules.py" --check 2>&1)
  check_status=$?
  if [ $check_status -eq 1 ]; then
    printf "\n\033[31mCOMMIT BLOCKED — dashboard/rules.js is out of date.\033[0m\n"
    printf "The dashboard would categorize differently from the CLI. Fix with:\n"
    printf "  python3 scripts/generate_dashboard_rules.py && git add dashboard/rules.js\n\n"
    exit 1
  elif [ $check_status -ne 0 ]; then
    # The checker itself failed. Say so rather than blaming the rules — a
    # blocked commit with a misleading reason is worse than no check.
    printf "\n\033[33mWarning:\033[0m couldn't verify dashboard/rules.js:\n%s\n\n" "$check_output"
  fi
fi

# Not a blocker: you may simply not have re-encrypted yet.
if [ -f "$repo_root/data/transactions.csv" ]; then
  if [ ! -f "$repo_root/data/transactions.csv.enc" ] \
     || [ "$repo_root/data/transactions.csv" -nt "$repo_root/data/transactions.csv.enc" ]; then
    printf "\n\033[33mNote:\033[0m data/transactions.csv is newer than its encrypted copy.\n"
    printf "Run scripts/encrypt_store.py if you want this state backed up in git.\n\n"
  fi
fi

exit 0
'''


def hooks_dir() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--git-path", "hooks"],
                             cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit("Not a git repository (or git is unavailable) — nothing to install into.")
    path = Path(out.stdout.strip())
    return path if path.is_absolute() else REPO_ROOT / path


def install() -> int:
    target = hooks_dir()
    target.mkdir(parents=True, exist_ok=True)
    hook_path = target / "pre-commit"

    if hook_path.exists() and HOOK_MARKER not in hook_path.read_text(encoding="utf-8", errors="replace"):
        raise SystemExit(
            f"{hook_path} already exists and isn't ours — refusing to overwrite it.\n"
            f"Merge the guard from scripts/install_git_hooks.py into it by hand."
        )

    hook_path.write_text(HOOK, encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed {hook_path}")
    print("  Blocks: data/*.csv, data/review_decisions.json, *.xlsx/*.xls, stale dashboard/rules.js")
    print("  Warns:  transactions.csv newer than transactions.csv.enc")
    return 0


def remove() -> int:
    hook_path = hooks_dir() / "pre-commit"
    if not hook_path.exists():
        print("No pre-commit hook to remove.")
        return 0
    if HOOK_MARKER not in hook_path.read_text(encoding="utf-8", errors="replace"):
        raise SystemExit(f"{hook_path} isn't ours — leaving it alone.")
    hook_path.unlink()
    print(f"Removed {hook_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="Uninstall the hook")
    args = parser.parse_args()
    return remove() if args.remove else install()


if __name__ == "__main__":
    sys.exit(main())
