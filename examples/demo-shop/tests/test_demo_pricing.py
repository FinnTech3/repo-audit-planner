"""Tests for the demo shop pricing."""

from shop.orders import checkout
from shop.pricing import Item, apply_tax, order_total


def test_order_total_multiplies_price_by_quantity():
    assert order_total([Item("pen", 2.5, 2)]) == 5.0


def test_apply_tax_on_a_round_amount():
    assert apply_tax(100.0, 0.0825) == 108.25


def test_checkout_returns_subtotal_and_total():
    result = checkout([Item("pen", 2.5, 2)])
    assert result["subtotal"] == 5.0
    assert result["total"] == 5.41
