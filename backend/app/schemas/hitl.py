from pydantic import BaseModel
from typing import Dict, Any

class HumanInTheLoopApproval(BaseModel):
    session_id: str
    is_approved: bool
    modifications: str
    captured_state: Dict[str, Any]