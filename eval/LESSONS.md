# Lessons and limitations

A more rigorous evaluation than this one would address the following. Each section corresponds to a limit listed in [EVAL.md §5](./EVAL.md#5-what-this-comparison-does-not-show).

## One-shot generations vs. multi-shot variance

Each suite here is the output of one Claude Code session. LLM outputs vary with sampling temperature even when prompt and skill are held fixed. The right way to control for this is to run each setup 5–10 times against the same prompt and SUT, score every produced suite under the same criteria, and report mean and variance per dimension. The properties an agent reaches for can shift run-to-run; what looks like "TRAILOFBITS uses `assume` for monotonicity" in this run might be "TRAILOFBITS uses sorted-pair swap" in a re-run. A single point estimate is the weakest claim that can be made.

A still-stronger version would also vary the prompt slightly (within the same intent) to control for prompt-engineering luck, since real users will not phrase their request identically to the way it was phrased here.

## Single task vs. benchmark suite

This evaluation has one stateless module and one stateful class. PBT is a wide technique that covers parsers, serializers, data structures, numerical code, protocols, concurrent systems, and ML model invariants — each of which surfaces different category mixes and different generator-design challenges. A benchmark suite with 10–20 tasks across at least four or five domains (parsers, financial code, data structures, state machines, numerics) would let the comparison generalize beyond "what this skill does on a pricing engine and a bank."

The relevant prior art for benchmark construction is Hughes' eight-bug binary-search-tree benchmark in [*How to Specify It!*](https://research.chalmers.se/publication/517894/file/517894_Fulltext.pdf) and the broader benchmarks used in the [Property-Generated Solver paper](https://arxiv.org/abs/2506.18315). A reasonable v2 of this evaluation would borrow from both.

## Bug selection bias

The two planted bugs (shipping `>` vs `>=`, self-transfer aliasing) were chosen to be PBT-catchable. They are exactly the kind of defects random-input generation hits routinely. Both PBT-focused setups catch both bugs; the bugs-caught axis saturates quickly and stops being a differentiator. The interesting differences in this evaluation live in *test-quality* dimensions, not in *bugs-caught*.

A more rigorous version would include bugs of multiple kinds, including some that PBT is *not* well-suited to (e.g., misimplemented requirements that example tests anchored on the requirements document would catch but properties might not). That makes the comparison less flattering to PBT but more honest about its scope.

## Author-as-evaluator bias

The author of [`pbt-skills`](https://github.com/alialavia/pbt-skills) is the author of this evaluation. There is no independent grader. The risk this introduces is real even with the best intentions: "this oracle is independent" and "this property is coupled to the implementation" are partly subjective calls.

The right fix is an independent reviewer — ideally a Hypothesis or QuickCheck practitioner who has not seen the skills — classifying the tests blind to which suite produced them. That removes the strongest source of bias without requiring a re-run. If you are such a practitioner and read this, your write-up of disagreements is welcome.

## Subjective property-quality assessment

[EVAL.md §4](./EVAL.md#4-quality-analysis-where-each-suite-wins-and-loses) makes qualitative judgments — is this oracle "independent enough," is this property "coupled to the implementation," is this test "stronger than that one." These judgments are partly subjective: two experienced PBT practitioners can disagree on whether `expected = sum(line_total(i) for i in items)` is a "self-oracle" or "a check against the documented contract." The writeup picks one reading and supports each call with a code reference; another reasonable reading might shift the wins/losses balance.

A more rigorous evaluation would either define each quality dimension as an objectively checkable rubric (e.g., "an oracle is independent if and only if it does not call any function in the SUT module") and apply it mechanically, or have multiple independent graders score the same suites and report inter-rater agreement. This evaluation does neither. The category mapping in §3 and the wins/losses in §4 should be read as one careful reading, not as ground truth.

## The SUT was constructed for PBT

The pricing and bank modules in [`src/`](./src/) are small (under 100 LOC each), have clean invariants, declared exception types, and intentionally placed bugs. Real codebases have fuzzier contracts, modules that span thousands of lines, behaviors that depend on external state, and bugs whose root cause is far from where they manifest. PBT *can* help with those — see Hughes' BST work, the Property-Generated Solver benchmarks, or any of the QuickCheck industrial use cases — but performance on a hand-crafted demo SUT does not generalize to "this skill will make your tests better on your production code."

A more rigorous evaluation would test against codebases the evaluator did not control: pull a few open-source Python libraries with known test suites, ask each setup to generate property tests, and measure how the generated suites compare against the maintainers' own hand-written property tests (where they exist). That removes the demo-SUT bias and exposes the skills to whatever real-world ugliness they actually have to handle.

## Category counts can mislead

[EVAL.md §3](./EVAL.md#coverage-by-property-category) presents a category-coverage table. A check mark in that table means "at least one property in this category exists in this suite." It does not mean "this category is *covered well*." A suite with one weak invariant in category 5 looks the same in that table as a suite with five strong invariants in category 5.

A more rigorous evaluation would assess category coverage with depth, not breadth: for each category, how many *distinct facets* of the contract are pinned down? How redundant are the properties? Does the suite have one strong property per category or three weak ones? Hughes' bug-finding rate in *How to Specify It!* is one principled way to answer this: count how many bugs (from a benchmark with known bugs) a suite catches per category. Category counts are a first-pass proxy at best.

## Other things this comparison does not measure

A few axes the writeup deliberately did not try to score, listed here so a future evaluator can pick them up:

- **Shrinkability.** When a property fails, how minimal is the counterexample Hypothesis produces? Bad generator design degrades shrinking even when the property is correct. None of the three suites was scored on this.
- **Test execution time.** PBT suites can be slow if the generator is heavy or the property is expensive. None of the three suites is dramatically slow here, but a real evaluation would track time per property.
- **Maintainability after a refactor.** A property that's coupled to the current implementation breaks under a behavior-preserving refactor; an independent property survives. The right measurement is to apply a known-safe refactor and count which properties survive. The [implementation-coupling diagnostic](../skills/property-based-testing/references/interpreting-failures.md#the-five-possible-causes) in this repo's skill anticipates this; the eval doesn't measure it.
- **Generation cost.** Tokens consumed, time elapsed, retries needed. PBT-focused skills carry an upfront context cost. A real evaluation would put a price on that.
