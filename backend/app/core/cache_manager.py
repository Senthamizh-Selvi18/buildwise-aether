import time
from typing import Dict, Any

class LocalCacheManager:
    def __init__(self):
        self._storage: Dict[str, Any] = {}
        self._ttl = 300  # 5 minute expiration window

    def get(self, key: str) -> Any:
        if key in self._storage:
            item = self._storage[key]
            if time.time() - item["timestamp"] < self._ttl:
                return item["data"]
        return None

    def set(self, key: str, value: Any):
        self._storage[key] = {
            "data": value,
            "timestamp": time.time()
        }

global_cache = LocalCacheManager()