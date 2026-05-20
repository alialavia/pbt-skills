"""
PROPERTY-BASED TESTS for the pricing engine.

The example-based suite in tests/eb/test_pricing_examples.py picks a handful
of inputs that a human thought were worth checking. These tests instead
declare *invariants* — statements that should hold for ANY input — and let
Hypothesis hunt for counterexamples.

Each property below maps to a piece of business logic that would lose money
or anger customers if it broke. Compare the line count to the example suite:
fewer tests, much stronger coverage, and Hypothesis will hit edge cases
(empty carts, free-shipping threshold, rounding boundaries, 0%/100% discount)
without anyone having to remember to write them down.
"""
from decimal import Decimal

import pytest
from hypothesis import assume, example, given, settings, strategies as st

from src.pricing import (
    CENTS,
    LineItem,
    apply_percentage_discount,
    calculate_order_total,
    calculate_shipping,
    calculate_tax,
    line_total,
    subtotal,
)


# ---------- strategies ----------

# Realistic prices, quantities, percentages. Kept tight enough that the
# tests stay fast and the inputs stay believable.
money = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("10000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
quantities = st.integers(min_value=0, max_value=100)
percents = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
line_items = st.builds(LineItem, name=st.text(max_size=20), unit_price=money, quantity=quantities)
carts = st.lists(line_items, max_size=20)


def _is_money(x: Decimal) -> bool:
    """A Decimal is 'money' if it has at most 2 places after the point."""
    return x == x.quantize(CENTS)


# ---------- line_total / subtotal ----------

@given(line_items)
def test_line_total_is_non_negative_and_money(item):
    """A line total is always a non-negative amount, rounded to cents."""
    total = line_total(item)
    assert total >= 0
    assert _is_money(total)


@given(unit_price=money, q=quantities)
def test_line_total_zero_quantity_is_zero(unit_price, q):
    """An item with quantity zero contributes nothing, regardless of price."""
    assert line_total(LineItem("x", unit_price, 0)) == Decimal("0.00")


@given(carts)
@example([])
def test_subtotal_non_negative_and_money(items):
    """A cart's subtotal is never negative and always a clean money amount."""
    sub = subtotal(items)
    assert sub >= 0
    assert _is_money(sub)


@given(carts)
def test_subtotal_is_sum_of_line_totals(items):
    """Subtotal == sum(line_total) (modulo the engine's rounding step)."""
    expected = sum((line_total(i) for i in items), Decimal("0")).quantize(CENTS)
    assert subtotal(items) == expected


@given(carts)
def test_subtotal_independent_of_order(items):
    """Reordering the cart never changes what the customer is charged."""
    assert subtotal(items) == subtotal(list(reversed(items)))


# ---------- apply_percentage_discount ----------

@given(amount=money, percent=percents)
def test_discount_result_in_range(amount, percent):
    """A discount can only lower the price, and never below zero."""
    result = apply_percentage_discount(amount, percent)
    assert Decimal("0") <= result <= amount


@given(amount=money)
@example(amount=Decimal("0"))
def test_zero_percent_discount_is_identity(amount):
    """0% off leaves the amount unchanged."""
    assert apply_percentage_discount(amount, Decimal("0")) == amount.quantize(CENTS)


@given(amount=money)
def test_full_discount_zeroes_the_amount(amount):
    """100% off always produces zero — never a stray cent."""
    assert apply_percentage_discount(amount, Decimal("100")) == Decimal("0.00")


@given(amount=money, p1=percents, p2=percents)
def test_discount_is_monotonic_in_percent(amount, p1, p2):
    """A larger discount percent never costs the customer more."""
    assume(p1 <= p2)
    assert apply_percentage_discount(amount, p1) >= apply_percentage_discount(amount, p2)


@given(amount=money, percent=st.decimals(min_value=Decimal("-100"), max_value=Decimal("-0.01"), places=2))
def test_negative_discount_rejected(amount, percent):
    with pytest.raises(ValueError):
        apply_percentage_discount(amount, percent)


@given(amount=money, percent=st.decimals(min_value=Decimal("100.01"), max_value=Decimal("1000"), places=2))
def test_over_hundred_percent_discount_rejected(amount, percent):
    with pytest.raises(ValueError):
        apply_percentage_discount(amount, percent)


# ---------- calculate_shipping ----------

@given(amount=money)
def test_shipping_is_zero_or_flat_rate(amount):
    """Shipping is always either free or exactly the flat rate."""
    s = calculate_shipping(amount)
    assert s in (Decimal("0.00"), Decimal("5.99"))


@given(amount=st.decimals(min_value=Decimal("0"), max_value=Decimal("49.99"), places=2))
def test_shipping_charged_below_threshold(amount):
    """Below the threshold, the customer pays the flat rate."""
    assert calculate_shipping(amount) == Decimal("5.99")


# The docstring on calculate_shipping says shipping is free 'when the subtotal
# MEETS the threshold' — i.e. at or above $50.00. The example suite in
# tests/eb explicitly notes it never tests the $50.00 boundary itself.
# Hypothesis will pick that exact value within seconds while sampling
# uniformly from this range, finding the off-by-one (>= vs >) that the
# example suite cannot see.
@given(amount=st.decimals(min_value=Decimal("50.00"), max_value=Decimal("10000"), places=2))
@example(amount=Decimal("50.00"))  # the boundary, made explicit for the demo
def test_shipping_free_at_or_above_threshold(amount):
    """If subtotal meets or exceeds the threshold, shipping must be free."""
    assert calculate_shipping(amount) == Decimal("0.00")


# ---------- calculate_tax ----------

@given(amount=money, rate=percents)
def test_tax_non_negative_and_money(amount, rate):
    tax = calculate_tax(amount, rate)
    assert tax >= 0
    assert _is_money(tax)


@given(amount=money)
def test_zero_tax_rate_yields_zero(amount):
    assert calculate_tax(amount, Decimal("0")) == Decimal("0.00")


@given(amount=money, r1=percents, r2=percents)
def test_tax_monotonic_in_rate(amount, r1, r2):
    """A higher tax rate never charges the customer less."""
    assume(r1 <= r2)
    assert calculate_tax(amount, r1) <= calculate_tax(amount, r2)


@given(amount=money, rate=st.decimals(min_value=Decimal("-100"), max_value=Decimal("-0.01"), places=2))
def test_negative_tax_rate_rejected(amount, rate):
    with pytest.raises(ValueError):
        calculate_tax(amount, rate)


# ---------- calculate_order_total ----------

@given(items=carts, discount=percents, tax=percents)
@example(items=[], discount=Decimal("0"), tax=Decimal("0"))
@example(items=[LineItem("x", Decimal("50.00"), 1)], discount=Decimal("0"), tax=Decimal("0"))
def test_order_total_non_negative_and_money(items, discount, tax):
    """No customer is ever charged a negative or sub-cent amount."""
    total = calculate_order_total(items, discount_percent=discount, tax_rate_percent=tax)
    assert total >= 0
    assert _is_money(total)


@given(items=carts, tax=percents)
def test_full_discount_leaves_only_shipping(items, tax):
    """
    A 100% discount zeroes the goods. Tax is applied to the discounted
    subtotal (zero), so the customer should only ever pay shipping.
    """
    total = calculate_order_total(items, discount_percent=Decimal("100"), tax_rate_percent=tax)
    assert total in (Decimal("0.00"), Decimal("5.99"))


@given(items=carts, d1=percents, d2=percents, tax=percents)
def test_order_total_monotonic_in_discount(items, d1, d2, tax):
    """
    A bigger discount never makes the order more expensive.
    (Note: this can be subtle around the shipping threshold — a deeper
    discount could push the cart below the free-shipping cutoff. The
    property still holds because shipping is added AFTER the discount,
    so a customer paying less for goods + flat shipping is still paying
    no more than someone with a smaller discount.)
    """
    assume(d1 <= d2)
    t1 = calculate_order_total(items, discount_percent=d1, tax_rate_percent=tax)
    t2 = calculate_order_total(items, discount_percent=d2, tax_rate_percent=tax)
    assert t1 >= t2
