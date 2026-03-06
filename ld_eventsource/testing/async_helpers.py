from __future__ import annotations

import asyncio
from logging import Logger
from typing import AsyncIterable, AsyncIterator, List, Optional

from ld_eventsource.config.async_connect_strategy import (
    AsyncConnectionClient, AsyncConnectionResult, AsyncConnectStrategy)
from ld_eventsource.config.error_strategy import ErrorStrategy
from ld_eventsource.config.retry_delay_strategy import RetryDelayStrategy
from ld_eventsource.errors import HTTPStatusError
from ld_eventsource.testing.http_util import ChunkedResponse


def make_stream() -> ChunkedResponse:
    return ChunkedResponse({'Content-Type': 'text/event-stream'})


def retry_for_status(status: int) -> ErrorStrategy:
    return ErrorStrategy.from_lambda(
        lambda error: (
            (
                ErrorStrategy.CONTINUE
                if isinstance(error, HTTPStatusError) and error.status == status
                else ErrorStrategy.FAIL
            ),
            None,
        )
    )


def no_delay() -> RetryDelayStrategy:
    return RetryDelayStrategy.from_lambda(lambda _: (0, None))


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
