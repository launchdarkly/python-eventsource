from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError
from ld_eventsource.event import Event
from ld_eventsource.reader import _BufferedLineReader, _SSEReader
from ld_eventsource.retry_delay import _DefaultBackoffStrategy, _DefaultJitterStrategy, _RetryDelayStrategy

import logging
import time
from typing import Iterable, Optional
from urllib3 import PoolManager, Timeout


class SSEClient:
    chunk_size = 10000

    """
    A simple Server-Sent Events client.

    This implementation does not include automatic retrying of a dropped connection; the caller will do that.
    If a connection ends, the events iterator will simply end.
    """
    def __init__(
        self, 
        url: str,
        initial_retry_delay: float=1.0,
        max_retry_delay: float=30.0,
        backoff_reset_threshold: Optional[float]=None,
        last_event_id: Optional[str]=None,
        headers: Optional[dict]=None,
        http_pool: Optional[PoolManager]=None,
        timeout: Optional[Timeout]=None,
        request_options: Optional[dict]=None,
        logger: Optional[logging.Logger]=None
    ):
        self._url = url
        self._last_event_id = last_event_id
        self._headers = headers or {}
        self._http = http_pool or PoolManager()
        self._http_should_close = (http_pool is not None)
        self._timeout = timeout
        self._request_options = request_options or {}
        
        if logger is None:
            logger = logging.getLogger('launchdarkly-eventsource.null')
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
        self._logger = logger
        
        self._retry_delay=_RetryDelayStrategy(
            initial_retry_delay,
            backoff_reset_threshold,
            backoff_strategy=_DefaultBackoffStrategy(max_retry_delay),
            jitter_strategy=_DefaultJitterStrategy(0.5)
        )

        self._attempts = 0
        self._closed = False
        self._restarting = False

        self._connect()

    def _connect(self):
        if self._attempts > 0:
            delay = self._retry_delay.next_retry_delay(time.time())
            if delay > 0:
                self._logger.info("Will reconnect after delay of %fs" % delay)
                time.sleep(delay)
        self._attempts += 1

        headers = self._headers.copy()
        headers['Cache-Control'] = 'no-cache'
        headers['Accept'] = 'text/event-stream'

        if self._last_event_id:
            headers['Last-Event-ID'] = self._last_event_id

        request_options = self._request_options.copy()
        request_options['headers'] = headers

        self._logger.info("Connecting to stream at %s" % self._url)
        self._response = self._http.request(
            'GET',
            self._url,
            timeout=self._timeout,
            preload_content=False,
            retries=0, # caller is responsible for implementing appropriate retry semantics, e.g. backoff
            **request_options)

        if self._response.status >= 400:
            raise HTTPStatusError(self._response.status)

        content_type = self._response.getheader('Content-Type')
        if content_type is None or not str(content_type).startswith("text/event-stream"):
            raise HTTPContentTypeError(content_type)
        
        self._stream = self._response.stream(amt=self.chunk_size)

    def close(self):
        self._closed = True
        if self._response:
            self._response.release_conn()
        if self._http_should_close:
            self._http.close()
    
    def restart(self):
        if self._response:
            print("*** restarting!")
            self._restarting = True  # this lets us avoid logging a spurious error when we've deliberately closed the connection
            self._response.release_conn()

    @property
    def all(self):
        """
        An iterable series of notifications from the stream. Each of these can be either an :class:`Event`,
        an :class:`Exception`, or a :class:`Comment`.

        You can use :prop:`events` instead if you are only interested in Events.
        """
        while True:
            lines = _BufferedLineReader.lines_from(self._stream)
            reader = _SSEReader(lines, self._last_event_id, None)
            try:
                for ec in reader.events_and_comments:
                    yield ec
            except Exception as e:
                if not self._closed and not self._restarting:
                    yield e
            finally:
                self._last_event_id = reader.last_event_id

            self._restarting = False

            # We have either hit an exception or the stream ended; we will normally always try to reconnect
            while True:
                if self._closed:
                    return
                try:
                    self._connect()
                    break
                except Exception as e:
                    if not self._closed:
                        yield e

    @property
    def events(self) -> Iterable[Event]:
        """
        An iterable series of Event objects received from the stream.

        Use :prop:`all` instead if you also want to know about other kinds of occurrences.
        """
        for item in self.all:
            if isinstance(item, Event):
                yield item
            elif isinstance(item, Exception):
                raise item

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()
