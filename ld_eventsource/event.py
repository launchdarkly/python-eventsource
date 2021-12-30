import json
from typing import Optional

class Event:
    """
    An event received by SSEClient.
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
    def __init__(self, comment: str):
        self._comment = comment

    @property
    def comment(self) -> str:
        return self._comment

    def __eq__(self, other):
        return isinstance(other, Comment) and self._comment == other._comment

    def __repr__(self):
        return ":" + self._comment
