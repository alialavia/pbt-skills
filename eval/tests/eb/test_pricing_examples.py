"""
EXAMPLE-BASED TESTS for the pricing engine.

This is what most teams write today. Each test picks a specific scenario,
hard-codes the inputs, hard-codes the expected output, and checks they match.

These tests are easy to read and easy to write. They catch the bugs we
*thought to look for*. The catch is in that last clause: they only cover
the cases a human chose to write down. If a customer hits an input the
author never imagined, an example-based suite will happily pass while
production loses money.

Compare with test_pricing_properties.py to see the same code under test
covered by properties instead of single examples.
"""
from decimal import Decimal

import pytest

from src.pricing import (
    LineItem,
    apply_percentage_discount,
    calculate_order_total,
    calculate_shipping,
    calculate_tax,
    line_total,
    subtotal,
)


# ---------- line totals & subtotal ----------

def test_line_total_simple():
    item = LineItem("widget", Decimal("9.99"), 3)
    assert line_total(item) == Decimal("29.97")


def test_subtotal_of_two_items():
    items = [
        LineItem("widget", Decimal("9.99"), 2),
        LineItem("gadget", Decimal("4.50"), 1),
    ]
    assert subtotal(items) == Decimal("24.48")


def test_subtotal_of_empty_cart_is_zero():
    assert subtotal([]) == Decimal("0.00")


# ---------- discounts ----------

def test_ten_percent_off_one_hundred():
    assert apply_percentage_discount(Decimal("100.00"), Decimal("10")) == Decimal("90.00")


def test_zero_percent_off_leaves_amount_unchanged():
    assert apply_percentage_discount(Decimal("42.00"), Decimal("0")) == Decimal("42.00")


def test_one_hundred_percent_off_makes_it_free():
    assert apply_percentage_discount(Decimal("42.00"), Decimal("100")) == Decimal("0.00")


def test_negative_discount_rejected():
    with pytest.raises(ValueError):
        apply_percentage_discount(Decimal("100"), Decimal("-5"))


def test_over_hundred_percent_discount_rejected():
    with pytest.raises(ValueError):
        apply_percentage_discount(Decimal("100"), Decimal("150"))


# ---------- shipping ----------

def test_shipping_free_above_threshold():
    assert calculate_shipping(Decimal("75.00")) == Decimal("0.00")


def test_shipping_charged_below_threshold():
    assert calculate_shipping(Decimal("25.00")) == Decimal("5.99")


# Notice: there is no test here for the EXACT $50.00 threshold value.
# Most engineers wouldn't think to write one. A property test will hit it.


# ---------- tax ----------

def test_tax_eight_point_five_percent_on_one_hundred():
    assert calculate_tax(Decimal("100.00"), Decimal("8.5")) == Decimal("8.50")


def test_zero_tax():
    assert calculate_tax(Decimal("100.00"), Decimal("0")) == Decimal("0.00")


# ---------- end-to-end order totals ----------

def test_order_total_simple_cart_no_discount_no_tax():
    items = [LineItem("book", Decimal("12.00"), 2)]
    # subtotal $24 -> below shipping threshold -> +$5.99
    assert calculate_order_total(items) == Decimal("29.99")


def test_order_total_with_tax_and_free_shipping():
    items = [LineItem("monitor", Decimal("299.99"), 1)]
    # subtotal $299.99 -> free shipping -> +8.5% tax = $25.50 -> total $325.49
    total = calculate_order_total(items, tax_rate_percent=Decimal("8.5"))
    assert total == Decimal("325.49")


def test_order_total_with_discount():
    items = [LineItem("jacket", Decimal("100.00"), 1)]
    # 20% off -> $80 -> still above $50 free-shipping threshold -> no shipping, no tax
    total = calculate_order_total(items, discount_percent=Decimal("20"))
    assert total == Decimal("80.00")


def test_order_total_with_discount_below_shipping_threshold():
    items = [LineItem("t-shirt", Decimal("25.00"), 1)]
    # 20% off -> $20 -> below $50 threshold -> +$5.99 shipping, no tax
    total = calculate_order_total(items, discount_percent=Decimal("20"))
    assert total == Decimal("25.99")
