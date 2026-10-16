# Anti-Patterns in Property-Based Tests

A catalog of bad property tests, why they're bad, and how to fix them. Examples are in **Hypothesis** (Python) and **fast-check** (TypeScript); the patterns themselves are universal — they appear in proptest, QuickCheck, ScalaCheck, and every other PBT library, because they're failures of reasoning, not syntax.

Review this *before* writing tests, not after — most of these mistakes look reasonable in isolation.

## 1. The Tautology

```python
# Hypothesis
@given(st.integers(), st.integers())
def test_add(a, b):
    assert add(a, b) == a + b
```

```typescript
// fast-check
fc.assert(fc.property(fc.integer(), fc.integer(), (a, b) => add(a, b) === a + b));
```

**Why it's bad**: If `add` is implemented as `a + b`, the test passes trivially. If `add` has a bug (say, integer overflow handling), the test passes anyway because the assertion uses the same operator the bug would be in.

**Fix**: Find an independent oracle, or test invariants instead.

```python
@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    assert add(a, b) == add(b, a)

@given(st.integers())
def test_add_identity(x):
    assert add(x, 0) == x
```

## 2. The Self-Oracle

```python
@given(st.lists(st.integers()))
def test_sort(xs):
    result = my_sort(xs)
    assert result == sorted(result)  # uses result, not xs!
```

**Why it's bad**: The assertion checks that `my_sort` returns something that the *standard sort* considers already sorted. That's a real check, but it doesn't verify the output is a permutation of the input. `my_sort` could return `[]` and pass.

**Fix**: Compare against the standard library applied to the *original input*, or check the permutation invariant separately.

```python
@given(st.lists(st.integers()))
def test_sort(xs):
    result = my_sort(xs)
    assert result == sorted(xs)                    # oracle
    assert Counter(result) == Counter(xs)          # permutation invariant
```

## 3. The Glorified Example Test

```typescript
fc.assert(
  fc.property(fc.integer({ min: 0, max: 10 }), (n) => {
    if (n === 0) return factorial(n) === 1;
    if (n === 1) return factorial(n) === 1;
    if (n === 2) return factorial(n) === 2;
    if (n === 3) return factorial(n) === 6;
    return true;  // silently passes for n >= 4!
  })
);
```

**Why it's bad**: This is parameterized testing with extra steps. The generator doesn't generalize anything — every input has a hardcoded expected output, and the catch-all `return true` makes most inputs trivially pass.

**Fix**: Either use the language's native parameterization (honest about being example-based), or find a real property.

```python
# Real property: factorial(n) = n * factorial(n-1)
@given(st.integers(min_value=1, max_value=20))
def test_factorial_recurrence(n):
    assert factorial(n) == n * factorial(n - 1)

# Real property: factorial is monotonic for n >= 1
@given(st.integers(min_value=1, max_value=20), st.integers(min_value=0, max_value=5))
def test_factorial_monotonic(n, k):
    assert factorial(n + k) >= factorial(n)
```

## 4. The Weak Property

```python
@given(st.lists(st.integers()))
def test_reverse(xs):
    assert len(reverse(xs)) == len(xs)
```

**Why it's bad**: Length preservation is necessary but nowhere near sufficient. A function that returns `xs` unchanged passes this test.

**Fix**: Add stronger properties that pin down the actual behavior.

```python
@given(st.lists(st.integers()))
def test_reverse(xs):
    assert reverse(reverse(xs)) == xs                          # involution
    assert len(reverse(xs)) == len(xs)                         # length
    assert Counter(reverse(xs)) == Counter(xs)                 # permutation
    if xs:
        assert reverse(xs)[0] == xs[-1]                        # first/last swap
        assert reverse(xs)[-1] == xs[0]
```

The combination is strong enough that no degenerate implementation can pass.

## 5. The Filter-Heavy Generator

```python
@given(st.lists(st.integers()))
def test_on_sorted(xs):
    assume(xs == sorted(xs))  # only test pre-sorted lists
    # ... test body
```

```typescript
fc.assert(
  fc.property(fc.array(fc.integer()), (xs) => {
    fc.pre(xs.every((v, i) => i === 0 || xs[i - 1] <= v));  // only sorted
    // ... test body
  })
);
```

**Why it's bad**: For non-trivial list sizes, almost no random lists are sorted. The library filters out 99%+ of generated inputs, runs slow, and may emit a "too many filtered examples" warning. The test ends up running on tiny lists only.

**Fix**: Generate sorted lists directly.

```python
sorted_lists = st.lists(st.integers()).map(sorted)

@given(sorted_lists)
def test_on_sorted(xs):
    # xs is guaranteed sorted; full test budget goes to interesting cases
    ...
```

```typescript
const sortedArrays = fc.array(fc.integer()).map((xs) => [...xs].sort((a, b) => a - b));

fc.assert(fc.property(sortedArrays, (xs) => { /* ... */ }));
```

Rule of thumb across all libraries: if you find yourself filtering for anything more selective than ~50%, redesign the generator.

## 6. The Reimplementation Oracle

```python
def my_mean(xs):
    return sum(xs) / len(xs)

@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1))
def test_mean(xs):
    expected = sum(xs) / len(xs)  # exactly the implementation
    assert my_mean(xs) == expected
```

**Why it's bad**: The "oracle" *is* the implementation. Any bug in `my_mean` is also a bug in the oracle. The test reduces to `assert my_mean(xs) == my_mean(xs)`.

**Fix**: Use an independent reference, or test properties that don't require an oracle.

```python
from statistics import mean as ref_mean

@given(st.lists(st.floats(allow_nan=False, allow_infinity=False,
                          min_value=-1e6, max_value=1e6), min_size=1))
def test_mean_matches_stdlib(xs):
    assert math.isclose(my_mean(xs), ref_mean(xs), rel_tol=1e-9)

# Or property-based without an oracle:
@given(st.lists(st.floats(allow_nan=False, allow_infinity=False,
                          min_value=-1e6, max_value=1e6), min_size=1))
def test_mean_bounded(xs):
    assert min(xs) <= my_mean(xs) <= max(xs)
```

## 7. Flat Generators for Structured Data

```typescript
fc.assert(
  fc.property(fc.string(), fc.string(), fc.string(), (name, email, address) => {
    const user = createUser({ name, email, address });
    // 99% of generated emails are not valid emails
    // The test rarely exercises real behavior
  })
);
```

**Why it's bad**: `fc.string()` (or `st.text()`) generates arbitrary Unicode. For an email field, almost nothing generated is a plausible email. The test exercises only the validation/rejection path.

**Fix**: Use built-in constrained generators or build a composite one for valid users.

```typescript
const validUserArb = fc.record({
  name: fc.string({ minLength: 1, maxLength: 20 }),
  email: fc.emailAddress(),  // fast-check has this built in
  address: fc.string({ minLength: 5, maxLength: 100 }),
});

fc.assert(
  fc.property(validUserArb, (u) => {
    const user = createUser(u);
    expect(user.email).toBe(u.email);
  })
);
```

For invalid-input tests, write a *separate* test with a generator targeting invalidity.

## 8. The Floating-Point Trap

```python
@given(st.floats(), st.floats())
def test_add_commutative(a, b):
    assert a + b == b + a
```

**Why it's bad**: Default float generators include NaN, and `NaN + NaN != NaN + NaN` (NaN is not equal to itself). Test fails on the first NaN.

**Fix**: Be explicit about what floats are in scope, and use approximate comparison.

```python
finite = st.floats(allow_nan=False, allow_infinity=False)

@given(finite, finite)
def test_add_commutative(a, b):
    assert a + b == b + a
```

```typescript
const finite = fc.double({ noNaN: true, noDefaultInfinity: true });

fc.assert(fc.property(finite, finite, (a, b) => a + b === b + a));
```

For non-trivial floating-point arithmetic, use an approximate-equality function with explicit tolerances.

## 9. Stateful Bugs Tested Statelessly

```python
@given(st.lists(st.tuples(st.sampled_from(["push", "pop"]), st.integers())))
def test_stack(ops):
    stack = Stack()
    for op, val in ops:
        if op == "push":
            stack.push(val)
        elif op == "pop" and stack.size() > 0:
            stack.pop()
    # ... assert something?
```

**Why it's bad**: This *looks* stateful but is awkward — there's no clean way to express what should be true after a sequence of ops. The author often gives up and asserts something trivial like `stack.size() >= 0`.

**Fix**: Use the library's stateful testing mode (`RuleBasedStateMachine`, `fc.commands`, proptest state-machine crates, etc.). They were designed for this; flat property tests over operation sequences reinvent it badly.

## 10. The "Just Add a Generator" Refactor

Someone took a working example test and slapped a generator on it:

```python
@given(st.integers())
def test_double(x):
    if x == 2:
        assert double(x) == 4
    elif x == 3:
        assert double(x) == 6
    else:
        pass  # silently passes for all other inputs!
```

**Why it's bad**: The `else: pass` makes the test pass for 99.99% of inputs without checking anything. The generator is window dressing.

**Fix**: Find a property that holds for *all* inputs, or convert back to a parameterized example test.

```python
@given(st.integers())
def test_double(x):
    assert double(x) == x + x      # property
    assert double(x) % 2 == 0      # invariant
```

## 11. Mutation Tests Without State Tracking

```python
@given(st.lists(st.integers()))
def test_sort_in_place(xs):
    original = xs  # NOT a copy!
    sort_in_place(xs)
    assert sorted(original) == xs  # original was mutated, so original == xs
```

**Why it's bad**: `original = xs` is an alias, not a copy. After mutation, `original` reflects the sorted state, making the assertion trivially true. Same trap in any language with reference semantics for collections.

**Fix**: Make a defensive copy before the mutation.

```python
@given(st.lists(st.integers()))
def test_sort_in_place(xs):
    original = list(xs)  # actual copy
    sort_in_place(xs)
    assert sorted(original) == xs
    assert Counter(original) == Counter(xs)
```

```typescript
fc.assert(
  fc.property(fc.array(fc.integer()), (xs) => {
    const original = [...xs];  // actual copy
    sortInPlace(xs);
    expect([...original].sort((a, b) => a - b)).toEqual(xs);
  })
);
```

## 12. Ignoring Shrinking

A test fails with a 200-element list of random integers. The agent reports the failure verbatim instead of letting the library shrink it to the minimal example.

**Why it's bad**: Shrinking is the *point* of property-based testing. A 200-element counterexample is much harder to debug than a 3-element one. If shrinking isn't working, the generator was built in a way that defeats it (heavy filter, complex transformation, opaque external randomness).

**Fix**: Let the library shrink. If shrinking is slow or unhelpful, redesign the generator. Use composites over filters, avoid filter for anything more selective than ~50%, and don't bring external randomness into generators — all randomness should flow through the library's PRNG so shrinking can replay it.

## 13. Equality That Doesn't Mean What You Think

```typescript
fc.assert(
  fc.property(fc.object(), (obj) => {
    expect(clone(obj) == obj).toBe(true);  // reference equality, not value!
  })
);
```

**Why it's bad**: `==` (or `===`) on objects compares references in most languages. The test passes only if `clone` returns the same reference, which is the opposite of what cloning should do.

**Fix**: Use the language's deep-equality utility (`toEqual` in Jest, `deepStrictEqual` in Node assert, `==` in Python for built-ins, `assertEquals` in Java/JUnit) and be explicit about what equality you mean.

```typescript
fc.assert(
  fc.property(fc.object(), (obj) => {
    const c = clone(obj);
    expect(c).toEqual(obj);   // structural equality
    expect(c).not.toBe(obj);  // but a different object
  })
);
```

This trap is most common in JavaScript/TypeScript but appears in any language with split reference/value equality (Java `==` vs `.equals()`, Scala `==` vs `eq`, etc.).

## 14. The Trigger-Excluding Filter

```python
@given(st.lists(st.integers()), st.integers())
def test_remove_drops_value(xs, v):
    assume(xs.count(v) <= 1)   # "duplicates make the assertion awkward"
    assert v not in remove(xs, v)
```

```typescript
fc.assert(
  fc.property(fc.integer(), fc.integer(), (a, b) => {
    fc.pre(a !== b);  // "transfers to self are a weird case"
    // ... transfer(a, b, amount) invariants
  })
);
```

**Why it's bad**: This is different from #5. The filter isn't wasteful — it may reject only a few percent of inputs — it's *targeted at the bug*. A `remove` that drops only the first occurrence, or a `transfer` that creates money when source and destination are the same account, is exactly what these filters hide. Agents add such filters when an input makes the assertion harder to write, and the awkward input is usually the interesting one. In PBT-Bench ([arXiv 2605.15229](https://arxiv.org/abs/2605.15229)) this was the single most common reason property tests missed bugs, for some models three quarters of misses.

**Fix**: Write the assertion so it holds for the awkward input too, or give the awkward input its own test. Never filter out an input the contract says is valid.

```python
@given(st.lists(st.integers()), st.integers())
def test_remove_drops_every_occurrence(xs, v):
    """Trigger: v appearing more than once — not filtered."""
    assert v not in remove(xs, v)

@given(st.lists(st.integers()), st.integers())
@example(xs=[1, 1], v=1)
def test_remove_keeps_everything_else(xs, v):
    assert Counter(remove(xs, v)) == Counter(x for x in xs if x != v)
```

For every filter, ask: does it remove inputs outside the contract's domain (fine), or awkward inputs inside it (a hidden bug)?

## 15. The Generator That Stops Short

```python
@given(st.integers(min_value=0, max_value=100))       # but the bug is at the int16 minimum
def test_encode_roundtrip(n): ...

@given(st.text(alphabet=string.ascii_letters))        # but the bug is in quoting/escaping
def test_csv_roundtrip(s): ...

@given(st.timedeltas(min_value=timedelta(0)))         # but the docs allow negative durations
def test_interval_roundtrip(d): ...
```

**Why it's bad**: The property is right; the strategy's range, alphabet, size cap or precision never reaches the inputs that break it. These limits are rarely chosen deliberately — they come from copying a "reasonable" range, from a strategy's defaults, or from a domain library's built-in generator. A suite that passes under such a generator says nothing about the region it never visits.

**Fix**: Derive bounds from the contract, not from convenience. Include the type's extremes, the separator/escape characters for text formats, negative and zero values where allowed, and the finest precision the type supports. When a library builds the strategy for you (a schema-driven row generator, a model factory), find out what it *doesn't* generate and override those columns or fields for properties whose trigger lies there. Pin very narrow triggers with explicit examples — more random examples is a weak substitute for a generator that reaches the region.
