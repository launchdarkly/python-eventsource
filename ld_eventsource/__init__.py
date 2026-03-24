from ld_eventsource.sse_client import *


def __getattr__(name):
    # Lazily import AsyncSSEClient so that aiohttp (an optional dependency)
    # is never imported for sync-only users who don't have it installed.
    if name == 'AsyncSSEClient':
        from ld_eventsource.async_client import AsyncSSEClient
        return AsyncSSEClient
    raise AttributeError(f"module 'ld_eventsource' has no attribute {name!r}")
