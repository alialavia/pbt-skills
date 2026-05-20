# Property-Driven Design

A forward-design counterpart to the discovery workflow. Use this when the code doesn't exist yet — properties come first and constrain the implementation, rather than being written post-hoc.

## The framing

Properties are a **partial specification**. Any implementation that satisfies them is one valid refinement of that spec. Property-driven design treats the property set as the deliverable that pins down behavior, then writes code to fit.

This is the opposite end of the workflow from discovery:

- **Discovery** (the eight-step workflow in `SKILL.md`): given an existing function, find good properties for it. Post-hoc.
- **Property-driven design** (this reference): given a problem, state what any correct solution must satisfy *before* writing the solution. Constructive.

They are siblings, not extensions. The discovery workflow's Steps 3, 4, and 6 (name the oracle, reject traps, critique the test) still apply to every property you write here — the difference is when in the lifecycle you write them.

## Why it matters

The Property-Generated Solver paper (arXiv 2506.18315) reports 23–37% pass@1 improvements when LLM-generated code is constrained by a property specification *before* the implementation is generated, compared with conventional TDD that lets the LLM write code and tests in the same pass. The mechanism is straightforward: when properties exist before code, the implementation cannot accidentally encode the same misunderstanding as the test, because the spec is fixed first.

For human engineers the same effect shows up as fewer "the test passes but the behavior is wrong" surprises — the property set, written without an implementation to anchor on, is more likely to reflect the actual contract.

## Worked example: merging two sorted lists

Problem: write `merge(xs, ys)` that takes two sorted lists and returns one sorted list containing all elements.

**Step 1 — state the properties first, before any implementation.**

```python
# 1. Output is sorted.
@given(sorted_lists, sorted_lists)
def test_merge_sorted(xs, ys):
    out = merge(xs, ys)
    assert all(out[i] <= out[i+1] for i in range(len(out) - 1))

# 2. Output is the multiset union of inputs. Oracle: Counter, independent.
@given(sorted_lists, sorted_lists)
def test_merge_preserves_elements(xs, ys):
    assert Counter(merge(xs, ys)) == Counter(xs) + Counter(ys)

# 3. Length is the sum of input lengths.
@given(sorted_lists, sorted_lists)
def test_merge_length(xs, ys):
    assert len(merge(xs, ys)) == len(xs) + len(ys)

# 4. Empty inputs behave like identity.
@given(sorted_lists)
def test_merge_left_identity(xs):
    assert merge([], xs) == xs
    assert merge(xs, []) == xs

# 5. Commutativity at the multiset level — merge(xs, ys) and merge(ys, xs)
#    contain the same elements (order may differ for unstable merges, but
#    if the merge is stable across ties, they should be equal).
@given(sorted_lists, sorted_lists)
def test_merge_commutative_as_multiset(xs, ys):
    assert Counter(merge(xs, ys)) == Counter(merge(ys, xs))
```

**Step 2 — note that several implementations satisfy these.** A two-pointer linear merge satisfies them. So does `sorted(xs + ys)`. So does a heap-based k-way merge restricted to k=2. The properties are an executable specification; the choice between valid refinements is a separate concern (performance, readability, dependency surface).

**Step 3 — implement one.** The properties run on every commit, so any future refactor stays inside the same spec.

## When to use this mode

Use property-driven design when:

- The code doesn't exist yet.
- You're designing an interface, a protocol, or a parser for an underspecified format — the contract is the hardest part of the problem.
- You're working with an LLM and want to constrain the implementation before generation (per the Property-Generated Solver result above).
- The function will have multiple implementations over time (an interface with several backends, a reference vs. an optimized version).

Use the discovery workflow when:

- The code already exists and you're retrofitting tests.
- You're reviewing PBT tests someone else wrote.
- The contract is clear and the work is verification, not design.

## Connection to the discovery workflow's three-pass discipline

Discovery and property-driven design are two ways of enforcing the same principle: **the specification should not be contaminated by the implementation.** They differ in mechanism only.

- **Discovery mode** (`SKILL.md` Steps 1A → 1B → 1C) enforces the separation in *time*: write the contract from the surface, design properties, then read the body. Hughes' three-pass discipline.
- **Design mode** (this reference) enforces the separation in *existence*: write the properties when there is no body to contaminate them. Step 1C — the implementation pass — does not apply, because there is no implementation yet.

When the implementation eventually exists, the design-mode session ends and the discovery workflow resumes for any future modifications. At that point Step 1C applies in its normal form: read the body, verify it satisfies the properties, refine the input generator with edge cases the code suggests, and audit each property for accidental coupling to whatever the first implementer chose.

Treat them as complementary postures on the same underlying epistemics, not as two unrelated workflows.

## Pairing with lightweight formal methods

Properties that hold for all valid refinements are a step toward executable specifications. "The implementation satisfies the properties" is a weaker claim than "the implementation satisfies the spec," but it is the same shape of claim — both quantify over the input domain. When the property set is complete enough to pin down behavior, property-driven design is the on-ramp to TLA+-style spec work without the up-front cost of learning a spec language.

## What this mode does *not* do

It does not skip the discovery workflow's depth discipline. Every property written here still needs an independent oracle (Step 3), still has to clear the trap checklist (Step 4), and still gets the critique-and-docstring pass (Step 6). The completeness check (Step 6.5) is even more important here than in discovery, because there is no existing code to anchor against — the eight categories are the only safety net against missing a class of behavior.

Property-driven design is a re-ordering of the workflow, not a relaxation of it.
