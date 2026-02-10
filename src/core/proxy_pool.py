"""
Thread-safe proxy pool manager.
"""
import threading
from datetime import datetime
from typing import List


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
                "last_updated": self.last_updated
            }