import pytest

from ld_eventsource.actions import Comment, Event
from ld_eventsource.async_reader import _AsyncBufferedLineReader, _AsyncSSEReader


async def lines_from_bytes(*chunks: bytes):
    """Helper: collect all lines from given byte chunks."""
    async def gen():
        for chunk in chunks:
            yield chunk

    result = []
    async for line in _AsyncBufferedLineReader.lines_from(gen()):
        result.append(line)
    return result


async def events_from_lines(*lines: str):
    """Helper: collect all events/comments from given lines."""
    async def gen():
        for line in lines:
            yield line

    reader = _AsyncSSEReader(gen())
    result = []
    async for item in reader.events_and_comments():
        result.append(item)
    return result


@pytest.mark.asyncio
async def test_line_reader_simple_newline():
    lines = await lines_from_bytes(b"hello\nworld\n")
    assert lines == ["hello", "world"]


@pytest.mark.asyncio
async def test_line_reader_carriage_return():
    lines = await lines_from_bytes(b"hello\rworld\r")
    assert lines == ["hello", "world"]


@pytest.mark.asyncio
async def test_line_reader_crlf():
    lines = await lines_from_bytes(b"hello\r\nworld\r\n")
    assert lines == ["hello", "world"]


@pytest.mark.asyncio
async def test_line_reader_crlf_split_across_chunks():
    lines = await lines_from_bytes(b"hello\r", b"\nworld\r\n")
    assert lines == ["hello", "world"]


@pytest.mark.asyncio
async def test_line_reader_partial_line_across_chunks():
    lines = await lines_from_bytes(b"hel", b"lo\n")
    assert lines == ["hello"]


@pytest.mark.asyncio
async def test_line_reader_empty_chunk():
    lines = await lines_from_bytes(b"hello\n", b"", b"world\n")
    assert lines == ["hello", "world"]


@pytest.mark.asyncio
async def test_sse_reader_simple_event():
    items = await events_from_lines("data: hello", "")
    assert len(items) == 1
    assert isinstance(items[0], Event)
    assert items[0].data == "hello"
    assert items[0].event == "message"


@pytest.mark.asyncio
async def test_sse_reader_event_with_type():
    items = await events_from_lines("event: ping", "data: test", "")
    assert len(items) == 1
    assert isinstance(items[0], Event)
    assert items[0].event == "ping"
    assert items[0].data == "test"


@pytest.mark.asyncio
async def test_sse_reader_multiline_data():
    items = await events_from_lines("data: line1", "data: line2", "")
    assert len(items) == 1
    assert items[0].data == "line1\nline2"


@pytest.mark.asyncio
async def test_sse_reader_comment():
    items = await events_from_lines(":this is a comment", "data: event", "")
    assert len(items) == 2
    assert isinstance(items[0], Comment)
    assert items[0].comment == "this is a comment"
    assert isinstance(items[1], Event)


@pytest.mark.asyncio
async def test_sse_reader_event_id():
    items = await events_from_lines("id: 123", "data: hello", "")
    assert len(items) == 1
    assert items[0].id == "123"
    assert items[0].last_event_id == "123"


@pytest.mark.asyncio
async def test_sse_reader_id_persists_across_events():
    items = await events_from_lines(
        "id: 1", "data: first", "",
        "data: second", "",
    )
    assert len(items) == 2
    assert items[0].last_event_id == "1"
    assert items[1].last_event_id == "1"


@pytest.mark.asyncio
async def test_sse_reader_retry_field():
    retries = []

    async def gen():
        for line in ["retry: 5000", "data: test", ""]:
            yield line

    reader = _AsyncSSEReader(gen(), set_retry=lambda n: retries.append(n))
    async for _ in reader.events_and_comments():
        pass
    assert retries == [5000]


@pytest.mark.asyncio
async def test_sse_reader_ignores_null_in_id():
    items = await events_from_lines("id: bad\x00id", "data: test", "")
    assert len(items) == 1
    assert items[0].id is None


@pytest.mark.asyncio
async def test_sse_reader_multiple_events():
    items = await events_from_lines(
        "event: e1", "data: d1", "",
        "event: e2", "data: d2", "",
    )
    assert len(items) == 2
    assert items[0].event == "e1"
    assert items[0].data == "d1"
    assert items[1].event == "e2"
    assert items[1].data == "d2"
