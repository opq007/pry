"""
Proxy fetcher - fetches proxy candidates from multiple sources.
"""
import requests
import random
from typing import List


def fetch_proxies() -> List[str]:
    """
    Fetch proxies from multiple sources.

    Returns:
        List of proxy strings in "ip:port" format
    """
    sources = [
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"
    ]

    raw_proxies = []

    for source in sources:
        try:
            r = requests.get(source, timeout=5)
            if r.status_code == 200:
                raw_proxies += r.text.strip().split("\n")
        except Exception as e:
            # Skip unavailable sources
            print(f"   Warning: Failed to fetch from {source}: {e}")

    # Deduplicate and shuffle
    raw_proxies = list(set(raw_proxies))
    random.shuffle(raw_proxies)

    return raw_proxies
