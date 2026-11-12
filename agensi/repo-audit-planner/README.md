# Repo audit planner

An agent skill that audits a codebase and writes ranked, self-contained implementation plans. A cheaper agent, or a person on their first day, can execute each plan without asking a question.

## What you get

- A folder of plan files, one issue per plan, ranked by impact against effort.
- Evidence you can check: every finding cites `file:line` and quotes the code. The checker opens the file and compares the quote, so an invented finding fails.
- Plans that cannot stay vague: missing sections, unfilled placeholders and hedges such as "as needed" are errors.
- A handoff that lists what was found, what was rejected and why, and proof that nothing outside the plans folder changed.

The skill never implements a change. The plans are the product.

## What it needs

- Python 3.10 or newer. Nothing to install and no network access.
- `git` is optional. With it the scripts honour `.gitignore`, report churn and detect drift.
- Permission for your agent to run commands in the repo and write files under the plans folder.

## How to use it

Ask your agent, for example:

- "Audit this repo and write plans for the top five problems."
- "Review `src/payments` and plan the fixes."
- "Prioritise our tech debt."
- "Refresh the plans folder."

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The workflow, the severity rubric and the plan standard |
| `scripts/repo_facts.py` | Facts about the repo: languages, tests, debt markers, big files, secret-like locations, churn |
| `scripts/check_plans.py` | Validates plans and compares each quote with the real file |
| `scripts/rank_plans.py` | Ranks plans by priority |
| `references/plan-template.md` | The plan template |
| `examples/001-use-decimal-for-money.md` | A finished plan that passes the checker |
| `examples/sample-handoff.md` | A real hand-off message from a run on the demo shop |
| `examples/demo-shop/` | The small project that plan was written for |
| `examples/sample-repo-facts.txt` | Real output of `repo_facts.py` on the demo shop |

## Limits

The scripts report facts and check form and evidence. Judging what matters is the agent's job, so plan quality follows the model you run it with. The checker cannot tell whether a fix is the right fix, only whether the plan is complete, concrete and backed by real code.
