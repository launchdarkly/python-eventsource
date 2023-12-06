from ld_eventsource import *
from ld_eventsource.actions import *
from ld_eventsource.config import *

from testing.helpers import *

import pytest

# Tests for SSEClient's basic properties and parsing behavior. These tests do not use real HTTP
# requests; instead, they use a ConnectStrategy that provides a preconfigured input stream. HTTP
# functionality is tested separately in test_http_connect_strategy.py and
# test_http_connect_strategy_with_sse_client.py.


@pytest.mark.asyncio
@pytest.mark.parametrize('explicitly_start', [False, True])
async def test_receives_events(explicitly_start: bool):
    mock = MockAIOConnectStrategy(
        AIORespondWithData("event: event1\ndata: data1\n\n:whatever\nevent: event2\ndata: data2\n\n")
    )
    with AIOSSEClient(connect=mock) as client:
        if explicitly_start:
            await client.start()  # shouldn't make a difference if we're just reading events

        events = []
        async for event in client.events:
            events.append(event)

        assert events[0].event == 'event1'
        assert events[0].data == 'data1'

        assert events[1].event == 'event2'
        assert events[1].data == 'data2'


@pytest.mark.asyncio
async def test_events_returns_eof_when_stream_ends():
    mock = MockAIOConnectStrategy(
        AIORespondWithData("event: event1\ndata: data1\n\n")
    )
    with AIOSSEClient(connect=mock) as client:

        events = []
        async for event in client.events:
            events.append(event)

        assert len(events) == 1
        assert events[0].event == 'event1'
        assert events[0].data == 'data1'

@pytest.mark.asyncio
async def test_receives_all():
    mock = MockAIOConnectStrategy(
        AIORespondWithData("event: event1\ndata: data1\n\n:whatever\nevent: event2\ndata: data2\n\n")
    )
    with AIOSSEClient(connect=mock) as client:
        events = []
        async for event in client.all:
            events.append(event)

        assert isinstance(events[0], Start)

        assert isinstance(events[1], Event)
        assert events[1].event == 'event1'
        assert events[1].data == 'data1'

        assert isinstance(events[2], Comment)
        assert events[2].comment == 'whatever'

        assert isinstance(events[3], Event)
        assert events[3].event == 'event2'
        assert events[3].data == 'data2'


@pytest.mark.asyncio
async def test_all_returns_fault_and_eof_when_stream_ends():
    mock = MockAIOConnectStrategy(
        AIORespondWithData("event: event1\ndata: data1\n\n")
    )
    with AIOSSEClient(connect=mock) as client:
        events = []
        async for event in client.all:
            events.append(event)

        assert len(events) == 3
        assert isinstance(events[0], Start)

        assert isinstance(events[1], Event)
        assert events[1].event == 'event1'
        assert events[1].data == 'data1'

        assert isinstance(events[2], Fault)
        assert events[2].error is None
