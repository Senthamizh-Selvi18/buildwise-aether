import math
from enum import Enum
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field

class RoomType(str, Enum):
    LIVING = "living"
    DINING = "dining"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    BATHROOM = "bathroom"
    STAIRS = "stairs"
    CORRIDOR = "corridor"
    BALCONY = "balcony"
    PARKING = "parking"
    GARDEN = "garden"
    UTILITY = "utility"
    CUSTOM = "custom"

class WallType(str, Enum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    PARTITION = "partition"
    SHARED = "shared"

class Point2D(BaseModel):
    x: float = Field(..., description="X coordinate in millimeters")
    y: float = Field(..., description="Y coordinate in millimeters")

    def distance_to(self, other: 'Point2D') -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

class LineSegment(BaseModel):
    start: Point2D
    end: Point2D

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def angle(self) -> float:
        return math.atan2(self.end.y - self.start.y, self.end.x - self.start.x)

class Door(BaseModel):
    id: str
    position: Point2D = Field(..., description="Center point of the door on the wall")
    width: float = Field(default=900.0, description="Door width in mm")
    thickness: float = Field(default=150.0, description="Door frame thickness in mm")
    swing_angle: float = Field(default=90.0, description="Swing arc angle in degrees")
    is_open_inward: bool = Field(default=True, description="Swing direction relative to the room")

class Window(BaseModel):
    id: str
    position: Point2D = Field(..., description="Center point of the window on the wall")
    width: float = Field(default=1200.0, description="Window width in mm")
    thickness: float = Field(default=150.0, description="Wall thickness at window location in mm")
    glazing_type: str = Field(default="standard", description="Type of window glass/frame")

class Wall(BaseModel):
    id: str
    segment: LineSegment
    thickness: float = Field(default=150.0, description="Wall thickness in mm (e.g., 230mm for exterior, 115mm for interior)")
    wall_type: WallType
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    connected_rooms: List[str] = Field(default_factory=list, description="IDs of rooms sharing this wall")

class Room(BaseModel):
    id: str
    name: str
    room_type: RoomType
    polygon: List[Point2D] = Field(..., description="Ordered list of vertices defining the room footprint")
    walls: List[Wall] = Field(default_factory=list)
    target_area_sqft: float = Field(..., description="Requested area in square feet")
    computed_area_sqft: float = Field(default=0.0, description="Actual computed area after layout geometry generation")
    color_hex: str = Field(default="#FFFFFF", description="Background color for SVG rendering")
    adjacent_to: List[str] = Field(default_factory=list, description="List of Room IDs this room must connect to")
    
    @property
    def centroid(self) -> Point2D:
        if not self.polygon:
            return Point2D(x=0.0, y=0.0)
        x_sum = sum(p.x for p in self.polygon)
        y_sum = sum(p.y for p in self.polygon)
        count = len(self.polygon)
        return Point2D(x=x_sum / count, y=y_sum / count)

class DimensionLine(BaseModel):
    start: Point2D
    end: Point2D
    label: str
    offset: float = Field(default=300.0, description="Distance from the measured object in mm")

class FloorLevel(BaseModel):
    level_index: int = Field(default=0, description="0 for ground floor, 1 for first floor, etc.")
    rooms: List[Room] = Field(default_factory=list)
    circulation_paths: List[LineSegment] = Field(default_factory=list)
    dimensions: List[DimensionLine] = Field(default_factory=list)
    bounding_box: Tuple[Point2D, Point2D] = Field(
        default=(Point2D(x=0, y=0), Point2D(x=0, y=0)), 
        description="Bottom-left and top-right coordinates of the floor footprint"
    )

class BuildingGeometry(BaseModel):
    project_id: str
    floors: List[FloorLevel] = Field(default_factory=list)
    total_area_sqft: float = Field(default=0.0)
    external_features: Dict[str, Room] = Field(
        default_factory=dict, 
        description="Features outside the main footprint, e.g., 'parking', 'garden'"
    )
    svg_payload: Optional[str] = Field(default=None, description="The final rendered SVG string")