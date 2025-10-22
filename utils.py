import random
import sys
from typing import List
from functools import lru_cache

_proxy_cache = None
_proxy_index = 0

@lru_cache(maxsize=1)
def load_all_proxies() -> List[str]:
    try:
        with open('proxies.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.splitlines()
        proxies = [
            f"http://{line.strip()}" 
            for line in lines 
            if line.strip() and '@' in line and ':' in line
        ]
        
        if proxies:
            print(f"Loaded {len(proxies)} proxies")
        else:
            print("Warning: No valid proxies found in proxies.txt")
            
        return proxies
    except FileNotFoundError:
        print("Warning: proxies.txt not found")
        return []
    except Exception as e:
        print(f"Error reading proxies.txt: {e}")
        return []

def get_proxy(proxies: List[str]) -> str:
    if not proxies:
        return ""
    
    global _proxy_index
    _proxy_index = (_proxy_index + 1) % len(proxies)
    return proxies[_proxy_index]

def get_random_proxy(proxies: List[str]) -> str:
    if not proxies:
        return ""
    
    return random.choice(proxies)