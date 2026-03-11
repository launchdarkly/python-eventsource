from __future__ import annotations

import asyncio
from logging import Logger
from typing import AsyncIterable, AsyncIterator, List, Optional

from ld_eventsource.config.async_connect_strategy import (
    AsyncConnectionClient, AsyncConnectionResult, AsyncConnectStrategy)


class MockAsyncConnectStrategy(AsyncConnectStrategy):
    def __init__(self, *request_handlers: MockAsyncConnectionHandler):
        self.__handlers = list(request_handlers)

    def create_client(self, logger: Logger) -> AsyncConnectionClient:
        return MockAsyncConnectionClient(self.__handlers)


class MockAsyncConnectionClient(AsyncConnectionClient):
    def __init__(self, handlers: List[MockAsyncConnectionHandler]):
        self.__handlers = handlers
        self.__request_count = 0

    async def connect(self, last_event_id: Optional[str]) -> AsyncConnectionResult:
        handler = self.__handlers[self.__request_count]
        if self.__request_count < len(self.__handlers) - 1:
            self.__request_count += 1
        return await handler.apply()


class MockAsyncConnectionHandler:
    async def apply(self) -> AsyncConnectionResult:
        raise NotImplementedError(
            "MockAsyncConnectionHandler base class cannot be used by itself"
        )


class AsyncRejectConnection(MockAsyncConnectionHandler):
    def __init__(self, error: Exception):
        self.__error = error

    async def apply(self) -> AsyncConnectionResult:
        raise self.__error


class AsyncRespondWithStream(MockAsyncConnectionHandler):
    def __init__(self, stream: AsyncIterable[bytes], headers: Optional[dict] = None):
        self.__stream = stream
        self.__headers = headers

    async def apply(self) -> AsyncConnectionResult:
        return AsyncConnectionResult(
            stream=self.__stream.__aiter__(),
            closer=None,
            headers=self.__headers,
        )


class AsyncRespondWithData(AsyncRespondWithStream):
    def __init__(self, data: str, headers: Optional[dict] = None):
        super().__init__(_bytes_async_iter([bytes(data, 'utf-8')]), headers)


class AsyncExpectNoMoreRequests(MockAsyncConnectionHandler):
    async def apply(self) -> AsyncConnectionResult:
        assert False, "AsyncSSEClient should not have made another request"


async def _bytes_async_iter(items: List[bytes]) -> AsyncIterator[bytes]:
    for item in items:
        yield item
