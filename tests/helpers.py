"""Shared fixtures for the script tests."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

HAS_GIT = shutil.which("git") is not None
needs_git = pytest.mark.skipif(not HAS_GIT, reason="git is not installed")
NAME = "001-cache-the-parsed-config.md"

# Marker words and fake credentials are built from parts so this file is not flagged in a scan.
TODO = "TO" + "DO"
FIXME = "FIX" + "ME"
AWS_KEY = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
SECRET_VALUE = "q7r8s9t0u1v2w3x4"


def write(root: Path, rel: str, content: str | bytes = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="\n")
    return path


def git(cwd: Path, *args: str) -> str:
    cmd = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args]
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def commit_all(path: Path, message: str = "change") -> str:
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", message)
    return git(path, "rev-parse", "--short", "HEAD")


APP_PY = 'import json\nPATH = "cfg.json"\n\n\ndef load_config():\n    data = json.load(open(PATH))\n    return data\n'
# `data = json.load(open(PATH))` is line 6 of APP_PY.

GOOD_PLAN = """\
---
id: 001
title: Cache the parsed config
severity: high
effort: S
status: todo
category: performance
confidence: confirmed
depends_on: []
base_commit: abc1234
created: 2026-11-12
---

# 001: Cache the parsed config

## Goal

`load_config` parses the file once per process instead of once per call.

## Context

Conventions: plain functions, no classes. Baseline: `python -m pytest -q` passes.

## Evidence

- `src/app.py:6` `data = json.load(open(PATH))` - the file is opened and parsed on every call.

Reproduce: call `load_config()` twice and watch `open` run twice.

## Scope

### In scope

- `src/app.py`

### Out of scope

- `src/other.py`

## Steps

1. Edit `src/app.py`: wrap `load_config` with `functools.lru_cache(maxsize=1)`.
   Verify: `pytest -q` prints `2 passed`.

## Acceptance criteria

- [ ] `pytest -q` exits 0.

## Test commands

```sh
pytest -q
```

Expected: exit code 0 and `2 passed`.

## Halt conditions

Halt and report back if `src/app.py` no longer matches the quoted code.

## Risks and rollback

### Risks

- Callers that mutate the returned dict would now share it.

### Rollback

- `git revert <commit>`.
"""


def with_replacement(text: str, old: str, new: str) -> str:
    assert old in text, f"{old!r} not in text"
    return text.replace(old, new, 1)


def without_section(text: str, heading: str) -> str:
    """Remove the '## heading' section (up to the next '## ' heading)."""
    pattern = rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)"
    result, count = re.subn(pattern, "", text, flags=re.S | re.M)
    assert count == 1, f"section {heading!r} not found"
    return result
