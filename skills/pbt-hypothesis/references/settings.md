# Hypothesis Settings and Configuration

Brief notes on tuning Hypothesis for different contexts. Most defaults are fine for local development; CI and slow tests need attention.

## Profiles

Define settings profiles for different contexts:

```python
# conftest.py
from hypothesis import settings, Verbosity, HealthCheck

settings.register_profile("dev", max_examples=50, verbosity=Verbosity.verbose)
settings.register_profile("ci", max_examples=500, deadline=None)
settings.register_profile("nightly", max_examples=10000, deadline=None)
settings.register_profile("debug", max_examples=20, verbosity=Verbosity.debug)

import os
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
```

Then in CI: `HYPOTHESIS_PROFILE=ci pytest`. For overnight regression runs: `HYPOTHESIS_PROFILE=nightly`.

## `max_examples`

The number of generated inputs Hypothesis will try per test. Default is 100.

- **Dev**: 50 — fast feedback loop.
- **CI**: 500–1000 — catches more, slows runs.
- **Nightly / pre-release**: 10000+ — find the rare bugs.

For very fast property tests, you can crank `max_examples` very high. For slow tests (database, network), keep it low and rely on the `example database` (next section) to remember past failures.

## The example database

Hypothesis records every failure to a local database (`.hypothesis/examples` by default). On the next run, those examples are tried first. This means:

- Once a bug is found, subsequent runs reproduce it immediately.
- The database accumulates a regression suite automatically.
- **Commit the example database for important projects** (or at least share it via CI cache).

```python
from hypothesis import settings
from hypothesis.database import DirectoryBasedExampleDatabase

settings.register_profile("ci", database=DirectoryBasedExampleDatabase(".hypothesis-ci-examples"))
```

## `deadline`

Per-example time limit. Default is 200ms. If an example takes longer, Hypothesis fails the test as a "deadline exceeded."

- For pure-Python algorithmic code, 200ms is appropriate.
- For tests that hit a database, filesystem, or network, set `deadline=None` to disable.
- For machine learning model evaluation, set generous deadlines (`deadline=timedelta(seconds=30)`).

```python
from datetime import timedelta

@settings(deadline=timedelta(seconds=5))
@given(...)
def test_slow_thing(...): ...
```

## Health checks

Hypothesis warns about strategies that produce mostly-filtered inputs, are too slow, or have other pathologies. Don't silence health checks without understanding them — they're usually pointing at a strategy design problem.

```python
# Don't do this without good reason
@settings(suppress_health_check=[HealthCheck.filter_too_much])
```

The right fix is almost always to redesign the strategy.

## Verbosity

For debugging, `Verbosity.verbose` shows every example generated. `Verbosity.debug` shows shrinking steps too. Useful when a test is producing weird counterexamples.

## Reproducing a specific failure

When Hypothesis reports a failure, it prints a seed-like blob:

```
Falsifying example: test_thing(xs=[1, 0])

You can reproduce this example by temporarily adding @reproduce_failure('6.x.y', b'...') as a decorator on your test case
```

Paste that `@reproduce_failure` decorator onto the test temporarily to re-run the same counterexample without searching.

## CI considerations

- Use a higher `max_examples` in CI than locally.
- Disable deadlines for tests that touch external resources.
- Cache `.hypothesis/` between CI runs so found failures persist.
- Surface Hypothesis's statistics (number of examples, shrinks) in CI logs — they help diagnose flaky tests.

```python
@settings(print_blob=True)  # always print the reproduction blob
```

## Don't tune until you need to

Default settings are good. Tune when you have a specific reason: tests timing out, strategies filtering too much, CI taking too long, a bug that only appears at high `max_examples`. Premature tuning is just noise in the test config.
