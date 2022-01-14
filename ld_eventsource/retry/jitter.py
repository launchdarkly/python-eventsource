from ld_eventsource.retry.backoff import BackoffParams

from random import Random
import time
from typing import Callable, Optional


class JitterParams:
    """
    Parameters that are passed to the `JitterStrategy` used with
    :func:`ld_eventsource.retry.default_retry_delay_strategy`.
    
    These are represented as a class, rather than being separate parameters to
    `JitterStrategy`, for extensibility so that existing implementations will still work if
    more parameters are added.
    """
    def __init__(self, delay: float, backoff_params: BackoffParams):
        self.__delay = delay
        self.__backoff_params = backoff_params
    
    @property
    def delay(self) -> float:
        """
        The delay, in seconds, that was computed by the backoff strategy.
        """
        return self.__delay

    @property
    def backoff_params(self) -> BackoffParams:
        """
        The parameters that were previously passed to the backoff strategy, in case the jitter strategy
        wants to do anything differently depending on (for instance) the number of attempts.
        """
        return self.__backoff_params


JitterStrategy = Callable[[JitterParams], 'JitterResult']
"""
The signature of a function that applies pseudo-random variation to a retry delay.

See :func:`ld_eventsource.retry.default_retry_delay_strategy` and
:func:`ld_eventsource.retry.default_jitter_strategy` for more details.
"""


class JitterResult:
    """
    Values that are returned by the `JitterStrategy` used with
    :func:`ld_eventsource.retry.default_retry_delay_strategy`.
    """
    def __init__(self, delay: float, next_strategy: Optional[JitterStrategy] = None):
        self.__delay = delay
        self.__next_strategy = next_strategy
    
    @property
    def delay(self) -> float:
        """
        The computed delay, in seconds, before applying jitter.
        """
        return self.__delay
    
    @property
    def next_strategy(self) -> Optional[JitterStrategy]:
        """
        If present, this will be used instead of the previous `JitterStrategy` on the next attempt.
        This allows the `JitterStrategy` to maintain state without being mutable.
        """
        return self.__next_strategy


class _DefaultJitterStrategy:
    def __init__(self, ratio: float, seed: float, random: Random):
        self.__ratio = ratio
        self.__seed = seed
        self.__random = random

    def apply(self, params: JitterParams) -> JitterResult:
        # To avoid having this object contain mutable state, we create a new Random with the same
        # state as our previous Random before using it.
        rand_state = self.__random.getstate()
        new_random = Random(self.__seed)
        new_random.setstate(rand_state)

        result = params.delay - (new_random.random() * self.__ratio * params.delay)

        updated_strategy = _DefaultJitterStrategy(self.__ratio, self.__seed, new_random)
        return JitterResult(result, next_strategy=updated_strategy.apply)


def default_jitter_strategy(ratio: float = 0.5, random_seed: Optional[float] = None) -> JitterStrategy:
    """
    Provides the default retry delay jitter behavior for
    :func:`ld_eventsource.retry.default_retry_delay_strategy`.
    
    The default behavior is that the computed backoff delay will be decreased by a pseudo-random
    proportion between zero and `ratio`. That is, if `ratio` is 0.25, then each delay N may be
    decreased by up to one-quarter of N. If `ratio` is zero, there is no jitter.

    :param ratio: the jitter multiplier, between zero and 1 inclusive
    :param random_seed: if specified, the random number generator uses this seed (for test
      reproducibility)
    """
    seed = time.time() if random_seed is None else random_seed
    return _DefaultJitterStrategy(ratio, seed, Random(seed)).apply


def no_jitter() -> JitterStrategy:
    """
    A `JitterStrategy` that does not do any jitter: it always returns the exact computed backoff delay.
    """
    def apply(params: JitterParams) -> JitterResult:
        return JitterResult(params.delay)
    return apply
