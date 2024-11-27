import random

def load_all_proxies() -> list[str]:
    proxies = []
    with open('proxies.txt') as f:
        proxies = f.read().splitlines()

    formatted_proxies = []
    for proxy in proxies:
        try:
            proxy = f"http://{proxy}"
            formatted_proxies.append(proxy)
        except:
            pass
    return formatted_proxies

def get_proxy(proxies):
    return random.choice(proxies)