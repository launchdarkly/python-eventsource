from typing import AsyncIterator, Callable, Optional

from ld_eventsource.actions import Comment, Event


class _AsyncBufferedLineReader:
    """
    Async version of _BufferedLineReader. Reads UTF-8 stream data as a series of text lines,
    each of which can be terminated by \n, \r, or \r\n.
    """

    @staticmethod
    async def lines_from(chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
        last_char_was_cr = False
        partial_line = None

        async for chunk in chunks:
            if len(chunk) == 0:
                continue

            lines = chunk.splitlines()
            if last_char_was_cr:
                last_char_was_cr = False
                if chunk[0] == 10:
                    lines.pop(0)
                    if len(lines) == 0:
                        continue
            if partial_line is not None:
                lines[0] = partial_line + lines[0]
                partial_line = None
            last_char = chunk[-1]
            if last_char == 13:
                last_char_was_cr = True
            elif last_char != 10:
                partial_line = lines.pop()
            for line in lines:
                yield line.decode()


class _AsyncSSEReader:
    def __init__(
        self,
        lines_source: AsyncIterator[str],
        last_event_id: Optional[str] = None,
        set_retry: Optional[Callable[[int], None]] = None,
    ):
        self._lines_source = lines_source
        self._last_event_id = last_event_id
        self._set_retry = set_retry

    @property
    def last_event_id(self):
        return self._last_event_id

    async def events_and_comments(self) -> AsyncIterator:
        event_type = ""
        event_data = None
        event_id = None
        async for line in self._lines_source:
            if line == "":
                if event_data is not None:
                    if event_id is not None:
                        self._last_event_id = event_id
                    yield Event(
                        "message" if event_type == "" else event_type,
                        event_data,
                        event_id,
                        self._last_event_id,
                    )
                event_type = ""
                event_data = None
                event_id = None
                continue
            colon_pos = line.find(':')
            if colon_pos == 0:
                yield Comment(line[1:])
                continue
            if colon_pos < 0:
                name = line
                value = ""
            else:
                name = line[:colon_pos]
                if colon_pos < (len(line) - 1) and line[colon_pos + 1] == ' ':
                    colon_pos += 1
                value = line[colon_pos + 1:]
            if name == 'event':
                event_type = value
            elif name == 'data':
                event_data = (
                    value if event_data is None else (event_data + "\n" + value)
                )
            elif name == 'id':
                if value.find("\x00") < 0:
                    event_id = value
            elif name == 'retry':
                try:
                    n = int(value)
                    if self._set_retry:
                        self._set_retry(n)
                except Exception:
                    pass
