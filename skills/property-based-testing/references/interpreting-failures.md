# Interpreting a Failed Property Test

When a property test fails, the first move is *not* to fix the implementation. There are five possible causes; only one of them means the code is wrong.

## The five possible causes

1. **Bug in the implementation.** The function violates a property it should hold. This is the common case but not the assumed case.
2. **Bug in the property.** The property is mis-stated and the implementation is correct. Common when the property was derived from a fuzzy understanding of the contract.
3. **Bug in the generator.** The strategy produces inputs that fall outside the documented input domain, and the property is correctly *not* claimed to hold for those inputs.
4. **Flakiness.** Nondeterminism in the system under test (time, ordering, external state, uninitialized memory) that property-based testing surfaced because it ran the function many times.
5. **Implementation coupling.** The property held for the implementation that existed when it was written, but it was silently testing more behavior than the contract guaranteed. A legitimate, behavior-preserving refactor changed an implementation detail the property depended on. Distinct from cause 2: the property may have been a perfectly fine *test of the old code*; it was just over-specified relative to the contract. Symptom: the property starts failing after a refactor that was supposed to be a no-op.

Each cause has a different fix. Treating cause 2, 3, 4, or 5 as cause 1 produces a "fix" that masks the real issue. The fix for cause 5 is to weaken the property to the contract level, not to revert the refactor.

## The LLM-specific risk: the cycle of self-deception

When the same agent wrote both the implementation and the property, a shared misunderstanding produces a passing-but-invalid test or a failing-but-invalid one — the agent's mental model of the contract is encoded into both halves, so they agree with each other rather than with reality. The Property-Generated Solver paper (arXiv 2506.18315) names this **the cycle of self-deception**: tests written alongside code by the same author confirm the author's assumptions rather than catching their mistakes.

The diagnostic procedure below exists partly to break this cycle. Reading the property and the implementation *as if a different author wrote each* is the cheap version of independent review.

## Decision tree

Work through these in order. Stop at the first one that fires.

**1. Is the shrunk counterexample inside the documented input domain?**

Look at the shrunk input. Is it a value the function is supposed to handle? If the contract says "non-empty list" and the counterexample is `[]`, the generator is wrong — it shouldn't produce empty lists for this property. Fix the strategy, re-run.

**2. Is the property correctly stated?**

Reread the test's docstring against the function's actual contract (interface comment, spec, design doc). If the property mismatches the contract, the property is the bug. Often: the property assumed associativity for an operation that's only commutative, or assumed exact equality where the contract allows approximate.

**2b. Did the failure follow a refactor that should have been behavior-preserving?**

Check `git log` on the function. If a recent change was intended as a no-op refactor (rename, restructure, swap an internal data structure) and the property started failing afterwards, suspect implementation coupling (cause 5). Ask: does the property assert something the *contract* guarantees, or something the *old implementation* happened to do? If the latter, weaken the property to the contract level — the refactor is correct.

**3. Does a known-correct reference also fail the property on this input?**

Run the shrunk counterexample through a reference implementation — the stdlib version, a brute-force version, a previous release. If the reference also fails the property, then the property is wrong about reality, not about the code. Fix the property.

**4. Is the failure reproducible?**

Re-run with the `@reproduce_failure(...)` blob (Hypothesis) or the equivalent seed (fast-check `seed`, proptest persistence file). If the same input passes on the second run, you have flakiness — chase the nondeterminism (clock, ordering, uninitialized state, network, filesystem) before treating this as a property failure. A flaky property test is worse than no test: it teaches the team to ignore failures.

**5. All five checks passed — it's a real bug.**

Now isolate. Is the bug in the function itself, or in something it calls transitively? The shrunk counterexample is your starting input; reduce further by hand if the shrinker stopped early, then bisect through the call stack.

## Triage: use the shrunk counterexample as a bug report

The shrunk counterexample *is* the minimal repro. Don't discard it:

- Pin it as an explicit example on the test (`@example(...)` in Hypothesis, `fc.pre`/explicit value in fast-check) so the regression catches immediately on future runs, even before random search.
- Paste it into the bug-tracker entry, verbatim.
- If shrinking stopped at something that's still complex, the generator is probably shrink-hostile (heavy filtering, opaque transformations, external randomness). Fixing that is its own task — but the counterexample as-is is still useful.

## A note on confidence

A property test that fails is more useful than a property test that passes. A passing test rules out the bugs the property could catch; a failing test, after this diagnostic, either reveals a real bug, a misunderstanding of the contract, or a flawed generator — all three of which improve the test suite. Treat failures as findings, not as setbacks.
