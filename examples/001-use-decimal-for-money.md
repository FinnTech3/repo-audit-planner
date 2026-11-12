---
id: 001
title: Stop storing money as float in the demo shop
severity: high
effort: S
status: todo
category: correctness
confidence: confirmed
depends_on: []
base_commit: n/a
created: 2026-11-12
---

# 001: Stop storing money as float in the demo shop

## Goal

After this plan, `order_total` and `apply_tax` in `examples/demo-shop/shop/pricing.py` compute with `decimal.Decimal`. An order of 0.10 plus 0.20 totals exactly `Decimal("0.30")`, and `apply_tax(Decimal("10.00"), Decimal("0.0825"))` returns `Decimal("10.83")`.

## Evidence

- `examples/demo-shop/shop/pricing.py:9` `unit_price: float` - item prices are binary floats, which cannot hold most decimal amounts exactly.
- `examples/demo-shop/shop/pricing.py:14` `return sum(item.unit_price * item.quantity for item in items)` - the total is a float sum of float products.
- `examples/demo-shop/shop/pricing.py:18` `return round(total * (1 + rate), 2)` - tax is rounded with float `round`, so 10.825 becomes 10.82 instead of 10.83.
- `examples/demo-shop/shop/config.py:3` `TAX_RATE = 0.0825` - the tax rate is a float as well.
- `examples/demo-shop/shop/orders.py:10` `return {"subtotal": subtotal, "total": apply_tax(subtotal, TAX_RATE)}` - the unrounded float subtotal is handed back to callers.

Reproduce, run from the repo root before any change. It printed `0.30000000000000004` and then `10.82`:

```sh
cd examples/demo-shop && python -c "from shop.pricing import Item, order_total, apply_tax; print(order_total([Item('a', 0.1, 1), Item('b', 0.2, 1)])); print(apply_tax(10.0, 0.0825))"
```

## Context

- The demo shop is a plain Python package with no dependencies. Source is in `examples/demo-shop/shop/`, tests are in `examples/demo-shop/tests/` and run with pytest.
- Baseline, run before any change: `cd examples/demo-shop && python -m pytest -q` printed `3 passed`.
- Rounding rule this plan assumes: round half up to the cent. If the shop uses another rule, stop and report.
- Style to match: the existing small functions in `examples/demo-shop/shop/pricing.py`, with type hints and no comments.

## Scope

### In scope

- `examples/demo-shop/shop/pricing.py`: change the money types and the rounding.
- `examples/demo-shop/shop/config.py`: make `TAX_RATE` a `Decimal`.
- `examples/demo-shop/tests/test_demo_pricing.py`: move the tests to `Decimal` and add the two new cases.

### Out of scope

- `examples/demo-shop/shop/orders.py`: no edit is needed, and the discount feature in its comment at line 8 is a separate piece of work.
- Turning `Decimal` values into JSON or strings for any API. No caller does that today.
- Any file outside `examples/demo-shop/`.

## Steps

1. Replace the contents of `examples/demo-shop/tests/test_demo_pricing.py` with the version below. It moves the three existing tests to `Decimal` and adds the exactness and half-up cases.

   ```python
   from decimal import Decimal

   from shop.orders import checkout
   from shop.pricing import Item, apply_tax, order_total


   def test_order_total_multiplies_price_by_quantity():
       assert order_total([Item("pen", Decimal("2.50"), 2)]) == Decimal("5.00")


   def test_order_total_is_exact():
       items = [Item("a", Decimal("0.10"), 1), Item("b", Decimal("0.20"), 1)]
       assert order_total(items) == Decimal("0.30")


   def test_apply_tax_on_a_round_amount():
       assert apply_tax(Decimal("100.00"), Decimal("0.0825")) == Decimal("108.25")


   def test_apply_tax_rounds_half_up_to_the_cent():
       assert apply_tax(Decimal("10.00"), Decimal("0.0825")) == Decimal("10.83")


   def test_checkout_returns_subtotal_and_total():
       result = checkout([Item("pen", Decimal("2.50"), 2)])
       assert result["subtotal"] == Decimal("5.00")
       assert result["total"] == Decimal("5.41")
   ```

   Verify: `cd examples/demo-shop && python -m pytest -q` prints `2 failed, 3 passed`. The two failures are `test_apply_tax_rounds_half_up_to_the_cent` and `test_checkout_returns_subtotal_and_total`.

2. Replace the contents of `examples/demo-shop/shop/pricing.py` with:

   ```python
   """Order pricing."""

   from dataclasses import dataclass
   from decimal import ROUND_HALF_UP, Decimal

   CENT = Decimal("0.01")


   @dataclass
   class Item:
       sku: str
       unit_price: Decimal
       quantity: int


   def order_total(items: list[Item]) -> Decimal:
       return sum((item.unit_price * item.quantity for item in items), Decimal("0"))


   def apply_tax(total: Decimal, rate: Decimal) -> Decimal:
       return (total * (1 + rate)).quantize(CENT, rounding=ROUND_HALF_UP)
   ```

   Verify: `grep -n "float" examples/demo-shop/shop/pricing.py` prints nothing and exits 1.

3. In `examples/demo-shop/shop/config.py`, make this change. Lines that start with `-` are removed, lines that start with `+` are added, and every other line stays as it is:

   ```diff
    """Shop settings."""

   +from decimal import Decimal
   +
   -TAX_RATE = 0.0825
   +TAX_RATE = Decimal("0.0825")
   ```

   Verify: `cd examples/demo-shop && python -m pytest -q` prints `5 passed`.

## Acceptance criteria

- [ ] `cd examples/demo-shop && python -m pytest -q` exits 0 and prints `5 passed`.
- [ ] `grep -n "float" examples/demo-shop/shop/pricing.py examples/demo-shop/shop/config.py` prints nothing and exits 1.
- [ ] This command prints `0.30` and then `10.83`:
  `cd examples/demo-shop && python -c "from decimal import Decimal; from shop.pricing import Item, order_total, apply_tax; print(order_total([Item('a', Decimal('0.10'), 1), Item('b', Decimal('0.20'), 1)])); print(apply_tax(Decimal('10.00'), Decimal('0.0825')))"`
- [ ] `git diff --name-only` lists exactly three files: `examples/demo-shop/shop/config.py`, `examples/demo-shop/shop/pricing.py` and `examples/demo-shop/tests/test_demo_pricing.py`.

## Test commands

```sh
cd examples/demo-shop && python -m pytest -q
grep -rn "order_total\|apply_tax" --include=*.py examples/demo-shop
```

Expected: pytest exits 0 and prints `5 passed`. The grep lists matches only in `shop/orders.py`, `shop/pricing.py` and `tests/test_demo_pricing.py`.

## Halt conditions

Halt and report back, without improvising, if:

- A line cited in Evidence no longer holds the quoted code.
- The baseline prints anything other than `3 passed`.
- The grep in Test commands lists a caller in any file other than the three named there.
- A Verify line still differs from its expected output after you followed its step exactly twice.

## Risks and rollback

### Risks

- A caller that still passes `float` prices now gets a `TypeError` from `Decimal` times `float`. That failure is deliberate and loud. The grep in Test commands shows that no such caller exists in this package.
- `json.dumps` cannot encode `Decimal`. `checkout` is not serialised anywhere in this package, so nothing breaks today, but a future caller must convert the values first.

### Rollback

- Before committing: `git checkout -- examples/demo-shop`.
- After committing: `git revert <commit-hash>`.
