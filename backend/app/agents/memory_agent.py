import json
import os
from backend.app.schemas.floorplan import LayoutOptionPayload

class MemoryAgent:
    def __init__(self):
        self.storage_path = "data/memory_store/long_term.json"
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    def persist_generation_context(self, session_id: str, prompt: str, option_a: LayoutOptionPayload, option_b: LayoutOptionPayload) -> bool:
        record = {
            "session_id": session_id,
            "user_prompt": prompt,
            "payloads": {
                "option_a": option_a.dict(),
                "option_b": option_b.dict()
            }
        }
        
        try:
            history = []
            if os.path.exists(self.storage_path) and os.path.getsize(self.storage_path) > 0:
                with open(self.storage_path, "r") as f:
                    history = json.load(f)
            
            # Upsert history log record context matching session signatures
            history = [h for h in history if h.get("session_id") != session_id]
            history.append(record)
            
            with open(self.storage_path, "w") as f:
                json.dump(history, f, indent=2)
            return True
        except Exception:
            return False