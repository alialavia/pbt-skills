"""
STATEFUL PROPERTY-BASED TESTS for the Bank.

This is where PBT really earns its keep. The bank's behaviour depends on
the SEQUENCE of operations: open, deposit, transfer, withdraw, close.
An example-based suite picks specific stories ("Alice transfers $40 to
Bob"); Hypothesis builds a state machine that generates RANDOM SEQUENCES
of operations and checks invariants after every step.

Invariants we keep honest no matter the sequence:
  * no account balance ever goes negative
  * the bank's total assets equals our independent shadow tally
    (no operation should create or destroy money)
  * every account's individual balance equals our shadow balance

A failure here is reported as a minimal counterexample — the shortest
sequence of operations that breaks an invariant — which is far more
useful than "test_X failed: assertion error".

One line below replaces all 10 hand-picked stories in
test_bank_examples.py, and explores millions more.
"""
from decimal import Decimal

from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    consumes,
    invariant,
    rule,
)

from src.bank import Bank, InsufficientFunds


money = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


class BankStateMachine(RuleBasedStateMachine):
    accounts = Bundle("accounts")

    def __init__(self):
        super().__init__()
        self.bank = Bank()
        # Independent shadow ledger of what each account should hold,
        # built up from the operations we asked the bank to perform.
        self.shadow: dict[str, Decimal] = {}
        self._next_id = 0

    @rule(target=accounts, initial=money)
    def open_account(self, initial):
        aid = f"acct-{self._next_id}"
        self._next_id += 1
        self.bank.open_account(aid, initial)
        self.shadow[aid] = initial
        return aid

    @rule(account_id=consumes(accounts))
    def close_account(self, account_id):
        returned = self.bank.close_account(account_id)
        assert returned == self.shadow.pop(account_id)

    @rule(account_id=accounts, amount=money)
    def deposit(self, account_id, amount):
        self.bank.deposit(account_id, amount)
        self.shadow[account_id] += amount

    @rule(account_id=accounts, amount=money)
    def withdraw(self, account_id, amount):
        if self.shadow[account_id] >= amount:
            self.bank.withdraw(account_id, amount)
            self.shadow[account_id] -= amount
        else:
            try:
                self.bank.withdraw(account_id, amount)
            except InsufficientFunds:
                return
            raise AssertionError("expected InsufficientFunds")

    @rule(from_id=accounts, to_id=accounts, amount=money)
    def transfer(self, from_id, to_id, amount):
        # The shadow models the *correct* semantics: a self-transfer is a
        # no-op (money leaves and arrives at the same account). Hypothesis
        # will explore from_id == to_id and reveal whether the real bank
        # agrees.
        if self.shadow[from_id] >= amount:
            self.bank.transfer(from_id, to_id, amount)
            self.shadow[from_id] -= amount
            self.shadow[to_id] += amount
        else:
            try:
                self.bank.transfer(from_id, to_id, amount)
            except InsufficientFunds:
                return
            raise AssertionError("expected InsufficientFunds")

    # ---------- invariants checked after every operation ----------

    @invariant()
    def balances_are_non_negative(self):
        for aid in self.bank.account_ids():
            assert self.bank.balance(aid) >= 0, f"{aid} went negative"

    @invariant()
    def total_assets_match_shadow(self):
        assert self.bank.total_assets() == sum(self.shadow.values(), Decimal("0"))

    @invariant()
    def per_account_balances_match_shadow(self):
        for aid, expected in self.shadow.items():
            actual = self.bank.balance(aid)
            assert actual == expected, (
                f"{aid}: bank says {actual}, shadow says {expected}"
            )


# Expose the generated state machine to pytest as a regular test class.
TestBank = BankStateMachine.TestCase
