from ld_eventsource import *
from ld_eventsource.retry import *

from testing.http_util import *


def make_stream() -> ChunkedResponse:
    return ChunkedResponse({ 'Content-Type': 'text/event-stream' })

def never_retry(params: RetryFilterParams) -> RetryFilterResult:
    return RetryFilterResult(False)

def retry_for_status(status: int) -> RetryFilter:
    def apply(params: RetryFilterParams) -> RetryFilterResult:
        if isinstance(params.error, HTTPStatusError):
            return RetryFilterResult(params.error.status == status)
        return RetryFilterResult(False)
    return apply

def no_delay(params: RetryDelayParams) -> RetryDelayResult:
    return RetryDelayResult(0)
