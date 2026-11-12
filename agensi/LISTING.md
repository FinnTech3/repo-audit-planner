# Agensi listing copy

Paste these into the submit form at agensi.io/dashboard/submit. Upload `dist/repo-audit-planner.zip`
(build it with `python3 tools/agensi_build.py agensi/repo-audit-planner --with examples`, which also checks this
file against Agensi's field limits). Logo and screenshots are in `agensi/media/`.

| Field | Value |
|---|---|
| Title | Repo Audit Planner: Evidence-Checked Fix Plans |
| Categories | Code Quality & Review; Technical Documentation; Product Management |
| Suggested price | $12 one-time |
| Tags | code-audit, tech-debt, planning, code-quality, refactoring |
| Compatibility note | Requires Python 3.10+ (git optional). No packages, no network access. |
| Permissions | Terminal (runs three Python scripts from temporary files); reads files in the repo; writes files under the plans folder only. No network access, no environment variables. |
| Docs link | https://github.com/FinnTech3/repo-audit-planner |

## Summary

Audit any repo and get ranked, evidence-checked work orders that a cheaper agent can execute without asking questions.

## Description

Use your best model where judgement counts, and a cheap one for the typing.

This skill makes your agent audit a codebase and write a folder of implementation plans. Each plan is a work order:
the goal, the evidence, the exact steps with a verify command after each one, acceptance criteria, test commands,
halt conditions and a rollback. A smaller model, or a new team member, can carry it out without asking anything.

**How it works.** Your agent gathers facts with a bundled script (languages, tests, debt markers, largest files,
manifests, CI, secret-like locations, churn), hunts for problems, tries to disprove each one, ranks the survivors
by severity against effort, and writes one plan per issue. A second script then validates every plan: it opens the
files the plan cites and compares the quoted code with the real line. A third script ranks the plans.

**What makes it different**

- No invented findings: every finding cites `file:line` and quotes the code. If the code is not there, the plan fails.
- No vague plans: missing sections, unfilled placeholders and hedges such as "as needed" are errors.
- Ranked by value, with dependencies respected.
- It never touches your code. The skill declines to implement. It writes only under the plans folder and shows
  `git status` to prove it.
- Safe on any repo: the scripts only read, make no network calls and never print a secret value.

**Where it stops.** The scripts check form and evidence. They cannot tell whether a fix is the right fix, so plan
quality follows the model you run. Secret detection is pattern-based and finds common shapes, not every secret.

## See it in action

**Request:** "Audit this repo and write plans for the top problems."

**Result:**

**1. Scope.** Covered: the whole repo, 5 files, 54 lines of Python (`repo_facts.py`: not truncated, no binary or
oversized files). Not covered: nothing was skipped. The repo has no dependencies, no CI config and no lockfile, so
there was nothing to audit there.

**2. Ranked plans.**

| Rank | Plan | Title | Severity | Effort | Priority | Status |
|---:|---|---|---|---|---:|---|
| 1 | 001 | Stop storing money as float in the demo shop | high | S | 4 | todo |

Recommended order: just `001`. It computes totals and tax with binary floats, so `0.1 + 0.2` totals
`0.30000000000000004` and a tax of 10.825 rounds to `10.82` instead of `10.83`. That is wrong money on every order.

**3. Rejected candidates.**

- `shop/orders.py:8` has a note about discount codes. It is a feature someone wants, not a defect, so it is not a finding.
- One test file for four source files (ratio 0.25). The three tests pass and cover pricing and checkout. I found no
  untested behaviour that is wrong, so "add more tests" would be generic advice, not a finding.
- No CI and no lockfile. The project is a small fixture with no dependencies, so there is nothing to pin or gate.

**4. Baseline.** From the repo root:

```sh
cd examples/demo-shop && python -m pytest -q
```

Printed `3 passed in 0.01s`. The plan checker printed:

```text
ok    001-use-decimal-for-money.md
1 plan(s) checked: 0 error(s), 0 warning(s)
```

**5. Nothing else changed.** `git status --short` at the start printed nothing. At the end it printed:

```text
?? plans/
```

**6. How to run the plan.**

> Implement `plans/001-use-decimal-for-money.md`. Follow it exactly. Run each Verify line and compare with the
> expected output. Halt and report at any halt condition. Do not touch files outside the plan's scope.

I did not implement anything. To change code, hand that instruction to an executor.

The plan the run produced (`001-use-decimal-for-money.md`, 7 KB, passes the checker) is in `examples/`.

**What the checker does with an invented finding.** This is a separate run of the same checker. I wrote a bad
draft, `002-fix-sql-injection-in-orders.md`, that claims a SQL injection at `shop/orders.py:14`. The demo shop has no
database and `orders.py` has 10 lines. From the repo root:

```sh
python3 check_plans.py plans --repo .
```

```text
ok    001-use-decimal-for-money.md
FAIL  002-fix-sql-injection-in-orders.md
  warning plan      [section-missing] missing section '## Halt conditions'
  warning plan      [tests] Test commands should state 'Expected:' with the exit code and success line
  error   line 22   [evidence-unresolved] examples/demo-shop/shop/orders.py:14: the file has 10 lines
  error   line 32   [vague] vague wording 'as needed': name the exact file, value or condition
  error   line 40   [step-no-verify] step has no 'Verify:' line with a command and its expected output
  error   line 42   [acceptance] Acceptance criteria needs '- [ ]' checklist items
2 plan(s) checked: 4 error(s), 2 warning(s)
```

Exit code 1. The draft never reaches an executor. The draft is in the GitHub repo under `docs/media-src/`.

## Limitations

- The checker verifies that a plan is complete, concrete and backed by real code. It cannot judge whether the plan is the right fix.
- Reads up to 20,000 files of up to 1 MB each and stops after 20 seconds. It says when it truncated.
- Secret detection is pattern-based.
- Needs Python 3.10 or newer to run the scripts. Without it the skill still audits, but cannot validate.

## FAQ

**Will it change my code?** No. It refuses to implement and writes only under the plans folder.

**Do I need git?** No, but with it the scripts honour `.gitignore`, report churn and detect plans gone stale.

**Which model should run the plans?** Any cheaper model or a person. The plans are written so nobody needs to ask.

**What if a plan goes stale?** Ask your agent to refresh the plans folder. The checker flags files changed since each plan's base commit.

**Does it send my code anywhere?** No. The scripts make no network calls.

## Use cases

- Audit a repo and get a ranked backlog of fix plans
- Hand precise work orders to a cheaper model or a junior developer
- Refresh an old plans folder and catch plans that have gone stale
