from collections.abc import Mapping
from typing import Any, Optional, Protocol, runtime_checkable

Headers = Mapping[str, Any]
"""
A case-insensitive mapping of HTTP response headers.

Header name lookups are case-insensitive per RFC 7230, so
``headers.get('content-type')`` and ``headers.get('Content-Type')``
return the same value. The concrete type returned depends on the HTTP
backend in use and should not be relied upon directly.
"""


@runtime_checkable
class ExceptionWithHeaders(Protocol):
    """
    Protocol for exceptions that include HTTP response headers.

    This allows type-safe access to headers from error responses without
    using hasattr checks.
    """

    @property
    def headers(self) -> Optional[Headers]:
        """The HTTP response headers associated with this exception."""
        raise NotImplementedError


class HTTPStatusError(Exception):
    """
    This exception indicates that the client was able to connect to the server, but that
    the HTTP response had an error status.

    When available, the response headers are accessible via the :attr:`headers` property.
    """

    def __init__(self, status: int, headers: Optional[Headers] = None):
        super().__init__("HTTP error %d" % status)
        self._status = status
        self._headers = headers

    @property
    def status(self) -> int:
        return self._status

    @property
    def headers(self) -> Optional[Headers]:
        """The HTTP response headers, if available. Header names are case-insensitive."""
        return self._headers


class HTTPContentTypeError(Exception):
    """
    This exception indicates that the HTTP response did not have the expected content
    type of `"text/event-stream"`.

    When available, the response headers are accessible via the :attr:`headers` property.
    """

    def __init__(self, content_type: str, headers: Optional[Headers] = None):
        super().__init__("invalid content type \"%s\"" % content_type)
        self._content_type = content_type
        self._headers = headers

    @property
    def content_type(self) -> str:
        return self._content_type

    @property
    def headers(self) -> Optional[Headers]:
        """The HTTP response headers, if available. Header names are case-insensitive."""
        return self._headers
