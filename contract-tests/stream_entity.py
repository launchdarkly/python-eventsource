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

port = 8000

stream_counter = 0
streams = {}

http_client = urllib3.PoolManager()

def to_millis(t):
    if t is None:
        return None
    return t / 1000


class StreamEntity:
    def __init__(self, options):
        self.options = options
        self.callback_url = options["callbackUrl"]
        self.log = logging.getLogger(options["tag"])
        self.closed = False
        self.callback_counter = 0
        
        thread = threading.Thread(target=self.run)
        thread.start()

    def run(self):
        stream_url = self.options["streamUrl"]
        try:
            self.log.info('Opening stream from %s', stream_url)
            sse = SSEClient(
                stream_url,
                initial_retry_delay=to_millis(self.options.get("initialDelayMs")),
                last_event_id=self.options.get("lastEventId"),
                headers=self.options.get("headers"),
                timeout=None if self.options.get("readTimeoutMs") is None else
                    urllib3.Timeout(read=to_millis(self.options.get("readTimeoutMs"))),
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
                elif isinstance(item, Exception):
                    self.log.info('Received error from stream: %s' % item)
                    self.send_message({
                        'kind': 'error',
                        'error': str(item)
                    })
            self.send_message({
                'kind': 'error',
                'error': 'Stream closed'
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
        if command == 'restart':
            self.sse.restart()
            return True
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
        if self.sse:
            self.sse.close()
        self.closed = True
        self.log.info('Test ended')
