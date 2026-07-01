import json
from google.adk.agents import Agent
from backend.app.schemas.floorplan import AetherRequestSchema, ClarificationPayload
from backend.app.core.config import settings

try:
    from backend.app.core import cache_manager
    if hasattr(cache_manager, "CacheManager"):
        cache_service = getattr(cache_manager, "CacheManager")
    elif hasattr(cache_manager, "cache_manager"):
        cache_service = getattr(cache_manager, "cache_manager")
    else:
        cache_service = cache_manager 
except (ImportError, AttributeError):
    cache_service = None

class RequirementsAgent:
    def __init__(self):
        self.adk_agent = Agent(
            name="RequirementsAgent",
            model=settings.GEMINI_MODEL,
            instruction="Extract structural space configurations into structured JSON payloads. Intercept if parameters are omitted."
        )

    def extract(self, req: AetherRequestSchema) -> dict:
        missing_fields = []
        questions = []
        
        combined_text = (req.user_prompt + " " + " ".join(req.current_answers.values())).lower()
        answers = {k.lower(): v.lower() for k, v in req.current_answers.items()}
        
        # 1. Dimensional Checks
        if req.plot_width <= 0 or req.plot_depth <= 0:
            missing_fields.append("plot_dimensions")
            questions.append("What are the exact dimensions of your plot in feet (Width x Depth)?")
            
        # 2. Floor Checks
        if "floor" not in combined_text and req.floors_requested <= 1 and "floors" not in answers:
            missing_fields.append("floors_requested")
            questions.append("How many floors do you plan to construct (e.g., Ground Floor only, G+1, G+2)?")
                
        # 3. Vastu Preference
        if "vastu" not in combined_text and "wasthu" not in combined_text and "vastu" not in answers:
            missing_fields.append("vastu_compliance")
            questions.append("Do you require strict Vastu compliance for room orientations?")

        # 4. Mandatory Modern Amenities Checks
        if "parking" not in combined_text and "garage" not in combined_text and "parking" not in answers:
            missing_fields.append("parking_requirements")
            questions.append("Do you need dedicated car parking or a garage within the plot?")

        if "balcony" not in combined_text and "balcony" not in answers:
            missing_fields.append("balcony_requirements")
            questions.append("Would you like to include a balcony in the layout?")

        if "garden" not in combined_text and "landscape" not in combined_text and "garden" not in answers:
            missing_fields.append("garden_requirements")
            questions.append("Should space be allocated for a garden or outdoor landscaping?")

        if missing_fields:
            return {
                "requires_clarification": True,
                "missing_fields": missing_fields,
                "questions": questions
            }

        cache_key = f"req_{req.session_id}_{hash(combined_text)}"
        if cache_service and hasattr(cache_service, "get"):
            try:
                cached_val = cache_service.get(cache_key)
                if cached_val:
                    return json.loads(cached_val)
            except Exception:
                pass

        # Deterministic extraction logic (Fallback when AI fails or is bypassed)
        extracted_rooms = ["Living Room", "Kitchen", "Common Bathroom", "Staircase"]
        
        if "dining" in combined_text:
            extracted_rooms.append("Dining Room")
            
        if "master" in combined_text or "attached" in combined_text:
            extracted_rooms.append("Master Bedroom (Attached Bath)")

        if "3bhk" in combined_text or "3 bhk" in combined_text:
            extracted_rooms.extend(["Bedroom 2", "Bedroom 3"])
        elif "4bhk" in combined_text or "4 bhk" in combined_text:
            extracted_rooms.extend(["Bedroom 2", "Bedroom 3", "Bedroom 4"])
        else:
            if "master" not in combined_text:
                extracted_rooms.extend(["Bedroom 1"])
                
        if "pooja" in combined_text or "puja" in combined_text:
            extracted_rooms.append("Pooja Room")

        if "parking" in answers and "yes" in answers["parking"]:
            extracted_rooms.append("Parking Area")

        parsed = {
            "rooms": extracted_rooms, 
            "style": answers.get("style", "Modern Contemporary"),
            "plot_shape": req.plot_shape,
            "width": req.plot_width,
            "depth": req.plot_depth,
            "floors": int(answers.get("floors", req.floors_requested)),
            "requires_clarification": False
        }
        
        if cache_service and hasattr(cache_service, "set"):
            try:
                cache_service.set(cache_key, json.dumps(parsed))
            except Exception:
                pass
                
        return parsed