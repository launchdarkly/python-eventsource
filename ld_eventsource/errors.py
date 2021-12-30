
class HTTPStatusError(Exception):
    def __init__(self, status: int):
        super().__init__("HTTP error %d" % status)
        self._status = status
    
    @property
    def status(self) -> int:
        return self._status

class HTTPContentTypeError(Exception):
    def __init__(self, content_type: str):
        super().__init__("invalid content type \"%s\"" % content_type)
        self._content_type = content_type
    
    @property
    def content_type(self) -> str:
        return self._content_type
