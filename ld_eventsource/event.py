import json
from typing import Optional


class Event:
    """
    An event received by :class:`ld_eventsource.SSEClient`.

    Instances of this class are returned by both :prop:`ld_eventsource.SSEClient.events` and
    :prop:`ld_eventsource.SSEClient.all`.
    """
    def __init__(self,
        event: str='message',
        data: str='',
        id: Optional[str]=None,
        last_event_id: Optional[str]=None
    ):
        self._event = event
        self._data = data
        self._id = id
        self._last_event_id = last_event_id

    @property
    def event(self) -> str:
        """
        The event type, or "message" if not specified.
        """
        return self._event

    @property
    def data(self) -> str:
        """
        The event data.
        """
        return self._data

    @property
    def id(self) -> Optional[str]:
        """
        The value of the `id:` field for this event, or `None` if omitted.
        """
        return self._id

    @property
    def last_event_id(self) -> Optional[str]:
        """
        The value of the most recent `id:` field of an event seen in this stream so far.
        """
        return self._last_event_id

    def __eq__(self, other):
        if not isinstance(other, Event):
            return False
        return self._event == other._event and self._data == other._data \
            and self._id == other._id and self.last_event_id == other.last_event_id

    def __repr__(self):
        return "Event(event=\"%s\", data=%s, id=%s, last_event_id=%s)" % (
            self._event,
            json.dumps(self._data),
            "None" if self._id is None else json.dumps(self._id),
            "None" if self._last_event_id is None else json.dumps(self._last_event_id)
        )


class Comment:
    """
    A comment received by :class:`ld_eventsource.SSEClient`.
    
    Comment lines (any line beginning with a colon) have no significance in the SSE specification
    and can be ignored, but if you want to see them, use :prop:`ld_eventsource.SSEClient.all`.
    They will never be returned by :prop:`ld_eventsource.SSEClient.events`.
    """
    
    def __init__(self, comment: str):
        self._comment = comment

    @property
    def comment(self) -> str:
        """
        The comment text, not including the leading colon.
        """
        return self._comment

    def __eq__(self, other):
        return isinstance(other, Comment) and self._comment == other._comment

    def __repr__(self):
        return ":" + self._comment


class Start:
    """
    Indicates that :class:`ld_eventsource.SSEClient` has successfully connected to a stream.

    Instances of this class are only available from :prop:`ld_eventsource.SSEClient.all`.
    A `Start` is returned for the first successful connection. If the client reconnects
    after a failure, there will be a :class:`ld_eventsource.Fault` followed by a
    `Start`.    
    """
    pass


class Fault:
    """
    Indicates that :class:`ld_eventsource.SSEClient` encountered an error or end of stream.

    Instances of this class are only available from :prop:`ld_eventsource.SSEClient.all`.
    They indicate either 1. a problem that happened after an initial successful connection
    was made, or 2. a problem with the initial connection, if you passed `True` for
    the `defer_connect` parameter to the :class:`ld_eventsource.SSEClient` constructor.
    """

    def __init__(self, error: Optional[Exception], will_retry: bool, retry_delay: float):
        self.__error = error
        self.__will_retry = will_retry
        self.__retry_delay = retry_delay
    
    @property
    def error(self) -> Optional[Exception]:
        """
        The exception that caused the stream to fail, if any. If this is `None`, it means
        that the stream simply ran out of data, i.e. the server shut down the connection
        in an orderly way after sending an EOF chunk as defined by chunked transfer encoding.
        """
        return self.__error
    
    @property
    def will_retry(self) -> bool:
        """
        True if the :class:`ld_eventsource.SSEClient` will try to reconnect. This depends on
        the nature of the error and whether a custom `retry_filter` was specified.
        """
        return self.__will_retry
    
    @property
    def retry_delay(self) -> float:
        """
        The time, in seconds, that the :class:`ld_eventsource.SSEClient` will wait before
        trying to reconnect. If :prop:`will_retry` was False, then this value is undefined.
        """
        return self.__retry_delay
