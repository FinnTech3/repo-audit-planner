"""Checkout."""

from .config import TAX_RATE
from .pricing import Item, apply_tax, order_total


def checkout(items: list[Item]) -> dict:
    # TODO: apply discount codes before tax
    subtotal = order_total(items)
    return {"subtotal": subtotal, "total": apply_tax(subtotal, TAX_RATE)}
