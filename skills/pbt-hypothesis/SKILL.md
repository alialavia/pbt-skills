---
name: pbt-hypothesis
description: Hypothesis-specific patterns for property-based testing in Python — strategies, RuleBasedStateMachine, settings, and Hypothesis ecosystem gotchas. Use this skill whenever the task involves Hypothesis tests, the `hypothesis` package, `@given`, `st.` strategies, `RuleBasedStateMachine`, `@example`, or any Python property-based testing work. This skill pairs with the core `property-based-testing` skill, which handles property discovery and design — load both together for any Hypothesis task. This skill does not re-derive the workflow; it assumes the core skill is loaded and only covers Hypothesis syntax, idioms, and library-specific patterns.
---

# Property-Based Testing with Hypothesis (Python)

This skill covers **Hypothesis-specific** patterns. It assumes the core `property-based-testing` skill is loaded and you have already worked through the discovery workflow (understand the function → brainstorm properties → name oracles → reject traps). This file picks up at Step 5 of that workflow: turning a chosen property into a Hypothesis test.

If you have not done the discovery work yet, **stop and do it first.** Hypothesis syntax is easy; finding the right property is hard, and skipping that step produces the tautologies and weak tests this skill exists to prevent.

## Reference files

- `references/strategies.md` — Strategy patterns: composite, recursive, FK-aware, shrinking-friendly designs
- `references/stateful.md` — `RuleBasedStateMachine`, rules, invariants, preconditions, bundles
- `references/settings.md` — Profiles, deadlines, example database, CI tuning

## Quickstart by category

A minimal Hypothesis test:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_permutation(xs):
    """sort returns a permutation of its input.
    Oracle: collections.Counter (independent of my_sort).
    """
    from collections import Counter
    assert Counter(my_sort(xs)) == Counter(xs)
```

Key elements every Hypothesis test should have:

1. `@given(...)` with a strategy that matches the input domain precisely
2. A docstring stating the property in English and naming the oracle
3. An assertion that fails meaningfully — not just `assert result`
4. Where applicable, `@example(...)` decorators pinning known-tricky cases

## Strategies: the 30-second tour

For full coverage see `references/strategies.md`. The essentials:

| Need                                | Strategy                                                 |
|-------------------------------------|----------------------------------------------------------|
| Integer in a range                  | `st.integers(min_value=0, max_value=100)`                |
| Finite float                        | `st.floats(allow_nan=False, allow_infinity=False)`       |
| ASCII text                          | `st.text(alphabet=string.printable)`                     |
| List with constraints               | `st.lists(elem, min_size=1, unique=True)`                |
| Dict                                | `st.dictionaries(key_strategy, value_strategy)`          |
| Dataclass / class                   | `st.builds(MyClass, field1=strategy1, ...)`              |
| Custom structure                    | `@st.composite` (see below)                              |
| One of several                      | `st.one_of(strat1, strat2, ...)`                         |
| Recursive (trees, JSON)             | `st.recursive(base, lambda c: extend(c), max_leaves=N)`  |
| From a regex                        | `st.from_regex(r"...", fullmatch=True)`                  |

### `@st.composite` — the workhorse

For any input with internal structure or cross-field constraints:

```python
@st.composite
def valid_dates(draw):
    year = draw(st.integers(min_value=1900, max_value=2100))
    month = draw(st.integers(min_value=1, max_value=12))
    max_day = calendar.monthrange(year, month)[1]
    day = draw(st.integers(min_value=1, max_value=max_day))
    return datetime(year, month, day)

@given(valid_dates())
def test_date_arithmetic(date):
    ...
```

This is dramatically better than `st.dates().filter(lambda d: ...)` — composite generators shrink well and don't waste budget.

### FK-aware generation (relevant for SqlProof-style work)

Generate parent rows first, then draw children from the parent keys:

```python
@st.composite
def order_with_customer(draw):
    customers = draw(st.lists(
        st.fixed_dictionaries({
            "id": st.integers(min_value=1, max_value=1000),
            "name": st.text(min_size=1, max_size=50),
        }),
        unique_by=lambda c: c["id"],
        min_size=1, max_size=20,
    ))
    customer_ids = [c["id"] for c in customers]
    orders = draw(st.lists(
        st.fixed_dictionaries({
            "id": st.integers(min_value=1),
            "customer_id": st.sampled_from(customer_ids),
            "amount": st.decimals(min_value=0, max_value=10000, places=2),
        }),
        max_size=50,
    ))
    return {"customers": customers, "orders": orders}
```

The `st.sampled_from(parent_keys)` step guarantees referential integrity without any filtering.

## Stateful testing: `RuleBasedStateMachine`

For systems with state (databases, caches, classes with mutable instances), flat `@given` won't find sequence-dependent bugs. Use `RuleBasedStateMachine`. Quick sketch:

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, precondition

class StackMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.stack = MyStack()
        self.model = []  # reference model

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

TestStack = StackMachine.TestCase
```

For full coverage of `Bundle`, `consumes()`, multi-actor patterns, and lifecycle handling: read `references/stateful.md`.

## Hypothesis-specific gotchas

These are mistakes that are syntactically valid Hypothesis but produce bad tests. The general PBT anti-patterns are in the core skill's `references/anti-patterns.md`; the items below are Hypothesis-specific traps not covered there.

### Don't mutate strategy outputs in place

```python
# BAD
@given(st.lists(st.integers()))
def test_mutating(xs):
    xs.sort()  # mutates the input Hypothesis gave you
    # ...
```

Hypothesis may reuse strategy outputs across runs (especially during shrinking). Mutating them produces nondeterministic test failures. Always copy:

```python
@given(st.lists(st.integers()))
def test_no_mutation(xs):
    xs_copy = list(xs)
    xs_copy.sort()
    # ...
```

### `assume()` is not free

Each `assume(cond)` that fails costs Hypothesis an example. If your assumption fails often, you get warned with `HealthCheck.filter_too_much` — but the warning is the *symptom*, not the cause. The cause is a strategy that doesn't match the input domain. Fix the strategy, don't suppress the health check.

### `st.floats()` defaults include NaN and infinity

`assert a + b == b + a` fails for NaN because NaN is not equal to itself. Always use `st.floats(allow_nan=False, allow_infinity=False)` unless you're explicitly testing NaN behavior.

### `@example` should pin known edge cases

Always layer `@example(...)` decorators on `@given` for known-tricky inputs:

```python
@given(st.lists(st.integers()))
@example(xs=[])
@example(xs=[0])
@example(xs=[1, 1, 1])
def test_dedupe(xs):
    ...
```

These run *in addition* to the random search, guaranteeing those cases are always tested.

### Deadline issues with slow tests

Hypothesis's default 200ms per-example deadline trips often on tests that hit a database, filesystem, or network. Either disable it for those tests or set a generous deadline:

```python
from hypothesis import settings
from datetime import timedelta

@settings(deadline=None)  # or deadline=timedelta(seconds=5)
@given(...)
def test_slow_thing(...): ...
```

### Reproduce failures cleanly

When Hypothesis reports a failure, it prints a `@reproduce_failure(...)` decorator. Paste it temporarily onto the test to re-run the same counterexample without searching. Don't try to manually reproduce — use the blob.

### Commit the example database

Hypothesis records failures to `.hypothesis/examples`. Commit this directory (or share it via CI cache) so found bugs reproduce immediately on every run, building a free regression suite over time.

## Workflow integration

Recall the core workflow:

1. Understand the function under test
2. Brainstorm ≥5 candidate properties
3. Name the oracle for each
4. Reject the obvious traps
5. **Design the strategy** ← Hypothesis specifics start here
6. **Write the test, then critique it** ← and continue here
7. **Use stateful testing when appropriate** ← `RuleBasedStateMachine` if so

When the property is identified and the oracle is clear, the Hypothesis-specific work is: pick the right strategy (often `@st.composite`), write the `@given` and assertion with a docstring stating the property, pin known edge cases with `@example`, and tune settings if needed. The library is small once you know what you're testing.
