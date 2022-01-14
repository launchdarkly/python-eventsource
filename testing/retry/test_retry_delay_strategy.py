from ld_eventsource.retry import BackoffParams, BackoffResult, JitterParams, JitterResult, RetryDelayParams, \
    default_retry_delay_strategy, no_backoff, no_jitter


def arithmetically_increasing_backoff(params: BackoffParams) -> BackoffResult:
    return BackoffResult(params.base_delay * params.current_retry_count)

def non_random_half_jitter(params: JitterParams) -> JitterResult:
    return JitterResult(params.delay / 2)


def test_retry_delay_default_backoff_and_jitter():
    ds = default_retry_delay_strategy(30)
    base = 1
    fake_time = 0
    last_delay = None
    for count in range(0, 3):
        fake_time += 1000
        result = ds(RetryDelayParams(base, fake_time))
        assert last_delay is None or result.delay > last_delay
        assert result.delay <= base * (2 ** count)
        last_delay = result.delay
        ds = result.next_strategy


def test_retry_delay_default_backoff_without_jitter():
    ds = default_retry_delay_strategy(30, jitter=no_jitter())
    base = 1
    fake_time = 0
    last_delay = None
    for count in range(0, 3):
        fake_time += 1000
        result = ds(RetryDelayParams(base, fake_time))
        assert last_delay is None or result.delay > last_delay
        assert result.delay == base * (2 ** count)
        last_delay = result.delay
        ds = result.next_strategy


def test_retry_delay_custom_backoff_without_jitter():
    ds = default_retry_delay_strategy(30, backoff=arithmetically_increasing_backoff, jitter=no_jitter())
    base = 1
    fake_time = 0
    for count in range(0, 3):
        fake_time += 1000
        result = ds(RetryDelayParams(base, fake_time))
        assert result.delay == base * (count + 1)
        ds = result.next_strategy


def test_retry_delay_default_jitter_without_backoff():
    ds = default_retry_delay_strategy(30, backoff=no_backoff())
    base = 1
    fake_time = 0
    for count in range(0, 3):
        fake_time += 1000
        result = ds(RetryDelayParams(base, fake_time))
        assert result.delay <= base
        ds = result.next_strategy


def test_retry_delay_custom_jitter_without_backoff():
    ds = default_retry_delay_strategy(30, backoff=no_backoff(), jitter=non_random_half_jitter)
    base = 1
    fake_time = 0
    for count in range(0, 3):
        fake_time += 1000
        result = ds(RetryDelayParams(base, fake_time))
        assert result.delay == base / 2
        ds = result.next_strategy


def test_max_delay():
    max = 4
    ds = default_retry_delay_strategy(max, jitter=no_jitter())
    base = 1.5
    fake_time = 0
    for count in range(0, 10000):
        fake_time += 1
        result = ds(RetryDelayParams(base, fake_time))
        if count < 2:
            assert result.delay == base * (count + 1)
        else:
            assert result.delay == max
        ds = result.next_strategy


def test_reset_interval():
    base = 1
    ds = default_retry_delay_strategy(30, jitter=no_jitter(), reset_interval=2000)

    r1 = ds(RetryDelayParams(base, 1000, last_success_time=None))
    assert r1.delay == 1
    ds = r1.next_strategy

    r2 = ds(RetryDelayParams(base, 2000, last_success_time=1000))
    assert r2.delay == 2
    ds = r2.next_strategy

    r3 = ds(RetryDelayParams(base, 3000, last_success_time=2000))
    assert r3.delay == 4
    ds = r3.next_strategy

    r4 = ds(RetryDelayParams(base, 5000, last_success_time=3000))
    assert r4.delay == 1
