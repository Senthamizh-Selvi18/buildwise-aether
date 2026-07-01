import json
from google.adk.agents import Agent
from backend.app.schemas.floorplan import AetherRequestSchema, ClarificationPayload
from backend.app.core.config import settings

class ClarificationAgent:
    def __init__(self):
        self.adk_agent = Agent(
            name="ClarificationAgent",
            model=settings.GEMINI_MODEL,
            instruction="You are a meticulous validation agent. Check if requirements are missing: plot size, plot shape, floors, vastu preference. Output strictly valid JSON."
        )

    def verify_inputs(self, req: AetherRequestSchema) -> ClarificationPayload:
        missing = []
        questions = []
        
        if not req.plot_width or req.plot_width <= 0:
            missing.append("plot_width")
            questions.append("What is the exact width measurement of your construction plot in feet?")
        if not req.plot_depth or req.plot_depth <= 0:
            missing.append("plot_depth")
            questions.append("What is the absolute depth measurement of your property boundary line in feet?")
        if not req.plot_shape or req.plot_shape == "string":
            missing.append("plot_shape")
            questions.append("What is your property's geometric configuration outline profile (Rectangle, Triangle, L-Shape)?")
            
        if len(missing) > 0:
            return ClarificationPayload(
                requires_clarification=True,
                missing_fields=missing,
                questions=questions
            )
            
        return ClarificationPayload(requires_clarification=False, missing_fields=[], questions=[])