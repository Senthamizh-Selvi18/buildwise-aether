from typing import Dict, Any

class ShortTermMemoryBus:
    def __init__(self):
        self._active_sessions: Dict[str, Any] = {}

    def save_step(self, session_id: str, key: str, val: Any):
        if session_id not in self._active_sessions:
            self._active_sessions[session_id] = {}
        self._active_sessions[session_id][key] = val

    def read_step(self, session_id: str, key: str) -> Any:
        return self._active_sessions.get(session_id, {}).get(key, None)

short_memory = ShortTermMemoryBus()