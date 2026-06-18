"""
Parity guard for the hand-maintained synchronous and asynchronous client pairs.

The sync and async implementations in this package are written and maintained by hand as
parallel files. This test asserts that each public sync/async pair exposes the same public
surface, so that a method or property added to one side but forgotten on the other fails CI.

The public surface includes properties as well as methods, so the comparison is over all
public attribute names (anything not starting with ``_``) rather than callables only.
"""

import pytest

from ld_eventsource.async_client import AsyncSSEClient
from ld_eventsource.config.async_connect_strategy import (AsyncConnectionClient,
                                                          AsyncConnectionResult,
                                                          AsyncConnectStrategy)
from ld_eventsource.config.connect_strategy import (ConnectionClient,
                                                    ConnectionResult,
                                                    ConnectStrategy)
from ld_eventsource.sse_client import SSEClient

# Each entry pairs a public synchronous class with its asynchronous counterpart, plus
# allowlists of names that are intentionally present on only one side. Every allowlisted
# name must carry a justification; if the test flags a genuinely one-sided member, add it
# here with a comment rather than weakening the comparison.
_PAIRS = [
    {
        "sync": SSEClient,
        "async": AsyncSSEClient,
        # Names allowed to exist only on the sync class.
        "sync_only": set(),
        # Names allowed to exist only on the async class.
        "async_only": set(),
    },
    {
        "sync": ConnectStrategy,
        "async": AsyncConnectStrategy,
        "sync_only": set(),
        "async_only": set(),
    },
    {
        "sync": ConnectionClient,
        "async": AsyncConnectionClient,
        "sync_only": set(),
        "async_only": set(),
    },
    {
        "sync": ConnectionResult,
        "async": AsyncConnectionResult,
        "sync_only": set(),
        "async_only": set(),
    },
]


def _public_names(cls):
    return {name for name in dir(cls) if not name.startswith("_")} - set(dir(object))


@pytest.mark.parametrize(
    "pair",
    _PAIRS,
    ids=[f"{p['sync'].__name__}/{p['async'].__name__}" for p in _PAIRS],
)
def test_sync_async_public_surface_matches(pair):
    sync_names = _public_names(pair["sync"])
    async_names = _public_names(pair["async"])

    sync_only = sync_names - async_names - pair["sync_only"]
    async_only = async_names - sync_names - pair["async_only"]

    assert not sync_only, (
        f"{pair['sync'].__name__} exposes public names with no counterpart on "
        f"{pair['async'].__name__}: {sorted(sync_only)}. Add the missing member to the "
        f"async class, or allowlist it in 'sync_only' with a justification."
    )
    assert not async_only, (
        f"{pair['async'].__name__} exposes public names with no counterpart on "
        f"{pair['sync'].__name__}: {sorted(async_only)}. Add the missing member to the "
        f"sync class, or allowlist it in 'async_only' with a justification."
    )
