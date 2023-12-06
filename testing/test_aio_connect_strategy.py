import pytest
from ld_eventsource.config.connect_strategy import *

from testing.helpers import *
from testing.http_util import *

import logging
from aiohttp.client_exceptions import ServerDisconnectedError

# Tests of the basic client/request configuration methods and HTTP functionality in
# ConnectStrategy.http(), using an embedded HTTP server as a target, but without using
# SSEClient.

def logger():
    return logging.getLogger("test")

@pytest.mark.asyncio
async def test_aio_request_gets_chunked_data():
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', stream)
            with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                async with await client.aioconnect(None) as cxn:
                    stream.push('hello')
                    assert await cxn.stream.__anext__() == b'hello'
                    stream.push('world')
                    assert await cxn.stream.__anext__() == b'world'


@pytest.mark.asyncio
async def test_aio_request_default_headers():
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', stream)
            with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                async with await client.aioconnect(None):
                    r = server.await_request()
                    assert r.headers['Accept'] == 'text/event-stream'
                    assert r.headers['Cache-Control'] == 'no-cache'
                    assert r.headers.get('Last-Event-Id') is None


@pytest.mark.asyncio
async def test_aio_request_custom_default_headers():
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', stream)
            strategy = ConnectStrategy.aiohttp(server.uri, headers={'name1': 'value1'})
            with strategy.create_client(logger()) as client:
                async with await client.aioconnect(None):
                    r = server.await_request()
                    assert r.headers['Accept'] == 'text/event-stream'
                    assert r.headers['Cache-Control'] == 'no-cache'
                    assert r.headers['name1'] == 'value1'


@pytest.mark.asyncio
async def test_aio_request_last_event_id_header():
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', stream)
            strategy = ConnectStrategy.aiohttp(server.uri, headers={'name1': 'value1'})
            with strategy.create_client(logger()) as client:
                async with await client.aioconnect('id123'):
                    r = server.await_request()
                    assert r.headers['Last-Event-Id'] == 'id123'


@pytest.mark.asyncio
async def test_aio_status_error():
    with start_server() as server:
        server.for_path('/', BasicResponse(400))
        try:
            with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                await client.aioconnect(None)
            raise Exception("expected exception, did not get one")
        except HTTPStatusError as e:
            assert e.status == 400


@pytest.mark.asyncio
async def test_aio_content_type_error():
    with start_server() as server:
        with ChunkedResponse({ 'Content-Type': 'text/plain' }) as stream:
            server.for_path('/', stream)
            try:
                with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                    await client.aioconnect(None)
                raise Exception("expected exception, did not get one")
            except HTTPContentTypeError as e:
                assert e.content_type == "text/plain"


@pytest.mark.asyncio
async def test_aio_io_error():
    with start_server() as server:
            server.for_path('/', CauseNetworkError())
            try:
                with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                    await client.aioconnect(None)
                raise Exception("expected exception, did not get one")
            except ServerDisconnectedError as e:
                pass


@pytest.mark.asyncio
async def test_auto_redirect_301():
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', BasicResponse(301, None, {'Location': server.uri + '/real-stream'}))
            server.for_path('/real-stream', stream)
            with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                await client.aioconnect(None)
        server.await_request()
        server.await_request()


@pytest.mark.asyncio
async def test_auto_redirect_307():
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', BasicResponse(307, None, {'Location': server.uri + '/real-stream'}))
            server.for_path('/real-stream', stream)
            with ConnectStrategy.aiohttp(server.uri).create_client(logger()) as client:
                await client.aioconnect(None)
        server.await_request()
        server.await_request()


@pytest.mark.asyncio
async def test_sse_client_with_http_connect_strategy():
    # Just a basic smoke test to prove that SSEClient interacts with the ConnectStrategy correctly.
    with start_server() as server:
        with make_stream() as stream:
            server.for_path('/', stream)
            with AIOSSEClient(connect=ConnectStrategy.aiohttp(server.uri)) as client:
                await client.start()
                stream.push("data: data1\n\n")
                event = await client.events.__anext__()
                assert event.data == 'data1'
