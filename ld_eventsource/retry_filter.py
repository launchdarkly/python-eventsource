from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError
from ld_eventsource.request_params import RequestParams

from typing import Callable, Optional


class RetryFilterParams:
    """
    Parameters that are passed to the `RetryFilter` used by :class:`ld_eventsource.SSEClient`.
    """
    def __init__(
        self,
        error: Optional[Exception]
    ):
        self.__error = error
    
    @property
    def error(self) -> Optional[Exception]:
        """
        The exception that was encountered by the client, if any.
        
        If this is an exception class other than :class:`ld_eventsource.errors.HTTPStatusError` or
        :class:`ld_eventsource.errors.HTTPContentTypeError`, it can be assumed to be an I/O error
        thrown by `urllib3`.

        A value of `None` means that the stream terminated without an error, that is, the server
        sent an explicit EOF as defined by chunked transfer encoding before closing the connection.
        """
        return self.__error


class RetryFilterResult:
    """
    Values that are returned by the `RetryFilter` used by :class:`ld_eventsource.SSEClient`,
    indicating what the client should do next.
    """
    def __init__(
        self,
        should_retry: bool,
        request_params: Optional[RequestParams] = None
    ):
        self.__should_retry = should_retry
        self.__request_params = request_params
    
    @property
    def should_retry(self) -> bool:
        """
        True if the client should attempt to reconnect.

        If this value is False, the behavior of the client depends on whether it is still in
        the :class:`ld_eventsource.SSEClient` constructor or not. If the connection attempt was
        happening within the constructor, then an exception is thrown from the constructor. If
        the constructor has already returned, then a :class:`ld_eventsource.Fault` is generated
        which can be read from :prop:`ld_eventsource.SSEClient.all`, after which both
        :prop:`ld_eventsource.SSEClient.events` and :prop:`ld_eventsource.SSEClient.events`
        stop returning values.
        """
        return self.__should_retry
    
    @property
    def request_params(self) -> Optional[RequestParams]:
        """
        If specified, causes :class:`ld_eventsource.SSEClient` to use these request parameters
        instead of the original request parameters for subsequent reconnections.
        """
        return self.__request_params


RetryFilter = Callable[[RetryFilterParams], RetryFilterResult]
"""
The signature of a function that controls retries after a stream disconnection.

See :class:`ld_eventsource.SSEClient` and :func:`ld_eventsource.retry.default_retry_filter`
for more details.
"""


def default_retry_filter() -> RetryFilter:
    """
    Default retry behavior if you do not specify a `retry_filter` parameter for
    :class:`ld_eventsource.SSEClient`.

    The default behavior is that the client always retries after an I/O error or end of stream,
    but never retries if an HTTP response had an error status (:class:`ld_eventsource.errors.HTTPStatusError`)
    or had the wrong content type (:class:`ld_eventsource.errors.HTTPContentTypeError`).
    """
    def apply(params: RetryFilterParams) -> RetryFilterResult:
        return RetryFilterResult(
            (not isinstance(params.error, HTTPStatusError)) and (not isinstance(params.error, HTTPContentTypeError))
        )
    return apply
