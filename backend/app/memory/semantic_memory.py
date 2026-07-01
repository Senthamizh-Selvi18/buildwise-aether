import os
import json
from typing import List, Dict, Any

MEMORY_FILE_PATH = os.path.join(os.path.dirname(__file__), "design_memory.json")

class SemanticLocalMemory:
    def __init__(self):
        if not os.path.exists(MEMORY_FILE_PATH):
            with open(MEMORY_FILE_PATH, "w") as f:
                json.dump([], f)

    def commit_design(self, session_id: str, prompt: str, payload: Dict[str, Any]):
        try:
            with open(MEMORY_FILE_PATH, "r") as f:
                data = json.load(f)
        except Exception:
            data = []

        data.append({
            "session_id": session_id,
            "prompt": prompt,
            "payload": payload
        })

        with open(MEMORY_FILE_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def retrieve_similar_context(self, prompt: str) -> List[Dict[str, Any]]:
        try:
            with open(MEMORY_FILE_PATH, "r") as f:
                data = json.load(f)
        except Exception:
            return []
        
        words = set(prompt.lower().split())
        scored_matches = []
        for entry in data:
            entry_words = set(entry.get("prompt", "").lower().split())
            intersection = words.intersection(entry_words)
            if intersection:
                scored_matches.append((len(intersection), entry["payload"]))
                
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_matches[:2]]

local_memory = SemanticLocalMemory()