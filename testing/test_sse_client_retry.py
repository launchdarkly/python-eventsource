from ld_eventsource import *
from ld_eventsource.retry import *

from testing.helpers import *
from testing.http_util import *


class TestSSEClientRetryDuringInitialConnect:
    def test_retry_succeeds(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', SequentialHandler(BasicResponse(503), stream))

                with SSEClient(
                    server.uri,
                    retry_delay_strategy=no_delay,
                    retry_filter=retry_for_status(503)
                ) as client:
                    stream.push("data: data1\n\n")

                    events = client.events
                    event1 = next(events)
                    assert event1.data == 'data1'

                server.await_request()
                server.await_request()
                server.should_have_no_more_requests()

    def test_retry_succeeds_then_fails(self):
        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', SequentialHandler(BasicResponse(503), BasicResponse(400), stream))

                try:
                    with SSEClient(
                        server.uri,
                        retry_delay_strategy=no_delay,
                        retry_filter=retry_for_status(503)
                    ):
                        pass
                    raise Exception("expected exception, did not get one")
                except HTTPStatusError as e:
                    assert e.status == 400

                server.await_request()
                server.await_request()
                server.should_have_no_more_requests()


class TestSSEClientRetryWhileReadingStream:
    def test_events_iterator_continues_after_retry(self):
        with start_server() as server:
            with make_stream() as stream1:
                with make_stream() as stream2:
                    server.for_path('/', SequentialHandler(stream1, stream2))

                    stream1.push("data: data1\n\n")
                    stream2.push("data: data2\n\n")

                    with SSEClient(server.uri, retry_delay_strategy=no_delay) as client:
                        events = client.events

                        event1 = next(events)
                        assert event1.data == 'data1'

                        stream1.close()

                        event2 = next(events)
                        assert event2.data == 'data2'

    def test_all_iterator_continues_after_retry(self):
        initial_delay = 0.005

        with start_server() as server:
            with make_stream() as stream1:
                with make_stream() as stream2:
                    with make_stream() as stream3:
                        server.for_path('/', SequentialHandler(stream1, stream2, stream3))

                        stream1.push("data: data1\n\n")
                        stream2.push("data: data2\n\n")
                        stream3.push("data: data3\n\n")

                        with SSEClient(
                            server.uri,
                            initial_retry_delay=initial_delay,
                            retry_delay_strategy=default_retry_delay_strategy(jitter_multiplier=None)
                        ) as client:
                            all = client.all

                            item1 = next(all)
                            assert isinstance(item1, Start)

                            item2 = next(all)
                            assert isinstance(item2, Event)
                            assert item2.data == 'data1'

                            stream1.close()

                            item3 = next(all)
                            assert isinstance(item3, Fault)
                            assert item3.error is None
                            assert item3.will_retry is True
                            assert item3.retry_delay == initial_delay

                            item4 = next(all)
                            assert isinstance(item4, Start)
                            
                            item5 = next(all)
                            assert isinstance(item5, Event)
                            assert item5.data == 'data2'

                            stream2.close()

                            item6 = next(all)
                            assert isinstance(item6, Fault)
                            assert item6.error is None
                            assert item6.will_retry is True
                            assert item6.retry_delay == initial_delay * 2


class TestSSEClientRetryWithDeferConnect:
    def test_all_iterator_shows_initial_retry(self):
        initial_delay = 0.005

        with start_server() as server:
            with make_stream() as stream:
                server.for_path('/', SequentialHandler(BasicResponse(503), stream))

                stream.push("data: data1\n\n")

                with SSEClient(
                    server.uri,
                    initial_retry_delay=initial_delay,
                    retry_delay_strategy=default_retry_delay_strategy(jitter_multiplier=None),
                    retry_filter=retry_for_status(503),
                    defer_connect=True
                ) as client:
                    all = client.all

                    item1 = next(all)
                    assert isinstance(item1, Fault)
                    assert isinstance(item1.error, HTTPStatusError)
                    assert item1.error.status == 503

                    item2 = next(all)
                    assert isinstance(item2, Start)

                    item3 = next(all)
                    assert isinstance(item3, Event)
                    assert item3.data == 'data1'
