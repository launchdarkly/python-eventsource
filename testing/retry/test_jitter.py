from ld_eventsource.retry import BackoffParams, JitterParams, default_jitter_strategy

from math import trunc
from random import Random


def test_default_jitter():
    base = 1
    seed = 1000
    js = default_jitter_strategy(0.5, seed)

    backoff_params = BackoffParams(0, 0) # the API requires this, but the default jitter strategy shouldn't care

    r1 = js(JitterParams(base, backoff_params))
    assert trunc(r1.offset * 1000) == 388
    js1 = r1.next_strategy or js

    r2 = js1(JitterParams(base, backoff_params))
    assert trunc(r2.offset * 1000) == 334
    js2 = r2.next_strategy or js1

    r3 = js2(JitterParams(base, backoff_params))
    assert trunc(r3.offset * 1000) == 49

    # Check that we're returning new states rather than mutating the old ones
    r2a = js1(JitterParams(base, backoff_params))
    assert trunc(r2a.offset * 1000) == 334
