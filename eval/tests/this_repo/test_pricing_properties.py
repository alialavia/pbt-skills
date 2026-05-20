"""
PROPERTY-BASED TESTS for the pricing engine.

These tests describe *invariants*, not specific examples. Hypothesis
generates inputs from the entire valid domain and looks for any input
that breaks the property. When a property fails, Hypothesis shrinks the
counterexample to the smallest one it can find and prints it.

Contrast with tests/eb/test_pricing_examples.py: the example-based
suite hand-picks scenarios and explicitly notes it does not test the
exact $50.00 shipping boundary. The property tests below land on that
boundary every run -- and expose an off-by-one between the docstring
("free when the subtotal meets the threshold") and the implementation
(`if discounted_subtotal > free_shipping_threshold`).

Two failing tests in this file are deliberate demonstrations of PBT
catching bugs that the example suite cannot:

    - test_shipping_free_at_or_above_threshold
"""
from decimal import Decimal

import pytest
from hypothesis import given, example, strategies as st

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
    min_value=Decimal("0.00"),
    max_value=Decimal("100000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

positive_money = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("100000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

percent = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("100"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

tax_rate = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("30"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@st.composite
def line_items(draw):
    """A LineItem with a reasonable unit price and quantity.

    Composite generator (not a filter chain): drawing each field directly
    from a bounded strategy keeps shrinking effective.
    """
    return LineItem(
        name=draw(st.text(min_size=1, max_size=20)),
        unit_price=draw(money),
        quantity=draw(st.integers(min_value=0, max_value=1000)),
    )


carts = st.lists(line_items(), max_size=20)


# ---------- line_total ----------

@given(item=line_items())
def test_line_total_is_cent_quantized(item):
    """line_total always returns a value rounded to the cent.
    Oracle: Decimal.quantize -- independent of line_total's arithmetic.
    """
    result = line_total(item)
    assert result == result.quantize(CENTS)


@given(item=line_items())
def test_line_total_non_negative(item):
    """Non-negative price and quantity cannot produce a negative total.
    Oracle: comparison against Decimal("0").
    """
    assert line_total(item) >= Decimal("0")


@given(unit_price=money)
def test_line_total_zero_quantity_is_zero(unit_price):
    """Zero quantity always means zero charge -- regardless of price."""
    assert line_total(LineItem("x", unit_price, 0)) == Decimal("0.00")


# ---------- subtotal ----------

@given(items=carts, data=st.data())
def test_subtotal_invariant_under_permutation(items, data):
    """Reordering a cart cannot change its subtotal.
    Oracle: st.permutations produces an independent reordering;
    we compare two calls to subtotal on equivalent multisets.
    """
    permuted = data.draw(st.permutations(items))
    assert subtotal(items) == subtotal(permuted)


@given(items_a=carts, items_b=carts)
def test_subtotal_splits_additively(items_a, items_b):
    """Subtotal of a concatenation equals the sum of subtotals.
    Oracle: independent Decimal addition over two already-rounded subtotals.
    (Each line_total is exact-to-the-cent, so adding two rounded subtotals
    introduces no further rounding.)
    """
    assert subtotal(items_a + items_b) == subtotal(items_a) + subtotal(items_b)


@given(items=carts)
def test_subtotal_non_negative_and_cent_quantized(items):
    """Subtotal of non-negative items is non-negative and rounded to cents.
    Oracle: arithmetic comparison and Decimal.quantize.
    """
    result = subtotal(items)
    assert result >= Decimal("0")
    assert result == result.quantize(CENTS)


# ---------- apply_percentage_discount ----------

@given(amount=money)
def test_zero_percent_discount_is_identity(amount):
    """0% off leaves the amount unchanged (after cent rounding).
    Oracle: amount.quantize(CENTS), independent of the function.
    """
    assert apply_percentage_discount(amount, Decimal("0")) == amount.quantize(CENTS)


@given(amount=money)
def test_full_discount_zeroes_amount(amount):
    """100% off makes the amount zero -- regardless of starting value.
    Oracle: literal Decimal("0.00").
    """
    assert apply_percentage_discount(amount, Decimal("100")) == Decimal("0.00")


@given(amount=money, p=percent)
def test_discount_result_in_bounds(amount, p):
    """0 <= discounted <= rounded original. The discount can never
    inflate the price or take it negative.
    Oracle: arithmetic comparison against the rounded input.
    """
    discounted = apply_percentage_discount(amount, p)
    assert Decimal("0.00") <= discounted <= amount.quantize(CENTS)


@given(amount=money, p1=percent, p2=percent)
def test_discount_monotonic_in_percent(amount, p1, p2):
    """A bigger discount cannot produce a larger remaining amount.
    Oracle: the ORDERING between two computations (relational property,
    not a tautology -- we're not reimplementing apply_percentage_discount,
    we're asserting f is monotone-decreasing in its second argument).
    """
    if p1 > p2:
        p1, p2 = p2, p1
    assert (
        apply_percentage_discount(amount, p1)
        >= apply_percentage_discount(amount, p2)
    )


@given(
    amount=money,
    bad_percent=st.decimals(
        min_value=Decimal("-1000"),
        max_value=Decimal("-0.01"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_negative_discount_rejected(amount, bad_percent):
    """Any negative percent must raise -- function is partial here."""
    with pytest.raises(ValueError):
        apply_percentage_discount(amount, bad_percent)


@given(
    amount=money,
    bad_percent=st.decimals(
        min_value=Decimal("100.01"),
        max_value=Decimal("10000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_over_hundred_percent_rejected(amount, bad_percent):
    """Discount > 100 must raise -- you cannot give back more than 100%."""
    with pytest.raises(ValueError):
        apply_percentage_discount(amount, bad_percent)


# ---------- calculate_shipping ----------

@given(amount=money)
@example(amount=Decimal("50.00"))  # the exact boundary
@example(amount=Decimal("50.01"))
def test_shipping_free_at_or_above_threshold(amount):
    """When the discounted subtotal MEETS or exceeds the threshold,
    shipping is free.
    Oracle: the function's own docstring, which says "free when the
    (post-discount) subtotal meets the threshold". 'Meets' means >=.

    This test deliberately fails on the current implementation at
    exactly $50.00: the code uses `>` instead of `>=`. The example
    suite explicitly notes it does not test this boundary; PBT lands
    on it every run.
    """
    threshold = Decimal("50.00")
    if amount >= threshold:
        assert calculate_shipping(amount, threshold) == Decimal("0.00")


@given(amount=money)
def test_shipping_strictly_below_threshold_charges_flat_rate(amount):
    """Strictly below threshold means flat rate is charged.
    Oracle: the flat_rate parameter we passed in (independent of the function).
    """
    threshold = Decimal("50.00")
    flat = Decimal("5.99")
    if amount < threshold:
        assert calculate_shipping(amount, threshold, flat) == flat


@given(amount=money, threshold=money, flat=positive_money)
def test_shipping_returns_zero_or_flat_rate(amount, threshold, flat):
    """Shipping is a two-valued function: 0 or flat_rate.
    Oracle: a literal set {0, flat}, independent of the function.
    Catches any bug where shipping is mis-scaled (e.g. percentage applied).
    """
    result = calculate_shipping(amount, threshold, flat)
    assert result in {Decimal("0.00"), flat}


# ---------- calculate_tax ----------

@given(amount=money)
def test_zero_rate_means_no_tax(amount):
    """A 0% tax rate produces zero tax."""
    assert calculate_tax(amount, Decimal("0")) == Decimal("0.00")


@given(amount=money, rate=tax_rate)
def test_tax_non_negative(amount, rate):
    """Tax on non-negative inputs is non-negative.
    Oracle: comparison against Decimal("0.00").
    """
    assert calculate_tax(amount, rate) >= Decimal("0.00")


@given(amount=money, rate=tax_rate)
def test_tax_within_half_cent_of_exact(amount, rate):
    """Rounded tax differs from the exact amount * rate / 100 by at most
    half a cent in either direction.
    Oracle: exact (un-rounded) Decimal arithmetic -- independent of the
    function's own quantize step.
    """
    tax = calculate_tax(amount, rate)
    exact = amount * rate / Decimal("100")
    assert abs(tax - exact) <= Decimal("0.005")


@given(
    amount=money,
    bad_rate=st.decimals(
        min_value=Decimal("-1000"),
        max_value=Decimal("-0.01"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
)
def test_negative_tax_rate_rejected(amount, bad_rate):
    """Negative tax rates must raise."""
    with pytest.raises(ValueError):
        calculate_tax(amount, bad_rate)


# ---------- calculate_order_total ----------

@given(items=carts, discount=percent, rate=tax_rate)
def test_order_total_non_negative(items, discount, rate):
    """End-to-end total is never negative.
    Oracle: comparison against Decimal("0.00").
    """
    assert calculate_order_total(items, discount, rate) >= Decimal("0.00")


@given(items=carts)
def test_full_discount_collapses_to_shipping_only(items):
    """A 100% discount zeroes the cart; the only remaining charge is
    flat-rate shipping (because $0 is below the free-shipping threshold)
    and tax on zero is zero.
    Oracle: literal Decimal("5.99") (the default flat rate).
    """
    total = calculate_order_total(items, discount_percent=Decimal("100"))
    assert total == Decimal("5.99")


@given(items=carts, rate=tax_rate)
def test_order_total_monotonic_in_tax_rate(items, rate):
    """A higher tax rate cannot produce a smaller total.
    Oracle: the ORDERING between two computations -- a relational
    property, not a tautology.
    """
    lower = calculate_order_total(items, tax_rate_percent=rate)
    higher = calculate_order_total(items, tax_rate_percent=rate + Decimal("1"))
    assert lower <= higher


@given(items=carts)
def test_order_total_decomposes_when_no_discount_no_tax(items):
    """With zero discount and zero tax, the total equals subtotal +
    shipping(subtotal).
    Oracle: the COMPOSITION of two simpler, separately-tested functions
    (subtotal and calculate_shipping). Not a tautology: we are NOT
    calling calculate_order_total to compute the expected value.
    """
    expected = subtotal(items) + calculate_shipping(subtotal(items))
    assert calculate_order_total(items) == expected
