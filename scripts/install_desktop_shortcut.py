#!/usr/bin/env python3
"""Put a double-clickable "Finance Dashboard" shortcut on the Desktop.

The shortcut is a **symlink** to scripts/Finance Dashboard.command, never a
copy. That distinction is the point: a copy would freeze today's launcher onto
the Desktop and quietly keep running the old one after the project changes,
which is exactly the "am I looking at the latest version?" problem the
shortcut is supposed to solve. A symlink always runs what's in the project
right now, and the server it starts sends no-cache headers so the browser
can't serve you a stale page either.

Usage:
    python3 scripts/install_desktop_shortcut.py            # install / repair
    python3 scripts/install_desktop_shortcut.py --remove   # take it off the Desktop
"""

import argparse
import os
import stat
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = REPO_ROOT / "scripts" / "Finance Dashboard.command"
SHORTCUT_NAME = "Finance Dashboard.command"


def desktop_dir() -> Path:
    desktop = Path.home() / "Desktop"
    if not desktop.is_dir():
        raise SystemExit(f"No Desktop folder at {desktop} — nothing to install into.")
    return desktop


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install() -> int:
    if not LAUNCHER.exists():
        raise SystemExit(f"Launcher missing: {LAUNCHER}")
    ensure_executable(LAUNCHER)

    shortcut = desktop_dir() / SHORTCUT_NAME

    if shortcut.is_symlink():
        current = os.readlink(shortcut)
        if Path(current).resolve() == LAUNCHER.resolve():
            print(f"Already installed and pointing at the right place:\n  {shortcut}")
            return 0
        shortcut.unlink()  # stale symlink from an older location — repoint it
    elif shortcut.exists():
        raise SystemExit(
            f"{shortcut} already exists and is a real file, not a shortcut.\n"
            f"Move or delete it first — refusing to overwrite something that isn't ours."
        )

    shortcut.symlink_to(LAUNCHER)
    print(f"Installed: {shortcut}\n  -> {LAUNCHER}")
    print("\nDouble-click it to start the dashboard. The first launch may show a macOS")
    print('prompt about running a downloaded script — choose Open. A Terminal window stays')
    print("open while the server runs; close it (or Ctrl-C) when you're done.")
    return 0


def remove() -> int:
    shortcut = desktop_dir() / SHORTCUT_NAME
    if shortcut.is_symlink():
        shortcut.unlink()
        print(f"Removed {shortcut}")
    elif shortcut.exists():
        raise SystemExit(f"{shortcut} is a real file, not our shortcut — leaving it alone.")
    else:
        print("Nothing to remove.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="Remove the Desktop shortcut")
    args = parser.parse_args()
    return remove() if args.remove else install()


if __name__ == "__main__":
    sys.exit(main())
