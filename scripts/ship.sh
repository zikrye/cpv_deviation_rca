#!/usr/bin/env bash
#
# One-command deploy: test -> commit -> push to main.
#
# Pushing to main auto-refreshes the public Streamlit Community Cloud app.
# The public link never changes — only the content behind it updates, so a
# recruiter with the link will see the new version after the redeploy finishes.
#
#   ./scripts/ship.sh "short commit message describing the change"
#
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "usage: ./scripts/ship.sh \"commit message\"" >&2
  exit 1
fi

# Always run from the repo root, regardless of where the script is called from.
cd "$(dirname "$0")/.."

echo "▶ Running tests…"
.venv/bin/python -m pytest -q

echo
echo "▶ Changes to be committed:"
git status --short
if [ -z "$(git status --porcelain)" ]; then
  echo "  (nothing changed — already up to date)"
  exit 0
fi

git add -A
git commit -m "$1"
git push origin main

echo
echo "✅ Pushed to main. Streamlit Cloud will redeploy in ~1–2 minutes."
echo "   Then hard-refresh the public link (Cmd+Shift+R)."
echo
echo "   NOTE: if this change added/renamed an import or touched requirements.txt,"
echo "   reboot the app once to clear cached modules:"
echo "     Manage app  →  ⋮  →  Reboot app   (not 'Rerun')"
