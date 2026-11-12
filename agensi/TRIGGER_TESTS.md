# Trigger tests: Repo Audit Planner

Agensi's pre-publish rule: the skill should trigger on 5 of 5 relevant prompts and 0 of 5 unrelated ones. If it
triggers on fewer than 4 relevant prompts, the description is too narrow. If it triggers on more than 1 unrelated
prompt, it is too broad.

Status: **not yet run in an agent.** Run each prompt in a fresh session with the skill installed, tick the box when
the result is right, and record the agent and date. Run again after a model update.

## Should trigger

- [ ] Audit this repo and write plans for the top problems
- [ ] Review the codebase and plan the fixes so a cheaper model can do them
- [ ] Prioritise our tech debt
- [ ] Refresh the plans folder, some are probably stale
- [ ] Spec the fix for this so another agent can implement it

## Should not trigger

- [ ] Fix the failing test in this repo
- [ ] Review this pull request
- [ ] Explain what this function does
- [ ] Write a README for this project
- [ ] Rename the variable foo to bar everywhere

## Record

| Agent | Date | Relevant (of 5) | Unrelated that triggered (of 5) |
|---|---|---|---|
