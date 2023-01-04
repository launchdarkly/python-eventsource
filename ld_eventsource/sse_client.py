from ld_eventsource.actions import *
from ld_eventsource.errors import *
from ld_eventsource.config import *
from ld_eventsource.reader import _BufferedLineReader, _SSEReader
from ld_eventsource.request_params import *

import logging
import time
from typing import Iterable, Iterator, Optional, Union
from urllib3 import HTTPResponse, PoolManager
from urllib3.exceptions import MaxRetryError
from urllib3.util import Retry


class SSEClient:
    """
    A Server-Sent Events client that uses ``urllib3``.

    This is a synchronous implementation which blocks the caller's thread when reading events or
    reconnecting. It can be run on a worker thread. The expected usage is to create an `SSEClient`
    instance, then read from it using the iterator properties :attr:`events` or :attr:`all`.
    
    Connection failures and error responses can be handled in various ways depending on the
    constructor parameters. The default behavior, if no non-default parameters are passed, is
    that the client will attempt to reconnect as many times as necessary if a connection is
    dropped or cannot be made; but if a connection is made and returns an invalid response
    (non-2xx status, 204 status, or invalid content type), it will not retry. This behavior can
    be customized with ``error_strategy``. The client will automatically follow 3xx redirects.
    
    For any non-retryable error, if this is the first connection attempt then the constructor
    will throw an exception (such as :class:`.HTTPStatusError`). Or, if a
    successful connection was made so the constructor has already returned, but a
    non-retryable error occurs subsequently, the iterator properties will simply run out of
    values to indicate that the ``SSEClient`` is finished (if you are reading :attr:`all`, it will
    first yield a :class:`.Fault` to indicate what the error was).

    To avoid flooding the server with requests, it is desirable to have a delay before each
    reconnection. There is a base delay set by ``initial_retry_delay`` (which can be overridden
    by the stream if the server sends a ``retry:`` line). By default, as defined by
    :meth:`.RetryDelayStrategy.default()`, this delay will double with each subsequent retry,
    and will also have a pseudo-random jitter subtracted. You can customize this behavior with
    ``retry_delay_strategy``.
    """

    chunk_size = 10000

    def __init__(
        self, 
        request: Union[str, RequestParams],
        initial_retry_delay: float=1,
        retry_delay_strategy: Optional[RetryDelayStrategy]=None,
        retry_delay_reset_threshold: float=60,
        error_strategy: Optional[ErrorStrategy]=None,
        last_event_id: Optional[str]=None,
        http_pool: Optional[PoolManager]=None,
        logger: Optional[logging.Logger]=None
    ):
        """
        Creates a client instance.

        The client is created in an inactive state. It will not try to make a stream connection
        until either you call :meth:`start()`, or you attempt to read events from
        :attr:`events` or :attr:`all`.

        :param request: either a stream URL or a :class:`RequestParams` instance
        :param initial_retry_delay: the initial delay before reconnecting after a failure,
            in seconds; this can increase as described in :class:`SSEClient`
        :param retry_delay_strategy: allows customization of the delay behavior for retries; if
            not specified, uses :meth:`.RetryDelayStrategy.default()`
        :param retry_delay_reset_threshold: the minimum amount of time that a connection must
            stay open before the SSEClient resets its retry delay strategy
        :param error_strategy: allows customization of the behavior after a stream failure; if
            not specified: uses :meth:`.ErrorStrategy.always_fail()`
        :param last_event_id: if provided, the ``Last-Event-Id`` value will be preset to this
        :param http_pool: optional urllib3 ``PoolManager`` to provide an HTTP client
        :param logger: if provided, log messages will be written here
        """
        if isinstance(request, RequestParams):
            self.__request_params = request  # type: RequestParams
        elif isinstance(request, str):
            self.__request_params = RequestParams(url=request)
        else:
            raise TypeError("request must be either a string or RequestParams")

        self.__base_retry_delay = initial_retry_delay
        self.__base_retry_delay_strategy = retry_delay_strategy or RetryDelayStrategy.default()
        self.__retry_delay_reset_threshold = retry_delay_reset_threshold
        self.__current_retry_delay_strategy = self.__base_retry_delay_strategy
        self.__next_retry_delay = 0

        self.__base_error_strategy = error_strategy or ErrorStrategy.always_fail()
        self.__current_error_strategy = self.__base_error_strategy
        
        self.__last_event_id = last_event_id

        self.__http = http_pool or PoolManager()
        self.__http_should_close = (http_pool is None)
        
        if logger is None:
            logger = logging.getLogger('launchdarkly-eventsource.null')
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
        self.__logger = logger
      
        self.__connected_time = self.__disconnected_time = 0  # type: float

        self.__closed = False
        self.__response = None  # type: Optional[HTTPResponse]
        self.__stream = None  # type: Optional[Iterator[bytes]]

    def start(self):
        """
        Attempts to start the stream if it is not already active.

        If there is not an active stream connection, this method attempts to start one using
        the previously configured parameters. If successful, it returns and you can proceed
        to read events. You should only read events on the same thread where you called
        :meth:`start()`.

        If the connection fails, the behavior depends on the configured :class:`.ErrorStrategy`.
        The default strategy is to raise an exception, but you can configure it to continue
        instead, in which case :meth:`start()` will keep retrying until the :class:`.ErrorStrategy`
        says to give up.

        If the stream was previously active and then failed, :meth:`start()` will sleep for
        some amount of time-- the retry delay-- before trying to make the connection. The
        retry delay is determined by the ``initial_retry_delay``, ``retry_delay_strategy``,
        and ``retry_delay_reset_threshold`` parameters to :class:`SSEClient`.
        """
        self._try_start(False)

    def close(self):
        """
        Permanently shuts down this client instance and closes any active connection.
        """
        self.__closed = True
        if self.__response:
            self.__response.release_conn()
        if self.__http_should_close:
            self.__http.clear()
    
    @property
    def all(self) -> Iterable[Action]:
        """
        An iterable series of notifications from the stream.
        
        Each of these can be any subclass of :class:`.Action`: :class:`.Event`, :class:`.Comment`,
        :class:`.Start`, or :class:`.Fault`.

        You can use :attr:`events` instead if you are only interested in Events.

        Iterating over this property automatically starts or restarts the stream if it is not
        already active, so you do not need to call :meth:`start()` unless you want to verify that
        the stream is connected before trying to read events.
        """
        while True:
            # Reading implies starting the stream if it isn't already started. We might also
            # be restarting since we could have been interrupted at any time.
            while self.__stream is None:
                fault = self._try_start(True)
                # return either a Start action or a Fault action
                yield Start() if fault is None else fault
            
            lines = _BufferedLineReader.lines_from(self.__stream)
            reader = _SSEReader(lines, self.__last_event_id, None)
            error = None  # type: Optional[Exception]
            try:
                for ec in reader.events_and_comments:
                    yield ec
                # If we finished iterating all of reader.events_and_comments, it means the stream
                # was closed without an error.
                self.__stream = None
            except Exception as e:
                if self.__closed:
                    # It's normal to get an I/O error if we force-closed the stream to shut down
                    return
                error = e
                self.__stream = None
            finally:
                self.__last_event_id = reader.last_event_id

            # We've hit an error, so ask the ErrorStrategy what to do: raise an exception or yield a Fault.
            self._compute_next_retry_delay()
            fail_or_continue, self.__current_error_strategy = self.__current_error_strategy.apply(error)
            if fail_or_continue == ErrorStrategy.FAIL:
                if error is None:
                    # If error is None, the stream was ended normally by the server. Just stop iterating.
                    yield Fault(None)  # this is only visible if you're reading from "all"
                    return
                raise error
            yield Fault(error)
            continue  # try to connect again

    @property
    def events(self) -> Iterable[Event]:
        """
        An iterable series of :class:`.Event` objects received from the stream.

        Use :attr:`all` instead if you also want to know about other kinds of occurrences.

        Iterating over this property automatically starts or restarts the stream if it is not
        already active, so you do not need to call :meth:`start()` unless you want to verify that
        the stream is connected before trying to read events.
        """
        for item in self.all:
            if isinstance(item, Event):
                yield item

    @property
    def next_retry_delay(self) -> float:
        """
        The retry delay that will be used for the next reconnection, in seconds, if the stream
        has failed or ended.
        
        This is initially zero, because SSEClient does not compute a retry delay until there is
        a failure. If you have just received an exception or a :class:`.Fault`, or if you were
        iterating through events and the events ran out because the stream closed, the value
        tells you how long SSEClient will sleep before the next reconnection attempt. The value
        is computed by applying the configured :class:`.RetryDelayStrategy` to the base retry delay.
        """
        return self.__next_retry_delay
    
    def _compute_next_retry_delay(self):
        if self.__retry_delay_reset_threshold > 0 and self.__connected_time != 0:
            connection_duration = time.time() - self.__connected_time
            if connection_duration >= self.__retry_delay_reset_threshold:
                self.__current_retry_delay_strategy = self.__base_retry_delay_strategy
        self.__next_retry_delay, self.__current_retry_delay_strategy = \
            self.__current_retry_delay_strategy.apply(self.__base_retry_delay)

    def _try_start(self, can_return_fault: bool) -> Optional[Fault]:
        if self.__stream is not None:
            return None
        while True:
            if self.__next_retry_delay > 0:
                delay = self.__next_retry_delay if self.__disconnected_time == 0 else \
                    self.__next_retry_delay - (time.time() - self.__disconnected_time)
                if delay > 0:
                    self.__logger.info("Will reconnect after delay of %fs" % delay)
                    time.sleep(delay)

            self.__logger.info("Connecting to stream at %s" % self.__request_params.url)
            try:
                resp = self._do_request()
            except Exception as e:
                self.__disconnected_time = time.time()
                self._compute_next_retry_delay()
                fail_or_continue, self.__current_error_strategy = self.__current_error_strategy.apply(e)
                if fail_or_continue == ErrorStrategy.FAIL:
                    raise e
                if can_return_fault:
                    return Fault(e)
                # If can_return_fault is false, it means the caller explicitly called start(), in
                # which case there's no way to return a Fault so we just keep retrying transparently.
                continue

            self.__response = resp
            self.__connected_time = time.time()
            self.__stream = resp.stream(amt=self.chunk_size)
            self.__current_error_strategy = self.__base_error_strategy
            return None

    def _do_request(self) -> HTTPResponse:
        params = self.__request_params
        headers = params.headers.copy() if params.headers else {}
        headers['Cache-Control'] = 'no-cache'
        headers['Accept'] = 'text/event-stream'

        if self.__last_event_id:
            headers['Last-Event-ID'] = self.__last_event_id

        request_options = params.urllib3_request_options.copy() if params.urllib3_request_options else {}
        request_options['headers'] = headers

        try:
            resp = self.__http.request(
                'GET',
                params.url,
                preload_content=False,
                retries=Retry(total=None, read=0, connect=0, status=0, other=0, redirect=3),
                **request_options)
        except MaxRetryError as e:
            reason = e.reason  # type: Optional[Exception]
            if reason is not None:
                raise reason  # e.reason is the underlying I/O error        
        if resp.status >= 400 or resp.status == 204:
            raise HTTPStatusError(resp.status)
        content_type = resp.getheader('Content-Type')
        if content_type is None or not str(content_type).startswith("text/event-stream"):
            raise HTTPContentTypeError(content_type or '')
        return resp

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


__all__ = ['SSEClient']
