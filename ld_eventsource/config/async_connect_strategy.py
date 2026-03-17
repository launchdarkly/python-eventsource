from __future__ import annotations

from logging import Logger
from typing import AsyncIterator, Callable, Optional

from ld_eventsource.errors import Headers


class AsyncConnectStrategy:
    """
    An abstraction for how :class:`.AsyncSSEClient` should obtain an input stream.

    The default implementation is :meth:`http()`, which makes HTTP requests with ``aiohttp``.
    Or, if you want to consume an input stream from some other source, you can create your own
    subclass of :class:`AsyncConnectStrategy`.

    Instances of this class should be immutable and should not contain any state that is specific
    to one active stream. The :class:`AsyncConnectionClient` that they produce is stateful and
    belongs to a single :class:`.AsyncSSEClient`.
    """

    def create_client(self, logger: Logger) -> AsyncConnectionClient:
        """
        Creates a client instance.

        This is called once when an :class:`.AsyncSSEClient` is created.

        :param logger: the logger being used by the AsyncSSEClient
        """
        raise NotImplementedError("AsyncConnectStrategy base class cannot be used by itself")

    @staticmethod
    def http(
        url: str,
        headers: Optional[dict] = None,
        session=None,
        aiohttp_request_options: Optional[dict] = None,
        query_params=None,
    ) -> AsyncConnectStrategy:
        """
        Creates the default async HTTP implementation using aiohttp.

        :param url: the stream URL
        :param headers: optional HTTP headers to add to the request
        :param session: optional ``aiohttp.ClientSession`` to use
        :param aiohttp_request_options: optional kwargs passed to the aiohttp ``get()`` call
        :param query_params: optional callable that returns a dict of query params per connection
        """
        # Import here to avoid requiring aiohttp for users who don't use async HTTP
        from ld_eventsource.async_http import (_AsyncHttpClientImpl,
                                               _AsyncHttpConnectParams)
        return _AsyncHttpConnectStrategy(
            _AsyncHttpConnectParams(url, headers, session, aiohttp_request_options, query_params)
        )


class AsyncConnectionClient:
    """
    An object provided by :class:`.AsyncConnectStrategy` that is retained by a single
    :class:`.AsyncSSEClient` to perform all connection attempts by that instance.
    """

    async def connect(self, last_event_id: Optional[str]) -> AsyncConnectionResult:
        """
        Attempts to connect to a stream. Raises an exception if unsuccessful.

        :param last_event_id: the current value of last_event_id (sent to server for resuming)
        :return: an :class:`AsyncConnectionResult` representing the stream
        """
        raise NotImplementedError("AsyncConnectionClient base class cannot be used by itself")

    async def close(self):
        """
        Does whatever is necessary to release resources when the AsyncSSEClient is closed.
        """
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, type, value, traceback):
        await self.close()


class AsyncConnectionResult:
    """
    The return type of :meth:`AsyncConnectionClient.connect()`.
    """

    def __init__(
        self,
        stream: AsyncIterator[bytes],
        closer: Optional[Callable],
        headers: Optional[Headers] = None,
    ):
        self.__stream = stream
        self.__closer = closer
        self.__headers = headers

    @property
    def stream(self) -> AsyncIterator[bytes]:
        """
        An async iterator that returns chunks of data.
        """
        return self.__stream

    @property
    def headers(self) -> Optional[Headers]:
        """
        The HTTP response headers, if available.

        Header name lookups are case-insensitive per RFC 7230.
        """
        return self.__headers

    async def close(self):
        """
        Does whatever is necessary to release the connection.
        """
        if self.__closer:
            await self.__closer()
            self.__closer = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, type, value, traceback):
        await self.close()


class _AsyncHttpConnectStrategy(AsyncConnectStrategy):
    def __init__(self, params):
        self.__params = params

    def create_client(self, logger: Logger) -> AsyncConnectionClient:
        from ld_eventsource.async_http import _AsyncHttpClientImpl
        return _AsyncHttpConnectionClient(self.__params, logger)


class _AsyncHttpConnectionClient(AsyncConnectionClient):
    def __init__(self, params, logger: Logger):
        from ld_eventsource.async_http import _AsyncHttpClientImpl
        self.__impl = _AsyncHttpClientImpl(params, logger)

    async def connect(self, last_event_id: Optional[str]) -> AsyncConnectionResult:
        stream, closer, headers = await self.__impl.connect(last_event_id)
        return AsyncConnectionResult(stream, closer, headers)

    async def close(self):
        await self.__impl.close()


__all__ = ['AsyncConnectStrategy', 'AsyncConnectionClient', 'AsyncConnectionResult']
