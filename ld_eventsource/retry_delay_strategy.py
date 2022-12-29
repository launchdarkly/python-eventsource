from random import Random
import time
from typing import Callable, Optional


RetryDelayStrategy = Callable[[float], 'RetryDelayResult']
"""
The signature of a function that computes how long to wait before retrying a connection. The
input parameter is the current base reconnect delay.

See :class:`ld_eventsource.SSEClient` and :func:`ld_eventsource.default_retry_delay_strategy`
for more details.
"""


class _ReusableRandom:
    def __init__(self, seed: float):
        self.__seed = seed
        self.__random = Random(seed)
    
    def clone(self):
        state = self.__random.getstate()
        ret = _ReusableRandom(self.__seed)
        ret.__random.setstate(state)
        return ret

    def random(self) -> float:
        return self.__random.random()


class RetryDelayResult:
    """Return type of RetryDelayStrategy."""
    def __init__(
        self,
        delay: float,
        next_strategy: Optional[RetryDelayStrategy] = None
    ):
        self.__delay = delay
        self.__next_strategy = next_strategy
    
    @property
    def delay(self) -> float:
        """
        The computed delay, in seconds, after applying whatever transformation the strategy may
        use from the base delay.
        """
        return self.__delay
    
    @property
    def next_strategy(self) -> Optional[RetryDelayStrategy]:
        """
        If present, this will be used instead of the previous RetryDelayStrategy on the next attempt.
        This allows the RetryDelayStrategy to maintain state without being mutable.
        """
        return self.__next_strategy


class _DefaultRetryDelayStrategy:
    def __init__(
        self,
        max_delay: float,
        backoff_multiplier: float,
        jitter_multiplier: float,
        last_base_delay: float,
        random: _ReusableRandom
    ):
        self.__max_delay = max_delay
        self.__backoff_multiplier = backoff_multiplier
        self.__jitter_multiplier = jitter_multiplier
        self.__last_base_delay = last_base_delay
        self.__random = random

    def apply(
        self,
        base_delay: float
    ) -> RetryDelayResult:
        next_base_delay = base_delay if self.__last_base_delay == 0 else \
            self.__last_base_delay * self.__backoff_multiplier
        if self.__max_delay > 0 and next_base_delay > self.__max_delay:
            next_base_delay = self.__max_delay
        adjusted_delay = next_base_delay

        random = self.__random
        if self.__jitter_multiplier > 0:
            # To avoid having this object contain mutable state, we create a new Random with the same
            # state as our previous Random before using it.
            random = random.clone()
            adjusted_delay -= (random.random() * self.__jitter_multiplier * adjusted_delay)
        
        next_strategy = _DefaultRetryDelayStrategy(
            self.__max_delay,
            self.__backoff_multiplier,
            self.__jitter_multiplier,
            next_base_delay,
            random
        )
        return RetryDelayResult(adjusted_delay, next_strategy.apply)


def default_retry_delay_strategy(
    max_delay: Optional[float] = 30,
    backoff_multiplier: Optional[float] = 2,
    jitter_multiplier: Optional[float] = 0.5
) -> RetryDelayStrategy:
    """
    Provides the default retry delay behavior for :class:`SSEClient`, which includes
    customizable backoff and jitter options.

    The behavior is as follows:

    - Start with the configured base delay as set by the ``initial_retry_delay`` parameter to
      :class:`EventSource`.
    - On each subsequent attempt, multiply the base delay by `backoff_multiplier`, giving the
      current base delay.
    - If `max_delay` is set and is greater than zero, the base delay is pinned to be no greater
      than that value.
    - If `jitter_multiplier` is set and is greater than zero, the actual delay for each attempt is
      equal to the current base delay minus a pseudo-random number equal to that ratio times itself.
      For instance, a jitter multiplier of 0.25 would mean that a base delay of 1000 is changed to a
      value in the range [750, 1000].
    
    :param max_delay: the maximum possible delay value, in seconds; default is 30 seconds
    :param backoff_multiplier: the exponential backoff factor
    :param jitter_multiplier: a fraction from 0.0 to 1.0 for how much of the delay may be
      pseudo-randomly subtracted
    """
    strategy = _DefaultRetryDelayStrategy(max_delay or 0, backoff_multiplier or 1, jitter_multiplier or 0,
        0, _ReusableRandom(time.time()))
    return strategy.apply
