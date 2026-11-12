#!/usr/bin/env python3
"""Validate implementation plans before they are handed to an executor. Standard library only.

Usage:
    python3 check_plans.py PLANS_DIR [--repo PATH] [--json]

Every plan file `NNN-slug.md` must have valid front matter, every required section, no
unfilled {{placeholder}}, no vague wording, and evidence written as `path:line` `quoted code`.
With --repo the script opens each cited file and fails the plan when the file is missing, the
line is past the end, the quote is absent, or the quote is not on that line. That is what stops
an invented finding. Write [REDACTED] in a quote in place of a secret value.

Read-only, no network. Exit codes: 0 all plans pass, 1 a plan has an error or no plans were
found, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SEVERITIES = ("critical", "high", "medium", "low")
EFFORTS = ("XS", "S", "M", "L", "XL")
STATUSES = ("todo", "in-progress", "blocked", "done", "dropped")
REQUIRED = ("Goal", "Evidence", "Context", "Scope", "Steps", "Acceptance criteria", "Test commands")
REQUIRED += ("Risks and rollback",)
CHECKED_FOR_VAGUE = ("goal", "scope", "steps", "acceptance criteria", "test commands")
VAGUE = (
    "as needed", "as appropriate", "as necessary", "if needed", "if necessary", "where appropriate",
    "and so on", "etc", "properly", "correctly handle", "works as expected", "should work", "good enough",
    "best practice", "best practices", "make it better", "clean up the code", "more readable",
    "more maintainable", "more robust", "reasonable", "consider", "maybe", "perhaps", "probably",
    "possibly", "try to", "ideally", "feel free", "you may want to", "you might want to", "tbd", "tbc",
)  # fmt: skip
NAME = re.compile(r"^(\d{3,})-[a-z0-9][a-z0-9-]*\.md$")
REF = re.compile(r"`([\w@+~./ -]+):(\d+)(?:-(\d+))?`(?:\s*[:\-–—]?\s*`([^`\n]{3,})`)?")
VAGUE_RE = re.compile(r"\b(" + "|".join(re.escape(v) for v in sorted(VAGUE, key=len, reverse=True)) + r")\b", re.I)
PLACEHOLDER = re.compile(r"(?<![$\w{])\{\{")
INLINE_CODE = re.compile(r"`[^`\n]*`")
STEP = re.compile(r"^\s{0,3}\d+[.)]\s+\S")
REDACTED = "[REDACTED]"
MAX_CITED_BYTES = 5_000_000


def squash(text: str) -> str:
    return " ".join(text.split())


def parse_front(lines: list[str]) -> dict[str, str]:
    """Read `key: value` lines. A trailing ` # comment` is dropped, except on the title."""
    front = {}
    for line in lines:
        if ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            front[key] = (value if key == "title" else re.sub(r"\s#.*$", "", value)).strip().strip("'\"")
    return front


class Plan:
    """A parsed plan: front matter, numbered lines with a fence flag, and its sections."""

    def __init__(self, text: str):
        # HTML comments are guidance for the author; blank them but keep the line numbers.
        text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
        raw = text.split("\n")
        self.front: dict[str, str] | None = None
        start = 0
        if raw[0].strip() == "---":
            end = next((i for i, ln in enumerate(raw[1:], 1) if ln.strip() == "---"), None)
            if end:
                self.front = parse_front(raw[1:end])
                start = end + 1
        self.lines: list[tuple[int, str, bool]] = []
        self.sections: dict[str, list[tuple[int, str, bool]]] = {}
        self.subs: dict[str, set[str]] = {}
        self.where: dict[str, int] = {}
        fence, current = None, None  # inside a code fence: (character, length, opening line number)
        for number, line in enumerate(raw[start:], start + 1):
            shape = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
            marker, ticks, rest = bool(shape), *(shape.groups() if shape else ("", ""))
            if marker and fence is None:
                fence = (ticks[0], len(ticks), number)
            elif marker and ticks[0] == fence[0] and len(ticks) >= fence[1] and not rest.strip():
                fence = None
            item = (number, line, fence is not None or marker)
            self.lines.append(item)
            if not item[2] and line.startswith("## "):
                current = line[3:].strip().rstrip(":").lower()
                self.sections[current], self.subs[current], self.where[current] = [], set(), number
            elif current:
                if not item[2] and line.startswith("### "):
                    self.subs[current].add(line[4:].strip().rstrip(":").lower())
                self.sections[current].append(item)
        self.unclosed = fence[2] if fence else None

    def prose(self, key: str) -> list[tuple[int, str]]:
        """Lines of a section outside code fences, with inline code removed."""
        return [(n, INLINE_CODE.sub(" ", text)) for n, text, fenced in self.sections.get(key, []) if not fenced]


def quote_matches(quote: str, window: str) -> bool:
    if not squash(quote.replace(REDACTED, "")):
        return False  # a quote that is only the marker proves nothing
    position = 0
    for part in (p.strip() for p in squash(quote).split(REDACTED)):
        found = window.find(part, position) if part else position
        if found < 0:
            return False
        position = found + len(part)
    return True


def reach(start: str, graph: dict[str, set[str]]) -> set[str]:
    """Every plan number that `start` depends on, directly or through other plans."""
    seen: set[str] = set()
    todo = [start]
    while todo:
        for dep in graph.get(todo.pop(), ()):
            if dep not in seen:
                seen.add(dep)
                todo.append(dep)
    return seen


def changed_since(repo: Path, commit: str) -> set[str] | None:
    """Paths under repo that differ between a commit and the working tree, or None when git cannot say.

    core.fsmonitor is switched off because a repo's own config can name a command for it, and
    this script must not run anything a repo supplies.
    """
    if not re.fullmatch(r"[0-9a-fA-F]{4,40}", commit):
        return None
    try:
        cmd = ["git", "-c", "core.fsmonitor=false", "-C", str(repo), "diff", "--name-only", "--relative", "-z", commit]
        done = subprocess.run(cmd, capture_output=True, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return {p for p in done.stdout.decode("utf-8", "replace").split("\0") if p}


def check_plan(path: Path, repo: Path | None, ids: dict[str, list[str]], graph: dict[str, set[str]]) -> list[dict]:
    out: list[dict] = []

    def add(level: str, code: str, message: str, line: int | None = None) -> None:
        out.append({"level": level, "line": line, "code": code, "message": message})

    try:
        plan = Plan(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError):
        add("error", "unreadable", "file is not readable UTF-8 text")
        return out

    front = plan.front or {}
    number = NAME.match(path.name).group(1)
    if plan.front is None:
        add("error", "front-matter", "missing front matter (id, title, severity, effort, status)", 1)
    else:
        if front.get("id") != number:
            add("error", "front-matter", f"id '{front.get('id', '')}' does not match the file number {number}", 1)
        if not front.get("title"):
            add("error", "front-matter", "title is empty", 1)
        for key, allowed in (("severity", SEVERITIES), ("effort", EFFORTS), ("status", STATUSES)):
            if front.get(key) not in allowed:
                add("error", "front-matter", f"{key} '{front.get(key, '')}' is not one of: {', '.join(allowed)}", 1)
        for dep in re.findall(r"[^\s,\[\]]+", front.get("depends_on", "")):
            if not re.fullmatch(r"\d{3,}", dep):
                add("error", "depends-on", f"depends_on entry '{dep}' is not a plan number such as 001", 1)
            elif dep == number or dep not in ids:
                add("error", "depends-on", f"depends_on names {dep}, which is this plan or does not exist", 1)
            elif number in reach(dep, graph):
                add("error", "depends-on", f"depends_on {dep} depends back on this plan: a cycle", 1)
    if len(ids.get(number, [])) > 1:
        add("error", "duplicate-number", f"number {number} is used by: {', '.join(sorted(ids[number]))}")

    for title in REQUIRED + ("Halt conditions",):
        key = title.lower()
        if key not in plan.sections:
            level = "warning" if title == "Halt conditions" else "error"
            add(level, "section-missing", f"missing section '## {title}'")
        elif not any(text.strip() for _, text, _ in plan.sections[key]):
            add("error", "section-empty", f"section '{title}' is empty", plan.where[key])
    for key, needed in (("scope", ("in scope", "out of scope")), ("risks and rollback", ("risks", "rollback"))):
        for sub in needed:
            if key in plan.sections and sub not in plan.subs[key]:
                add("error", "subsection-missing", f"'{key.capitalize()}' needs a '### {sub.capitalize()}' part")

    if plan.unclosed:
        add("error", "fence", "code fence opened here is never closed, so what follows is read as code", plan.unclosed)
    for line_no, text, fenced in plan.lines:
        found = None if fenced else PLACEHOLDER.search(INLINE_CODE.sub(" ", text))
        if found:
            add("error", "placeholder", "unfilled {{placeholder}}", line_no)
        elif not fenced and re.match(r"#\s+NNN\b", text):
            add("error", "placeholder", "the heading still says NNN: write the plan number", line_no)
    for key in CHECKED_FOR_VAGUE:
        for line_no, text in plan.prose(key):
            for hit in VAGUE_RE.finditer(squash(text)):
                add(
                    "error",
                    "vague",
                    f"vague wording '{hit.group(1)}': name the exact file, value or condition",
                    line_no,
                )

    steps = plan.sections.get("steps", [])
    starts = [i for i, (_, text, fenced) in enumerate(steps) if not fenced and STEP.match(text)]
    if "steps" in plan.sections and not starts:
        add("error", "steps", "Steps needs a numbered list", plan.where["steps"])
    for index, begin in enumerate(starts):
        block = steps[begin : starts[index + 1] if index + 1 < len(starts) else len(steps)]
        if not any(re.match(r"^\s*Verify:\s*\S", text) for _, text, fenced in block if not fenced):
            add(
                "error",
                "step-no-verify",
                "step has no 'Verify:' line with a command and its expected output",
                block[0][0],
            )
    if "acceptance criteria" in plan.sections and not any(
        re.match(r"^\s*[-*]\s+\[[ xX]\]\s+\S", text) for _, text in plan.prose("acceptance criteria")
    ):
        add(
            "error",
            "acceptance",
            "Acceptance criteria needs '- [ ]' checklist items",
            plan.where["acceptance criteria"],
        )
    tests = plan.sections.get("test commands")
    if tests is not None:
        if not any(fenced for _, _, fenced in tests):
            add("error", "tests", "Test commands needs a fenced block of exact commands", plan.where["test commands"])
        if not any(text.strip().startswith("Expected:") for _, text, fenced in tests if not fenced):
            add("warning", "tests", "Test commands should state 'Expected:' with the exit code and success line")

    refs = [(n, m) for n, text, fenced in plan.sections.get("evidence", []) if not fenced for m in REF.finditer(text)]
    if "evidence" in plan.sections and not refs:
        add("error", "evidence-missing", "Evidence needs at least one `path/to/file:LINE` `quoted code` bullet")
    if repo is None or front.get("status") in ("done", "dropped"):
        return out  # a finished plan's code has moved on by design

    cited: set[str] = set()
    cited_missing = False
    for line_no, m in refs:
        rel, first, last, quote = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2)), m.group(4)
        target = (repo / rel).resolve()
        if repo.resolve() not in target.parents:
            add("error", "evidence-unresolved", f"{rel}: path leaves the repo", line_no)
            continue
        if not target.is_file():
            hint = "" if cited_missing else " (--repo must be the folder the cited paths start from)"
            cited_missing = True
            add("error", "evidence-unresolved", f"{rel}: no such file in the repo{hint}", line_no)
            continue
        try:
            if target.stat().st_size > MAX_CITED_BYTES:
                add("error", "evidence-unresolved", f"{rel}: file is over 5 MB, cite a smaller one", line_no)
                continue
            lines = target.read_text(encoding="utf-8", errors="replace").split("\n")
        except OSError:
            add("error", "evidence-unresolved", f"{rel}: the file cannot be read", line_no)
            continue
        if lines[-1] == "":
            lines.pop()  # the empty piece after a final newline is not a line
        cited.add(rel)
        if first < 1 or last < first or last > len(lines):
            add("error", "evidence-unresolved", f"{rel}:{first}: the file has {len(lines)} lines", line_no)
        elif not quote:
            add(
                "error", "evidence-no-quote", f"{rel}:{first}: copy the exact code from that line in backticks", line_no
            )
        elif not quote_matches(quote, squash(" ".join(lines[first - 1 : last]))):
            add("error", "evidence-quote", f"quoted code is not at {rel}:{first}; the file may have changed", line_no)
    changed = changed_since(repo, front.get("base_commit", ""))
    if changed is None and cited and re.fullmatch(r"[0-9a-fA-F]{4,40}", front.get("base_commit", "")):
        add(
            "warning",
            "drift",
            f"base_commit {front['base_commit']} cannot be compared: not a git repo, or not in its history",
        )
    for rel in sorted(cited & (changed or set())):
        add("warning", "drift", f"{rel} changed since base_commit {front['base_commit']}; re-open the cited lines")
    return out


def check_dir(plans_dir: Path, repo: Path | None) -> dict:
    files = sorted(p for p in plans_dir.glob("*.md") if NAME.match(p.name))
    stray = sorted(
        p.name for p in plans_dir.glob("*.md") if not NAME.match(p.name) and p.stem not in ("README", "INDEX")
    )
    ids: dict[str, list[str]] = {}
    for p in files:
        ids.setdefault(NAME.match(p.name).group(1), []).append(p.name)
    graph: dict[str, set[str]] = {}
    for p in files:
        try:
            front = Plan(p.read_text(encoding="utf-8-sig")).front or {}
        except (OSError, UnicodeDecodeError):
            continue
        graph.setdefault(NAME.match(p.name).group(1), set()).update(re.findall(r"\d{3,}", front.get("depends_on", "")))
    plans = [{"file": p.name, "findings": check_plan(p, repo, ids, graph)} for p in files]
    for name in stray:
        plans.append({"file": name, "findings": [{"level": "error", "line": None, "code": "misnamed",
                                                  "message": "plan files are named NNN-slug.md"}]})  # fmt: skip
    errors = sum(f["level"] == "error" for p in plans for f in p["findings"])
    warnings = sum(f["level"] == "warning" for p in plans for f in p["findings"])
    return {"ok": bool(files) and errors == 0, "plans_found": len(files), "errors": errors, "warnings": warnings,
            "plans": plans}  # fmt: skip


def render(report: dict) -> str:
    out = []
    for plan in report["plans"]:
        failed = any(f["level"] == "error" for f in plan["findings"])
        out.append(f"{'FAIL' if failed else 'ok  '}  {plan['file']}")
        for f in sorted(plan["findings"], key=lambda f: f["line"] or 0):
            where = f"line {f['line']}" if f["line"] else "plan"
            out.append(f"  {f['level']:<7} {where:<9} [{f['code']}] {f['message']}")
    if not report["plans_found"]:
        out.append("no plan files (NNN-slug.md) found")
    out.append(f"{report['plans_found']} plan(s) checked: {report['errors']} error(s), {report['warnings']} warning(s)")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate implementation plans.")
    ap.add_argument("plans_dir")
    ap.add_argument("--repo", help="repo root: open every cited file and compare the quoted code")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    plans_dir, repo = Path(args.plans_dir), Path(args.repo) if args.repo else None
    for label, folder in (("PLANS_DIR", plans_dir), ("--repo", repo)):
        if folder is not None and not folder.is_dir():
            print(f"error: {label} is not an existing directory: {folder}", file=sys.stderr)
            return 2
    report = check_dir(plans_dir, repo)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
