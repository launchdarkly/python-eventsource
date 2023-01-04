from ld_eventsource import *

from testing.http_util import *


def make_stream() -> ChunkedResponse:
    return ChunkedResponse({ 'Content-Type': 'text/event-stream' })

def retry_for_status(status: int) -> ErrorStrategy:
    return ErrorStrategy.from_lambda(lambda error: \
        (ErrorStrategy.CONTINUE if isinstance(error, HTTPStatusError) and error.status == status \
            else ErrorStrategy.FAIL, None))

def no_delay() -> RetryDelayStrategy:
    return RetryDelayStrategy.from_lambda(lambda _: (0, None))

