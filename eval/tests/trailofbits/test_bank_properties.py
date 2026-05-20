"""
PROPERTY-BASED TESTS for the Bank — stateful edition.

The bank's correctness depends on the *sequence* of operations, not on any
single one. The example suite in tests/eb/test_bank_examples.py can only
check the specific sequences a human thought to write down.

Hypothesis' stateful testing generates random programs against the Bank
(open, deposit, withdraw, transfer, close, …) and after every step checks
the invariants below. If any reachable sequence breaks an invariant,
Hypothesis shrinks it to the smallest reproducing program and prints it.

The invariants we care about:
  * No account balance is ever negative.
  * Total assets only change in the way deposits / withdrawals / closes
    explicitly say they should. Transfers conserve total assets exactly.
  * Every account we believe exists actually exists, with the balance
    we believe it has (a model-based check against a parallel dict).
"""
from decimal import Decimal

from hypothesis import settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
)

from src.bank import (
    AccountAlreadyExists,
    AccountNotFound,
    Bank,
    InsufficientFunds,
)


# Realistic transaction amounts; keep them in clean cents so the model
# stays exact and the failure messages are easy to read.
amounts = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("1000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
account_ids = st.sampled_from(["alice", "bob", "carol", "dave", "eve"])


class BankStateMachine(RuleBasedStateMachine):
    """
    Drives a Bank with random operations and keeps a parallel 'model'
    (plain dict) of what the balances *should* be. Every invariant
    compares the bank's view to the model's view.
    """

    def __init__(self) -> None:
        super().__init__()
        self.bank = Bank()
        self.model: dict[str, Decimal] = {}

    # ---------- rules ----------

    @rule(account_id=account_ids, initial=amounts)
    def open_account(self, account_id, initial):
        if account_id in self.model:
            try:
                self.bank.open_account(account_id, initial)
            except AccountAlreadyExists:
                return
            assert False, "Bank allowed re-opening an existing account"
        else:
            self.bank.open_account(account_id, initial)
            self.model[account_id] = initial

    @rule(account_id=account_ids, amount=amounts)
    def deposit(self, account_id, amount):
        if account_id not in self.model:
            try:
                self.bank.deposit(account_id, amount)
            except AccountNotFound:
                return
            assert False, "Bank allowed deposit into a missing account"
        self.bank.deposit(account_id, amount)
        self.model[account_id] += amount

    @rule(account_id=account_ids, amount=amounts)
    def withdraw(self, account_id, amount):
        if account_id not in self.model:
            try:
                self.bank.withdraw(account_id, amount)
            except AccountNotFound:
                return
            assert False, "Bank allowed withdrawal from a missing account"
        if self.model[account_id] < amount:
            try:
                self.bank.withdraw(account_id, amount)
            except InsufficientFunds:
                return
            assert False, "Bank allowed an overdraft"
        self.bank.withdraw(account_id, amount)
        self.model[account_id] -= amount

    @rule(src=account_ids, dst=account_ids, amount=amounts)
    def transfer(self, src, dst, amount):
        if src not in self.model or dst not in self.model:
            try:
                self.bank.transfer(src, dst, amount)
            except AccountNotFound:
                return
            assert False, "Bank allowed transfer involving a missing account"
        if self.model[src] < amount:
            try:
                self.bank.transfer(src, dst, amount)
            except InsufficientFunds:
                return
            assert False, "Bank allowed a transfer that would overdraw the source"
        self.bank.transfer(src, dst, amount)
        # A transfer from an account to itself should be a no-op: same money,
        # same place. Hypothesis loves to try src == dst — if the bank's
        # transfer() reads-then-writes naively, the second write can clobber
        # the first and conjure money out of nothing. That's exactly the kind
        # of business-logic invariant PBT catches and example tests miss.
        if src == dst:
            return
        self.model[src] -= amount
        self.model[dst] += amount

    @precondition(lambda self: bool(self.model))
    @rule(data=st.data())
    def close_account(self, data):
        account_id = data.draw(st.sampled_from(sorted(self.model.keys())))
        returned = self.bank.close_account(account_id)
        assert returned == self.model[account_id]
        del self.model[account_id]

    # ---------- invariants (checked after every rule) ----------

    @invariant()
    def no_negative_balances(self):
        for account_id in self.bank.account_ids():
            assert self.bank.balance(account_id) >= 0, (
                f"NEGATIVE BALANCE at {account_id}: {self.bank.balance(account_id)}"
            )

    @invariant()
    def total_assets_match_model(self):
        assert self.bank.total_assets() == sum(self.model.values(), Decimal("0"))

    @invariant()
    def per_account_balance_matches_model(self):
        assert set(self.bank.account_ids()) == set(self.model.keys())
        for account_id, expected in self.model.items():
            assert self.bank.balance(account_id) == expected


# Hypothesis converts the state machine into a pytest test class.
TestBank = BankStateMachine.TestCase
TestBank.settings = settings(max_examples=100, stateful_step_count=30)
