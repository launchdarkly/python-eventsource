import json
import logging
import os
import sys
from logging.config import dictConfig

import aiohttp.web
from async_stream_entity import AsyncStreamEntity

default_port = 8000

dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    },
})

global_log = logging.getLogger('testservice')

stream_counter = 0
streams = {}


async def handle_get_status(request):
    body = {
        'capabilities': [
            'comments',
            'headers',
            'last-event-id',
            'read-timeout',
        ]
    }
    return aiohttp.web.Response(
        body=json.dumps(body),
        content_type='application/json',
    )


async def handle_delete_stop(request):
    global_log.info("Test service has told us to exit")
    os._exit(0)


async def handle_post_create_stream(request):
    global stream_counter, streams

    options = json.loads(await request.read())

    stream_counter += 1
    stream_id = str(stream_counter)
    resource_url = '/streams/%s' % stream_id

    stream = AsyncStreamEntity(options, request.app['http_session'])
    streams[stream_id] = stream

    return aiohttp.web.Response(status=201, headers={'Location': resource_url})


async def handle_post_stream_command(request):
    stream_id = request.match_info['id']
    params = json.loads(await request.read())

    stream = streams.get(stream_id)
    if stream is None:
        return aiohttp.web.Response(status=404)
    if not await stream.do_command(params.get('command')):
        return aiohttp.web.Response(status=400)
    return aiohttp.web.Response(status=204)


async def handle_delete_stream(request):
    stream_id = request.match_info['id']

    stream = streams.get(stream_id)
    if stream is None:
        return aiohttp.web.Response(status=404)
    await stream.close()
    return aiohttp.web.Response(status=204)


async def on_startup(app):
    app['http_session'] = aiohttp.ClientSession()


async def on_cleanup(app):
    await app['http_session'].close()


def make_app():
    app = aiohttp.web.Application()
    app.router.add_get('/', handle_get_status)
    app.router.add_delete('/', handle_delete_stop)
    app.router.add_post('/', handle_post_create_stream)
    app.router.add_post('/streams/{id}', handle_post_stream_command)
    app.router.add_delete('/streams/{id}', handle_delete_stream)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    port = default_port
    if sys.argv[len(sys.argv) - 1] != 'async_service.py':
        port = int(sys.argv[len(sys.argv) - 1])
    global_log.info('Listening on port %d', port)
    aiohttp.web.run_app(make_app(), host='0.0.0.0', port=port)
