"""
Proxy validator - validates proxies by testing connectivity to YouTube.
"""
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from .config import config


def validate_proxy(ip: str):
    """
    Validate a single proxy against YouTube.

    Args:
        ip: Proxy string in "ip:port" format

    Returns:
        Proxy string if valid, None otherwise
    """
    proxies = {"http": f"http://{ip}", "https": f"http://{ip}"}
    try:
        r = requests.get(config.VALIDATION_URL, proxies=proxies, timeout=config.TIMEOUT_SEC)
        if r.status_code == 200:
            return ip
    except:
        pass
    return None


def validate_proxies(proxy_list: List[str]) -> List[str]:
    """
    Validate multiple proxies concurrently.

    Args:
        proxy_list: List of proxy strings to validate

    Returns:
        List of valid proxy strings
    """
    valid_proxies = []

    with ThreadPoolExecutor(max_workers=config.MAX_THREADS) as executor:
        future_to_ip = {executor.submit(validate_proxy, ip): ip for ip in proxy_list}

        for future in as_completed(future_to_ip):
            result = future.result()
            if result:
                if result not in valid_proxies:
                    print(f"   ✅ VALID: {result}")
                    valid_proxies.append(result)

            # Early stop if we have enough proxies
            if len(valid_proxies) >= config.TARGET_COUNT + 5:
                print("   🎯 Target hit! Stopping scan early.")
                executor.shutdown(wait=False, cancel_futures=True)
                break

    return valid_proxies