#!/usr/bin/env python3
"""Rank a folder of plans by priority. Standard library only, read-only, no network.

Usage:
    python3 rank_plans.py PLANS_DIR [--json]

priority = severity weight / effort weight
    severity: critical 20, high 8, medium 3, low 1      effort: XS 1, S 2, M 4, L 8, XL 16
Critical plans come first, then the rest by priority. A plan never appears before an unfinished
plan it depends on. Finished and dropped plans are listed last. Prints a Markdown table.
Exit codes: 0 ok, 1 no plans found, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SEVERITY = {"critical": 20, "high": 8, "medium": 3, "low": 1}
EFFORT = {"XS": 1, "S": 2, "M": 4, "L": 8, "XL": 16}
CLOSED = ("done", "dropped")
NAME = re.compile(r"^(\d{3,})-[a-z0-9][a-z0-9-]*\.md$")


def read_front(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").split("\n")
    except OSError:
        return {}
    if lines[0].strip() != "---":
        return {}
    end = next((i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---"), len(lines))
    front = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            front[key] = (value if key == "title" else re.sub(r"\s#.*$", "", value)).strip().strip("'\"")
    return front


def rank(plans_dir: Path) -> list[dict]:
    plans = []
    for path in sorted(plans_dir.glob("*.md")):
        match = NAME.match(path.name)
        if not match:
            continue
        front = read_front(path)
        severity, effort = front.get("severity", ""), front.get("effort", "")
        if severity not in SEVERITY or effort not in EFFORT:
            print(f"warning: {path.name}: severity or effort is not valid, so its priority is 0", file=sys.stderr)
        plans.append(
            {
                "id": match.group(1),
                "title": front.get("title", path.stem),
                "severity": severity,
                "effort": effort,
                "status": front.get("status", ""),
                "priority": round(SEVERITY.get(severity, 0) / EFFORT.get(effort, 16), 2),
                "depends_on": re.findall(r"\d{3,}", front.get("depends_on", "")),
            }
        )
    plans.sort(key=lambda p: (p["status"] in CLOSED, p["severity"] != "critical", -p["priority"], p["id"]))
    open_ids = {p["id"] for p in plans if p["status"] not in CLOSED}
    ordered: list[dict] = []
    waiting = plans[:]
    while waiting:
        placed = {p["id"] for p in ordered}
        ready = [p for p in waiting if all(d in placed or d not in open_ids for d in p["depends_on"])]
        nxt = ready[0] if ready else waiting[0]  # a dependency cycle: keep priority order
        ordered.append(nxt)
        waiting.remove(nxt)
    return ordered


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="replace")  # a title the console cannot show must not crash the run
    ap = argparse.ArgumentParser(description="Rank plans by priority.")
    ap.add_argument("plans_dir")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    if not Path(args.plans_dir).is_dir():
        print(f"error: not a directory: {args.plans_dir}", file=sys.stderr)
        return 2
    ordered = rank(Path(args.plans_dir))
    if args.json:
        print(json.dumps(ordered, indent=2))
    else:
        print("| Rank | Plan | Title | Severity | Effort | Priority | Status |")
        print("|---:|---|---|---|---|---:|---|")
        for i, p in enumerate(ordered, 1):
            cells = [i, p["id"], p["title"], p["severity"], p["effort"], f"{p['priority']:g}", p["status"]]
            print("| " + " | ".join(str(c) for c in cells) + " |")
    return 0 if ordered else 1


if __name__ == "__main__":
    sys.exit(main())
