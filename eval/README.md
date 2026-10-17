# Evaluation

Signal tests live in the harness, not in this directory.

The T04 harness is [`faustcoder/signal.py`](../faustcoder/signal.py).
Its fixtures are [`tests/fixtures/dsp/signal`](../tests/fixtures/dsp/signal).
Those fixtures are not a development suite and not a sealed holdout, and
they are not Faust `tests/impulse-tests` sources.

This directory stays empty of programs until a later task freezes a
development suite (spec §9). The sealed holdout is newly written and is
not stored here.
