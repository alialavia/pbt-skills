# `eval/` — comparison of three PBT setups on the same SUT

A reproducible, public-facing comparison of property-based tests produced by three Claude Code configurations against the same two-module system under test. Used as the empirical backing for claims about [`pbt-skills`](https://github.com/alialavia/pbt-skills) in the repository's README and in related writeups.

## What's here

- [`EVAL.md`](./EVAL.md) — the writeup. Seven sections, ~10–15 minutes to read.
- [`LESSONS.md`](./LESSONS.md) — methodological limits and what a stronger evaluation would look like.
- [`src/`](./src/) — the system under test: a stateless pricing engine and a stateful `Bank` class, with two deliberate bugs.
- [`tests/eb/`](./tests/eb/) — example-based baseline tests (context, not part of the three-way comparison).
- [`tests/no_skill/`](./tests/no_skill/), [`tests/trailofbits/`](./tests/trailofbits/), [`tests/this_repo/`](./tests/this_repo/) — the three property-based suites being compared.
- [`run_eval.sh`](./run_eval.sh) — bash script that runs all four suites and writes a JSON summary.
- [`results/`](./results/) — pytest logs and `summary.json` populated by `run_eval.sh`.

## Quick run

```sh
./run_eval.sh
```

Requires Python 3.10+, `pytest`, and `hypothesis`. Takes under a minute on a recent laptop. Per-suite logs land in `results/<suite>.log` and the machine-readable summary in `results/summary.json`.

## What the comparison shows, briefly

| Suite | Tests | Passed | Failed | Catches shipping bug | Catches self-transfer bug |
|---|---:|---:|---:|:---:|:---:|
| `eb` (example-based) | 26 | 26 | 0 | ✗ | ✗ |
| `no_skill` | 13 | 11 | 2 | ✓ | ✓ |
| `trailofbits` | 22 | 20 | 2 | ✓ | ✓ |
| `this_repo` | 29 | 26 | 3 | ✓ | ✓ |

All three PBT suites catch both planted bugs. The interesting differences are in oracle independence, generator hygiene, composition oracles, rounding characterization, and rejection-test coverage — see [EVAL.md §4](./EVAL.md#4-quality-analysis-where-each-suite-wins-and-loses).

## What this is NOT

Not an experiment — there is no controlled methodology behind it. Single one-shot generation per suite, single task, single grader (the author of this repo's skill is the author of this writeup). See [LESSONS.md](./LESSONS.md) for the limits, and what a more rigorous follow-up would do differently.

If you find this writeup unfair to TRAILOFBITS, or want to challenge a specific claim, the suites are all here verbatim and the runner is reproducible. Open an issue.
