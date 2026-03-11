import asyncio
import logging
import time
from typing import AsyncIterable, Optional, Union

from ld_eventsource.actions import Action, Event, Fault, Start
from ld_eventsource.async_reader import (_AsyncBufferedLineReader,
                                         _AsyncSSEReader)
from ld_eventsource.config.async_connect_strategy import (
    AsyncConnectionClient, AsyncConnectionResult, AsyncConnectStrategy)
from ld_eventsource.config.error_strategy import ErrorStrategy
from ld_eventsource.config.retry_delay_strategy import RetryDelayStrategy


class AsyncSSEClient:
    """
    An async client for reading a Server-Sent Events stream.

    This is an async/await implementation. The expected usage is to create an ``AsyncSSEClient``
    instance (either as an async context manager or directly), then read from it using the async
    iterator properties :attr:`events` or :attr:`all`.

    By default, ``AsyncSSEClient`` uses ``aiohttp`` to make HTTP requests to an SSE endpoint.
    You can customize this behavior using :class:`.AsyncConnectStrategy`.

    Connection failures and error responses can be handled in various ways depending on the
    constructor parameters. The default behavior is the same as :class:`.SSEClient`.

    Example::

        async with AsyncSSEClient("https://my-server/events") as client:
            async for event in client.events:
                print(event.data)
    """

    def __init__(
        self,
        connect: Union[str, AsyncConnectStrategy],
        initial_retry_delay: float = 1,
        retry_delay_strategy: Optional[RetryDelayStrategy] = None,
        retry_delay_reset_threshold: float = 60,
        error_strategy: Optional[ErrorStrategy] = None,
        last_event_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Creates an async client instance.

        :param connect: either an :class:`.AsyncConnectStrategy` instance or a URL string
        :param initial_retry_delay: the initial delay before reconnecting after a failure, in seconds
        :param retry_delay_strategy: allows customization of the delay behavior for retries
        :param retry_delay_reset_threshold: minimum connection time before resetting retry delay
        :param error_strategy: allows customization of the behavior after a stream failure
        :param last_event_id: if provided, the ``Last-Event-Id`` value will be preset to this
        :param logger: if provided, log messages will be written here
        """
        if isinstance(connect, str):
            connect = AsyncConnectStrategy.http(connect)
        elif not isinstance(connect, AsyncConnectStrategy):
            raise TypeError("connect must be either a string or AsyncConnectStrategy")

        self.__base_retry_delay = initial_retry_delay
        self.__base_retry_delay_strategy = (
            retry_delay_strategy or RetryDelayStrategy.default()
        )
        self.__retry_delay_reset_threshold = retry_delay_reset_threshold
        self.__current_retry_delay_strategy = self.__base_retry_delay_strategy
        self.__next_retry_delay = 0

        self.__base_error_strategy = error_strategy or ErrorStrategy.always_fail()
        self.__current_error_strategy = self.__base_error_strategy

        self.__last_event_id = last_event_id

        if logger is None:
            logger = logging.getLogger('launchdarkly-eventsource-async.null')
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
        self.__logger = logger

        self.__connection_client: AsyncConnectionClient = connect.create_client(logger)
        self.__connection_result: Optional[AsyncConnectionResult] = None
        self._retry_reset_baseline: float = 0
        self.__disconnected_time: float = 0

        self.__closed = False
        self.__interrupted = False

    async def start(self):
        """
        Attempts to start the stream if it is not already active.
        """
        await self._try_start(False)

    async def close(self):
        """
        Permanently shuts down this client instance and closes any active connection.
        """
        self.__closed = True
        await self.interrupt()
        await self.__connection_client.close()

    async def interrupt(self):
        """
        Stops the stream connection if it is currently active, without permanently closing.
        """
        if self.__connection_result:
            self.__interrupted = True
            await self.__connection_result.close()
            self.__connection_result = None
            self._compute_next_retry_delay()

    @property
    def all(self) -> AsyncIterable[Action]:
        """
        An async iterable series of notifications from the stream.

        Each can be any subclass of :class:`.Action`: :class:`.Event`, :class:`.Comment`,
        :class:`.Start`, or :class:`.Fault`.
        """
        return self._all_generator()

    @property
    def events(self) -> AsyncIterable[Event]:
        """
        An async iterable series of :class:`.Event` objects received from the stream.
        """
        return self._events_generator()

    async def _all_generator(self):
        while True:
            while self.__connection_result is None:
                result = await self._try_start(True)
                if result is not None:
                    yield result

            lines = _AsyncBufferedLineReader.lines_from(self.__connection_result.stream)
            reader = _AsyncSSEReader(lines, self.__last_event_id, None)
            error: Optional[Exception] = None
            try:
                async for ec in reader.events_and_comments():
                    self.__last_event_id = reader.last_event_id
                    yield ec
                    if self.__interrupted:
                        break
                self.__connection_result = None
            except Exception as e:
                if self.__closed:
                    return
                error = e
                self.__connection_result = None
            finally:
                self.__last_event_id = reader.last_event_id

            self._compute_next_retry_delay()
            fail_or_continue, self.__current_error_strategy = (
                self.__current_error_strategy.apply(error)
            )
            if fail_or_continue == ErrorStrategy.FAIL:
                if error is None:
                    yield Fault(None)
                    return
                raise error
            yield Fault(error)
            continue

    async def _events_generator(self):
        async for item in self._all_generator():
            if isinstance(item, Event):
                yield item

    @property
    def next_retry_delay(self) -> float:
        """
        The retry delay that will be used for the next reconnection, in seconds.
        """
        return self.__next_retry_delay

    def _compute_next_retry_delay(self):
        if self.__retry_delay_reset_threshold > 0 and self._retry_reset_baseline != 0:
            now = time.time()
            connection_duration = now - self._retry_reset_baseline
            if connection_duration >= self.__retry_delay_reset_threshold:
                self.__current_retry_delay_strategy = self.__base_retry_delay_strategy
                self._retry_reset_baseline = now
        self.__next_retry_delay, self.__current_retry_delay_strategy = (
            self.__current_retry_delay_strategy.apply(self.__base_retry_delay)
        )

    async def _try_start(self, can_return_fault: bool):
        if self.__connection_result is not None:
            return None
        while True:
            if self.__next_retry_delay > 0:
                delay = (
                    self.__next_retry_delay
                    if self.__disconnected_time == 0
                    else self.__next_retry_delay
                    - (time.time() - self.__disconnected_time)
                )
                if delay > 0:
                    self.__logger.info("Will reconnect after delay of %fs" % delay)
                    await asyncio.sleep(delay)
            try:
                self.__connection_result = await self.__connection_client.connect(
                    self.__last_event_id
                )
            except Exception as e:
                self.__disconnected_time = time.time()
                self._compute_next_retry_delay()
                fail_or_continue, self.__current_error_strategy = (
                    self.__current_error_strategy.apply(e)
                )
                if fail_or_continue == ErrorStrategy.FAIL:
                    raise e
                if can_return_fault:
                    return Fault(e)
                continue
            self._retry_reset_baseline = time.time()
            self.__current_error_strategy = self.__base_error_strategy
            self.__interrupted = False
            return Start(self.__connection_result.headers)

    @property
    def last_event_id(self) -> Optional[str]:
        """
        The ID value, if any, of the last known event.
        """
        return self.__last_event_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, type, value, traceback):
        await self.close()


__all__ = ['AsyncSSEClient']
