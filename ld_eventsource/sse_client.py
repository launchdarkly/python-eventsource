from ld_eventsource.errors import *
from ld_eventsource.event import *
from ld_eventsource.reader import _BufferedLineReader, _SSEReader
from ld_eventsource.request_params import *
from ld_eventsource.retry import *

import logging
import time
from typing import Iterable, Optional, Union
from urllib3 import PoolManager
from urllib3.exceptions import MaxRetryError
from urllib3.util import Retry


class SSEClient:
    """
    A Server-Sent Events client that uses `urllib3`.

    This is a synchronous implementation which blocks the caller's thread when reading events or
    reconnecting. It can be run on a worker thread. The expected usage is to create an `SSEClient`
    instance, then read from it using the iterator properties :prop:`events` or :prop:`all`.
    
    Connection failures and error responses can be handled in various ways depending on the
    constructor parameters. The default behavior, if no non-default parameters are passed, is
    that the client will attempt to reconnect as many times as necessary if a connection is
    dropped or cannot be made; but if a connection is made and returns an invalid response
    (non-2xx status, 204 status, or invalid content type), it will not retry. This behavior can
    be customized with `retry_filter`. The client will automatically follow 3xx redirects.
    
    For any non-retryable error, if this is the first connection attempt then the constructor
    will throw an exception (such as :class:`ld_eventsource.HTTPStatusError`). Or, if a
    successful connection was made so the constructor has already returned, but a
    non-retryable error occurs subsequently, the iterator properties will simply run out of
    values to indicate that the `SSEClient` is finished (if you are reading :prop:`all`, it will
    first yield a :class:`ld_eventsource.Fault` to indicate what the error was).

    To avoid flooding the server with requests, it is desirable to have a delay before each
    reconnection. There is a base delay set by `initial_retry_delay` (which can be overridden
    by the stream if the server sends a `retry:` line). By default, as defined by
    :func:`ld_eventsource.retry.default_retry_delay_strategy`, this delay will double with each
    subsequent retry, and will also have a pseudo-random jitter applied. You can customize this
    behavior with `retry_delay_strategy`.

    If the application wants to track every state change, including retries of the initial
    connection, then pass `True` for `defer_connect`, causing the constructor to return
    immediately and defer the first connection attempt until you start reading from the client.
    This way, if you are reading from :prop:`all`, you can see any :class:`ld_eventsource.Fault`
    conditions that might occur before the first successful connection.
    """

    chunk_size = 10000

    def __init__(
        self, 
        request: Union[str, RequestParams],
        initial_retry_delay: float=1.0,
        retry_delay_strategy: Optional[RetryDelayStrategy]=None,
        retry_filter: Optional[RetryFilter]=None,
        last_event_id: Optional[str]=None,
        http_pool: Optional[PoolManager]=None,
        logger: Optional[logging.Logger]=None,
        defer_connect: bool=False
    ):
        """
        Creates a client instance and attempts to connect to the stream.

        :param request: either a stream URL or a :class:`RequestParams` instance
        :param initial_retry_delay: the initial delay before reconnecting after a failure,
            in seconds; this can increase as described in :class:`SSEClient`
        :param retry_delay_strategy: allows customization of the delay behavior for retries; if
            not specified, uses :func:`ld_eventsource.retry.default_retry_delay_strategy`
        :param retry_filter: allows customization of the logic for whether to retry; if not
            specified, uses :func:`ld_eventsource.retry.default_retry_filter`
        :param last_event_id: if provided, the `Last-Event-Id` value will be preset to this
        :param http_pool: optional urllib3 `PoolManager` to provide an HTTP client
        :param logger: if provided, log messages will be written here
        :param defer_connect: if `True`, the constructor will return immediately so the
            connection attempt only happens when you start reading :prop:`SSEClient.events`
            or :prop:`SSEClient.all`
        """
        if isinstance(request, RequestParams):
            self.__request_params = request  # type: RequestParams
        elif isinstance(request, str):
            self.__request_params = RequestParams(url=request)
        else:
            raise TypeError("request must be either a string or RequestParams")

        self.__base_delay = 1.0 if initial_retry_delay is None else initial_retry_delay
        self.__retry_delay_strategy = retry_delay_strategy or default_retry_delay_strategy()
        self.__retry_filter = retry_filter or default_retry_filter()
        self.__last_event_id = last_event_id
        self.__http = http_pool or PoolManager()
        self.__http_should_close = (http_pool is not None)
        
        if logger is None:
            logger = logging.getLogger('launchdarkly-eventsource.null')
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
        self.__logger = logger
        
        self.__last_success_time = None  # type: Optional[float]

        self.__closed = False
        self.__first_attempt = True
        self.__response = None
        self.__stream = None

        if not defer_connect:
            while True:
                delay = self._compute_next_delay()
                try:
                    self._connect(delay)
                    return
                except Exception as e:
                    if not self._should_retry(e):
                        raise e

    def close(self):
        """
        Permanently shuts down this client instance and closes any active connection.
        """
        self.__closed = True
        if self.__response:
            self.__response.release_conn()
        if self.__http_should_close:
            self.__http.close()
    
    @property
    def all(self):
        """
        An iterable series of notifications from the stream. Each of these can be any of the following:
        
        * :class:`ld_eventsource.Event`
        * :class:`ld_eventsource.Comment`
        * :class:`ld_eventsource.Start`
        * :class:`ld_eventsource.Fault`

        You can use :prop:`events` instead if you are only interested in Events.
        """
        next_reconnect_delay = None  # type: Optional[float]
        while True:
            connected = self.__stream is not None
            error = None  # type: Optional[Exception]

            if not connected:
                # We haven't connected yet, or we need to reconnect after a failure. If _connect
                # throws an exception at this point, we catch the exception and yield it as a Fault.
                try:
                    self._connect(self._compute_next_delay() if next_reconnect_delay is None else next_reconnect_delay)
                    connected = True
                except Exception as e:
                    error = e

            if connected:
                yield Start()
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
                finally:
                    self.__last_event_id = reader.last_event_id

            # Here, we have either run out of data (error = None) or hit an error. Either way, we will
            # yield a Fault and then ask the RetryFilter what to do.
            should_retry = self._should_retry(error)
            next_reconnect_delay = self._compute_next_delay() if should_retry else 0
            yield Fault(error, should_retry, next_reconnect_delay)
            if not should_retry:
                return  # not retrying, so the stream simply ends
            continue  # try to connect again

    @property
    def events(self) -> Iterable[Event]:
        """
        An iterable series of :class:`ld_eventsource.Event` objects received from the stream.

        Use :prop:`all` instead if you also want to know about other kinds of occurrences.
        """
        for item in self.all:
            if isinstance(item, Event):
                yield item
            elif isinstance(item, Exception):
                raise item

    def _compute_next_delay(self) -> float:
        if self.__first_attempt:
            self.__first_attempt = False
            return 0
        retry_delay_result = self.__retry_delay_strategy(
            RetryDelayParams(self.__base_delay, time.time(), self.__last_success_time))
        self.__retry_delay_strategy = retry_delay_result.next_strategy or self.__retry_delay_strategy
        return retry_delay_result.delay

    def _should_retry(self, error: Optional[Exception]) -> bool:
        retry_result = self.__retry_filter(RetryFilterParams(error))
        if retry_result.request_params:
            self.__request_params = retry_result.request_params
        return retry_result.should_retry

    def _connect(self, delay: float):
        if delay > 0:
            self.__logger.info("Will reconnect after delay of %fs" % delay)
            time.sleep(delay)

        params = self.__request_params

        headers = params.headers.copy() if params.headers else {}
        headers['Cache-Control'] = 'no-cache'
        headers['Accept'] = 'text/event-stream'

        if self.__last_event_id:
            headers['Last-Event-ID'] = self.__last_event_id

        request_options = params.urllib3_request_options.copy() if params.urllib3_request_options else {}
        request_options['headers'] = headers

        self.__logger.info("Connecting to stream at %s" % params.url)

        resp = None
        try:
            resp = self.__http.request(
                'GET',
                params.url,
                preload_content=False,
                retries=Retry(total=None, read=0, connect=0, status=0, other=0, redirect=3),
                **request_options)
        except MaxRetryError as e:
            raise e.reason  # e.reason is the underlying I/O error
        
        if resp.status >= 400 or resp.status == 204:
            raise HTTPStatusError(resp.status)
        else:
            content_type = resp.getheader('Content-Type')
            if content_type is None or not str(content_type).startswith("text/event-stream"):
                raise HTTPContentTypeError(content_type)

        self.__response = resp
        self.__last_success_time = time.time()

        self.__stream = resp.stream(amt=self.chunk_size)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()
