#!/usr/bin/env python3
"""Clear executed cell outputs from the notebooks, keeping the code.

`notebook/pipeline_walkthrough.ipynb` is tracked in git, and it should be — the
code and the explanations are the point of it. Its *outputs* are a different
matter: run it and every printed frame is written back into the file, so a
committed notebook carries real transaction descriptions, counterparty names
and salary amounts in a file that .gitignore was never going to catch, because
the file itself genuinely belongs in the repo.

That is not hypothetical. Before this script existed, the committed notebook
held 17 lines of real bank descriptions.

So: run the notebook locally as much as you like, and clear it before
committing. The pre-commit hook from scripts/install_git_hooks.py refuses a
staged .ipynb that still has outputs, and points here.

Usage:
    python3 scripts/strip_notebook_outputs.py            # clear every notebook
    python3 scripts/strip_notebook_outputs.py --check    # exit 1 if any has outputs
    python3 scripts/strip_notebook_outputs.py a.ipynb    # clear specific files
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _notebooks(paths) -> list:
    if paths:
        return [Path(p) for p in paths]
    return sorted(p for p in REPO_ROOT.rglob("*.ipynb")
                  if ".ipynb_checkpoints" not in p.parts and ".venv" not in p.parts)


def _executed_cells(notebook: dict) -> int:
    return sum(1 for c in notebook.get("cells", [])
               if c.get("cell_type") == "code"
               and (c.get("outputs") or c.get("execution_count") is not None))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="Notebooks to clear (default: all)")
    parser.add_argument("--check", action="store_true",
                        help="Don't write; exit 1 if any notebook still has outputs")
    args = parser.parse_args()

    dirty = 0
    for path in _notebooks(args.paths):
        if not path.exists():
            print(f"{path}: not found", file=sys.stderr)
            return 2
        notebook = json.loads(path.read_text(encoding="utf-8"))
        count = _executed_cells(notebook)
        if not count:
            print(f"{path.relative_to(REPO_ROOT)}: already clean")
            continue
        dirty += 1
        if args.check:
            print(f"{path.relative_to(REPO_ROOT)}: {count} cell(s) still carry outputs",
                  file=sys.stderr)
            continue
        for cell in notebook["cells"]:
            if cell.get("cell_type") == "code":
                cell["outputs"] = []
                cell["execution_count"] = None
        # Trailing newline and indent=1 match what Jupyter itself writes, so
        # clearing a notebook doesn't show up as a whole-file diff.
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
        print(f"{path.relative_to(REPO_ROOT)}: cleared {count} cell(s)")

    if args.check and dirty:
        print("\nRun: python3 scripts/strip_notebook_outputs.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
