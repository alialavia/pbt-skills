"""
A small e-commerce pricing engine.

Calculates the total for a shopping cart given:
  - line items (unit price * quantity)
  - an optional percentage discount
  - sales tax
  - shipping (free above a configurable threshold)

This is intentionally small so you can hold the whole thing in your head,
but it's the kind of code that mis-charging customers by even a penny
across millions of orders becomes a real business problem.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import List


CENTS = Decimal("0.01")


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineItem:
    name: str
    unit_price: Decimal
    quantity: int


def line_total(item: LineItem) -> Decimal:
    return _round_money(item.unit_price * item.quantity)


def subtotal(items: List[LineItem]) -> Decimal:
    return _round_money(sum((line_total(i) for i in items), Decimal("0")))


def apply_percentage_discount(amount: Decimal, percent: Decimal) -> Decimal:
    """
    Apply a percentage discount (0-100) to an amount.
    A 100% discount makes the total zero; the result is never negative.
    """
    if percent < 0 or percent > 100:
        raise ValueError(f"Discount percent must be in [0, 100], got {percent}")
    if amount < 0:
        raise ValueError(f"Amount must be non-negative, got {amount}")
    discount = amount * percent / Decimal("100")
    return _round_money(amount - discount)


def calculate_shipping(
    discounted_subtotal: Decimal,
    free_shipping_threshold: Decimal = Decimal("50.00"),
    flat_rate: Decimal = Decimal("5.99"),
) -> Decimal:
    """Flat-rate shipping, free when the (post-discount) subtotal meets the threshold."""
    if discounted_subtotal > free_shipping_threshold:
        return Decimal("0.00")
    return flat_rate


def calculate_tax(taxable_amount: Decimal, tax_rate_percent: Decimal) -> Decimal:
    """Compute sales tax. tax_rate_percent is e.g. Decimal('8.5') for 8.5%."""
    if tax_rate_percent < 0:
        raise ValueError(f"Tax rate must be non-negative, got {tax_rate_percent}")
    return _round_money(taxable_amount * tax_rate_percent / Decimal("100"))


def calculate_order_total(
    items: List[LineItem],
    discount_percent: Decimal = Decimal("0"),
    tax_rate_percent: Decimal = Decimal("0"),
) -> Decimal:
    """
    End-to-end cart total:
      subtotal -> apply discount -> compute shipping -> compute tax -> sum.
    Tax is applied to the discounted subtotal (not shipping), which matches
    a common US sales-tax model.
    """
    sub = subtotal(items)
    discounted = apply_percentage_discount(sub, discount_percent)
    shipping = calculate_shipping(discounted)
    tax = calculate_tax(discounted, tax_rate_percent)
    return _round_money(discounted + shipping + tax)
