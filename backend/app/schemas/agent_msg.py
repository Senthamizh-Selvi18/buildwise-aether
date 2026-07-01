# backend/app/schemas/agent_msg.py
from pydantic import BaseModel, Field
from typing import List, Optional

class VectorPoint(BaseModel):
    x: float
    y: float

class FurnitureItem(BaseModel):
    item_type: str
    label: str
    x: float
    y: float
    w: float
    h: float

class ArchitecturalRoomPolygon(BaseModel):
    room_id: str
    name: str
    points: List[VectorPoint]
    center_x: float
    center_y: float
    width_ft: float
    height_ft: float
    area_sqft: float
    fill_color_hex: str
    paint_name: str
    furniture_layout: List[FurnitureItem]

class StructuralWall(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    is_exterior: bool

class ArchitecturePortal(BaseModel):
    portal_type: str  # "door" or "window"
    x1: float
    y1: float
    x2: float
    y2: float
    associated_room: str

class StructuralColumn(BaseModel):
    x: float
    y: float

class FloorBlueprintLayer(BaseModel):
    floor_level: int
    floor_name: str
    rooms: List[ArchitecturalRoomPolygon]
    walls: List[StructuralWall]
    portals: List[ArchitecturePortal]
    columns: List[StructuralColumn]
    has_staircase: bool = True
    has_balcony: bool = False

class CompleteHomeDesignLayout(BaseModel):
    layout_id: str
    title: str
    space_efficiency_sentence: str
    vastu_compliance_sentence: str
    estimated_cost_usd: float
    floors: List[FloorBlueprintLayer]

class DesignGenerationResponse(BaseModel):
    requires_clarification: bool
    missing_fields: List[str]
    questions: List[str]
    options: Optional[dict] = None