from logging import Logger
import socket
from typing import Callable, Iterator, Optional, Tuple
from urllib3 import HTTPResponse, PoolManager
from urllib3.exceptions import MaxRetryError
from urllib3.util import Retry

from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError

_CHUNK_SIZE = 10000


class _HttpConnectParams:
    def __init__(
        self,
        url: str,
        headers: Optional[dict]=None,
        pool: Optional[PoolManager]=None,
        urllib3_request_options: Optional[dict]=None
    ):
        self.__url = url
        self.__headers = headers
        self.__pool = pool
        self.__urllib3_request_options = urllib3_request_options

    @property
    def url(self) -> str:
        return self.__url
    
    @property
    def headers(self) -> Optional[dict]:
        return self.__headers
    
    @property
    def pool(self) -> Optional[PoolManager]:
        return self.__pool
    
    @property
    def urllib3_request_options(self) -> Optional[dict]:
        return self.__urllib3_request_options


def _force_close_http_response(resp: HTTPResponse, logger: Logger):
    # There are two possible scenarios here:
    # 1. The caller started the stream on thread A, and is now closing it from the same thread.
    # 2. The caller started the stream on thread A, and thread A is waiting on a blocking read, but now
    #    thread B wants to forcibly close the stream.
    # The problem is that in scenario 2, calling urllib3.HTTPResponse.close() (or the equivalent lower-level
    # method http.client.HTTPResponse.close()) from thread B will hang. To forcibly break the connection
    # from the client side regardless of whether a read is happening on it, we have to access the low-level
    # file descriptor. That will cause any current blocking read to error out.
    socket.close(resp._fp.fileno())
    resp.release_conn()


class _HttpClientImpl:
    def __init__(self, params: _HttpConnectParams, logger: Logger):
        self.__params = params
        self.__pool = params.pool or PoolManager()
        self.__should_close_pool = params.pool is not None
        self.__logger = logger
    
    def connect(self, last_event_id: Optional[str]) -> Tuple[Iterator[bytes], Callable]:
        self.__logger.info("Connecting to stream at %s" % self.__params.url)
        
        headers = self.__params.headers.copy() if self.__params.headers else {}
        headers['Cache-Control'] = 'no-cache'
        headers['Accept'] = 'text/event-stream'

        if last_event_id:
            headers['Last-Event-ID'] = last_event_id

        request_options = self.__params.urllib3_request_options.copy() if self.__params.urllib3_request_options else {}
        request_options['headers'] = headers

        try:
            resp = self.__pool.request(
                'GET',
                self.__params.url,
                preload_content=False,
                retries=Retry(total=None, read=0, connect=0, status=0, other=0, redirect=3),
                **request_options)
        except MaxRetryError as e:
            reason: Optional[Exception] = e.reason
            if reason is not None:
                raise reason  # e.reason is the underlying I/O error        
        if resp.status >= 400 or resp.status == 204:
            raise HTTPStatusError(resp.status)
        content_type = resp.headers.get('Content-Type', None)
        if content_type is None or not str(content_type).startswith("text/event-stream"):
            raise HTTPContentTypeError(content_type or '')

        stream = resp.stream(_CHUNK_SIZE)
        return stream, lambda: _force_close_http_response(resp, self.__logger)

    def close(self):
        if self.__should_close_pool:
            self.__pool.clear()
