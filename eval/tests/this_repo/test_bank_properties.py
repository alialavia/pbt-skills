"""
PROPERTY-BASED TESTS for the Bank.

A bank's behaviour depends on the *sequence* of operations:
open -> deposit -> transfer -> withdraw -> close, in any interleaving.
Example tests pick a handful of those sequences and never come close to
covering the space.

Hypothesis' RuleBasedStateMachine generates random sequences of
operations and checks invariants after every step. The state machine
below maintains a "reference model" (a plain dict[str, Decimal]) in
parallel with the real Bank and asserts they agree at every step. The
model is small enough to be obviously correct.

Invariants checked:
  - No account balance is ever negative.
  - Per-account balance matches the model.
  - The set of open accounts matches the model.
  - Total assets equals the sum of model balances.

The flat tests at the bottom of this file also cover specific algebraic
identities that example tests miss. One of them
(test_self_transfer_leaves_balance_unchanged) deliberately fails: the
implementation double-writes when from_id == to_id, so a self-transfer
of $X turns into a $X gift. Example tests test "A -> B" and never land
on "A -> A".
"""
from decimal import Decimal
from typing import Dict

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    consumes,
    invariant,
    rule,
)

from src.bank import (
    AccountNotFound,
    Bank,
    InsufficientFunds,
)


# ---------- strategies ----------

# Money values exact to the cent, in a realistic range.
money = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("10000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------- stateful test ----------

class BankStateMachine(RuleBasedStateMachine):
    """Drives random sequences of bank operations and checks invariants.

    The model (self.model) is a plain dict[str, Decimal] mirroring the
    bank's accounts. The bank IS the obvious-correct implementation --
    if at any point it diverges from the model, the test fails with
    the minimal counterexample sequence that produced the divergence.
    """

    accounts = Bundle("accounts")

    def __init__(self) -> None:
        super().__init__()
        self.bank = Bank()
        self.model: Dict[str, Decimal] = {}
        self._next_id = 0

    def _fresh_id(self) -> str:
        self._next_id += 1
        return f"acct-{self._next_id}"

    @rule(target=accounts, initial=money)
    def open_account(self, initial: Decimal) -> str:
        account_id = self._fresh_id()
        self.bank.open_account(account_id, initial)
        self.model[account_id] = initial
        return account_id

    @rule(account=accounts, amount=money)
    def deposit(self, account: str, amount: Decimal) -> None:
        self.bank.deposit(account, amount)
        self.model[account] += amount

    @rule(account=accounts, amount=money)
    def withdraw(self, account: str, amount: Decimal) -> None:
        if amount > self.model[account]:
            # Overdraw: bank must raise; model unchanged.
            with pytest.raises(InsufficientFunds):
                self.bank.withdraw(account, amount)
            return
        self.bank.withdraw(account, amount)
        self.model[account] -= amount

    @rule(src=accounts, dst=accounts, amount=money)
    def transfer(self, src: str, dst: str, amount: Decimal) -> None:
        if amount > self.model[src]:
            with pytest.raises(InsufficientFunds):
                self.bank.transfer(src, dst, amount)
            return
        self.bank.transfer(src, dst, amount)
        if src == dst:
            # A self-transfer should be a no-op on the model.
            # If the bank's implementation diverges (e.g. double-writes
            # and ends up adding `amount`), the balances_match_model
            # invariant will catch it on the very next check.
            return
        self.model[src] -= amount
        self.model[dst] += amount

    @rule(account=consumes(accounts))
    def close_account(self, account: str) -> None:
        expected = self.model.pop(account)
        returned = self.bank.close_account(account)
        assert returned == expected
        # After close, the bank should report AccountNotFound for the id.
        with pytest.raises(AccountNotFound):
            self.bank.balance(account)

    # ---- invariants ----

    @invariant()
    def no_negative_balances(self):
        """The defining invariant of a bank: no account ever goes negative."""
        for account_id in self.bank.account_ids():
            assert self.bank.balance(account_id) >= Decimal("0")

    @invariant()
    def balances_match_model(self):
        """Each per-account balance matches the model.
        Oracle: the model dict, an independent reference implementation.
        """
        for account_id, expected in self.model.items():
            assert self.bank.balance(account_id) == expected, (
                f"Bank balance for {account_id} = {self.bank.balance(account_id)}, "
                f"model says {expected}"
            )

    @invariant()
    def account_set_matches_model(self):
        """The set of open accounts and their count match the model."""
        assert set(self.bank.account_ids()) == set(self.model.keys())
        assert self.bank.num_accounts() == len(self.model)

    @invariant()
    def total_assets_matches_model(self):
        """Sum of all account balances equals the sum of the model's balances.
        Oracle: Python's sum() over the model -- independent of how the
        bank computes its own total_assets.
        """
        expected = sum(self.model.values(), Decimal("0"))
        assert self.bank.total_assets() == expected


# The state machine becomes a pytest TestCase via this class attribute.
TestBank = BankStateMachine.TestCase
# Settings are applied at the machine level so each generated *run*
# (a sequence of operations) has enough steps to find sequence bugs.
TestBank.settings = settings(max_examples=200, stateful_step_count=50, deadline=None)


# ---------- flat @given property tests ----------

@given(initial=money, amounts=st.lists(money, max_size=10))
def test_deposits_accumulate_to_sum(initial, amounts):
    """After a sequence of deposits, balance == initial + sum(deposits).
    Oracle: Python's built-in sum -- entirely independent of the bank's
    accumulation logic.
    """
    bank = Bank()
    bank.open_account("a", initial)
    for amount in amounts:
        bank.deposit("a", amount)
    assert bank.balance("a") == initial + sum(amounts, Decimal("0"))


@given(initial_a=money, initial_b=money, amount=money)
def test_transfer_conserves_total_assets(initial_a, initial_b, amount):
    """A transfer (successful or not) never changes total assets.
    Oracle: total before == total after -- an invariant independent of
    the function under test.
    """
    bank = Bank()
    bank.open_account("a", initial_a)
    bank.open_account("b", initial_b)
    before = bank.total_assets()
    try:
        bank.transfer("a", "b", amount)
    except InsufficientFunds:
        pass
    assert bank.total_assets() == before


@given(initial=money, amount=money)
def test_self_transfer_leaves_balance_unchanged(initial, amount):
    """Transferring money from an account to itself is a no-op.
    Oracle: identity -- the balance before equals the balance after,
    because money that goes nowhere has gone nowhere.

    This test deliberately fails on the current implementation: when
    from_id == to_id, transfer() computes the two new balances, then
    writes both back into the same dict slot in sequence. The second
    write (to_balance = balance + amount) overwrites the first
    (from_balance = balance - amount), turning a no-op into a free
    gift of `amount` dollars.

    No example-based test in the suite tests A -> A. PBT does, every run.
    """
    bank = Bank()
    bank.open_account("a", initial)
    if amount <= initial:
        bank.transfer("a", "a", amount)
        assert bank.balance("a") == initial


@given(initial=money, deposit_amount=money, withdraw_amount=money)
def test_deposit_then_withdraw_inverse(initial, deposit_amount, withdraw_amount):
    """Deposit X, then withdraw Y, the balance is initial + X - Y --
    provided the withdrawal is funded.
    Oracle: independent arithmetic on the inputs.
    """
    bank = Bank()
    bank.open_account("a", initial)
    bank.deposit("a", deposit_amount)
    if withdraw_amount <= initial + deposit_amount:
        bank.withdraw("a", withdraw_amount)
        assert bank.balance("a") == initial + deposit_amount - withdraw_amount


@given(initial=money)
def test_close_returns_full_balance(initial):
    """Closing an account hands back exactly its current balance.
    Oracle: the value we know we put in, independent of close_account.
    """
    bank = Bank()
    bank.open_account("a", initial)
    returned = bank.close_account("a")
    assert returned == initial
    with pytest.raises(AccountNotFound):
        bank.balance("a")
