"""
Background worker - periodically refreshes the proxy pool.
"""
import threading
import time
from datetime import datetime
from typing import Optional
from .proxy_pool import ProxyPool
from .fetcher import fetch_proxies
from .validator import validate_proxies
from .config import config


class ProxyWorker:
    """Background worker to refresh proxy pool."""

    def __init__(self, proxy_pool: ProxyPool):
        """
        Initialize background worker.

        Args:
            proxy_pool: ProxyPool instance to manage
        """
        self.proxy_pool = proxy_pool
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start the background worker thread."""
        if self._thread is None or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True
            )
            self._thread.start()

    def stop(self):
        """Stop the background worker thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run_loop(self):
        """Main worker loop."""
        while self._running:
            try:
                self._refresh_pool()
            except Exception as e:
                print(f"   Error in worker loop: {e}")

            time.sleep(config.CHECK_INTERVAL)

    def _refresh_pool(self):
        """Refresh proxy pool with new validated proxies."""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ☢️ Starting AGGRESSIVE Scan (Threads: {config.MAX_THREADS})...")

        # 1. MASSIVE FETCH (Fill RAM with Candidates)
        raw_proxies = fetch_proxies()
        print(f"   📥 Fetched {len(raw_proxies)} candidates")

        # 2. RE-VALIDATE EXISTING + CHECK NEW (Mixed Pool)
        existing_proxies = self.proxy_pool.get_proxies()
        check_list = existing_proxies + raw_proxies
        check_list = check_list[:5000]  # Limit to 5000 to prevent freezing

        new_valid_pool = []
        print(f"   🚀 Validating {len(check_list)} candidates...")

        new_valid_pool = validate_proxies(check_list)

        # Update Storage
        self.proxy_pool.update_proxies(new_valid_pool)

        print(f"   💤 Sleeping for {config.CHECK_INTERVAL}s. Active Pool: {len(self.proxy_pool.get_proxies())}")