#!/bin/bash
# Double-clickable launcher for the finance dashboard (macOS).
#
# The Desktop shortcut is a symlink to this file, not a copy — so it always
# runs the current version of the project, and there is never a stale duplicate
# of the launcher drifting out of date on the Desktop. Re-run
# scripts/install_desktop_shortcut.py only if you move the project folder.
#
# Prefers the project's .venv if one exists (the pipeline's dependencies live
# there), but the server itself only needs the standard library, so a plain
# python3 works fine for just viewing the dashboard.

set -euo pipefail

# Resolve symlinks to find the real project root — $0 is the Desktop symlink
# when launched from there. macOS `readlink` has no -f, hence python3.
SCRIPT_PATH="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$0")"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_PATH")")"

cd "$REPO_ROOT"

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

exec "$PYTHON" scripts/serve_dashboard.py "$@"
