# Hypothesis Strategies

How to design `@given` strategies that exercise the property well, shrink informatively, and don't waste the test budget on uninteresting cases. This file covers the Hypothesis API specifically — for the general principles of matching the input domain and avoiding filter-heavy designs, see the core PBT skill.

## The cardinal rule

**Generate valid inputs directly. Don't generate arbitrary inputs and filter.**

```python
# Bad: heavy filtering
@given(st.lists(st.integers()).filter(lambda xs: len(set(xs)) == len(xs)))
def test_on_unique(xs): ...

# Good: built-in support
@given(st.lists(st.integers(), unique=True))
def test_on_unique(xs): ...

# Bad: filtering for sortedness
@given(st.lists(st.integers()).filter(lambda xs: xs == sorted(xs)))
def test_on_sorted(xs): ...

# Good: map to sorted
@given(st.lists(st.integers()).map(sorted))
def test_on_sorted(xs): ...
```

The rule of thumb: if you find yourself writing `.filter(...)` for anything more selective than ~50%, redesign the strategy.

## `@st.composite` — the workhorse

For any input with internal structure or constraints, use `@st.composite`.

```python
@st.composite
def valid_dates(draw):
    """Generate a (year, month, day) tuple with day valid for that month."""
    year = draw(st.integers(min_value=1900, max_value=2100))
    month = draw(st.integers(min_value=1, max_value=12))
    max_day = calendar.monthrange(year, month)[1]
    day = draw(st.integers(min_value=1, max_value=max_day))
    return (year, month, day)

@given(valid_dates())
def test_date_handling(date):
    ...
```

Inside `@st.composite`, you can:
- Draw values conditionally
- Make later draws depend on earlier ones
- Use `assume()` for the rare cases that can't be expressed structurally
- Return any Python value, not just a tuple

## Foreign-key-aware data generation

A pattern from database/SQL testing — generating related rows that satisfy referential integrity:

```python
@st.composite
def order_with_customer(draw):
    customers = draw(st.lists(
        st.fixed_dictionaries({
            "id": st.integers(min_value=1, max_value=1000),
            "name": st.text(min_size=1, max_size=50),
        }),
        unique_by=lambda c: c["id"],
        min_size=1,
        max_size=20,
    ))
    customer_ids = [c["id"] for c in customers]
    orders = draw(st.lists(
        st.fixed_dictionaries({
            "id": st.integers(min_value=1),
            "customer_id": st.sampled_from(customer_ids),
            "amount": st.decimals(min_value=0, max_value=10000, places=2),
        }),
        min_size=0,
        max_size=50,
    ))
    return {"customers": customers, "orders": orders}
```

Key technique: draw the parent rows first, extract their keys, then draw children via `st.sampled_from(parent_keys)`. This guarantees FK validity without filtering.

## Recursive strategies

For tree-shaped data (ASTs, JSON, nested config), use `st.recursive`.

```python
json_values = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(max_size=10), children, max_size=5),
    ),
    max_leaves=20,
)

@given(json_values)
def test_json_roundtrip(value):
    assert json.loads(json.dumps(value)) == value
```

`max_leaves` controls overall size. Without it, you can get extremely deep trees that slow tests to a crawl.

## `st.builds` for object construction

```python
@dataclass
class User:
    name: str
    age: int
    email: str

user_strategy = st.builds(
    User,
    name=st.text(min_size=1, max_size=50),
    age=st.integers(min_value=0, max_value=150),
    email=st.from_regex(r"[a-z]+@[a-z]+\.com", fullmatch=True),
)
```

Cleaner than `st.composite` when you're just feeding kwargs to a constructor.

## Strategies for difficult domains

### Floats

```python
# Finite floats (no NaN, no inf)
finite_floats = st.floats(allow_nan=False, allow_infinity=False)

# Floats in a reasonable range (avoid overflow in computations)
reasonable_floats = st.floats(
    allow_nan=False,
    allow_infinity=False,
    min_value=-1e9,
    max_value=1e9,
)

# Positive floats
positive_floats = st.floats(min_value=0, exclude_min=True,
                            allow_nan=False, allow_infinity=False)
```

### Strings

```python
# ASCII only
ascii_text = st.text(alphabet=string.printable, min_size=1, max_size=100)

# Identifiers
identifiers = st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]{0,30}", fullmatch=True)

# Unicode but no surrogates / control chars
clean_text = st.text(alphabet=st.characters(
    blacklist_categories=("Cs", "Cc"),
))
```

### Datetimes

```python
from hypothesis.strategies import datetimes, timezones

# Naive datetimes
naive_dt = datetimes()

# Timezone-aware
tz_dt = datetimes(timezones=timezones())

# Bounded range
bounded_dt = datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2030, 12, 31),
)
```

## Shrinking-friendly design

When a test fails, Hypothesis shrinks the counterexample to the minimal example that still fails. Shrinking works best when:

- Strategies are built from primitives (`integers`, `text`, `lists`) rather than transformed via `.map()` with non-monotonic functions.
- `@st.composite` is preferred over `.filter()`.
- You avoid embedding random Python computations in strategies — Hypothesis can't shrink through opaque code.

Example of shrinking-hostile design:

```python
# Bad: external randomness defeats shrinking
def random_user():
    import random
    return User(name=f"user_{random.randint(0, 1000)}", age=random.randint(0, 100))

@given(st.lists(st.builds(random_user)))
def test_users(users): ...
```

```python
# Good: all randomness goes through Hypothesis
user_strategy = st.builds(
    User,
    name=st.text(min_size=1, max_size=20),
    age=st.integers(min_value=0, max_value=150),
)
@given(st.lists(user_strategy))
def test_users(users): ...
```

## `@example` for known cases

Always pin known edge cases with `@example`:

```python
@given(st.lists(st.integers()))
@example(xs=[])
@example(xs=[0])
@example(xs=[1, 1, 1])  # all-duplicates
def test_dedupe(xs):
    ...
```

This guarantees those cases are always tested, even when the random strategy doesn't happen to generate them.

## When to use `assume()`

`assume()` is appropriate when:

- The constraint is rare enough that filtering is fine (< ~10% of inputs rejected)
- The constraint is awkward to express structurally
- You're using it to skip a specific known-bad case during exploratory testing

`assume()` is *inappropriate* when:

- It rejects more than ~10% of inputs (redesign the strategy)
- The "constraint" is really part of the input's definition (build it into the strategy)
- You're using it to silence test failures (you're hiding bugs)
- It removes inputs the contract says are valid because they make the assertion awkward to write — duplicates, equal pairs, empty inputs, zero, self-reference. These are the inputs most likely to break the property; a low rejection rate doesn't make the filter safe. Rewrite the assertion to cover them, or test them separately.

A quick audit for every `assume(cond)` and `.filter(pred)`: write down an input it rejects and ask whether a buggy implementation would misbehave on it. If yes, the filter is hiding the bug.

## Customizing example generation: `target`

For numeric properties where you suspect bugs near boundaries, use `target()` to bias Hypothesis toward extreme cases:

```python
@given(st.lists(st.integers(min_value=0)))
def test_sum_doesnt_overflow(xs):
    total = my_sum(xs)
    target(total, label="total magnitude")  # bias toward large totals
    assert total >= 0
    assert total >= max(xs, default=0)
```

This makes Hypothesis search harder near the conditions you suspect break the code.
