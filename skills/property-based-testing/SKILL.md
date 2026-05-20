---
name: property-based-testing
description: Find genuine property-based tests for existing code, design new code so properties hold by construction, and diagnose property-test failures — always contract-first, reading the implementation only after properties have been designed. Use this skill whenever the user asks for property-based tests, PBT, QuickCheck-style tests, invariant tests, generative tests, or fuzz tests, in any language (Python/Hypothesis, TypeScript/fast-check, Rust/proptest, Haskell/QuickCheck, Scala/ScalaCheck, etc.). Also use it whenever the task mentions properties, invariants, oracles, generators, arbitraries, shrinking, stateful/model-based testing, or a property test that is failing — even if the user doesn't say "property-based" explicitly. Pair this skill with the library-specific skill (pbt-hypothesis, pbt-fast-check, etc.) when one is available — this skill handles property discovery, design, and failure interpretation; the library skill handles syntax, strategies/arbitraries, and ecosystem-specific patterns. Without this skill, generated property tests tend to degenerate into trivial example tests, tautologies that reimplement the function under test, or properties silently coupled to the current implementation rather than the contract.
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

## Which workflow to follow

What is the user actually doing? The skill has one default workflow and three sibling modes; pick the one that matches the task.

- **Writing tests for existing code** → the discovery workflow below (Steps 1–7). The default for most requests.
- **Designing new code, a new feature, or a new interface** → `references/property-driven-design.md`. Properties come *before* the implementation and constrain it. Especially valuable when working with an LLM, where it measurably reduces the rate of code-and-test sharing the same misunderstanding.
- **A property test failed and the user wants to understand why** → `references/interpreting-failures.md`. Don't assume the implementation is wrong; there are five possible causes, and the procedure pins down which one.
- **Reviewing PBT tests written by someone else** → apply Step 6's critique questions and Step 6.5's completeness check to the existing suite. The discovery workflow's depth and breadth discipline is the audit checklist.

The design and diagnostic modes are siblings to the discovery workflow, not extensions of it. They share Steps 3 (name the oracle), 4 (reject traps), and 6 (critique) — the depth discipline is the same — but they enter the lifecycle at different points.

## The workflow

Follow these steps in order. Do not skip ahead to code. Step 1 splits the act of reading the function into three passes — contract, properties, implementation — because they are different epistemic acts. Hughes (2019, "How to Specify It!") opens his paper warning that the dominant pitfall in PBT is *replicating the code in the tests*: properties that mirror what the implementation does rather than what the contract requires. Once you have read the body, your properties drift toward it. The three-pass structure prevents that drift.

### Step 1: Understand the function under test

#### 1A — Contract pass

Read only the contract surface: signature, type annotations, docstring/spec, parameter and return names (which often carry semantic information), declared error types, and adjacent functions in the same module for interface context. Do **not** read the function body, called helpers, existing tests, or the branch structure. From this surface alone, articulate:

- **Input domain**: types and constraints (non-empty? sorted? positive? valid UTF-8?)
- **Output domain**: types and constraints
- **Side effects**: mutates inputs? touches the filesystem? calls the network?
- **Preconditions**: what must be true of inputs for the function to be defined
- **Error contract**: what does it raise, and when

If the contract is unclear from the surface — common with underspecified docstrings — note which parts are unclear and either ask the user or proceed with the smallest defensible interpretation. Resolving ambiguity by reading the body is exactly the contamination this pass is designed to prevent.

#### 1B — Property design (Steps 2–4 below)

Design properties using only the contract from 1A. Every candidate should claim what any correct implementation must do, not what the current one happens to do.

#### 1C — Implementation pass

Only after Steps 2–4 are complete, read the body. Use it for three purposes, and only these:

1. **Contract verification.** Does the code appear to satisfy the contract you inferred? If they diverge, either the contract is wrong (re-read the docstring) or the code is — you have found a bug before writing a test. Note which.
2. **Generator refinement.** Does the implementation reveal edge cases the author thought about (empty input, negative numbers, boundary conditions)? Use these to refine the input generator in Step 5 — *not* the properties.
3. **Coupling audit.** For each property from 1B: does it hold only because of an implementation choice the contract doesn't guarantee (e.g., stable-sort ordering when the contract is silent on stability)? Weaken it to the contract level or discard.

Do *not* use this pass to add properties suggested by the implementation's structure (a binary search is a *how*, not a *what*), to pin tests to whichever variant the current code produces when the contract permits variation, or to silently resolve docstring ambiguity by reading the code — surface the ambiguity to the user; the code might be wrong.

### Step 2: Brainstorm candidate properties across categories

Read `references/property-catalog.md` for the full taxonomy with examples in multiple languages. Aim for **at least one candidate per applicable category**, not a fixed number. For most functions this produces 5–10 candidates; for trivial functions fewer is fine, but be explicit about which categories you considered and ruled out. The eight categories to scan:

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
- [ ] Would the property still hold for a *plausible alternative implementation* that satisfies the same contract? Picture a different algorithm or data structure that solves the same problem. → If your property fails for that alternative, it is implementation-coupled. Weaken it to the contract level or discard.

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

### Step 6.5: Completeness check

Steps 3, 4, and 6 give you per-property rigor. This step gives you breadth across the surface, so the suite doesn't stop at the handful of properties that came to mind first.

Before declaring the suite complete, walk the eight categories in `references/property-catalog.md` and, for each, write one sentence: either which test covers it, or why it doesn't apply to this function. The most commonly missed in practice are:

- **Output-shape invariants** (category 5): does the output have the right type, structure, and precision? A `Decimal` function should return values quantized to the right number of places; a JSON producer should return well-formed JSON. Bugs slip through when the assertion checks the value but not the shape.
- **Partial-function rejection** (category 7): does the function raise on invalid inputs, and *only* on invalid inputs? Happy-path PBT often forgets this half — if a function silently accepts a negative discount, no per-element property notices.
- **Order-independence** (category 2, commutativity flavor): when the function aggregates over a collection, does swapping input order change the output? Easy to skip with "obviously order doesn't matter"; a sorting step inserted for performance or a hash-based dedupe can quietly break it.

If a category applies and is missing, add a test. If it doesn't apply, say so out loud — the explicit ruling-out is the discipline.

### Step 7: Use stateful testing when appropriate

If the system under test has state (a database, a cache, a parser with internal state, a class with mutable instances), a flat property test will miss bugs that only appear after specific sequences of operations. Every major PBT library has a stateful/model-based mode (Hypothesis: `RuleBasedStateMachine`; fast-check: `fc.commands`; proptest: state-machine crates). The library skill has the syntax; the *pattern* is universal:

- Maintain a **reference model** (a simple, obviously correct version) in parallel with the real implementation.
- Define **operations** that the library can schedule in arbitrary sequences.
- After each operation, check **invariants** that should hold across all states.

Signs you need stateful testing: the function is a method on a class; the system has init/teardown lifecycle; bugs depend on operation ordering; the user mentions "regression after N operations" or "intermittent failures."

## Anti-patterns to actively avoid

Read `references/anti-patterns.md` for an annotated catalog of bad property tests and how to fix them. Some of these patterns are so seductive that even experienced engineers fall into them — review the catalog before generating tests, not after.

## When the user pushes back

If the user says "just write the tests, I don't need the analysis," still do Steps 1–4 and the Step 6.5 completeness check internally, and surface only the result. Do **not** silently skip them. The discovery work is what separates a real property test from a parameterized example. Present the properties compactly before showing tests:

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

- `references/property-catalog.md` — Eight categories of properties with multi-language examples, plus the strength hierarchy
- `references/anti-patterns.md` — Annotated bad tests and how to fix them, with examples in multiple languages
- `references/property-driven-design.md` — Forward-design mode: properties before implementation
- `references/interpreting-failures.md` — Diagnostic procedure for failed property tests
