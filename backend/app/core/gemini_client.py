import os
import json
from google.adk import Agent
from google.adk.runners import InMemoryRunner

class GoogleAdkClientWrapper:
    def __init__(self):
        # Read the environment variable we configured earlier
        self.api_key = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))
        
        # Initialize the official Google ADK Agent structural configuration
        self.adk_agent = Agent(
            name="ExtractionBrain",
            model="gemini-2.5-flash",
            instruction=(
                "You are an expert architectural parser. Analyze the user prompt and output a strict "
                "JSON array containing strings of individual room titles requested (e.g. ['Living Room', 'Kitchen']). "
                "Do not include any chat formatting, markdown blocks, or explanation text. Only raw JSON arrays."
            )
        )
        self.runner = InMemoryRunner(agent=self.adk_agent)

    def extract_requirements_deterministic(self, prompt: str) -> list:
        # If no API key is provided, gracefully drop back to local parsing instantly
        if not self.api_key or self.api_key == "FREE_TIER_KEY":
            return self._execute_local_fallback(prompt)

        try:
            # Use the Google ADK runtime architecture to trigger a generation step
            response = self.runner.run(
                user_id="default_user",
                session_id="default_session",
                new_message={"parts": [{"text": prompt}]}
            )
            
            # The ADK returns a stream/iterable of block events; extract the text content safely
            response_text = ""
            for event in response:
                if hasattr(event, "is_final_response") and event.is_final_response():
                    response_text = event.content.parts[0].text
                    break
                elif hasattr(event, "text"):
                    response_text = event.text
                    break
                    
            response_text = response_text.strip()
            # Clean off accidental markdown formatting backticks if the model adds them
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            parsed_rooms = json.loads(response_text.strip())
            if isinstance(parsed_rooms, list) and len(parsed_rooms) > 0:
                # Keep 'Staircase' fixed if present to guarantee multi-floor structural integrity
                if "Staircase" not in parsed_rooms:
                    parsed_rooms.insert(0, "Staircase")
                return parsed_rooms
        except Exception as e:
            print(f"[ADK Warning] Live calling pipe errored out: {e}. Activating safety layout net.")
            
        return self._execute_local_fallback(prompt)

    def _execute_local_fallback(self, prompt: str) -> list:
        cleaned = prompt.lower()
        rooms = ["Staircase", "Living Room", "Kitchen", "Bathroom"]
        if "3bhk" in cleaned or "3 bhk" in cleaned or "three bedroom" in cleaned:
            rooms.extend(["Bedroom 1", "Bedroom 2", "Bedroom 3"])
        elif "2bhk" in cleaned or "2 bhk" in cleaned:
            rooms.extend(["Bedroom 1", "Bedroom 2"])
        else:
            rooms.extend(["Bedroom 1"])
            
        if "pooja" in cleaned or "puja" in cleaned:
            rooms.append("Pooja Room")
        return rooms

adk_client = GoogleAdkClientWrapper()