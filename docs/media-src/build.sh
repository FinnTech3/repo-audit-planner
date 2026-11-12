#!/usr/bin/env bash
# Rebuilds docs/demo.gif, docs/demo.mp4 and the PNGs from real runs of the scripts in this repo.
# Needs: python3, ffmpeg, Pillow, node, and Playwright (set PLAYWRIGHT_DIR to a folder that has it in node_modules).
# Nothing in the images is typed by hand: record.py runs the commands and keeps what they print.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# A clean folder shaped like the repo: scripts, the demo shop, one good plan and one bad draft.
mkdir -p "$work/plans" "$work/drafts"
cp "$root"/agensi/repo-audit-planner/scripts/*.py "$work/"
cp -r "$root/examples" "$work/examples"
find "$work/examples" -name __pycache__ -prune -exec rm -rf {} +
mv "$work/examples/001-use-decimal-for-money.md" "$work/plans/"
cp "$here"/002-*.md "$work/drafts/"

sed "s|@WORK@|$work|" "$here/demo.json" > "$work/demo.spec.json"
python3 "$here/record.py" "$work/demo.spec.json" "$work/demo.cast.json"
node "$here/termcast.mjs" "$work/demo.cast.json" "$root/docs/demo.gif" "$root/docs/demo.mp4"
node "$here/termcast.mjs" "$work/demo.cast.json" "$work/rejected.png" --still

WORK="$work" ROOT="$root" node "$here/media.mjs"
python3 "$here/finish.py" "$work" "$root"
