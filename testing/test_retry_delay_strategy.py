from ld_eventsource import *


def test_backoff_with_no_jitter_and_no_max():
    base = 4
    strategy = default_retry_delay_strategy(max_delay=None, backoff_multiplier=2, jitter_multiplier=None)

    r1 = strategy(base)
    assert r1.delay == base

    r2 = r1.next_strategy(base)
    assert r2.delay == base * 2

    r3 = r2.next_strategy(base)
    assert r3.delay == base * 4

    r4 = r3.next_strategy(base)
    assert r4.delay == base * 8


def test_backoff_with_no_jitter_and_max():
    base = 4
    max = base * 4 + 3
    strategy = default_retry_delay_strategy(max_delay=max, backoff_multiplier=2, jitter_multiplier=None)

    r1 = strategy(base)
    assert r1.delay == base

    r2 = r1.next_strategy(base)
    assert r2.delay == base * 2

    r3 = r2.next_strategy(base)
    assert r3.delay == base * 4

    r4 = r3.next_strategy(base)
    assert r4.delay == max


def test_no_backoff_and_no_jitter():
    base = 4
    strategy = default_retry_delay_strategy(max_delay=None, backoff_multiplier=1, jitter_multiplier=None)

    r1 = strategy(base)
    assert r1.delay == base

    r2 = r1.next_strategy(base)
    assert r2.delay == base

    r3 = r2.next_strategy(base)
    assert r3.delay == base


def test_backoff_with_jitter():
    base = 4
    backoff = 2
    max = base * backoff * backoff + 3
    jitter = 0.25
    strategy = default_retry_delay_strategy(max_delay=max, backoff_multiplier=backoff, jitter_multiplier=jitter)

    r1 = verify_jitter(strategy, base, base, jitter)
    r2 = verify_jitter(r1.next_strategy, base, base * backoff, jitter)
    r3 = verify_jitter(r2.next_strategy, base, base * backoff * backoff, jitter)
    verify_jitter(r3.next_strategy, base, max, jitter)


def zero_base_delay_always_produces_zero():
    strategy = default_retry_delay_strategy()
    for i in range(5):
        r = strategy(0)
        assert r.delay == 0
        r = r.next_strategy


def verify_jitter(strategy: RetryDelayStrategy, base: float, base_with_backoff: float, jitter: float) -> RetryDelayResult:
    # We can't 100% prove that it's using the expected jitter ratio, since the result
    # is pseudo-random, but we can at least prove that repeated computations don't
    # fall outside the expected range and aren't all equal.
    last_result = None  # type: Optional[RetryDelayResult]
    at_least_one_was_different = False
    for i in range(100):
        result = strategy(base)
        assert result.delay >= base_with_backoff * jitter
        assert result.delay <= base_with_backoff
        if last_result is not None and last_result != result.delay:
            at_least_one_was_different = True
        last_result = result
    assert at_least_one_was_different
    assert last_result is not None
    return last_result
