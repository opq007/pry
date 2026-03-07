"""
Thread-safe proxy pool manager.
"""
import threading
from datetime import datetime
from typing import List, Tuple, Optional


class ProxyPool:
    """Thread-safe proxy pool manager."""

    def __init__(self, target_count: int = 200):
        """
        Initialize proxy pool.

        Args:
            target_count: Maximum number of proxies to keep in pool
        """
        self.target_count = target_count
        self._lock = threading.Lock()
        self.valid_proxies: List[str] = []
        self.last_updated: str = "Not yet started"
        self._round_robin_index: int = 0  # 轮询索引

    def get_proxies(self) -> List[str]:
        """
        Get copy of valid proxies (thread-safe).

        Returns:
            List of proxy strings in "ip:port" format
        """
        with self._lock:
            return self.valid_proxies.copy()

    def update_proxies(self, new_proxies: List[str]) -> None:
        """
        Update proxy pool (thread-safe).

        Args:
            new_proxies: List of valid proxy strings
        """
        with self._lock:
            self.valid_proxies = new_proxies[:self.target_count]
            self.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def get_next_proxy(self) -> Optional[str]:
        """
        Get next proxy using round-robin (thread-safe).

        Returns:
            Proxy string in "ip:port" format, or None if pool is empty
        """
        with self._lock:
            if not self.valid_proxies:
                return None
            proxy = self.valid_proxies[self._round_robin_index % len(self.valid_proxies)]
            self._round_robin_index += 1
            return proxy

    def get_status(self) -> dict:
        """
        Get proxy pool status (thread-safe).

        Returns:
            Dictionary with pool status information
        """
        with self._lock:
            return {
                "proxy_pool_size": len(self.valid_proxies),
                "target_count": self.target_count,
                "last_updated": self.last_updated,
                "proxy_types": ["http", "socks5"]
            }