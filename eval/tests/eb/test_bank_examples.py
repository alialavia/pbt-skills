"""
EXAMPLE-BASED TESTS for the Bank.

Stateful business logic — a bank — is where example tests really show their
limits. A bank's behaviour depends on the SEQUENCE of operations:
open an account, deposit, transfer, withdraw, close. Two operations done
in opposite order can produce different (or broken) outcomes.

An example-based suite picks specific sequences and checks specific
end-states. It can never enumerate the (literally infinite) sequences a real
customer base would generate.

Compare with test_bank_properties.py, which uses Hypothesis' stateful
testing to generate *random sequences* of operations and check that the
no-negative-balances invariant holds no matter what.
"""
from decimal import Decimal

import pytest

from src.bank import (
    AccountAlreadyExists,
    AccountNotFound,
    Bank,
    InsufficientFunds,
)


def test_open_account_starts_at_zero():
    bank = Bank()
    bank.open_account("alice")
    assert bank.balance("alice") == Decimal("0")


def test_open_account_with_initial_deposit():
    bank = Bank()
    bank.open_account("alice", Decimal("100"))
    assert bank.balance("alice") == Decimal("100")


def test_cannot_open_same_account_twice():
    bank = Bank()
    bank.open_account("alice")
    with pytest.raises(AccountAlreadyExists):
        bank.open_account("alice")


def test_deposit_increases_balance():
    bank = Bank()
    bank.open_account("alice", Decimal("50"))
    bank.deposit("alice", Decimal("25"))
    assert bank.balance("alice") == Decimal("75")


def test_withdraw_decreases_balance():
    bank = Bank()
    bank.open_account("alice", Decimal("50"))
    bank.withdraw("alice", Decimal("20"))
    assert bank.balance("alice") == Decimal("30")


def test_cannot_overdraw():
    bank = Bank()
    bank.open_account("alice", Decimal("10"))
    with pytest.raises(InsufficientFunds):
        bank.withdraw("alice", Decimal("50"))


def test_transfer_moves_money_between_accounts():
    bank = Bank()
    bank.open_account("alice", Decimal("100"))
    bank.open_account("bob", Decimal("0"))
    bank.transfer("alice", "bob", Decimal("30"))
    assert bank.balance("alice") == Decimal("70")
    assert bank.balance("bob") == Decimal("30")


def test_transfer_conserves_total_assets():
    bank = Bank()
    bank.open_account("alice", Decimal("100"))
    bank.open_account("bob", Decimal("50"))
    before = bank.total_assets()
    bank.transfer("alice", "bob", Decimal("40"))
    after = bank.total_assets()
    assert before == after == Decimal("150")


def test_failed_transfer_leaves_balances_unchanged():
    bank = Bank()
    bank.open_account("alice", Decimal("10"))
    bank.open_account("bob", Decimal("0"))
    with pytest.raises(InsufficientFunds):
        bank.transfer("alice", "bob", Decimal("999"))
    assert bank.balance("alice") == Decimal("10")
    assert bank.balance("bob") == Decimal("0")


def test_operations_on_unknown_account_raise():
    bank = Bank()
    with pytest.raises(AccountNotFound):
        bank.balance("ghost")
    with pytest.raises(AccountNotFound):
        bank.deposit("ghost", Decimal("10"))


# Each test above is a single, hand-picked story.
# We tested A->B for $40, but not B->A, not three-account chains, not
# transfer-then-withdraw-then-transfer, not "open close open close open
# deposit transfer", and so on forever. That's what the stateful PBT does.
