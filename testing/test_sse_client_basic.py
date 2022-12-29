from ld_eventsource import *
from ld_eventsource.retry import *

from testing.helpers import *
from testing.http_util import *

from urllib3.exceptions import ProtocolError


# These tests for SSEClient are fairly basic, just ensuring that it is really making HTTP requests and that 
# the API works as expected. The contract test suite is much more thorough - see ../contract-tests.


class TestSSEClientHTTPBehavior:
    def test_sends_expected_headers(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', stream)
                with SSEClient(server.uri):
                    r = server.await_request()
                    assert r.headers['Accept'] == 'text/event-stream'
                    assert r.headers['Cache-Control'] == 'no-cache'

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
    
    def test_non_retryable_io_error(self):
        with start_server() as server:
            server.for_path('/', CauseNetworkError())
            try:
                with SSEClient(server.uri, retry_filter=never_retry):
                    pass
                raise Exception("expected exception, did not get one")
            except ProtocolError as e:
                pass
    
    def test_auto_redirect_301(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', BasicResponse(301, None, {'Location': server.uri + '/real-stream'}))
                server.for_path('/real-stream', stream)
                with SSEClient(server.uri):
                    pass
            server.await_request()
            server.await_request()
    
    def test_auto_redirect_307(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', BasicResponse(307, None, {'Location': server.uri + '/real-stream'}))
                server.for_path('/real-stream', stream)
                with SSEClient(server.uri):
                    pass
            server.await_request()
            server.await_request()


class TestSSEClientEventsStream:
    def test_receives_events(self):
        with start_server() as server:
            with make_stream() as stream:
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

    def test_receives_events_with_defer_connect(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', stream)

                with SSEClient(server.uri, defer_connect=True) as client:
                    stream.push("event: event1\ndata: data1\n\n")

                    events = client.events

                    event1 = next(events)
                    assert event1.event == 'event1'
                    assert event1.data == 'data1'

    def test_events_returns_eof_after_non_retryable_failure(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', stream)

                with SSEClient(server.uri, retry_filter=never_retry) as client:
                    stream.push("event: event1\ndata: data1\n\n")

                    events = client.events

                    event1 = next(events)
                    assert event1.event == 'event1'
                    assert event1.data == 'data1'

                    stream.close()

                    event2 = next(events, "done")
                    assert event2 == "done"


class TestSSEClientAllStream:
    def test_receives_all(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', stream)

                with SSEClient(server.uri) as client:
                    stream.push("event: event1\ndata: data1\n\n:whatever\nevent: event2\ndata: data2\n\n")

                    all = client.all

                    item1 = next(all)
                    assert isinstance(item1, Start)

                    item2 = next(all)
                    assert isinstance(item2, Event)
                    assert item2.event == 'event1'
                    assert item2.data == 'data1'

                    item3 = next(all)
                    assert isinstance(item3, Comment)
                    assert item3.comment == 'whatever'

                    item4 = next(all)
                    assert isinstance(item4, Event)
                    assert item4.event == 'event2'
                    assert item4.data == 'data2'

    def test_all_returns_fault_and_eof_after_non_retryable_failure(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', stream)

                with SSEClient(server.uri, retry_filter=never_retry) as client:
                    stream.push("event: event1\ndata: data1\n\n")

                    all = client.all

                    item1 = next(all)
                    assert isinstance(item1, Start)

                    item2 = next(all)
                    assert isinstance(item2, Event)
                    assert item2.event == 'event1'
                    assert item2.data == 'data1'

                    stream.close()

                    item3 = next(all)
                    assert isinstance(item3, Fault)
                    assert item3.error is None
                    assert item3.will_retry is False

                    item4 = next(all, 'done')
                    assert item4 == 'done'
