from ld_eventsource.retry import BackoffParams, default_backoff_strategy


def test_default_backoff():
    base = 2
    bs = default_backoff_strategy()

    # The expected exponential delays are 2, 4, 8... so the offsets from base are 0, 2, 6

    r1 = bs(BackoffParams(base, 1))
    assert r1.offset == 0
    bs1 = r1.next_strategy or bs

    r2 = bs1(BackoffParams(base, 2))
    assert r2.offset == 2
    bs2 = r2.next_strategy or bs1

    r3 = bs2(BackoffParams(base, 3))
    assert r3.offset == 6
