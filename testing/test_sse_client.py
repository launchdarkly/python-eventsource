from ld_eventsource import SSEClient
from ld_eventsource.errors import HTTPContentTypeError, HTTPStatusError

from testing.http_util import start_server, BasicResponse, ChunkedResponse


# The tests for SSEClient are fairly basic, just ensuring that it is really making HTTP requests and that the
# API works as expected. The contract test suite is much more thorough - see ../contract-tests.

class TestSSEClient:
    def test_sends_expected_headers(self):
        with start_server() as server:
            with ChunkedResponse({ 'Content-Type': 'text/event-stream' }) as stream:
                server.for_path('/', stream)
                with SSEClient(server.uri):
                    r = server.await_request()
                    assert r.headers['Accept'] == 'text/event-stream'
                    assert r.headers['Cache-Control'] == 'no-cache'

    def test_receives_messages(self):
        with start_server() as server:
            with ChunkedResponse({ 'Content-Type': 'text/event-stream' }) as stream:
                server.for_path('/', stream)

                with SSEClient(server.uri) as client:                
                    stream.push("event: event1\ndata: data1\n\nevent: event2\ndata: data2\n\n")

                    events = client.events

                    event1 = next(events)
                    assert event1.event == 'event1'
                    assert event1.data == 'data1'

                    event2 = next(events)
                    assert event2.event == 'event2'
                    assert event2.data == 'data2'

    def test_http_status_error(self):
        with start_server() as server:
            server.for_path('/', BasicResponse(400))
            try:
                with SSEClient(server.uri):
                    pass
                raise Exception("expected exception, did not get one")
            except HTTPStatusError as e:
                assert e.status == 400

    def test_http_content_type_error(self):
        with start_server() as server:
            with ChunkedResponse({ 'Content-Type': 'text/plain' }) as stream:
                server.for_path('/', stream)
                try:
                    with SSEClient(server.uri):
                        pass
                    raise Exception("expected exception, did not get one")
                except HTTPContentTypeError as e:
                    assert e.content_type == "text/plain"
