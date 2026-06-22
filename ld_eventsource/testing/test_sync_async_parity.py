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
from ld_eventsource.config.async_connect_strategy import (
    AsyncConnectionClient, AsyncConnectionResult, AsyncConnectStrategy)
from ld_eventsource.config.connect_strategy import (ConnectionClient,
                                                    ConnectionResult,
                                                    ConnectStrategy)
from ld_eventsource.sse_client import SSEClient


def _public_names(cls):
    return {name for name in dir(cls) if not name.startswith("_")} - set(dir(object))


# Each param pairs a public synchronous class with its asynchronous counterpart, plus
# allowlists of names intentionally present on only one side. Every allowlisted name must
# carry a justification; if the test flags a genuinely one-sided member, add it here with a
# comment rather than weakening the comparison.
@pytest.mark.parametrize(
    "sync_cls, async_cls, sync_only, async_only",
    [
        pytest.param(SSEClient, AsyncSSEClient, set(), set(), id="SSEClient/AsyncSSEClient"),
        pytest.param(ConnectStrategy, AsyncConnectStrategy, set(), set(), id="ConnectStrategy/AsyncConnectStrategy"),
        pytest.param(ConnectionClient, AsyncConnectionClient, set(), set(), id="ConnectionClient/AsyncConnectionClient"),
        pytest.param(ConnectionResult, AsyncConnectionResult, set(), set(), id="ConnectionResult/AsyncConnectionResult"),
    ],
)
def test_sync_async_public_surface_matches(sync_cls, async_cls, sync_only, async_only):
    sync_names = _public_names(sync_cls)
    async_names = _public_names(async_cls)

    sync_only_diff = sync_names - async_names - sync_only
    async_only_diff = async_names - sync_names - async_only

    assert not sync_only_diff, (
        f"{sync_cls.__name__} exposes public names with no counterpart on "
        f"{async_cls.__name__}: {sorted(sync_only_diff)}. Add the missing member to the "
        f"async class, or allowlist it in 'sync_only' with a justification."
    )
    assert not async_only_diff, (
        f"{async_cls.__name__} exposes public names with no counterpart on "
        f"{sync_cls.__name__}: {sorted(async_only_diff)}. Add the missing member to the "
        f"sync class, or allowlist it in 'async_only' with a justification."
    )
