import logging

import pytest

from ld_eventsource.async_client import AsyncSSEClient
from ld_eventsource.config.async_connect_strategy import AsyncConnectStrategy
from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError
from ld_eventsource.testing.async_helpers import no_delay
from ld_eventsource.testing.helpers import retry_for_status
from ld_eventsource.testing.http_util import (BasicResponse, ChunkedResponse,
                                               CauseNetworkError, start_server)


def logger():
    return logging.getLogger("test")


@pytest.mark.asyncio
async def test_http_request_gets_chunked_data():
    with start_server() as server:
        with ChunkedResponse({'Content-Type': 'text/event-stream'}) as stream:
            server.for_path('/', stream)
            strategy = AsyncConnectStrategy.http(server.uri)
            client_obj = strategy.create_client(logger())
            result = await client_obj.connect(None)
            try:
                stream.push('hello')
                chunk = await result.stream.__anext__()
                assert chunk == b'hello'
            finally:
                await result.close()
                await client_obj.close()


@pytest.mark.asyncio
async def test_http_request_default_headers():
    with start_server() as server:
        with ChunkedResponse({'Content-Type': 'text/event-stream'}) as stream:
            server.for_path('/', stream)
            strategy = AsyncConnectStrategy.http(server.uri)
            client_obj = strategy.create_client(logger())
            result = await client_obj.connect(None)
            try:
                r = server.await_request()
                assert r.headers['Accept'] == 'text/event-stream'
                assert r.headers['Cache-Control'] == 'no-cache'
                assert r.headers.get('Last-Event-Id') is None
            finally:
                await result.close()
                await client_obj.close()


@pytest.mark.asyncio
async def test_http_request_custom_headers():
    with start_server() as server:
        with ChunkedResponse({'Content-Type': 'text/event-stream'}) as stream:
            server.for_path('/', stream)
            strategy = AsyncConnectStrategy.http(server.uri, headers={'name1': 'value1'})
            client_obj = strategy.create_client(logger())
            result = await client_obj.connect(None)
            try:
                r = server.await_request()
                assert r.headers['Accept'] == 'text/event-stream'
                assert r.headers['Cache-Control'] == 'no-cache'
                assert r.headers['name1'] == 'value1'
            finally:
                await result.close()
                await client_obj.close()


@pytest.mark.asyncio
async def test_http_request_last_event_id_header():
    with start_server() as server:
        with ChunkedResponse({'Content-Type': 'text/event-stream'}) as stream:
            server.for_path('/', stream)
            strategy = AsyncConnectStrategy.http(server.uri)
            client_obj = strategy.create_client(logger())
            result = await client_obj.connect('id123')
            try:
                r = server.await_request()
                assert r.headers['Last-Event-Id'] == 'id123'
            finally:
                await result.close()
                await client_obj.close()


@pytest.mark.asyncio
async def test_http_status_error():
    with start_server() as server:
        server.for_path('/', BasicResponse(400))
        strategy = AsyncConnectStrategy.http(server.uri)
        client_obj = strategy.create_client(logger())
        try:
            with pytest.raises(HTTPStatusError) as exc_info:
                await client_obj.connect(None)
            assert exc_info.value.status == 400
        finally:
            await client_obj.close()


@pytest.mark.asyncio
async def test_http_content_type_error():
    with start_server() as server:
        with ChunkedResponse({'Content-Type': 'text/plain'}) as stream:
            server.for_path('/', stream)
            strategy = AsyncConnectStrategy.http(server.uri)
            client_obj = strategy.create_client(logger())
            try:
                with pytest.raises(HTTPContentTypeError) as exc_info:
                    await client_obj.connect(None)
                assert exc_info.value.content_type == "text/plain"
            finally:
                await client_obj.close()


@pytest.mark.asyncio
async def test_http_response_headers_captured():
    with start_server() as server:
        custom_headers = {
            'Content-Type': 'text/event-stream',
            'X-Custom-Header': 'custom-value',
        }
        with ChunkedResponse(custom_headers) as stream:
            server.for_path('/', stream)
            strategy = AsyncConnectStrategy.http(server.uri)
            client_obj = strategy.create_client(logger())
            result = await client_obj.connect(None)
            try:
                assert result.headers is not None
                assert result.headers.get('X-Custom-Header') == 'custom-value'
            finally:
                await result.close()
                await client_obj.close()


@pytest.mark.asyncio
async def test_http_status_error_includes_headers():
    with start_server() as server:
        server.for_path('/', BasicResponse(429, None, {
            'Retry-After': '120',
        }))
        strategy = AsyncConnectStrategy.http(server.uri)
        client_obj = strategy.create_client(logger())
        try:
            with pytest.raises(HTTPStatusError) as exc_info:
                await client_obj.connect(None)
            assert exc_info.value.status == 429
            assert exc_info.value.headers is not None
            assert exc_info.value.headers.get('Retry-After') == '120'
        finally:
            await client_obj.close()


@pytest.mark.asyncio
async def test_sse_client_with_http_connect_strategy():
    with start_server() as server:
        with ChunkedResponse({'Content-Type': 'text/event-stream'}) as stream:
            server.for_path('/', stream)
            async with AsyncSSEClient(connect=AsyncConnectStrategy.http(server.uri)) as client:
                await client.start()
                stream.push("data: data1\n\n")
                async for event in client.events:
                    assert event.data == 'data1'
                    break
