# Comparison: three property-based testing setups on the same SUT

A one-shot comparison of property-based tests produced by three Claude Code configurations against the same two-module system under test. The system has two deliberate bugs (one stateless boundary, one stateful aliasing) chosen because property-based testing is the kind of technique that should catch them and example-based testing systematically does not.

This is a *comparison*, not an experiment. See [LESSONS.md](./LESSONS.md) for the methodological limits and what a stronger evaluation would look like.

## 1. What this evaluates

The question: do property-based-testing-focused Claude Code skills measurably improve the quality of LLM-generated property-based tests, compared to no skill and to a popular publicly available competing skill?

The three setups:

- **NO SKILL** — Claude Code, no PBT skill loaded.
- **TRAILOFBITS** — Claude Code with [Trail of Bits' `property-based-testing` plugin](https://github.com/trailofbits/skills) loaded.
- **THIS REPO** — Claude Code with [`pbt-skills`'s `property-based-testing` and `pbt-hypothesis` skills](https://github.com/alialavia/pbt-skills) loaded.

The system under test, in [`src/`](./src/):

- [`src/pricing.py`](./src/pricing.py) — a stateless pricing engine with `LineItem`, `line_total`, `subtotal`, `apply_percentage_discount`, `calculate_shipping`, `calculate_tax`, `calculate_order_total`.
- [`src/bank.py`](./src/bank.py) — a stateful in-memory `Bank` class with `open_account`, `close_account`, `deposit`, `withdraw`, `transfer`, plus exception types `AccountNotFound`, `InsufficientFunds`, `AccountAlreadyExists`.

Two planted bugs:

1. **Shipping boundary** ([`src/pricing.py:60`](./src/pricing.py#L60)). The docstring says shipping is free when the discounted subtotal *meets* the threshold (`>= 50.00`), but the code uses `>`. At exactly $50.00 the customer is charged $5.99 in violation of the documented contract.
2. **Self-transfer money creation** ([`src/bank.py:75-95`](./src/bank.py#L75-L95)). `transfer(from_id, to_id, amount)` reads both balances, computes both new values, then writes both. When `from_id == to_id`, the write to `to_id` overwrites the write to `from_id` with `original + amount` — a self-transfer of `$X` adds `$X` to the account.

Both bugs are the kind random input generation hits routinely and humans miss when picking examples. An example-based suite that doesn't happen to test "exactly $50.00" or "A → A" sees nothing. The bugs are chosen precisely because they are PBT-catchable; see [section 5](#5-what-this-comparison-does-not-show) for what this biases.

There is also an example-based baseline ([`tests/eb/`](./tests/eb/)) to make the contrast visible.

## 2. How the comparison was run

Each PBT suite is a single one-shot Claude Code generation, with the prompt and SUT held identical across the three runs. The prompt was a request to write property-based tests for the pricing engine and the bank module; only the loaded skill differed.

No iteration, no follow-up, no asking the agent to improve its output. The suites are presented as-generated, with the exception that they were committed to disk and run unmodified through the test runner here. Anyone re-running with the same setups would get *similar* but not identical files due to sampling temperature; see [LESSONS.md](./LESSONS.md).

The system under test is the same file in all three working trees (verified via `diff`).

## 3. Results

Run `./run_eval.sh` from the `eval/` directory to reproduce the numbers below. The runner writes per-suite logs and a JSON summary into [`results/`](./results/).

### Pass/fail counts

| Suite | Test artifacts | Passed | Failed | Shipping bug caught | Self-transfer bug caught |
|---|---:|---:|---:|:---:|:---:|
| `eb` (example-based) | 26 | 26 | 0 | ✗ | ✗ |
| `no_skill` | 13 | 11 | 2 | ✓ | ✓ (stateful) |
| `trailofbits` | 22 | 20 | 2 | ✓ | ✓ (stateful) |
| `this_repo` | 29 | 26 | 3 | ✓ | ✓ (stateful + direct flat test) |

A "test artifact" is one decorator-bound function (`@given`, `@rule`+`@invariant` set as a state machine `TestCase`, or a plain `def test_`). Stateful state machines count as one artifact regardless of how many rules and invariants they contain.

**All three PBT setups catch both planted bugs.** The shipping bug is a single-property fail in each pricing suite; the self-transfer bug is caught by the stateful state machine (model divergence after a `from_id == to_id` operation). In the THIS REPO suite the self-transfer bug is *also* caught by a dedicated flat property test ([`test_self_transfer_leaves_balance_unchanged`](./tests/this_repo/test_bank_properties.py#L204-L223)) — the same bug shows up as two distinct test failures, which is a clearer signal at debug time.

The bug-catching axis saturates quickly. The interesting differentiation is elsewhere.

### Coverage by property category

Mapping each test to one of the [eight categories from `property-catalog.md`](../skills/property-based-testing/references/property-catalog.md):

| Category | `no_skill` | `trailofbits` | `this_repo` |
|---|:---:|:---:|:---:|
| 1. Round-trips | — | — | — |
| 2. Algebraic laws (identity, additivity) | ✓ | ✓ | ✓ |
| 2. Algebraic laws (commutativity / order-independence) | — | ✓ | ✓ |
| 3. Oracle comparison (independent reference) | — | weak (self-oracle, see §4) | ✓ |
| 4. Metamorphic / composition | — | partial | ✓ |
| 5. Invariants preserved (output-shape, bounds) | ✓ | ✓ | ✓ |
| 6. Stateful invariants | ✓ | ✓ | ✓ |
| 7. Error / partiality (rejection of invalid inputs) | 1 case | 3 cases | 3 cases |
| 8. Monotonicity / bounds | 1 case (sorted-pair) | 3 cases (uses `assume`) | 2 cases (full-budget) |

None of the three suites includes a round-trip property; the pricing module has no obvious inverse (you can't recover the input cart from the total) and the bank's only round-trip — `open_account → balance → close_account` returns the initial deposit — is partially covered by THIS REPO's [`test_close_returns_full_balance`](./tests/this_repo/test_bank_properties.py#L241-L250) but framed as a one-shot rather than a composed round-trip.

NO SKILL covers fewer categories and has thinner coverage within each (one rejection test, one monotonicity test, no order-independence, no oracle, no composition). TRAILOFBITS and THIS REPO are closer to each other than either is to NO SKILL.

## 4. Quality analysis: where each suite wins and loses

This is the part where category counts stop being interesting and individual test design matters.

### Where THIS REPO is stronger than TRAILOFBITS

**Generator hygiene on monotonicity.** TRAILOFBITS' [`test_discount_is_monotonic_in_percent`](./tests/trailofbits/test_pricing_properties.py#L120-L124) uses `assume(p1 <= p2)`. Because `p1` and `p2` are drawn independently from the same uniform strategy, about half of generated input pairs are rejected, and Hypothesis spends roughly half its budget on inputs that contribute nothing. THIS REPO's [`test_discount_monotonic_in_percent`](./tests/this_repo/test_pricing_properties.py#L175-L187) swaps `p1` and `p2` if needed (`if p1 > p2: p1, p2 = p2, p1`) so 100% of generated pairs land in the test. The same pattern is repeated in [`test_order_total_monotonic_in_tax_rate`](./tests/this_repo/test_pricing_properties.py#L329-L337) which compares `rate` and `rate + 1`. TRAILOFBITS does the same with `assume` in three places ([discount](./tests/trailofbits/test_pricing_properties.py#L121-L124), [tax rate](./tests/trailofbits/test_pricing_properties.py#L182-L185), [order total](./tests/trailofbits/test_pricing_properties.py#L217-L229)).

**Oracle independence on `subtotal`.** TRAILOFBITS' [`test_subtotal_is_sum_of_line_totals`](./tests/trailofbits/test_pricing_properties.py#L85-L89) reimplements `subtotal` using `line_total`:

```python
expected = sum((line_total(i) for i in items), Decimal("0")).quantize(CENTS)
assert subtotal(items) == expected
```

This is a self-oracle: the "expected" value uses the same `line_total` function the SUT uses. If `line_total` itself had a bug, both sides would have the same bug and the test would pass. THIS REPO instead asserts decomposition with an independent oracle ([`test_subtotal_splits_additively`](./tests/this_repo/test_pricing_properties.py#L127-L134)):

```python
assert subtotal(items_a + items_b) == subtotal(items_a) + subtotal(items_b)
```

The oracle here is `Decimal.__add__` on two already-rounded subtotals — entirely independent of `line_total` or `subtotal`'s internals.

**Composition oracle for the end-to-end function.** THIS REPO's [`test_order_total_decomposes_when_no_discount_no_tax`](./tests/this_repo/test_pricing_properties.py#L340-L349) asserts that `calculate_order_total(items)` with no discount and no tax equals `subtotal(items) + calculate_shipping(subtotal(items))`. The oracle is the *composition* of two simpler, separately-tested functions — independent of the function under test in the sense that it does not call `calculate_order_total` to compute the expected value. TRAILOFBITS has a related but weaker check in [`test_full_discount_leaves_only_shipping`](./tests/trailofbits/test_pricing_properties.py#L207-L213) that asserts the output is in `{0.00, 5.99}` after a 100% discount — useful but not the same shape.

**Rounding characterization.** THIS REPO's [`test_tax_within_half_cent_of_exact`](./tests/this_repo/test_pricing_properties.py#L280-L289) asserts the rounded tax differs from `amount * rate / 100` by at most half a cent. The oracle is exact (un-rounded) Decimal arithmetic. TRAILOFBITS has no equivalent — its tax tests are non-negativity, shape, monotonicity, and a zero-rate identity, but nothing pinning the *value* against a half-cent tolerance. The characterization test would catch a bug where the rounding mode changed from `HALF_UP` to `HALF_EVEN` (banker's rounding) or where the quantization unit was wrong (e.g., to the dollar).

**Docstring discipline.** Every THIS REPO property has a docstring with an explicit `Oracle: ...` line that names what the assertion compares against. This is a consequence of the discovery workflow's Step 6 (write the docstring stating the oracle). TRAILOFBITS' docstrings describe the property but rarely name the oracle. The benefit is at maintenance time: when a property fails after a refactor, the docstring tells the next reader whether the oracle was independent or coupled — see [`interpreting-failures.md`](../skills/property-based-testing/references/interpreting-failures.md) on the implementation-coupling cause of false failures.

**Direct flat test for the self-transfer bug.** Both suites catch the bug via their stateful state machines. THIS REPO additionally has [`test_self_transfer_leaves_balance_unchanged`](./tests/this_repo/test_bank_properties.py#L204-L223), which makes the bug appear as a named failure rather than "the model diverged on step 7 of the random sequence." For the same defect, the THIS REPO suite shows *two* failures at the same level, which is a meaningfully clearer debug signal.

### Where TRAILOFBITS is stronger than THIS REPO

**Bank error paths covered more thoroughly.** TRAILOFBITS' bank state machine uses [`account_ids = st.sampled_from(["alice", ...])`](./tests/trailofbits/test_bank_properties.py#L47) — a fixed vocabulary of five IDs that rules can independently pick. Because the rules can pick the same ID twice, or pick an ID not yet opened, the state machine naturally exercises three error paths: `AccountAlreadyExists` on re-open ([`test_bank_properties.py:64-74`](./tests/trailofbits/test_bank_properties.py#L64-L74)), and `AccountNotFound` on [deposit](./tests/trailofbits/test_bank_properties.py#L77-L85), [withdraw](./tests/trailofbits/test_bank_properties.py#L88-L93), and [transfer](./tests/trailofbits/test_bank_properties.py#L105-L111) to unknown IDs. THIS REPO uses `Bundle` with fresh `acct-N` IDs, which means every rule receives an existing account. The state machine never tries to open a duplicate or operate on a missing account, so all four error paths are exercised by zero tests in THIS REPO's bank suite. This is a real coverage gap.

**Slightly more pricing properties.** TRAILOFBITS pricing has 21 `@given` properties; THIS REPO has 23. The two extras in THIS REPO (composition oracle, rounding characterization) are higher-value than the four extras TRAILOFBITS doesn't have, but on raw count TRAILOFBITS is close.

**`@example` decorators pinning known-tricky inputs.** TRAILOFBITS uses `@example(amount=Decimal("50.00"))` on its shipping-boundary test ([`test_pricing_properties.py:161`](./tests/trailofbits/test_pricing_properties.py#L161)) and `@example([])` for empty-cart subtotal. THIS REPO uses `@example` on the shipping boundary too ([`test_pricing_properties.py:225-226`](./tests/this_repo/test_pricing_properties.py#L225-L226), pinning both `50.00` and `50.01`) but doesn't decorate the other tests. Difference is small.

### Where NO SKILL falls short

NO SKILL's pricing suite covers the basics: shape, non-negativity, identity, full-discount, the boundary check. It misses:

- Order-independence over the cart (not tested at all).
- Two of the three rejection cases (over-100% discount, negative tax rate).
- Tax monotonicity, end-to-end monotonicity in discount.
- Any composition oracle.
- Any characterization of the rounding behavior.
- Most of the [`Oracle: ...`](./tests/this_repo/test_pricing_properties.py#L95) docstring naming that the skill-trained suites have.

The Bank state machine is, however, surprisingly good — it uses a `Bundle`-based model, tests error paths via try/except, and asserts the right invariants. Even without a PBT skill, Hypothesis on a well-known problem (a bank account state machine) produces decent output. NO SKILL's weakness is most visible on the stateless side, where there are more *kinds* of property and the agent without guidance picks the obvious ones and stops.

## 5. What this comparison does NOT show

- **Single task, single domain.** One stateless module (pricing) and one stateful class (bank). Python and Hypothesis only. No parsers, no protocols, no concurrency, no numeric code, no graph algorithms, no machine-learned components. Different domains likely surface different strengths and weaknesses.
- **One-shot generations.** Each suite is one Claude Code session's output. Temperature and sampling variance mean re-running the same prompt would produce non-identical files. A more rigorous version would run each setup 5–10 times and report variance.
- **The SUT bugs are PBT-catchable by construction.** Both planted bugs (boundary, aliasing) are the kind random input enumeration finds easily. This biases the comparison toward PBT-relevant differentiators and away from things example tests are good at (e.g., specific scenarios documented in product requirements). It also means the bugs-caught axis saturates quickly across all three PBT setups — the meaningful differentiation lives in test-quality dimensions (oracle independence, generator hygiene, breadth of categories), not in the bug-catch count.
- **The author of this repo is the author of this comparison.** This is a self-evaluation. Read accordingly. A more rigorous version would have an independent practitioner classify the tests blind to which suite produced them.
- **Property-quality assessment is partly subjective.** Reasonable practitioners might disagree about whether a specific oracle is "independent enough" or whether a property is "over-specified vs. just specific." The category mapping in section 3 reflects one reading; another reading might shift some entries by one cell.
- **The SUT was written specifically to demonstrate PBT.** It is small, has known bugs, and was constructed to have clean invariants. Real codebases have fuzzier contracts, larger surface areas, and dependencies. Performance on this SUT does not transfer to real codebases without further evidence.

## 6. What this comparison DOES show

What the evidence actually supports:

- All three setups produce code that compiles and runs end-to-end.
- PBT-focused skills (both TRAILOFBITS and THIS REPO) produce more property categories and catch more planted bugs than NO SKILL — but the bugs-caught difference is small because the chosen bugs are easy for any working PBT suite to find.
- On the qualitative dimensions of section 4 — oracle independence, generator hygiene, composition oracles, rounding characterization, docstring discipline, direct (non-stateful) testing of the self-transfer bug — THIS REPO's output on this specific task is stronger than TRAILOFBITS'.
- On the bank's error paths (`AccountAlreadyExists` on re-open, `AccountNotFound` on operations against missing accounts), TRAILOFBITS' state-machine design exercises four paths that THIS REPO's `Bundle`-based design exercises zero of.
- TRAILOFBITS' published skill has broader scope than this repo's (smart-contract languages, refactoring guidance, proactive PBT-opportunity detection in unfamiliar codebases). Those dimensions are not exercised by this evaluation.

The defensible claim: **on this specific task with these specific planted bugs, THIS REPO's skill produces tests with stronger oracle independence, more efficient generators, and broader property-category coverage than NO SKILL or TRAILOFBITS, with one specific coverage gap (bank error paths) where TRAILOFBITS does better.** Generalizing beyond the specific task and bugs requires a benchmark suite — see [LESSONS.md](./LESSONS.md).

## 7. Reproducing the evaluation

```sh
# From the eval/ directory:
./run_eval.sh
```

Requirements: Python 3.10+, pytest, hypothesis. (`pyproject.toml` declares the deps.) On a recent laptop the four runs together take well under a minute.

Per-suite logs land in [`results/<suite>.log`](./results/) and a parseable summary lands in [`results/summary.json`](./results/summary.json). The JSON has one entry per suite with `passed`, `failed`, and the list of failed test IDs — that's how the numbers in section 3 were collected.

Cite Hughes (2019, [*How to Specify It!*](https://research.chalmers.se/publication/517894/file/517894_Fulltext.pdf)) for the underlying property taxonomy, and Maaz et al. ([*Agentic Property-Based Testing*, arXiv 2510.09907](https://arxiv.org/abs/2510.09907)) for the broader empirical case that PBT scaffolding helps LLM agents produce stronger tests.
