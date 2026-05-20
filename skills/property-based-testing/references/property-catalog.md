# Property Catalog

Eight categories of properties, with examples in multiple PBT libraries. When brainstorming, try to find at least one candidate in two or three different categories — the strongest test suites combine multiple kinds.

Examples below use **Hypothesis** (Python) and **fast-check** (TypeScript) as the two most common stacks, with occasional **proptest** (Rust) where it illuminates the pattern. The concepts transfer to any library; only the syntax differs.

## 1. Round-trips

If your code has an inverse, the composition of forward and inverse should be identity.

```python
# Hypothesis
@given(st.dictionaries(st.text(), st.integers()))
def test_json_roundtrip(d):
    assert json.loads(json.dumps(d)) == d
```

```typescript
// fast-check
fc.assert(
  fc.property(fc.dictionary(fc.string(), fc.integer()), (d) => {
    expect(JSON.parse(JSON.stringify(d))).toEqual(d);
  })
);
```

Common pairings: encode/decode, serialize/deserialize, parse/format, compress/decompress, encrypt/decrypt, push/pop, marshal/unmarshal.

Subtleties:
- The round-trip may not be exact (e.g., JSON loses tuple/list distinction; floats may lose precision). State the property as "round-trip preserves *semantic* equality" and define that equality explicitly.
- Both directions may have round-trip properties: `decode(encode(x)) == x` and also `encode(decode(y)) == y` for valid `y`. They test different things.

## 2. Algebraic laws

If the operation has algebraic structure, test the laws of that structure.

**Commutativity:**

```python
# Hypothesis
@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    assert add(a, b) == add(b, a)
```

```typescript
// fast-check
fc.assert(
  fc.property(fc.integer(), fc.integer(), (a, b) => add(a, b) === add(b, a))
);
```

**Associativity:**

```python
@given(st.integers(), st.integers(), st.integers())
def test_add_associative(a, b, c):
    assert add(add(a, b), c) == add(a, add(b, c))
```

**Identity:**

```python
@given(st.integers())
def test_add_identity(x):
    assert add(x, 0) == x
```

**Idempotence:**

```python
@given(st.lists(st.integers()))
def test_sort_idempotent(xs):
    assert sort(sort(xs)) == sort(xs)
```

```typescript
fc.assert(
  fc.property(fc.array(fc.integer()), (xs) => {
    expect(sort(sort(xs))).toEqual(sort(xs));
  })
);
```

**Distributivity:**

```python
@given(st.integers(), st.integers(), st.integers())
def test_mul_distributes_over_add(a, b, c):
    assert mul(a, add(b, c)) == add(mul(a, b), mul(a, c))
```

Other laws to look for: absorption, De Morgan's laws, monoid/group/ring laws, functor/monad laws for higher-order code.

**Commonly missed: order-independence over collections.** When the function aggregates over a list or set — `subtotal`, `mean`, `merge`, anything that consumes a collection — `f(xs) == f(shuffle(xs))` is a real property. Engineers often skip it because "obviously order doesn't matter," but a sorting step inserted for performance, a hash-based deduplication, or non-associative floating-point summation can quietly break commutativity without affecting any per-element test.

```python
@given(xs=st.lists(st.integers()), data=st.data())
def test_subtotal_order_independent(xs, data):
    """Oracle: subtotal of a permutation. Independent of the function under test."""
    shuffled = data.draw(st.permutations(xs))
    assert subtotal(xs) == subtotal(shuffled)
```

## 3. Oracle comparison

Compare against a simpler, slower, or canonical reference implementation.

```python
# Hypothesis — oracle is the standard library
@given(st.lists(st.integers()))
def test_quicksort_matches_sorted(xs):
    assert quicksort(xs) == sorted(xs)
```

```typescript
// fast-check — oracle is a built-in
fc.assert(
  fc.property(fc.array(fc.integer()), (xs) => {
    expect(quicksort(xs)).toEqual([...xs].sort((a, b) => a - b));
  })
);
```

```rust
// proptest — oracle is an obviously-correct brute-force version
proptest! {
    #[test]
    fn test_fast_max_matches_naive(xs in prop::collection::vec(any::<i32>(), 1..100)) {
        let naive = xs.iter().copied().fold(i32::MIN, i32::max);
        assert_eq!(fast_max(&xs), naive);
    }
}
```

Where do oracles come from?
- The standard library (`sorted`, `set`, `Counter`, built-in JSON, etc.)
- A naïve brute-force implementation you write inline (acceptable for `O(2^n)` reference vs. `O(n log n)` optimized)
- A previous version of the code (regression testing)
- A different language's implementation called via subprocess
- A formal specification expressed as code

If the oracle is itself complex, you've moved the bug — make sure the oracle is *obviously* correct, even at the cost of being slow.

## 4. Metamorphic relations

Two related inputs produce related outputs. Useful when no oracle exists.

```python
# Adding an element to a sorted list and re-sorting:
# the result is the same as inserting it then sorting the whole thing.
@given(st.lists(st.integers()), st.integers())
def test_sort_metamorphic(xs, y):
    assert sorted(xs + [y]) == sorted(sorted(xs) + [y])

# Scaling all inputs by k should scale the mean by k.
@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1),
       st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6))
def test_mean_scales(xs, k):
    assume(abs(k) > 1e-9)
    assert math.isclose(mean([x * k for x in xs]), mean(xs) * k, rel_tol=1e-9)
```

```typescript
// Translating geometry by v should translate the centroid by v.
fc.assert(
  fc.property(polygonArb, vectorArb, (poly, v) => {
    const c1 = centroid(translate(poly, v));
    const c2 = translatePoint(centroid(poly), v);
    expect(c1).toEqual(c2);
  })
);
```

Metamorphic testing is *the* technique for code where the right answer is unknown (machine learning models, simulations, optimization solvers). Find a transformation of input whose effect on output is predictable.

## 5. Invariants preserved

Properties that are true before *and* after the operation.

```python
# Sorting preserves the multiset of elements (permutation invariant)
@given(st.lists(st.integers()))
def test_sort_is_permutation(xs):
    assert Counter(sort(xs)) == Counter(xs)

# Sorting also produces sorted output (the obvious one)
@given(st.lists(st.integers()))
def test_sort_produces_sorted(xs):
    result = sort(xs)
    assert all(result[i] <= result[i+1] for i in range(len(result) - 1))
```

```typescript
// A balanced binary tree stays balanced after insertion
fc.assert(
  fc.property(balancedTreeArb, fc.integer(), (tree, x) => {
    expect(isBalanced(insert(tree, x))).toBe(true);
  })
);
```

This is the workhorse pattern. For most data structures and algorithms, you can list 3–5 invariants and check each one. Together they often pin down behavior as tightly as an oracle comparison would.

**Commonly missed: output-shape invariants.** It's not enough for the value to be right — the output also has to have the right type, structure, and precision. A pricing function that should return two-decimal `Decimal` values can quietly start returning `Decimal("4.999999")` after a missing `quantize` call; the numeric assertions still pass because they compare with tolerance, but downstream code that round-trips through `str()` will break. Define a shape predicate and assert it everywhere.

```python
from decimal import Decimal

CENTS = Decimal("0.01")

def _is_money(x: Decimal) -> bool:
    return isinstance(x, Decimal) and x == x.quantize(CENTS)

@given(money_arb, percent_arb)
def test_discount_output_is_money(amount, percent):
    """Output-shape invariant: result is a Decimal quantized to cents."""
    assert _is_money(apply_percentage_discount(amount, percent))
```

## 6. Stateful invariants

For systems with internal state, properties hold across sequences of operations. The library-specific skill covers the API; the *concept* is universal — generate a sequence of operations, run them, check invariants throughout.

The dominant pattern is **model-based testing**: maintain a simple reference (a basic data structure) in parallel with the real implementation and assert they stay observably equivalent.

```python
# Hypothesis: RuleBasedStateMachine
class StackMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.stack = MyStack()
        self.model = []  # reference

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
```

```typescript
// fast-check: commands
class PushCmd implements fc.Command<Model, MyStack> {
  constructor(readonly value: number) {}
  check = () => true;
  run(m: Model, r: MyStack) {
    r.push(this.value);
    m.values.push(this.value);
    expect(r.size()).toBe(m.values.length);
  }
}
class PopCmd implements fc.Command<Model, MyStack> {
  check = (m: Model) => m.values.length > 0;
  run(m: Model, r: MyStack) {
    expect(r.pop()).toBe(m.values.pop());
  }
}

fc.assert(
  fc.property(
    fc.commands([
      fc.integer().map((v) => new PushCmd(v)),
      fc.constant(new PopCmd()),
    ]),
    (cmds) => fc.modelRun(() => ({ model: { values: [] }, real: new MyStack() }), cmds)
  )
);
```

The key idea is identical across libraries: define operations, let the library schedule them, check invariants.

## 7. Error / partiality

The function raises/returns an error exactly when its preconditions are violated, and never otherwise.

```python
@given(st.integers())
def test_sqrt_negative_raises(x):
    if x < 0:
        with pytest.raises(ValueError):
            my_sqrt(x)
    else:
        my_sqrt(x)  # should not raise
```

```typescript
fc.assert(
  fc.property(fc.integer(), (x) => {
    if (x < 0) {
      expect(() => mySqrt(x)).toThrow();
    } else {
      expect(() => mySqrt(x)).not.toThrow();
    }
  })
);
```

Two complementary properties: (a) raises when it should, (b) doesn't raise when it shouldn't. Both matter — silent acceptance of invalid input is a common bug.

For languages with `Result`/`Either` types (Rust, Haskell, Scala), the same pattern applies — `Err` returned exactly when preconditions fail.

**Commonly missed: the "raises when invalid" half.** Engineers writing PBT for the happy path often forget the rejection test entirely. The fix is to write a dedicated property whose generator targets the *invalid* domain and assert the exception:

```python
# Stateless rejection test — generator targets the invalid domain
@given(
    amount=money_arb,
    percent=st.decimals(min_value=Decimal("-100"), max_value=Decimal("-0.01"), places=2),
)
def test_negative_discount_rejected(amount, percent):
    """Partial-function rejection: negative discount must raise ValueError."""
    with pytest.raises(ValueError):
        apply_percentage_discount(amount, percent)
```

Inside a stateful rule, the same pattern applies — and is often skipped. The instinct when a rule's preconditions aren't met is to `return` early, but that leaves the error-handling path untested. Call the operation anyway and assert the right exception:

```python
@rule(account=accounts, amount=positive_money)
def withdraw(self, account, amount):
    """If the model says this withdrawal is invalid, the bank must raise."""
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

See `pbt-hypothesis/references/stateful.md` ("Don't skip error paths in rules") for the full pattern.

## 8. Monotonicity and bounds

The output changes in a predictable direction relative to the input, or stays within known bounds.

```python
# Adding an item to a list monotonically increases its length
@given(st.lists(st.integers()), st.integers())
def test_append_increases_length(xs, y):
    assert len(append(xs, y)) == len(xs) + 1

# A probability is always in [0, 1]
@given(st.lists(st.floats(min_value=0, max_value=1), min_size=1))
def test_probability_bounded(xs):
    p = compute_probability(xs)
    assert 0.0 <= p <= 1.0
```

```typescript
// Compression never makes data dramatically larger
fc.assert(
  fc.property(realisticDataArb, (data) => {
    expect(compress(data).length).toBeLessThanOrEqual(data.length + OVERHEAD);
  })
);
```

The monotonicity pattern catches a surprising number of bugs in numeric, statistical, and resource-counting code.

## Strength hierarchy

Properties have a natural strength ordering, weakest to strongest:

> **No exception < Type preservation < Invariant < Idempotence < Round-trip**

- **No exception** — "the function didn't crash." Catches almost nothing; it doesn't distinguish a correct function from one that returns `null` for every input.
- **Type preservation** — the output has the right type and shape (length, structure, precision). Catches output-shape bugs and obvious type errors. Often the cheapest non-trivial property available.
- **Invariant** — structural claims about the output (sorted, non-negative, bounded, multiset-preserving). The workhorse layer; combinations of invariants frequently pin down behavior as tightly as an oracle.
- **Idempotence** — `f(f(x)) == f(x)`. Catches state pollution, accumulation bugs, and operations that fail to converge. Only applicable when the function is supposed to be idempotent.
- **Round-trip** — `decode(encode(x)) == x`. Usually the strongest available; pins down the function's full input/output relationship. Only applicable when an inverse exists.

When you have a weak property and the function admits a stronger claim, **climb the hierarchy**. A test that only asserts "no exception" should usually be replaced by, or augmented with, a type-preservation or invariant claim. A type-preservation test for an invertible function should be paired with a round-trip.

This is complementary to Step 4's trap rejection in the core workflow: that catches *bad* properties (tautologies, self-oracles); the hierarchy catches *weak but valid* properties and pushes them harder.

Not every function admits every level. A function with no inverse can't have a round-trip property; a non-idempotent operation can't be idempotent. The hierarchy is a checklist to push *up*, not a requirement to reach the top.

## Combining categories

The strongest test suites use multiple categories per function. For a sorting function, you might write:

- Invariant: output is sorted (#5)
- Invariant: output is a permutation of input (#5)
- Idempotence: `sort(sort(xs)) == sort(xs)` (#2)
- Oracle: `sort(xs) == sorted(xs)` (#3) — if you have one
- Monotonicity: max element of output equals max of input (#8)
- Metamorphic: `sort(reverse(xs)) == sort(xs)` (#4)

Each property catches different bugs. The oracle would catch all of them, but if you don't have an oracle, the combination of invariants is nearly as strong — and is often more robust to acceptable variations in implementation (e.g., stable vs unstable sort).
