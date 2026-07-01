import os
import json

class LongTermVectorMemory:
    # ... your existing __init__ or initialization code stays here ...

    def commit_blueprint(self, session_id: str, prompt: str, calculated_options: dict):
        try:
            # Prepare the storage file path safely
            log_file = "blueprint_memory_log.json"
            records = []
            
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r") as f:
                        records = json.load(f)
                except Exception:
                    records = []

            # CRITICAL FIX: Recursively convert custom object instances (like FloorPlan) into clean JSON data
            def make_serializable(obj):
                if hasattr(obj, "dict"):  # If it's a Pydantic model
                    return {k: make_serializable(v) for k, v in obj.dict().items()}
                if hasattr(obj, "__dict__"):  # If it's a standard custom Python class
                    return {k: make_serializable(v) for k, v in obj.__dict__.items()}
                if isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [make_serializable(item) for item in obj]
                return obj

            clean_options = make_serializable(calculated_options)

            new_record = {
                "session_id": session_id,
                "prompt": prompt,
                "data": clean_options
            }
            records.append(new_record)

            with open(log_file, "w") as f:
                json.dump(records, f, indent=2)
                
        except Exception as e:
            print(f"[Memory Warning] Skipped logging blueprint to vector file: {e}")

long_memory = LongTermVectorMemory()