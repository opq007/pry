"""
Proxy forwarder - forwards requests through proxy pool with SOCKS5 support.
"""
import requests
from typing import Optional, Dict, Any, Tuple
from .proxy_pool import ProxyPool
from .config import config


class ProxyForwarder:
    """
    Forward HTTP requests through proxy pool with round-robin selection.
    Supports both HTTP and SOCKS5 proxies.
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
        fallback_direct: bool = True
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
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts with different proxies
            fallback_direct: If True, fall back to direct request when proxy pool is empty

        Returns:
            Tuple of (Response, proxy_used) or (None, error_message) on failure.
            proxy_used is "DIRECT" when fallback to direct request.
        """
        if timeout is None:
            timeout = config.FORWARD_TIMEOUT

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
                    timeout=timeout,
                    allow_redirects=True
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
                    timeout=timeout,
                    allow_redirects=True
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
