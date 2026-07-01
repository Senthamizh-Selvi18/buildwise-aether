from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# =====================================================================
# INTEGRATED GEOMETRY ENGINE SCHEMA CONTRACTS
# =====================================================================

class Point2D(BaseModel):
    x: float
    y: float

class FurnitureItem(BaseModel):
    name: str
    type: str
    x: float
    y: float
    w: float
    h: float

class ArchitecturalElement(BaseModel):
    type: str  # "door", "window", "staircase"
    x1: float
    y1: float
    x2: float
    y2: float
    metadata: Optional[Dict[str, Any]] = None

class StructuralWall(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    is_exterior: bool

class ArchitecturePortal(BaseModel):
    portal_type: str  # "door", "window"
    x1: float = Field(default=0.0, alias="x1")
    y1: float = Field(default=0.0, alias="y1")
    x2: float = Field(default=0.0, alias="x2")
    y2: float = Field(default=0.0, alias="y2")
    associated_room: str

class Config:
    populate_by_name = True

class StructuralColumn(BaseModel):
    x: float
    y: float

class RoomLayout(BaseModel):
    name: str
    label: str
    x1: float
    y1: float
    x2: float
    y2: float
    area_sqft: float
    fill_color_hex: str = "#ffffff"
    paint_name: str = "Classic Alabaster"
    points: List[Point2D] = Field(default_factory=list)
    furniture: List[FurnitureItem] = Field(default_factory=list)
    furniture_layout: List[FurnitureItem] = Field(default_factory=list)
    elements: List[ArchitecturalElement] = Field(default_factory=list)

class FloorPlan(BaseModel):
    floor_name: str  # "Ground Floor", "First Floor", "Second Floor"
    rooms: List[RoomLayout]
    walls: List[StructuralWall] = Field(default_factory=list)
    portals: List[ArchitecturePortal] = Field(default_factory=list)
    columns: List[StructuralColumn] = Field(default_factory=list)
    has_balcony: bool = False
    svg_dump: str = ""

class CostReportSchema(BaseModel):
    total_estimated_cost_inr: float
    material_breakdown: Dict[str, float]
    labor_cost_inr: float
    finishing_cost_inr: float

class PaintRecommendationSchema(BaseModel):
    room_name: str
    primary_color_name: str
    primary_color_hex: str
    accent_color_name: str
    accent_color_hex: str

class EvaluationReportSchema(BaseModel):
    overall_score: float
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    vastu_score: float
    space_efficiency: float
    natural_lighting_score: float
    ventilation_score: float

class LayoutOptionPayload(BaseModel):
    option_id: str  # "OPTION_A_SPACE", "OPTION_B_VASTU"
    display_name: str
    floors: List[FloorPlan]
    vastu_score: float
    vastu_report: List[str] = Field(default_factory=list)
    style_applied: str
    paint_palette: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    space_utilization_score: float
    circulation_score: float
    wasted_area_score: float
    explanation: str
    svg_floorplans: List[str] = Field(default_factory=list)
    cost_estimation: Optional[CostReportSchema] = None
    paint_recommendations: List[PaintRecommendationSchema] = Field(default_factory=list)
    dimensions_data: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation_details: Optional[EvaluationReportSchema] = None

class ClarificationPayload(BaseModel):
    requires_clarification: bool
    missing_fields: List[str]
    questions: List[str]

class AetherResponseSchema(BaseModel):
    session_id: str
    clarification: Optional[ClarificationPayload] = None
    options: Optional[Dict[str, LayoutOptionPayload]] = None
    errors: List[str] = Field(default_factory=list)

class AetherRequestSchema(BaseModel):
    session_id: str
    user_prompt: str
    plot_shape: str  
    plot_width: float
    plot_depth: float
    floors_requested: int = 1
    current_answers: Optional[Dict[str, str]] = Field(default_factory=dict)