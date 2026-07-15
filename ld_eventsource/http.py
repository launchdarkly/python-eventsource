from logging import Logger
from typing import Any, Callable, Dict, Iterator, Optional, Tuple, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from urllib3 import PoolManager
from urllib3.exceptions import MaxRetryError
from urllib3.util import Retry

from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError

_CHUNK_SIZE = 10000

DynamicQueryParams = Callable[[], dict[str, str]]
"""
A callable that returns a dictionary of query parameters to add to the URL.
This can be used to modify query parameters dynamically for each connection attempt.
"""


class _HttpConnectParams:
    def __init__(
        self,
        url: str,
        headers: Optional[dict] = None,
        pool: Optional[PoolManager] = None,
        urllib3_request_options: Optional[dict] = None,
        query_params: Optional[DynamicQueryParams] = None
    ):
        self.__url = url
        self.__headers = headers
        self.__pool = pool
        self.__urllib3_request_options = urllib3_request_options
        self.__query_params = query_params

    @property
    def url(self) -> str:
        return self.__url

    @property
    def query_params(self) -> Optional[DynamicQueryParams]:
        return self.__query_params

    @property
    def headers(self) -> Optional[dict]:
        return self.__headers

    @property
    def pool(self) -> Optional[PoolManager]:
        return self.__pool

    @property
    def urllib3_request_options(self) -> Optional[dict]:
        return self.__urllib3_request_options


class _HttpClientImpl:
    def __init__(self, params: _HttpConnectParams, logger: Logger):
        self.__params = params
        self.__pool = params.pool or PoolManager()
        self.__should_close_pool = params.pool is None
        self.__logger = logger

    def connect(self, last_event_id: Optional[str]) -> Tuple[Iterator[bytes], Callable, Dict[str, Any]]:
        url = self.__params.url
        if self.__params.query_params is not None:
            qp = self.__params.query_params()
            if qp:
                url_parts = list(urlsplit(url))
                query = dict(parse_qsl(url_parts[3]))
                query.update(qp)
                url_parts[3] = urlencode(query)
                url = urlunsplit(url_parts)
        self.__logger.info("Connecting to stream at %s" % url)

        headers = self.__params.headers.copy() if self.__params.headers else {}
        headers['Cache-Control'] = 'no-cache'
        headers['Accept'] = 'text/event-stream'

        if last_event_id:
            headers['Last-Event-ID'] = last_event_id

        request_options = (
            self.__params.urllib3_request_options.copy()
            if self.__params.urllib3_request_options
            else {}
        )
        request_options['headers'] = headers

        try:
            resp = self.__pool.request(
                'GET',
                url,
                preload_content=False,
                retries=Retry(
                    total=None, read=0, connect=0, status=0, other=0, redirect=3
                ),
                **request_options
            )
        except MaxRetryError as e:
            reason: Optional[Exception] = e.reason
            if reason is not None:
                raise reason  # e.reason is the underlying I/O error

        # Capture headers early so they're available for both error and success cases
        response_headers = cast(Dict[str, Any], resp.headers)

        if resp.status >= 400 or resp.status == 204:
            raise HTTPStatusError(resp.status, response_headers)
        content_type = resp.headers.get('Content-Type', None)
        if content_type is None or not str(content_type).startswith(
            "text/event-stream"
        ):
            raise HTTPContentTypeError(content_type or '', response_headers)

        stream = resp.stream(_CHUNK_SIZE)

        def close():
            if hasattr(resp, "shutdown"):
                # urllib3 2.x: shutdown() wakes a reader blocked mid-read (SHUT_RD) so the
                # subsequent close() -- which calls self._fp.close() and would otherwise
                # deadlock on the reader's BufferedReader lock -- can proceed. close() then
                # sends the TCP FIN and releases the fd. Both are built-ins.
                try:
                    resp.shutdown()
                except Exception:
                    self.__logger.debug("Error interrupting stream via resp.shutdown()", exc_info=True)
                resp.close()
            else:
                # urllib3 1.26.x has no resp.shutdown(), and we deliberately do not reach
                # into private socket attributes to find and shut down the socket. Without a
                # way to wake a blocked reader first, resp.close() could deadlock on the
                # reader's BufferedReader lock, so we fall back to the original behavior of
                # releasing the connection back to the pool. This never hangs, but the socket
                # is not closed deterministically -- deterministic close requires urllib3 2.x.
                resp.release_conn()

        return stream, close, response_headers

    def close(self):
        if self.__should_close_pool:
            # Only clear a pool we created. On urllib3 2.x the active connection was already
            # closed by the connection closer (resp.close()); we do not iterate and close the
            # pool's connections ourselves, because doing so hangs on urllib3 1.26.x when a
            # reader is still blocked mid-read on a connection.
            self.__pool.clear()
