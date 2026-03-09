"""
Proxy forwarder - forwards requests through proxy pool with SOCKS5 support.
Supports streaming responses for OpenAI-compatible APIs.
"""
import requests
import json
from typing import Optional, Dict, Any, Tuple, Generator, Union
from .proxy_pool import ProxyPool
from .config import config


class ProxyForwarder:
    """
    Forward HTTP requests through proxy pool with round-robin selection.
    Supports both HTTP and SOCKS5 proxies, and streaming responses.
    """

    def __init__(self, proxy_pool: ProxyPool):
        """
        Initialize proxy forwarder.

        Args:
            proxy_pool: ProxyPool instance to use for proxy selection
        """
        self.proxy_pool = proxy_pool

    def _build_proxies(self, proxy: str, proxy_type: str = "http") -> Dict[str, str]:
        """
        Build proxy dict for requests library.

        Args:
            proxy: Proxy string in "ip:port" format
            proxy_type: "http" or "socks5"

        Returns:
            Dict with http and https proxy URLs
        """
        if proxy_type == "socks5":
            # SOCKS5 proxy format
            return {
                "http": f"socks5://{proxy}",
                "https": f"socks5://{proxy}"
            }
        else:
            # HTTP proxy format
            return {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }

    def _is_stream_request(self, headers: Optional[Dict[str, str]], body: Optional[bytes]) -> bool:
        """
        Detect if request is a streaming request.

        Checks:
        1. Accept header for text/event-stream
        2. Request body contains "stream": true (OpenAI style)
        3. Request body contains "sse": true (airforce and other platforms style)

        Args:
            headers: Request headers
            body: Request body

        Returns:
            True if this is a streaming request
        """
        # Check Accept header
        if headers:
            accept = headers.get("accept", "").lower()
            if "text/event-stream" in accept:
                return True

        # Check body for stream/sse flags (OpenAI and alternative API styles)
        if body:
            try:
                # Try to parse as JSON
                body_str = body.decode("utf-8") if isinstance(body, bytes) else body
                body_json = json.loads(body_str)
                # OpenAI style: stream: true
                if body_json.get("stream") is True:
                    return True
                # Alternative style (airforce, etc.): sse: true
                if body_json.get("sse") is True:
                    return True
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return False

    def _is_stream_response(self, response: requests.Response) -> bool:
        """
        Check if response is a streaming response.

        Args:
            response: The response object

        Returns:
            True if response is streaming (SSE)
        """
        content_type = response.headers.get("content-type", "").lower()
        return "text/event-stream" in content_type

    def forward_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        params: Optional[Dict[str, str]] = None,
        proxy_type: str = "http",
        timeout: Optional[int] = None,
        max_retries: int = 3,
        fallback_direct: bool = True,
        stream: bool = False
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """
        Forward a request through proxy pool with automatic retry.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            url: Target URL
            headers: Request headers
            body: Request body (for POST/PUT)
            params: Query parameters
            proxy_type: "http" or "socks5"
            timeout: Request timeout in seconds (for connection, not for full response in stream mode)
            max_retries: Maximum retry attempts with different proxies
            fallback_direct: If True, fall back to direct request when proxy pool is empty
            stream: If True, enable streaming mode for SSE responses

        Returns:
            Tuple of (Response, proxy_used) or (None, error_message) on failure.
            proxy_used is "DIRECT" when fallback to direct request.
            
            When stream=True and response is SSE, response.iter_content() can be used
            to iterate over chunks. The response connection stays open until consumed.
        """
        if timeout is None:
            timeout = config.FORWARD_TIMEOUT

        # Auto-detect stream mode if not explicitly set
        if not stream:
            stream = self._is_stream_request(headers, body)

        # For stream mode, use longer timeout for connection only
        # The response will be streamed, so we don't want a read timeout
        connect_timeout = timeout
        read_timeout = None if stream else timeout
        timeout_tuple = (connect_timeout, read_timeout) if stream else timeout

        last_error = None

        # Try proxy requests
        for attempt in range(max_retries):
            proxy = self.proxy_pool.get_next_proxy()
            if not proxy:
                break  # No more proxies available

            proxies = self._build_proxies(proxy, proxy_type)

            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    data=body,
                    params=params,
                    proxies=proxies,
                    timeout=timeout_tuple,
                    allow_redirects=True,
                    stream=stream  # Enable streaming mode
                )
                return response, proxy

            except requests.exceptions.ProxyError as e:
                last_error = f"Proxy error with {proxy}: {str(e)}"
                continue
            except requests.exceptions.Timeout as e:
                last_error = f"Timeout with proxy {proxy}: {str(e)}"
                continue
            except requests.exceptions.RequestException as e:
                last_error = f"Request failed with proxy {proxy}: {str(e)}"
                continue

        # Fallback: direct request without proxy
        if fallback_direct:
            try:
                response = requests.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    data=body,
                    params=params,
                    timeout=timeout_tuple,
                    allow_redirects=True,
                    stream=stream
                )
                return response, "DIRECT"
            except requests.exceptions.RequestException as e:
                last_error = f"Direct request failed: {str(e)}"

        return None, last_error or "All retry attempts failed"

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        proxy_type: str = "http",
        timeout: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Convenience method for GET requests."""
        return self.forward_request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            proxy_type=proxy_type,
            timeout=timeout
        )

    def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        params: Optional[Dict[str, str]] = None,
        proxy_type: str = "http",
        timeout: Optional[int] = None
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Convenience method for POST requests."""
        return self.forward_request(
            method="POST",
            url=url,
            headers=headers,
            body=body,
            params=params,
            proxy_type=proxy_type,
            timeout=timeout
        )
