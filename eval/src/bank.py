"""
A tiny in-memory bank.

The bank tracks multiple accounts. Customers can deposit, withdraw, and
transfer money between accounts. This is the textbook example of stateful
business logic: the *sequence* of operations matters, not just any one of
them in isolation.

One essential invariant a bank can have:

    No account balance should ever go negative.

If that invariant ever breaks, customers can overdraw accounts. The stateful
property test (test_bank_properties.py) exists
specifically to keep that invariant honest no matter what sequence of
operations a customer (or a buggy service) throws at it.
"""
from decimal import Decimal
from typing import Dict


class InsufficientFunds(Exception):
    pass


class AccountNotFound(Exception):
    pass


class AccountAlreadyExists(Exception):
    pass


class Bank:
    def __init__(self) -> None:
        self._accounts: Dict[str, Decimal] = {}

    def open_account(self, account_id: str, initial_deposit: Decimal = Decimal("0")) -> None:
        if account_id in self._accounts:
            raise AccountAlreadyExists(account_id)
        if initial_deposit < 0:
            raise ValueError("Initial deposit cannot be negative")
        self._accounts[account_id] = initial_deposit

    def close_account(self, account_id: str) -> Decimal:
        """Close an account and return its final balance to the customer."""
        if account_id not in self._accounts:
            raise AccountNotFound(account_id)
        return self._accounts.pop(account_id)

    def balance(self, account_id: str) -> Decimal:
        if account_id not in self._accounts:
            raise AccountNotFound(account_id)
        return self._accounts[account_id]

    def deposit(self, account_id: str, amount: Decimal) -> None:
        if account_id not in self._accounts:
            raise AccountNotFound(account_id)
        if amount < 0:
            raise ValueError("Deposit amount cannot be negative")
        self._accounts[account_id] += amount

    def withdraw(self, account_id: str, amount: Decimal) -> None:
        if account_id not in self._accounts:
            raise AccountNotFound(account_id)
        if amount < 0:
            raise ValueError("Withdrawal amount cannot be negative")
        if self._accounts[account_id] < amount:
            raise InsufficientFunds(
                f"Account {account_id} has {self._accounts[account_id]}, "
                f"cannot withdraw {amount}"
            )
        self._accounts[account_id] -= amount

    def transfer(self, from_id: str, to_id: str, amount: Decimal) -> None:
        """
        Move money between two accounts at this bank. Atomic: we compute
        both new balances first, then write them, so a failure in the
        middle can't leave one side updated and the other not.
        """
        if from_id not in self._accounts:
            raise AccountNotFound(from_id)
        if to_id not in self._accounts:
            raise AccountNotFound(to_id)
        if amount < 0:
            raise ValueError("Transfer amount cannot be negative")
        if self._accounts[from_id] < amount:
            raise InsufficientFunds(
                f"Account {from_id} has {self._accounts[from_id]}, "
                f"cannot transfer {amount}"
            )
        new_from_balance = self._accounts[from_id] - amount
        new_to_balance = self._accounts[to_id] + amount
        self._accounts[from_id] = new_from_balance
        self._accounts[to_id] = new_to_balance

    def total_assets(self) -> Decimal:
        """Sum of all account balances currently held at the bank."""
        return sum(self._accounts.values(), Decimal("0"))

    def num_accounts(self) -> int:
        return len(self._accounts)

    def account_ids(self) -> list:
        return list(self._accounts.keys())
