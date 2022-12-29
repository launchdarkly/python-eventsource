from typing import Callable, Optional, Tuple


class BackoffParams:
    """
    Parameters that are passed to the `BackoffStrategy` used with
    :func:`ld_eventsource.retry.default_retry_delay_strategy`.
    
    These are represented as a class, rather than being separate parameters to
    `BackoffStrategy`, for extensibility so that existing implementations will still work if
    more parameters are added.
    """
    def __init__(self, base_delay: float, current_retry_count: int):
        self.__base_delay = base_delay
        self.__current_retry_count = current_retry_count
    
    @property
    def base_delay(self) -> float:
        """
        The current base delay for the :class:`ld_eventsource.SSEClient`, in seconds. This is set
        when the :class:`ld_eventsource.SSEClient` is initialized, but can be overriden by a
        `retry:` directive in the stream.
        """
        return self.__base_delay

    @property
    def current_retry_count(self) -> int:
        """
        Starts at zero for the first connection attempt and increases with each retry, unless it
        is reset by the :func:`ld_eventsource.retry.default_retry_delay_strategy` logic.
        """
        return self.__current_retry_count


BackoffStrategy = Callable[[BackoffParams], 'BackoffResult']
"""
The signature of a function that computes a retry delay based on the number of attempts.

See :func:`ld_eventsource.retry.default_retry_delay_strategy` and
:func:`ld_eventsource.retry.default_backoff_strategy` for more details.
"""


class BackoffResult:
    """
    Values that are returned by the `BackoffStrategy` used with
    :func:`ld_eventsource.retry.default_retry_delay_strategy`.
    """
    def __init__(self, offset: float, next_strategy: Optional[BackoffStrategy] = None):
        self.__offset = offset
        self.__next_strategy = next_strategy
    
    @property
    def offset(self) -> float:
        """
        The additional time, in seconds, to add to the base delay before applying jitter.
        """
        return self.__offset
    
    @property
    def next_strategy(self) -> Optional[BackoffStrategy]:
        """
        If present, this will be used instead of the previous `BackoffStrategy` on the next attempt.
        This allows the `BackoffStrategy` to maintain state without being mutable.
        """
        return self.__next_strategy


def default_backoff_strategy() -> BackoffStrategy:
    """
    Provides the default retry delay backoff behavior for
    :func:`ld_eventsource.retry.default_retry_delay_strategy`.
    
    The default behavior is that the delay starts at the current base delay (specified either in
    the :class:`ld_eventsource.SSEClient` constructor, or by a `retry:` directive in the stream)
    and doubles on each subsequent attempt.
    """
    def apply(params: BackoffParams) -> BackoffResult:
        base = params.base_delay
        if base <= 0 or params.current_retry_count <= 1:
            return BackoffResult(0)
        return BackoffResult(base * (2 ** (params.current_retry_count - 1)) - base)
    return apply


def no_backoff() -> BackoffStrategy:
    """
    A `BackoffStrategy` that does not do any backoff: it never adds to the base delay (although
    a jitter might still be applied to the delay).
    """
    def apply(params: BackoffParams) -> BackoffResult:
        return BackoffResult(0)
    return apply
