# Sample hand-off

This is the final message of a real run on the demo shop in `examples/demo-shop`. The commands and their output are
copied from the run. The plan it refers to is `001-use-decimal-for-money.md` in this folder.

**Request:** "Audit this repo and write plans for the top problems."

---

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
