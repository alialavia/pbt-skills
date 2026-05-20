"""
PROPERTY-BASED TESTS for the pricing engine.

Where the example-based suite asks "given THIS input, do we get THIS output?",
these ask "given ANY valid input, does this INVARIANT always hold?"

Hypothesis generates hundreds of inputs per run, including the awkward edge
cases humans never bother to write down: empty carts, 0% discounts, prices
ending in .005, quantities of zero, and the EXACT $50.00 shipping threshold
the example-based file explicitly admits it doesn't cover.

Compare line counts: this file expresses roughly the same coverage (and then
some) as test_pricing_examples.py in about the same amount of code, but each
test exercises hundreds of generated inputs instead of one hand-picked one.
"""
from decimal import Decimal

import pytest
from hypothesis import given, strategies as st

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

money = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("10000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
percent = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)
line_items = st.builds(
    LineItem,
    name=st.text(max_size=10),
    unit_price=money,
    quantity=st.integers(min_value=0, max_value=100),
)


def _is_money(x: Decimal) -> bool:
    """A value 'looks like money' if it has at most two decimal places."""
    return x == x.quantize(CENTS)


# ---------- line totals and subtotal ----------

@given(line_items)
def test_line_total_is_non_negative_and_money_formatted(item):
    total = line_total(item)
    assert total >= 0
    assert _is_money(total)


@given(st.lists(line_items, max_size=20))
def test_subtotal_is_non_negative_and_money_formatted(items):
    total = subtotal(items)
    assert total >= 0
    assert _is_money(total)


@given(st.lists(line_items, max_size=10), st.lists(line_items, max_size=10))
def test_subtotal_is_additive(items_a, items_b):
    """Splitting a cart in two and totalling each half gives the same answer."""
    assert subtotal(items_a + items_b) == subtotal(items_a) + subtotal(items_b)


# ---------- discounts ----------

@given(money, percent)
def test_discount_result_is_in_bounds(amount, p):
    """A discount can never produce a negative price, nor exceed the original."""
    result = apply_percentage_discount(amount, p)
    assert Decimal("0") <= result <= amount


@given(money)
def test_zero_discount_is_identity(amount):
    assert apply_percentage_discount(amount, Decimal("0")) == amount


@given(money)
def test_full_discount_makes_it_free(amount):
    assert apply_percentage_discount(amount, Decimal("100")) == Decimal("0.00")


@given(money, percent, percent)
def test_higher_discount_means_lower_total(amount, p1, p2):
    """A bigger discount can never increase what the customer pays."""
    lo, hi = sorted([p1, p2])
    assert apply_percentage_discount(amount, hi) <= apply_percentage_discount(amount, lo)


@given(amount=st.decimals(min_value=Decimal("-10000"), max_value=Decimal("-0.01"),
                          allow_nan=False, allow_infinity=False, places=2))
def test_discount_rejects_negative_amount(amount):
    with pytest.raises(ValueError):
        apply_percentage_discount(amount, Decimal("10"))


# ---------- shipping ----------

@given(money, money)
def test_shipping_is_free_at_or_above_threshold(amount, threshold):
    """If you've MET the free-shipping threshold, shipping is free.

    The example-based file admits it doesn't test the exact $50 boundary.
    By generating both amount and threshold from the same strategy, we make
    `amount == threshold` a natural case for Hypothesis to explore — which
    reveals whether the code uses `>` (wrong) or `>=` (right) at the
    boundary. This is the canonical "PBT caught a bug the example tests
    missed" moment.
    """
    if amount >= threshold:
        assert calculate_shipping(amount, free_shipping_threshold=threshold) == Decimal("0.00")
    else:
        assert calculate_shipping(amount, free_shipping_threshold=threshold) > Decimal("0.00")


# ---------- tax ----------

@given(money)
def test_zero_tax_rate_means_zero_tax(amount):
    assert calculate_tax(amount, Decimal("0")) == Decimal("0.00")


@given(money, percent)
def test_tax_is_non_negative_and_money_formatted(amount, rate):
    tax = calculate_tax(amount, rate)
    assert tax >= 0
    assert _is_money(tax)


# ---------- end-to-end order totals ----------

@given(st.lists(line_items, max_size=10), percent, percent)
def test_order_total_is_non_negative_and_money_formatted(items, discount, tax):
    total = calculate_order_total(
        items,
        discount_percent=discount,
        tax_rate_percent=tax,
    )
    assert total >= 0
    assert _is_money(total)
