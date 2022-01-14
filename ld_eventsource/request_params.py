from typing import Optional


class RequestParams:
    """
    Parameters telling :class:`ld_eventsource.SSEClient` how to connect to a stream.

    When calling the :class:`ld_eventsource.SSEClient` constructor, you can pass a
    `RequestParams` instance for the first parameter instead of a simple URL string.
    Also, if you have specified a custom `retry_filter`, the filter can set
    :prop:`ld_eventsource.retry.RetryFilterResult.request_params` to change the
    parameters for the next request on a retry.
    """
    def __init__(
        self,
        url: str,
        headers: Optional[dict]=None,
        urllib3_request_options: Optional[dict]=None
    ):
        self.__url = url
        self.__headers = headers
        self.__urllib3_request_options = urllib3_request_options
    
    @property
    def url(self) -> str:
        """
        The stream URL.
        """
        return self.__url

    @property
    def headers(self) -> Optional[dict]:
        """
        Optional HTTP headers to add to the request.
        """
        return self.__headers

    @property
    def urllib3_request_options(self) -> Optional[dict]:
        """
        Optional `kwargs` to add to the `urllib3.request` call. These can include any parameters
        supported by `urllib3.request`, such as `timeout`.
        """
        return self.__urllib3_request_options
