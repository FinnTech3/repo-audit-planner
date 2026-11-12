#!/usr/bin/env python3
"""Repo facts for a code audit. Python 3.10+, standard library only.

Usage:
    python3 repo_facts.py [PATH] [--json]

Reports languages, test coverage by file count, debt markers, largest files, dependency
manifests, CI config, secret-like lines and git churn. Facts only, no judgement.

Safe on any repo: it only reads, makes no network calls, never follows symlinks, and caps
file count, file size and run time. For a secret-like line it prints the file, line and
kind, never the value. In a git repo it lists files with `git ls-files`, so ignored files
are skipped. Exit codes: 0 ok, 2 bad path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

MAX_FILES, MAX_BYTES, MAX_SECONDS, MAX_LOCATIONS = 20_000, 1_000_000, 20.0, 40
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target", "vendor"}
SKIP_DIRS |= {".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".next", "coverage", ".idea"}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby",
    ".php": "PHP", ".cs": "C#", ".c": "C", ".h": "C", ".cpp": "C++", ".hpp": "C++", ".swift": "Swift",
    ".scala": "Scala", ".sh": "Shell", ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".scss": "CSS",
    ".vue": "Vue", ".svelte": "Svelte", ".md": "Markdown", ".yml": "YAML", ".yaml": "YAML", ".json": "JSON",
    ".toml": "TOML",
}  # fmt: skip
NOT_CODE = {"Markdown", "YAML", "JSON", "TOML", "HTML", "CSS"}
MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "setup.py", "Pipfile", "go.mod", "Cargo.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "Gemfile", "composer.json",
}  # fmt: skip
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Pipfile.lock", "go.sum",
    "Cargo.lock", "Gemfile.lock", "composer.lock",
}  # fmt: skip
CI_PATHS = (".github/workflows/", ".gitlab-ci.yml", ".circleci/", "Jenkinsfile", "azure-pipelines.yml")
# Marker words and credential shapes are built from parts so this file does not flag itself.
MARKERS = re.compile(r"\b(" + "|".join(["TO" + "DO", "FIX" + "ME", "HA" + "CK", "X" + "XX"]) + r")\b")
SECRETS = [
    ("aws access key", re.compile("AK" + "IA[0-9A-Z]{16}")),
    ("private key", re.compile("-----BEGIN [A-Z ]*PRIVATE " + "KEY-----")),
    ("access token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{24,})")),
    (
        "hardcoded credential",
        re.compile(r"(?i)(pass" + r"word|passwd|api[_-]?key|secret|token)\w*\s*[:=]\s*['\"][^'\"\s{}<>$]{8,}['\"]"),
    ),
]
TEST_NAME = re.compile(r"(^test_.*\.py$|_test\.\w+$|\.(test|spec)\.\w+$|Tests?\.(java|cs|kt)$)")


# A repo's own config can name a command for core.fsmonitor, so every git call switches it off.
GIT = ["git", "-c", "core.fsmonitor=false"]


def list_files(root: Path) -> list[str]:
    """Paths relative to root. Uses git when it can, so .gitignore is honoured."""
    try:
        cmd = [*GIT, "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
        done = subprocess.run(cmd, capture_output=True, timeout=15, check=True)
        names = done.stdout.decode("utf-8", "replace").split("\0")
        return sorted(p for p in names if p and not SKIP_DIRS & set(p.replace("\\", "/").split("/")[:-1]))
    except (OSError, subprocess.SubprocessError):
        pass
    found = []
    for folder, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        found += [os.path.relpath(os.path.join(folder, n), root) for n in sorted(names)]
        if len(found) > MAX_FILES:
            break
    return found


def is_test(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return bool({"tests", "test", "__tests__", "spec"} & set(parts[:-1])) or bool(TEST_NAME.search(parts[-1]))


def churn(root: Path) -> list[dict]:
    """Files changed most often in the last six months of git history."""
    try:
        cmd = [*GIT, "-C", str(root), "log", "--since=6.months", "--name-only", "--format=", "--relative", "--", "."]
        done = subprocess.run(cmd, capture_output=True, timeout=15, check=True)
    except (OSError, subprocess.SubprocessError):
        return []
    counts = Counter(line for line in done.stdout.decode("utf-8", "replace").splitlines() if line)
    return [{"file": f, "commits": n} for f, n in counts.most_common(10)]


def scan(root: Path) -> dict:
    started, files = time.monotonic(), list_files(root)
    langs: dict[str, list[int]] = {}
    tests = {"test_files": 0, "source_files": 0, "test_lines": 0, "source_lines": 0}
    marker_counts: Counter = Counter()
    secret_total = 0
    markers, secrets, sized, manifests, lockfiles, ci = [], [], [], [], [], set()
    skipped = {"binary": 0, "oversized": 0, "unreadable": 0}
    truncated = len(files) > MAX_FILES
    for rel in files[:MAX_FILES]:
        if time.monotonic() - started > MAX_SECONDS:
            truncated = True
            break
        path, name = root / rel, os.path.basename(rel)
        posix = rel.replace("\\", "/")
        if name in MANIFESTS:
            manifests.append(posix)
        if name in LOCKFILES:
            lockfiles.append(posix)
        ci |= {c for c in CI_PATHS if posix.startswith(c)}
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if path.stat().st_size > MAX_BYTES:
                skipped["oversized"] += 1
                continue
            data = path.read_bytes()
        except OSError:
            skipped["unreadable"] += 1
            continue
        if b"\0" in data[:8192]:
            skipped["binary"] += 1
            continue
        text = data.decode("utf-8", "replace")
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        lang = LANGUAGES.get(os.path.splitext(name)[1].lower())
        if lang:
            entry = langs.setdefault(lang, [0, 0])
            entry[0] += 1
            entry[1] += lines
        code = bool(lang) and lang not in NOT_CODE
        if code:
            kind = "test" if is_test(posix) else "source"
            tests[f"{kind}_files"] += 1
            tests[f"{kind}_lines"] += lines
            sized.append((lines, posix))
        for number, line in enumerate(text.split("\n"), 1):
            kinds = [kind for kind, pattern in SECRETS if pattern.search(line)]
            secret_total += len(kinds)
            secrets += [{"file": posix, "line": number, "kind": k} for k in kinds][: MAX_LOCATIONS - len(secrets)]
            found = MARKERS.search(line) if code else None
            if found:
                marker_counts[found.group(1)] += 1
                if len(markers) < MAX_LOCATIONS:
                    markers.append({"file": posix, "line": number, "marker": found.group(1)})
    tests["ratio"] = round(tests["test_files"] / tests["source_files"], 2) if tests["source_files"] else None
    return {
        "root": str(root),
        "files_listed": len(files),
        "truncated": truncated,
        "languages": [
            {"language": k, "files": v[0], "lines": v[1]} for k, v in sorted(langs.items(), key=lambda kv: -kv[1][1])
        ],
        "tests": tests,
        "markers": {"counts": dict(marker_counts), "locations": markers},
        "largest": [{"file": f, "lines": n} for n, f in sorted(sized, reverse=True)[:10]],
        "manifests": manifests,
        "lockfiles": lockfiles,
        "ci": sorted(ci),
        "secrets": {"count": secret_total, "findings": secrets},
        "churn": churn(root),
        "skipped": skipped,
    }


def render(facts: dict) -> str:
    t = facts["tests"]
    out = [f"Repo facts for {facts['root']} ({facts['files_listed']} files listed)"]
    if facts["truncated"]:
        out.append("TRUNCATED: a file or time cap was hit, so the numbers below are partial.")
    out += ["", "Languages (files, lines):"]
    out += [f"  {x['language']:<12} {x['files']:>5} {x['lines']:>8}" for x in facts["languages"]] or ["  none"]
    out += [
        "",
        f"Tests: {t['test_files']} test files to {t['source_files']} source files "
        f"(ratio {'n/a' if t['ratio'] is None else t['ratio']}); "
        f"{t['test_lines']} test lines to {t['source_lines']} source lines",
        f"Debt markers: {facts['markers']['counts'] or 'none'}",
    ]
    out += [f"  {m['file']}:{m['line']}  {m['marker']}" for m in facts["markers"]["locations"]]
    if sum(facts["markers"]["counts"].values()) > len(facts["markers"]["locations"]):
        out.append(f"  (first {MAX_LOCATIONS} shown; the counts above are complete)")
    out += ["", "Largest code files (lines):"] + [f"  {x['lines']:>6}  {x['file']}" for x in facts["largest"]]
    out += [
        "",
        f"Manifests: {', '.join(facts['manifests']) or 'none'}",
        f"Lockfiles: {', '.join(facts['lockfiles']) or 'none'}",
        f"CI config: {', '.join(facts['ci']) or 'none'}",
        f"Secret-like lines: {facts['secrets']['count']} (location and kind only, the value is never shown)",
    ]
    out += [f"  {s['file']}:{s['line']}  {s['kind']}" for s in facts["secrets"]["findings"]]
    if facts["secrets"]["count"] > len(facts["secrets"]["findings"]):
        out.append(f"  (first {MAX_LOCATIONS} shown)")
    out += ["", "Most-changed files in six months (commits):"]
    out += [f"  {c['commits']:>4}  {c['file']}" for c in facts["churn"]] or ["  no git history available"]
    sk = facts["skipped"]
    out.append(f"\nSkipped: {sk['binary']} binary, {sk['oversized']} over 1 MB, {sk['unreadable']} unreadable")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(errors="replace")  # a file name the console cannot show must not crash the run
    ap = argparse.ArgumentParser(description="Repo facts for a code audit.")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    facts = scan(root.resolve())
    facts["root"] = args.path  # as typed, so the output reads the same wherever the repo lives
    print(json.dumps(facts, indent=2) if args.json else render(facts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
