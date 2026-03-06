import pytest

from ld_eventsource.actions import Comment, Event, Fault, Start
from ld_eventsource.async_client import AsyncSSEClient
from ld_eventsource.testing.async_helpers import (AsyncRespondWithData,
                                                   MockAsyncConnectStrategy)


@pytest.mark.asyncio
@pytest.mark.parametrize('explicitly_start', [False, True])
async def test_receives_events(explicitly_start: bool):
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData(
            "event: event1\ndata: data1\n\n:whatever\nevent: event2\ndata: data2\n\n"
        )
    )
    async with AsyncSSEClient(connect=mock) as client:
        if explicitly_start:
            await client.start()

        events = client.events
        event_iter = events.__aiter__()

        event1 = await event_iter.__anext__()
        assert event1.event == 'event1'
        assert event1.data == 'data1'

        event2 = await event_iter.__anext__()
        assert event2.event == 'event2'
        assert event2.data == 'data2'


@pytest.mark.asyncio
async def test_events_returns_eof_when_stream_ends():
    mock = MockAsyncConnectStrategy(AsyncRespondWithData("event: event1\ndata: data1\n\n"))
    async with AsyncSSEClient(connect=mock) as client:
        events = []
        async for event in client.events:
            events.append(event)

        assert len(events) == 1
        assert events[0].event == 'event1'
        assert events[0].data == 'data1'


@pytest.mark.asyncio
async def test_receives_all():
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData(
            "event: event1\ndata: data1\n\n:whatever\nevent: event2\ndata: data2\n\n"
        )
    )
    async with AsyncSSEClient(connect=mock) as client:
        all_iter = client.all.__aiter__()

        item1 = await all_iter.__anext__()
        assert isinstance(item1, Start)

        item2 = await all_iter.__anext__()
        assert isinstance(item2, Event)
        assert item2.event == 'event1'
        assert item2.data == 'data1'

        item3 = await all_iter.__anext__()
        assert isinstance(item3, Comment)
        assert item3.comment == 'whatever'

        item4 = await all_iter.__anext__()
        assert isinstance(item4, Event)
        assert item4.event == 'event2'
        assert item4.data == 'data2'


@pytest.mark.asyncio
async def test_all_returns_fault_and_eof_when_stream_ends():
    mock = MockAsyncConnectStrategy(AsyncRespondWithData("event: event1\ndata: data1\n\n"))
    async with AsyncSSEClient(connect=mock) as client:
        all_iter = client.all.__aiter__()

        item1 = await all_iter.__anext__()
        assert isinstance(item1, Start)

        item2 = await all_iter.__anext__()
        assert isinstance(item2, Event)
        assert item2.event == 'event1'
        assert item2.data == 'data1'

        item3 = await all_iter.__anext__()
        assert isinstance(item3, Fault)
        assert item3.error is None

        with pytest.raises(StopAsyncIteration):
            await all_iter.__anext__()


@pytest.mark.asyncio
async def test_start_headers_exposed():
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: hello\n\n", headers={'X-My-Header': 'myvalue'})
    )
    async with AsyncSSEClient(connect=mock) as client:
        all_iter = client.all.__aiter__()

        start = await all_iter.__anext__()
        assert isinstance(start, Start)
        assert start.headers is not None
        assert start.headers.get('X-My-Header') == 'myvalue'


@pytest.mark.asyncio
async def test_last_event_id_tracked():
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("id: abc\ndata: hello\n\n")
    )
    async with AsyncSSEClient(connect=mock) as client:
        async for event in client.events:
            assert event.last_event_id == 'abc'
            break
        assert client.last_event_id == 'abc'


@pytest.mark.asyncio
async def test_close_stops_iteration():
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: first\n\ndata: second\n\n")
    )
    async with AsyncSSEClient(connect=mock) as client:
        events_seen = []
        async for event in client.events:
            events_seen.append(event)
            await client.close()

    assert len(events_seen) == 1


@pytest.mark.asyncio
async def test_string_url_creates_http_strategy():
    # Just verifies the constructor accepts a string without crashing
    # (actual HTTP is tested separately)
    from ld_eventsource.config.async_connect_strategy import AsyncConnectStrategy
    client = AsyncSSEClient(connect="http://localhost:9999/stream")
    assert client is not None
    await client.close()


@pytest.mark.asyncio
async def test_invalid_connect_type_raises():
    with pytest.raises(TypeError):
        AsyncSSEClient(connect=12345)
