---
name: property-based-testing
description: Write genuine property-based tests — tests that capture universal invariants, not parameterized examples. Use this skill whenever the user asks for property-based tests, PBT, QuickCheck-style tests, invariant tests, generative tests, or fuzz tests, in any language (Python/Hypothesis, TypeScript/fast-check, Rust/proptest, Haskell/QuickCheck, Scala/ScalaCheck, etc.). Also use it whenever the task mentions properties, invariants, oracles, generators, arbitraries, shrinking, or stateful/model-based testing — even if the user doesn't say "property-based" explicitly. Pair this skill with the library-specific skill (pbt-hypothesis, pbt-fast-check, etc.) when one is available — this skill handles property discovery and design; the library skill handles syntax, strategies/arbitraries, and ecosystem-specific patterns. Without this skill, generated property tests tend to degenerate into trivial example tests or tautologies that reimplement the function under test.
---

# Property-Based Testing (core)

This skill is **language-agnostic**. It covers the reasoning every PBT engagement needs — finding properties, naming oracles, avoiding traps — regardless of whether you're writing Hypothesis, fast-check, proptest, QuickCheck, or anything else. For library-specific syntax and patterns, also load the relevant companion skill (e.g., `pbt-hypothesis`, `pbt-fast-check`).

## Why this skill exists

When asked to write property-based tests, models tend to skip the hard part — finding a real invariant — and jump straight to scaffolding that *looks* property-based but isn't. Common failure modes, in any language:

- **Tautologies**: the assertion reimplements the function under test (`assert add(x, 5) == x + 5`).
- **Glorified example tests**: a generator decorator wrapping a body that only meaningfully checks one or two inputs.
- **Self-oracles**: comparing the function's output to itself, often through a misleading reference (`assert sorted_list == sorted(my_sort(xs))`).
- **Flat generators**: arbitrary integers / arbitrary strings everywhere, ignoring that real inputs have structure, constraints, or relationships.
- **No shrinking discipline**: tests that, when they fail, produce 200-element counterexamples instead of minimal ones, because the generator was built in a shrink-hostile way.

The fix is procedural: **never write the generator decorator until you have written down the property in English, named the oracle, and rejected obvious traps.** This skill enforces that procedure.

## The workflow

Follow these steps in order. Do not skip ahead to code.

### Step 1: Understand the function under test

Before anything else, write a one-paragraph description of what the function is supposed to do. Identify:

- **Input domain**: what types and what constraints (non-empty? sorted? positive? valid UTF-8?)
- **Output domain**: what types and what constraints
- **Side effects**: does it mutate inputs? touch the filesystem? call the network?
- **Preconditions**: what must be true of inputs for the function to be defined

If you cannot articulate this clearly, ask the user before proceeding. Bad properties almost always trace back to a fuzzy understanding of the function's contract.

### Step 2: Brainstorm at least 5 candidate properties

Read `references/property-catalog.md` for the full taxonomy with examples in multiple languages. At minimum, consider:

1. **Round-trips**: `decode(encode(x)) == x`, `parse(format(x)) == x`, `deserialize(serialize(x)) == x`
2. **Algebraic laws**: identity, commutativity, associativity, idempotence, distributivity
3. **Oracle comparison**: compare against a simpler reference implementation (a brute-force version, a previous version, a spec, a standard library function)
4. **Metamorphic relations**: `f(x)` and `f(transform(x))` are related in a predictable way (e.g., `sort(xs + [y])` contains everything `sort(xs)` does, plus `y`)
5. **Invariants preserved**: properties that hold before and after the operation (length, sum, set of elements, type, sortedness)
6. **Stateful invariants**: properties of sequences of operations (e.g., `push` then `pop` returns the pushed value; size after `n` adds and `m` removes is `n - m`)
7. **Error / partiality**: function raises/returns an error exactly when preconditions are violated
8. **Monotonicity / boundedness**: output grows/shrinks predictably with input; output stays within known bounds

Write each candidate property in the form:

> **For all** inputs `X` satisfying **P**, the property **Y** holds.

If you cannot fill in both `P` and `Y` precisely, the property is not ready.

### Step 3: Name the oracle for each property

For every candidate, answer explicitly: **what am I comparing against, and is it independent of the function under test?**

A property is only useful if its oracle is independent. If the oracle *is* the function under test (or trivially derived from it), the test is a tautology.

- **Bad**: `my_sort(xs) == my_sort(xs)` — oracle is the same function.
- **Bad**: `my_sort(xs) == sorted(my_sort(xs))` — oracle depends on the function's own output.
- **Good**: `my_sort(xs) == sorted(xs)` — `sorted` is from the standard library, independent.
- **Good**: `is_sorted(my_sort(xs)) and multiset(my_sort(xs)) == multiset(xs)` — two independent invariants (sortedness + permutation), no reference implementation needed.

If no independent oracle exists, use **invariant decomposition**: list the structural properties the output must satisfy and check each. This is often as strong as oracle comparison and sometimes stronger — it pins down the *meaning* of the output rather than its bit-for-bit identity, which can be more robust to acceptable variations (e.g., stable vs unstable sort).

### Step 4: Reject the obvious traps

Before writing code, run each candidate through this checklist:

- [ ] Does the assertion mention the function under test on **both sides** of `==`? → Tautology, reject.
- [ ] Is the property trivially satisfied for all inputs by *any* function with the right type signature? → Too weak, reject or strengthen.
- [ ] Does the property only meaningfully test one or two example inputs? → It's an example test in disguise; either generalize or move it to a regular parameterized test.
- [ ] Would the property still hold if the function returned `input` unchanged? Or `[]`? Or `null`? → If yes, strengthen it.
- [ ] Is the oracle just the function's implementation re-expressed? → Tautology, reject.

### Step 5: Design generators that exercise the property

Only now think about the generator decorator. The library skill (`pbt-hypothesis`, `pbt-fast-check`, etc.) has the syntax. Universal principles:

- **Match the input domain precisely.** If the function requires sorted lists, generate sorted lists directly. Don't generate arbitrary lists and filter — you'll throw away most of the test budget.
- **Use composite/custom generators for structured inputs.** Records, ASTs, valid SQL, FK-respecting database rows — anything with internal constraints needs a custom generator, not a stack of filters on a primitive.
- **Avoid heavy filtering.** If more than ~10% of generated inputs get filtered out, redesign the generator. Most libraries emit a warning when filtering wastes too much budget, and the test will be weak even if it passes.
- **Think about shrinking.** When the test fails, the library shrinks the counterexample. Generators built from primitives shrink well; generators built with opaque transformations or external randomness may not. Prefer composites over filter chains.
- **Cover the edge of the domain.** Empty containers, single elements, duplicates, max-size, boundary values, Unicode edge cases for text, NaN/inf for floats, timezone-aware vs naive datetimes, zero/negative numbers where the contract allows them.

### Step 6: Write the test, then critique it

Write the test. Then, before declaring it done, read it once more and ask:

- If I deleted the function body and replaced it with `return arg` (or some other degenerate implementation), would this test still pass? If yes, the property is too weak.
- Could a buggy implementation still satisfy this property? Think of two or three plausible bugs and check mentally whether each would be caught.
- What does the library report on a failure? Is the shrunk counterexample going to be informative?
- Am I pinning known-tricky cases with explicit examples? (Most libraries have a mechanism for this — `@example` in Hypothesis, `fc.pre` and explicit values in fast-check, etc.)

**Always include a docstring or comment on each property test** that states the property in English and names the oracle. Future readers (human or agent) inherit the reasoning, and writing the docstring is itself a check — if you can't state the property clearly, the test isn't ready.

```
test_sort_permutation_invariant:
    Property: sort returns a permutation of its input — same multiset, possibly reordered.
    Oracle:   multiset equality, computed independently (Counter / Map / HashMap).
    Catches:  bugs that drop, duplicate, or invent elements.
```

### Step 7: Use stateful testing when appropriate

If the system under test has state (a database, a cache, a parser with internal state, a class with mutable instances), a flat property test will miss bugs that only appear after specific sequences of operations. Every major PBT library has a stateful/model-based mode (Hypothesis: `RuleBasedStateMachine`; fast-check: `fc.commands`; proptest: state-machine crates). The library skill has the syntax; the *pattern* is universal:

- Maintain a **reference model** (a simple, obviously correct version) in parallel with the real implementation.
- Define **operations** that the library can schedule in arbitrary sequences.
- After each operation, check **invariants** that should hold across all states.

Signs you need stateful testing: the function is a method on a class; the system has init/teardown lifecycle; bugs depend on operation ordering; the user mentions "regression after N operations" or "intermittent failures."

## Anti-patterns to actively avoid

Read `references/anti-patterns.md` for an annotated catalog of bad property tests and how to fix them. Some of these patterns are so seductive that even experienced engineers fall into them — review the catalog before generating tests, not after.

## When the user pushes back

If the user says "just write the tests, I don't need the analysis," still do Steps 1–4 internally and surface only the result. Do **not** silently skip them. The discovery work is what separates a real property test from a parameterized example. Present the properties compactly before showing tests:

```
Properties identified:
  1. [round-trip] decode(encode(x)) == x for all valid x
  2. [invariant]  len(compress(xs)) <= len(xs) for all xs
  3. [oracle]     my_sum(xs) ~= std_sum(xs) for all xs of finite floats
```

Then show the tests. If the user only wants one or two, ask which.

## When to push back on the user

If the user asks for property-based tests on a function where no meaningful properties exist (e.g., a pure I/O wrapper, a function whose entire contract is "return this specific string"), say so. Suggest example-based tests with the language's standard parameterization mechanism (pytest `parametrize`, Jest `each`, Rust `rstest`, etc.). Property-based testing is not always the right tool, and pretending it is produces the exact junk this skill is meant to prevent.

## Pairing with library-specific skills

When the task involves a specific PBT library, also load the library skill if available:

- **Hypothesis (Python)** → `pbt-hypothesis`
- **fast-check (TypeScript/JavaScript)** → `pbt-fast-check`
- **proptest (Rust)** → `pbt-proptest`
- **QuickCheck (Haskell)** → `pbt-quickcheck-hs`
- **ScalaCheck** → `pbt-scalacheck`

The library skill covers: generator/arbitrary API, stateful testing mechanics, shrinking specifics, settings and tuning, and library-specific anti-patterns. It assumes this core skill is already loaded — it does not re-derive the discovery workflow.

If no library skill exists for the user's stack, this core skill is still useful — the workflow is universal. You'll need to translate the patterns to the target library's idioms, but the *reasoning* doesn't change.

## Reference files

- `references/property-catalog.md` — Eight categories of properties with multi-language examples
- `references/anti-patterns.md` — Annotated bad tests and how to fix them, with examples in multiple languages
