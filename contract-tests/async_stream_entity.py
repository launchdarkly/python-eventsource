import asyncio
import json
import logging
import os
import sys
import traceback

import aiohttp

# Import ld_eventsource from parent directory
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from ld_eventsource.actions import Comment, Event, Fault  # noqa: E402
from ld_eventsource.async_client import AsyncSSEClient  # noqa: E402
from ld_eventsource.config.async_connect_strategy import AsyncConnectStrategy  # noqa: E402
from ld_eventsource.config.error_strategy import ErrorStrategy  # noqa: E402


def millis_to_seconds(t):
    return None if t is None else t / 1000


class AsyncStreamEntity:
    def __init__(self, options, http_session: aiohttp.ClientSession):
        self.options = options
        self.callback_url = options["callbackUrl"]
        self.log = logging.getLogger(options["tag"])
        self.closed = False
        self.callback_counter = 0
        self.sse = None
        self._http_session = http_session
        asyncio.create_task(self.run())

    async def run(self):
        stream_url = self.options["streamUrl"]
        try:
            self.log.info('Opening stream from %s', stream_url)

            request_options = {}
            if self.options.get("readTimeoutMs") is not None:
                request_options["timeout"] = aiohttp.ClientTimeout(
                    sock_read=millis_to_seconds(self.options.get("readTimeoutMs"))
                )

            connect = AsyncConnectStrategy.http(
                url=stream_url,
                headers=self.options.get("headers"),
                aiohttp_request_options=request_options if request_options else None,
            )
            sse = AsyncSSEClient(
                connect,
                initial_retry_delay=millis_to_seconds(self.options.get("initialDelayMs")),
                last_event_id=self.options.get("lastEventId"),
                error_strategy=ErrorStrategy.from_lambda(
                    lambda _: (
                        ErrorStrategy.FAIL if self.closed else ErrorStrategy.CONTINUE,
                        None,
                    )
                ),
                logger=self.log,
            )
            self.sse = sse
            async for item in sse.all:
                if isinstance(item, Event):
                    self.log.info('Received event from stream (%s)', item.event)
                    await self.send_message(
                        {
                            'kind': 'event',
                            'event': {
                                'type': item.event,
                                'data': item.data,
                                'id': item.last_event_id,
                            },
                        }
                    )
                elif isinstance(item, Comment):
                    self.log.info('Received comment from stream: %s', item.comment)
                    await self.send_message({'kind': 'comment', 'comment': item.comment})
                elif isinstance(item, Fault):
                    if self.closed:
                        break
                    if item.error:
                        self.log.info('Received error from stream: %s', item.error)
                        await self.send_message({'kind': 'error', 'error': str(item.error)})
        except Exception as e:
            self.log.info('Received error from stream: %s', e)
            self.log.info(traceback.format_exc())
            await self.send_message({'kind': 'error', 'error': str(e)})

    async def do_command(self, command: str) -> bool:
        self.log.info('Test service sent command: %s' % command)
        # currently we support no special commands
        return False

    async def send_message(self, message):
        if self.closed:
            return
        self.callback_counter += 1
        callback_url = "%s/%d" % (self.callback_url, self.callback_counter)
        try:
            async with self._http_session.post(
                callback_url,
                data=json.dumps(message),
                headers={'Content-Type': 'application/json'},
            ) as resp:
                if resp.status >= 300 and not self.closed:
                    self.log.error('Callback request returned HTTP error %d', resp.status)
        except Exception as e:
            if not self.closed:
                self.log.error('Callback request failed: %s', e)

    async def close(self):
        self.closed = True
        if self.sse is not None:
            await self.sse.close()
        self.log.info('Test ended')
