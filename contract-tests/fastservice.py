from stream_entity import StreamEntity

import logging
import os
from fastapi import Request, Response, FastAPI, status as faststatus


default_port = 8000

app = FastAPI()

stream_counter = 0
streams = {}
global_log = logging.getLogger('testservice')


@app.get('/')
def status():
    body = {
        'capabilities': [
            'comments',
            'headers',
            'last-event-id',
            'read-timeout'
        ]
    }
    return body


@app.delete('/')
def delete_stop_service():
    global_log.info("Test service has told us to exit")
    os._exit(0)


@app.post('/')
async def post_create_stream(request: Request, response: Response):
    global stream_counter, streams

    options = await request.json()

    stream_counter += 1
    stream_id = str(stream_counter)
    resource_url = '/streams/%s' % stream_id

    stream = StreamEntity(options)
    streams[stream_id] = stream

    response.status_code = faststatus.HTTP_201_CREATED
    response.headers['Location'] = resource_url
    return ''


@app.post('/streams/{id}')
async def post_stream_command(id, request: Request, response: Response):
    global streams

    params = await request.json()

    stream = streams[id]
    if stream is None:
        response.status_code = faststatus.HTTP_404_NOT_FOUND
        return ''
    if not stream.do_command(params.get('command')):
        response.status_code = faststatus.HTTP_400_BAD_REQUEST
        return ''

    response.status_code = faststatus.HTTP_204_NO_CONTENT
    return ''


@app.delete('/streams/{id}')
async def delete_stream(id, response: Response):
    global streams

    stream = streams[id]
    if stream is None:
        response.status_code = faststatus.HTTP_404_NOT_FOUND
        return ''
    await stream.close()
    response.status_code = faststatus.HTTP_204_NO_CONTENT
    return ''
