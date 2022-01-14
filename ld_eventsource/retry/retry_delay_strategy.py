from ld_eventsource.retry.backoff import BackoffParams, BackoffStrategy, default_backoff_strategy
from ld_eventsource.retry.jitter import JitterParams, JitterStrategy, default_jitter_strategy

from typing import Callable, Optional, Tuple


class RetryDelayParams:
    """
    Parameters that :class:`ld_eventsource.SSEClient` will pass to the `RetryDelayStrategy`
    when a retry is necessary.
    
    These are represented as a class, rather than being separate parameters to
    `RetryDelayStrategy`, for extensibility so that existing implementations will still work if
    more parameters are added.
    """
    def __init__(
        self,
        base_delay: float,
        current_time: float,
        last_success_time: Optional[float] = None
    ):
        self.__base_delay = base_delay
        self.__current_time = current_time
        self.__last_success_time = last_success_time
    
    @property
    def base_delay(self) -> float:
        """
        The current value of the base delay, in seconds. This is the value that can be changed
        by a `retry:` field in the stream data.
        """
        return self.__base_delay

    @property
    def current_time(self) -> float:
        """
        The current time in epoch seconds. This is passed in as part of the state, instead of
        letting the `RetryDelayStrategy` compute it, for testability.
        """
        return self.__current_time
    
    @property
    def last_success_time(self):
        """
        This is only set if the stream was in a good state prior to the most recent failed attempt.
        It is the time (in epoch seconds) when the stream entered a good state.
        """
        return self.__last_success_time


RetryDelayStrategy = Callable[[RetryDelayParams], 'RetryDelayResult']
"""
The signature of a function that computes how long to wait before retrying a connection.

See :class:`ld_eventsource.SSEClient` and :func:`ld_eventsource.retry.default_retry_delay_strategy`
for more details.
"""


class RetryDelayResult:
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
        The computed delay, in seconds, after applying both backoff and jitter.
        """
        return self.__delay
    
    @property
    def next_strategy(self) -> Optional[RetryDelayStrategy]:
        """
        If present, this will be used instead of the previous `RetryDelayStrategy` on the next attempt.
        This allows the `RetryDelayStrategy` to maintain state without being mutable.
        """
        return self.__next_strategy


class _DefaultRetryDelayStrategy:
    def __init__(
        self,
        max_delay: float,
        reset_interval: Optional[float],
        backoff: BackoffStrategy,
        jitter: JitterStrategy,
        current_retry_count: int
    ):
        self.__max_delay = max_delay
        self.__reset_interval = reset_interval
        self.__backoff = backoff
        self.__jitter = jitter
        self.__current_retry_count = current_retry_count

    def apply(
        self,
        params: RetryDelayParams
    ) -> Tuple[float, RetryDelayStrategy]:
        new_retry_count = self.__current_retry_count
        if self.__reset_interval \
            and params.last_success_time \
            and (params.current_time - params.last_success_time >= self.__reset_interval):
            new_retry_count = 0
        new_retry_count += 1
        
        backoff_params = BackoffParams(params.base_delay, new_retry_count)
        backoff_result = self.__backoff(backoff_params)
        jitter_result = self.__jitter(JitterParams(backoff_result.delay, backoff_params))
        
        delay = jitter_result.delay
        if delay > self.__max_delay:
            delay = self.__max_delay
            # increasing the count after this point would only make it likelier for us to get a math overflow
            # in the backoff calculation
            new_retry_count -= 1

        updated_strategy = _DefaultRetryDelayStrategy(
            self.__max_delay,
            self.__reset_interval,
            backoff_result.next_strategy or self.__backoff,
            jitter_result.next_strategy or self.__jitter,
            new_retry_count)
        return RetryDelayResult(delay, next_strategy=updated_strategy.apply)


def default_retry_delay_strategy(
    max_delay: float = 30,
    backoff: BackoffStrategy = default_backoff_strategy(),
    jitter: JitterStrategy = default_jitter_strategy(),
    reset_interval: Optional[float] = None
) -> RetryDelayStrategy:
    """
    Provides the default retry delay behavior for :class:`ld_eventsource.SSEClient`, which includes
    customizable backoff and jitter options.

    The behavior is as follows:

    * There is a "current retry count" which starts at 1 and increases after each retry. It can be
    automatically reset if `reset_interval` is specified.
    * On each attempt, the `BackoffStrategy` function is called, passing the current retry count
    and the current base delay in :class:`ld_eventsource.retry.BackoffParams`.
    * The time value returned by the `BackoffStrategy` is then passed to the `JitterStrategy` to
    provide pseudo-random variation.
    * The resulting time value is then pinned so it cannot exceed `max_delay`.

    :param max_delay: the maximum possible delay value, in seconds; default is 30 seconds
    :param backoff: a `BackoffStrategy`, defined as a function that takes
      :class:`ld_eventsource.retry.BackoffParams` and returns :class:`ld_eventsource.retry.BackoffResult`
    :param jitter: a `JitterStrategy`, defined as a function that takes
      :class:`ld_eventsource.retry.JitterParams` and returns :class:`ld_eventsource.retry.JitterResult`
    :param reset_interval: if provided, this means the "previous attempts" count should be reset
      whenever at least that amount of time (in seconds) has passed since
      :prop:`ld_eventsource.retry.BackoffParams.last_success_time`
    """
    return _DefaultRetryDelayStrategy(max_delay, reset_interval, backoff, jitter, 0).apply
