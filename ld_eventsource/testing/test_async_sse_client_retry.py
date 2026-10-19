import asyncio
import itertools
from unittest.mock import patch

import pytest

from ld_eventsource.actions import Event, Fault, Start
from ld_eventsource.async_client import AsyncSSEClient
from ld_eventsource.config.error_strategy import ErrorStrategy
from ld_eventsource.config.retry_delay_strategy import RetryDelayStrategy
from ld_eventsource.errors import HTTPStatusError
from ld_eventsource.testing.async_helpers import (AsyncExpectNoMoreRequests,
                                                  AsyncRejectConnection,
                                                  AsyncRespondWithData,
                                                  MockAsyncConnectStrategy)
from ld_eventsource.testing.helpers import no_delay, retry_for_status


@pytest.mark.asyncio
async def test_retry_during_initial_connect_succeeds():
    mock = MockAsyncConnectStrategy(
        AsyncRejectConnection(HTTPStatusError(503)),
        AsyncRespondWithData("data: data1\n\n"),
        AsyncExpectNoMoreRequests(),
    )
    async with AsyncSSEClient(
        connect=mock,
        retry_delay_strategy=no_delay(),
        error_strategy=retry_for_status(503),
    ) as client:
        await client.start()

        events = []
        async for event in client.events:
            events.append(event)
            break
        assert events[0].data == 'data1'


@pytest.mark.asyncio
async def test_retry_during_initial_connect_succeeds_then_fails():
    mock = MockAsyncConnectStrategy(
        AsyncRejectConnection(HTTPStatusError(503)),
        AsyncRejectConnection(HTTPStatusError(400)),
        AsyncExpectNoMoreRequests(),
    )
    with pytest.raises(HTTPStatusError) as exc_info:
        async with AsyncSSEClient(
            connect=mock,
            retry_delay_strategy=no_delay(),
            error_strategy=retry_for_status(503),
        ) as client:
            await client.start()
    assert exc_info.value.status == 400


@pytest.mark.asyncio
async def test_events_iterator_continues_after_retry():
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: data1\n\n"),
        AsyncRespondWithData("data: data2\n\n"),
        AsyncExpectNoMoreRequests(),
    )
    async with AsyncSSEClient(
        connect=mock,
        error_strategy=ErrorStrategy.always_continue(),
        retry_delay_strategy=no_delay(),
    ) as client:
        events = []
        async for event in client.events:
            events.append(event)
            if len(events) == 2:
                break

        assert events[0].data == 'data1'
        assert events[1].data == 'data2'


@pytest.mark.asyncio
async def test_all_iterator_continues_after_retry():
    initial_delay = 0.005
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: data1\n\n"),
        AsyncRespondWithData("data: data2\n\n"),
        AsyncRespondWithData("data: data3\n\n"),
        AsyncExpectNoMoreRequests(),
    )
    async with AsyncSSEClient(
        connect=mock,
        error_strategy=ErrorStrategy.always_continue(),
        initial_retry_delay=initial_delay,
        retry_delay_strategy=RetryDelayStrategy.default(jitter_multiplier=None),
    ) as client:
        all_iter = client.all.__aiter__()

        item1 = await all_iter.__anext__()
        assert isinstance(item1, Start)

        item2 = await all_iter.__anext__()
        assert isinstance(item2, Event)
        assert item2.data == 'data1'

        item3 = await all_iter.__anext__()
        assert isinstance(item3, Fault)
        assert item3.error is None
        assert client.next_retry_delay == initial_delay

        item4 = await all_iter.__anext__()
        assert isinstance(item4, Start)

        item5 = await all_iter.__anext__()
        assert isinstance(item5, Event)
        assert item5.data == 'data2'

        item6 = await all_iter.__anext__()
        assert isinstance(item6, Fault)
        assert item6.error is None
        assert client.next_retry_delay == initial_delay * 2


@pytest.mark.asyncio
async def test_can_interrupt_and_restart_stream():
    initial_delay = 0.005
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: data1\n\ndata: data2\n\n"),
        AsyncRespondWithData("data: data3\n\n"),
        AsyncExpectNoMoreRequests(),
    )
    async with AsyncSSEClient(
        connect=mock,
        error_strategy=ErrorStrategy.always_continue(),
        initial_retry_delay=initial_delay,
        retry_delay_strategy=RetryDelayStrategy.default(jitter_multiplier=None),
    ) as client:
        all_iter = client.all.__aiter__()

        item1 = await all_iter.__anext__()
        assert isinstance(item1, Start)

        item2 = await all_iter.__anext__()
        assert isinstance(item2, Event)
        assert item2.data == 'data1'

        await client.interrupt()
        assert client.next_retry_delay == initial_delay

        item3 = await all_iter.__anext__()
        assert isinstance(item3, Fault)

        item4 = await all_iter.__anext__()
        assert isinstance(item4, Start)

        item5 = await all_iter.__anext__()
        assert isinstance(item5, Event)
        assert item5.data == 'data3'


@pytest.mark.asyncio
async def test_retry_delay_gets_reset_after_threshold():
    initial_delay = 0.005
    retry_delay_reset_threshold = 0.1
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: data1\n\n"),
        AsyncRejectConnection(HTTPStatusError(503)),
    )
    async with AsyncSSEClient(
        connect=mock,
        error_strategy=ErrorStrategy.always_continue(),
        initial_retry_delay=initial_delay,
        retry_delay_reset_threshold=retry_delay_reset_threshold,
        retry_delay_strategy=RetryDelayStrategy.default(jitter_multiplier=None),
    ) as client:
        assert client._retry_reset_baseline == 0
        all_iter = client.all.__aiter__()

        item1 = await all_iter.__anext__()
        assert isinstance(item1, Start)
        assert client._retry_reset_baseline != 0

        item2 = await all_iter.__anext__()
        assert isinstance(item2, Event)
        assert item2.data == 'data1'

        item3 = await all_iter.__anext__()
        assert isinstance(item3, Fault)
        assert client.next_retry_delay == initial_delay

        item4 = await all_iter.__anext__()
        assert isinstance(item4, Fault)
        assert client.next_retry_delay == initial_delay * 2

        await asyncio.sleep(retry_delay_reset_threshold + 0.05)

        item5 = await all_iter.__anext__()
        assert isinstance(item5, Fault)
        assert client.next_retry_delay == initial_delay

        await asyncio.sleep(retry_delay_reset_threshold / 2)

        item6 = await all_iter.__anext__()
        assert isinstance(item6, Fault)
        assert client.next_retry_delay == initial_delay * 2


@pytest.mark.asyncio
async def test_reconnect_delay_ignores_wall_clock_step():
    initial_delay = 0.05
    mock = MockAsyncConnectStrategy(
        AsyncRejectConnection(HTTPStatusError(503)),
        AsyncRespondWithData("data: data1\n\n"),
        AsyncExpectNoMoreRequests(),
    )
    real_sleep = asyncio.sleep
    delays = []

    async def fake_sleep(delay, *args, **kwargs):
        delays.append(delay)
        await real_sleep(0)

    # Each wall-clock read steps back one hour.
    wall_clock = itertools.count(1_000_000_000, -3600)
    with patch('time.time', side_effect=lambda: next(wall_clock)), patch(
        'ld_eventsource.async_client.asyncio.sleep', fake_sleep
    ):
        async with AsyncSSEClient(
            connect=mock,
            error_strategy=retry_for_status(503),
            initial_retry_delay=initial_delay,
            retry_delay_strategy=RetryDelayStrategy.default(jitter_multiplier=None),
        ) as client:
            await client.start()

    assert len(delays) == 1
    assert 0 < delays[0] <= initial_delay


@pytest.mark.asyncio
async def test_retry_delay_reset_ignores_wall_clock_step():
    initial_delay = 0.005
    mock = MockAsyncConnectStrategy(
        AsyncRespondWithData("data: data1\n\n"),
        AsyncRejectConnection(HTTPStatusError(503)),
    )
    real_sleep = asyncio.sleep

    async def fake_sleep(delay, *args, **kwargs):
        await real_sleep(0)

    # Each wall-clock read steps forward one hour.
    wall_clock = itertools.count(1_000_000_000, 3600)
    with patch('time.time', side_effect=lambda: next(wall_clock)), patch(
        'ld_eventsource.async_client.asyncio.sleep', fake_sleep
    ):
        async with AsyncSSEClient(
            connect=mock,
            error_strategy=ErrorStrategy.always_continue(),
            initial_retry_delay=initial_delay,
            retry_delay_reset_threshold=1000,
            retry_delay_strategy=RetryDelayStrategy.default(jitter_multiplier=None),
        ) as client:
            all_iter = client.all.__aiter__()
            assert isinstance(await all_iter.__anext__(), Start)
            assert isinstance(await all_iter.__anext__(), Event)
            assert isinstance(await all_iter.__anext__(), Fault)
            assert client.next_retry_delay == initial_delay

            # The connection lasted far less than the threshold, so the
            # backoff must not reset.
            assert isinstance(await all_iter.__anext__(), Fault)
            assert client.next_retry_delay == initial_delay * 2
