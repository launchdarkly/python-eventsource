import asyncio
from logging import Logger
from typing import Any, AsyncIterator, Callable, Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiohttp

from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError

_CHUNK_SIZE = 10000


class _AsyncHttpConnectParams:
    def __init__(
        self,
        url: str,
        headers: Optional[dict] = None,
        session: Optional[aiohttp.ClientSession] = None,
        aiohttp_request_options: Optional[dict] = None,
        query_params=None,
    ):
        self.__url = url
        self.__headers = headers
        self.__session = session
        self.__aiohttp_request_options = aiohttp_request_options
        self.__query_params = query_params

    @property
    def url(self) -> str:
        return self.__url

    @property
    def headers(self) -> Optional[dict]:
        return self.__headers

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        return self.__session

    @property
    def aiohttp_request_options(self) -> Optional[dict]:
        return self.__aiohttp_request_options

    @property
    def query_params(self):
        return self.__query_params


class _AsyncHttpClientImpl:
    def __init__(self, params: _AsyncHttpConnectParams, logger: Logger):
        self.__params = params
        self.__external_session = params.session
        self.__session: Optional[aiohttp.ClientSession] = params.session
        self.__session_lock = asyncio.Lock()
        self.__logger = logger

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.__session is not None:
            return self.__session
        async with self.__session_lock:
            if self.__session is None:
                self.__session = aiohttp.ClientSession()
        return self.__session

    async def connect(
        self, last_event_id: Optional[str]
    ) -> Tuple[AsyncIterator[bytes], Callable, Dict[str, Any]]:
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
            self.__params.aiohttp_request_options.copy()
            if self.__params.aiohttp_request_options
            else {}
        )
        request_options['headers'] = headers

        session = await self._get_session()
        resp = await session.get(url, **request_options)

        response_headers: Dict[str, Any] = dict(resp.headers)

        if resp.status >= 400 or resp.status == 204:
            await resp.release()
            raise HTTPStatusError(resp.status, response_headers)

        content_type = resp.headers.get('Content-Type', None)
        if content_type is None or not str(content_type).startswith("text/event-stream"):
            await resp.release()
            raise HTTPContentTypeError(content_type or '', response_headers)

        async def chunk_iterator() -> AsyncIterator[bytes]:
            async for chunk in resp.content.iter_chunked(_CHUNK_SIZE):
                yield chunk

        async def closer():
            await resp.release()

        return chunk_iterator(), closer, response_headers

    async def close(self):
        # Only close the session if we created it ourselves
        if self.__external_session is None and self.__session is not None:
            await self.__session.close()
            self.__session = None
