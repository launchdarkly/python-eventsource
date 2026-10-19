import itertools
import time
from unittest.mock import patch

from ld_eventsource.config import *

err = Exception("sorry")


def test_always_raise():
    strategy = ErrorStrategy.always_fail()
    for i in range(100):
        should_raise, next_strategy = strategy.apply(err)
        assert should_raise is True
        strategy = next_strategy or strategy


def test_always_continue():
    strategy = ErrorStrategy.always_continue()
    for i in range(100):
        should_raise, next_strategy = strategy.apply(err)
        assert should_raise is False
        strategy = next_strategy or strategy


def test_max_attempts():
    strategy = ErrorStrategy.continue_with_max_attempts(2)

    should_raise, next1 = strategy.apply(err)
    assert should_raise is False

    should_raise, next2 = next1.apply(err)
    assert should_raise is False

    should_raise, next3 = next2.apply(err)
    assert should_raise is True


def test_max_time():
    strategy = ErrorStrategy.continue_with_time_limit(0.2)

    should_raise, next1 = strategy.apply(err)
    assert should_raise is False

    should_raise, next2 = next1.apply(err)
    assert should_raise is False

    time.sleep(0.25)

    should_raise, next3 = next2.apply(err)
    assert should_raise is True


def test_max_time_ignores_wall_clock_step():
    strategy = ErrorStrategy.continue_with_time_limit(0.2)

    # Each wall-clock read steps back one hour.
    wall_clock = itertools.count(1_000_000_000, -3600)
    with patch('time.time', side_effect=lambda: next(wall_clock)):
        should_raise, next1 = strategy.apply(err)
        assert should_raise is False

        time.sleep(0.25)

        should_raise, next2 = next1.apply(err)
        assert should_raise is True
