"""Order pricing."""

from dataclasses import dataclass


@dataclass
class Item:
    sku: str
    unit_price: float
    quantity: int


def order_total(items: list[Item]) -> float:
    return sum(item.unit_price * item.quantity for item in items)


def apply_tax(total: float, rate: float) -> float:
    return round(total * (1 + rate), 2)
