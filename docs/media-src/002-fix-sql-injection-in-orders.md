---
id: 002
title: Parameterise the order lookup query
severity: critical
effort: XS
status: todo
category: security
confidence: confirmed
depends_on: []
base_commit: n/a
created: 2026-11-12
---

# 002: Parameterise the order lookup query

## Goal

Order lookups in `examples/demo-shop/shop/orders.py` use a bound parameter instead of an f-string, so a crafted order id cannot change the query.

## Evidence

- `examples/demo-shop/shop/orders.py:14` `cursor.execute(f"SELECT * FROM orders WHERE id = {order_id}")` - the order id is pasted into the SQL text.

## Context

- Baseline, run before any change: `cd examples/demo-shop && python -m pytest -q` printed `3 passed`.

## Scope

### In scope

- `examples/demo-shop/shop/orders.py`: change the query and handle other places as needed.

### Out of scope

- Everything outside `examples/demo-shop/`.

## Steps

1. In `examples/demo-shop/shop/orders.py`, replace the f-string with `cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))`.

## Acceptance criteria

- The query is parameterised.

## Test commands

```sh
cd examples/demo-shop && python -m pytest -q
```

## Risks and rollback

### Risks

- A caller might pass a non-string id.

### Rollback

- `git revert <commit-hash>`.
