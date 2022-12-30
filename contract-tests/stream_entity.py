import json
import logging
import os
import sys
import threading
import traceback
import urllib3

# Import ld_eventsource from parent directory
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from ld_eventsource import *
from ld_eventsource.config import *


http_client = urllib3.PoolManager()

def millis_to_seconds(t):
    return None if t is None else t / 1000


class StreamEntity:
    def __init__(self, options):
        self.options = options
        self.callback_url = options["callbackUrl"]
        self.log = logging.getLogger(options["tag"])
        self.closed = False
        self.callback_counter = 0
        self.sse = None
        
        thread = threading.Thread(target=self.run)
        thread.start()

    def run(self):
        stream_url = self.options["streamUrl"]
        try:
            self.log.info('Opening stream from %s', stream_url)
            request = RequestParams(
                url=stream_url,
                headers=self.options.get("headers"),
                urllib3_request_options=None if self.options.get("readTimeoutMs") is None else {
                    "timeout": urllib3.Timeout(read=millis_to_seconds(self.options.get("readTimeoutMs")))
                }
            )                    
            sse = SSEClient(
                request,
                initial_retry_delay=millis_to_seconds(self.options.get("initialDelayMs")),
                last_event_id=self.options.get("lastEventId"),
                error_strategy=ErrorStrategy.from_lambda(lambda _:
                    (ErrorStrategy.FAIL if self.closed else ErrorStrategy.CONTINUE, None)),
                logger=self.log
            )
            self.sse = sse
            for item in sse.all:
                if isinstance(item, Event):
                    self.log.info('Received event from stream (%s)', item.event)
                    self.send_message({
                        'kind': 'event',
                        'event': {
                            'type': item.event,
                            'data': item.data,
                            'id': item.last_event_id
                        }
                    })
                elif isinstance(item, Comment):
                    self.log.info('Received comment from stream: %s', item.comment)
                    self.send_message({
                        'kind': 'comment',
                        'comment': item.comment
                    })
                elif isinstance(item, Fault):
                    if self.closed:
                        break
                    # item.error will be None if this is just an EOF rather than an I/O error or HTTP error.
                    # Currently the test harness does not expect us to send an error message in that case.
                    if item.error:
                        self.log.info('Received error from stream: %s' % item.error)
                        self.send_message({
                            'kind': 'error',
                            'error': str(item.error)
                        })
        except Exception as e:
            self.log.info('Received error from stream: %s', e)
            self.log.info(traceback.format_exc())
            self.send_message({
                'kind': 'error',
                'error': str(e)
            })

    def do_command(self, command: str) -> bool:
        self.log.info('Test service sent command: %s' % command)
        # currently we support no special commands
        return False
    
    def send_message(self, message):
        global http_client

        if self.closed:
            return
        self.callback_counter += 1
        callback_url = "%s/%d" % (self.options["callbackUrl"], self.callback_counter)

        try:
            resp = http_client.request(
                'POST',
                callback_url,
                headers = {'Content-Type': 'application/json'},
                body = json.dumps(message)
                )
            if resp.status >= 300 and not self.closed:
                self.log.error('Callback request returned HTTP error %d', resp.status)
        except Exception as e:
            if not self.closed:
                self.log.error('Callback request failed: %s', e)

    def close(self):
        self.closed = True
        # SSEClient.close() doesn't currently work, due to urllib3 hanging when we try to force-close a
        # socket that's doing a blocking read. However, in the context of the contract tests, we know that
        # the server will be closing the connection anyway when a test is done-- so all we need to do is
        # tell ourselves not to retry the connection when it fails, and setting self.closed does that.
        self.log.info('Test ended')
