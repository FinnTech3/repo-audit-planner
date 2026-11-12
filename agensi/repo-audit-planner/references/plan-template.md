---
id: NNN
title: {{short title in the imperative}}
severity: {{critical | high | medium | low}}
effort: {{XS | S | M | L | XL}}
status: todo
category: {{correctness | security | performance | tests | maintainability | dependencies | delivery | docs}}
confidence: likely
depends_on: []
base_commit: {{output of git rev-parse --short HEAD, or n/a}}
created: {{YYYY-MM-DD}}
---

# NNN: {{short title in the imperative}}

<!--
  Write for an executor that never saw the audit: a smaller model or a person on their first
  day in this repo. Everything it needs is in this file. Replace every {{placeholder}} and both NNN, then run
  the plan checker (`check_plans.py`) with `plans --repo .`. Comments like this one are ignored by the checker.
-->

## Goal

{{One or two sentences. State the end state a reader can observe, not the activity.}}

## Evidence

<!-- One bullet per fact: `path:line`, then the exact code in backticks, then what it shows. -->

- {{`path/to/file.ext:LINE` `exact code copied from that line` - what this line shows}}

Reproduce: {{a command that shows the problem, and the output you saw when you ran it}}

## Context

{{Repo conventions, one exemplar file to imitate, and the baseline test command with its output.}}

## Scope

### In scope

- {{files and behaviour this plan may change}}

### Out of scope

- {{things the executor must not touch, even when tempting}}

## Steps

1. {{Edit `path/to/file.ext`: say exactly what to change, with the new code if it is short.}}
   Verify: {{command, and the output that proves the step worked}}

## Acceptance criteria

- [ ] {{a check a machine can decide: a command, an exit code or an exact output line}}

## Test commands

```sh
{{exact command, runnable from the repo root}}
```

Expected: {{exit code, and the line the command prints on success}}

## Halt conditions

Halt and report back, without improvising, if:

- {{a cited line no longer matches the quoted code}}
- {{a Verify command fails twice after following its step exactly}}

## Risks and rollback

### Risks

- {{what could break, and who would notice}}

### Rollback

- {{the exact command or steps that undo this change, for example `git revert <commit>`}}
