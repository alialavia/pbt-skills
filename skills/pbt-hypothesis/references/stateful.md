# Stateful Testing with `RuleBasedStateMachine`

For systems with internal state, sequence-of-operations bugs are invisible to flat `@given` tests. `RuleBasedStateMachine` generates sequences of operations and checks invariants between them.

## When to reach for stateful testing

- The system under test is a class with mutable state
- The system has a lifecycle (init, transitions, teardown)
- Bugs depend on the order or interleaving of operations
- The user reports "regression after N operations" or "intermittent under concurrent use"
- You're testing a database, cache, parser-with-state, connection pool, or any resource manager

If the function is pure, you don't need stateful testing. Use flat `@given`.

## The basic shape

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, precondition
from hypothesis import strategies as st

class StackMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.stack = MyStack()       # system under test
        self.model = []              # reference model (a Python list)

    @rule(x=st.integers())
    def push(self, x):
        self.stack.push(x)
        self.model.append(x)

    @precondition(lambda self: self.model)
    @rule()
    def pop(self):
        assert self.stack.pop() == self.model.pop()

    @invariant()
    def size_matches(self):
        assert self.stack.size() == len(self.model)

    @invariant()
    def top_matches(self):
        if self.model:
            assert self.stack.peek() == self.model[-1]

TestStack = StackMachine.TestCase
```

Hypothesis will:
1. Generate sequences of `push` and `pop` calls (respecting preconditions)
2. After each operation, run all `@invariant()` methods
3. On failure, shrink the sequence to the minimal failing case

## The model-based pattern

The example above is *model-based testing*: maintain a simple reference (a Python list) in parallel with the real implementation (`MyStack`) and assert they stay in sync. This is the single most powerful pattern in stateful testing.

The reference model should be:
- **Obviously correct** — even if slow or memory-hungry, its behavior should be transparent.
- **Independent** — implemented without using the system under test.
- **Complete** — capturing all observable behavior, not just one aspect.

If a Python list is a complete model of your "advanced data structure," you've proven your data structure is observably equivalent to a list. That's a strong correctness result.

## Bundles — for objects produced by one rule and consumed by another

When the system creates objects that later operations need to reference, use `Bundle`:

```python
from hypothesis.stateful import Bundle, consumes

class DatabaseMachine(RuleBasedStateMachine):
    users = Bundle("users")

    def __init__(self):
        super().__init__()
        self.db = Database()
        self.model = {}

    @rule(target=users, name=st.text(min_size=1, max_size=20))
    def create_user(self, name):
        user_id = self.db.create_user(name)
        self.model[user_id] = name
        return user_id  # added to `users` bundle

    @rule(user_id=users, new_name=st.text(min_size=1, max_size=20))
    def rename_user(self, user_id, new_name):
        self.db.rename_user(user_id, new_name)
        self.model[user_id] = new_name

    @rule(user_id=consumes(users))
    def delete_user(self, user_id):
        self.db.delete_user(user_id)
        del self.model[user_id]

    @invariant()
    def all_users_match(self):
        for user_id, name in self.model.items():
            assert self.db.get_user(user_id).name == name
```

`Bundle` lets later rules draw from objects that earlier rules produced. `consumes()` removes the object from the bundle (use for deletions).

## Preconditions

Use `@precondition` when a rule only makes sense in certain states:

```python
@precondition(lambda self: self.connection.is_open())
@rule(query=st.text())
def run_query(self, query):
    ...
```

Hypothesis will skip rules whose preconditions are false. Don't use `assume()` inside the rule body for state checks — `@precondition` integrates with the search and shrinking; `assume()` just throws away cases.

## Don't skip error paths in rules

`@precondition` keeps the happy path clean, but a rule that *also* knows about invalid states should not silently `return` when those states arise. The natural instinct is:

```python
# Skips error-path coverage entirely:
@rule(account=accounts, amount=positive_money)
def withdraw(self, account, amount):
    if account not in self.model:
        return                              # bug here is invisible
    if self.model[account] < amount:
        return                              # bug here is invisible
    self.bank.withdraw(account, amount)
    self.model[account] -= amount
```

The bank's error-handling paths are now exercised by zero tests. If a refactor changes `AccountNotFound` to a silent no-op, this suite will not notice. The better pattern is to call the operation anyway and assert the exception:

```python
# Tests error-path coverage:
@rule(account=accounts, amount=positive_money)
def withdraw(self, account, amount):
    if account not in self.model:
        with pytest.raises(AccountNotFound):
            self.bank.withdraw(account, amount)
        return
    if self.model[account] < amount:
        with pytest.raises(InsufficientFunds):
            self.bank.withdraw(account, amount)
        return
    self.bank.withdraw(account, amount)
    self.model[account] -= amount
```

Now every generated operation tests *something* — either the happy path or the correct exception for an invalid state.

When to prefer `@precondition` over inline rejection tests: when the invalid state isn't meaningful for *this* rule (e.g., you're testing concurrency between rules and "no accounts exist" would just produce noise). When the invalid state *is* part of the contract you care about, inline `pytest.raises` is better — it converts a missed call into a real assertion.

Caveat: the rule-body discipline above only fires when the rule actually *receives* invalid input. Smart generators that produce only valid inputs — `Bundle`, composite strategies, anything well-formed by construction — remove invalid inputs from the search space and make the rejection branches above unreachable. See the next section.

## Smart generators hide error paths — cover them with a separate rule

Generators that produce only valid inputs by construction (`Bundle`, `@st.composite`, FK-respecting builders, recursive strategies that always emit well-formed trees) keep happy-path tests clean. They also remove invalid inputs from the search space. The rule-body discipline only fires when a rule *receives* invalid input; with a smart generator, no rule ever does, and the SUT's rejection branches go untested.

This is the stateful counterpart of the rejection-test pattern in [`property-catalog.md` §7](../../property-based-testing/references/property-catalog.md#7-error--partiality): if the SUT has an error branch you care about, generate from the invalid domain *directly* and assert the exception. In stateful tests that means a dedicated rule:

```python
# Identifiers disjoint from anything the happy-path generator produces.
invalid_ids = st.sampled_from(["__sentinel_a__", "__sentinel_b__"])

@rule(item_id=invalid_ids)
def lookup_on_unknown_id_raises(self, item_id):
    """lookup() must raise NotFoundError for an id that was never created."""
    with pytest.raises(NotFoundError):
        self.system.lookup(item_id)
```

Sentinel values disjoint from anything the smart generator produces are simpler than filtering or `assume()`. Add one such rule per rejection branch in the SUT's contract.

The general principle: **a generator that excludes invalid inputs by construction excludes the test-level coverage of the rejection branches that handle them.** Smart generators are a happy-path tool, not a complete-coverage tool — they need to be paired with rules whose strategies target the invalid domain, or with a generator design (e.g., `st.sampled_from(small_pool)`) that mixes valid and invalid inputs in every rule.

## Invariants vs. rules

- `@rule` — an operation that changes state.
- `@invariant` — a property checked after *every* operation, with no arguments.

If a property depends on which operation just happened, assert it inside the rule. If it should hold all the time, make it an `@invariant`.

## Common patterns

### Reference-model invariant

The model and the implementation should agree on every observable.

```python
@invariant()
def model_matches_impl(self):
    for key in self.model:
        assert self.impl.get(key) == self.model[key]
    assert set(self.impl.keys()) == set(self.model.keys())
```

### Lifecycle invariant

Resources are always in a valid state.

```python
@invariant()
def no_leaked_resources(self):
    assert self.pool.in_use_count + self.pool.available_count == self.pool.total_count
    assert self.pool.in_use_count >= 0
    assert self.pool.available_count >= 0
```

### Idempotence under rules

Calling a rule twice should sometimes be a no-op or have a known effect.

```python
@rule(user_id=users)
def login_twice(self, user_id):
    self.system.login(user_id)
    state_after_first = self.system.session_state(user_id)
    self.system.login(user_id)  # idempotent?
    state_after_second = self.system.session_state(user_id)
    assert state_after_first == state_after_second
```

## Tuning

```python
from hypothesis import settings, HealthCheck

class MyMachine(RuleBasedStateMachine):
    ...

TestMyMachine = MyMachine.TestCase
TestMyMachine.settings = settings(
    max_examples=200,           # number of operation sequences to try
    stateful_step_count=50,     # max operations per sequence
    deadline=None,              # disable per-test deadline for slow ops
)
```

For systems where individual operations are slow (real database, network), reduce `max_examples` and `stateful_step_count`. For fast in-memory systems, you can crank both up.

## Things stateful testing finds that flat testing misses

- Bugs that only appear after a specific *sequence* of operations
- Race conditions in single-threaded state machines (e.g., observers fire in wrong order)
- Resource leaks (counts drift after many operations)
- Off-by-one errors in transitions
- Reentrancy bugs (operation A's callback triggers operation B mid-A)
- Cleanup bugs (state not reset between operations)

If a flat `@given` test passes but the system still has bugs under real use, stateful testing is the next place to look.
