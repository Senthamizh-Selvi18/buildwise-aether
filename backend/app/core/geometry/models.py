from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class Point:
    x: float
    y: float

@dataclass
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> float:
        return abs(self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

@dataclass
class PlotShape:
    """
    Represents the actual buildable plot outline as a simple polygon
    (ordered list of vertices, edges implicitly closed from last -> first).
    A plain rectangle is just a 4-point polygon, so this is a strict
    superset of the old "plot_width x plot_depth rectangle" model and
    is fully backward compatible with it.
    """
    polygon: List[Point]
    shape_type: str = "rectangle"

    @property
    def bounding_box(self) -> BoundingBox:
        xs = [p.x for p in self.polygon]
        ys = [p.y for p in self.polygon]
        return BoundingBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))

    @property
    def edges(self) -> List[Tuple[Point, Point]]:
        n = len(self.polygon)
        return [(self.polygon[i], self.polygon[(i + 1) % n]) for i in range(n)]

    @property
    def area(self) -> float:
        # Shoelace formula -- exact area of the (possibly irregular) plot.
        n = len(self.polygon)
        total = 0.0
        for i in range(n):
            x1, y1 = self.polygon[i].x, self.polygon[i].y
            x2, y2 = self.polygon[(i + 1) % n].x, self.polygon[(i + 1) % n].y
            total += x1 * y2 - x2 * y1
        return abs(total) / 2.0

    @property
    def points_xy(self) -> List[Tuple[float, float]]:
        return [(p.x, p.y) for p in self.polygon]

@dataclass
class RoomGeometry:
    id: str
    name: str
    bbox: BoundingBox
    paint_name: str = "Classic Alabaster"
    paint_hex: str = "#ffffff"

    @property
    def polygon(self) -> List[Point]:
        return [
            Point(self.bbox.x1, self.bbox.y1),
            Point(self.bbox.x2, self.bbox.y1),
            Point(self.bbox.x2, self.bbox.y2),
            Point(self.bbox.x1, self.bbox.y2)
        ]

    @property
    def center(self) -> Point:
        # NOTE: previously referenced self.width / self.height, which do not
        # exist on RoomGeometry (only on BoundingBox). Fixed to read through
        # self.bbox, which is what actually carries width/height.
        return Point(
            x=self.bbox.x1 + (self.bbox.width / 2),
            y=self.bbox.y1 + (self.bbox.height / 2)
        )

@dataclass
class AdjacencyEdge:
    room_a_id: str
    room_b_id: str
    x1: float
    y1: float
    x2: float
    y2: float
    is_horizontal: bool

    @property
    def length(self) -> float:
        if self.is_horizontal:
            return abs(self.x2 - self.x1)
        return abs(self.y2 - self.y1)

@dataclass
class WallGeometry:
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    is_exterior: bool

@dataclass
class PortalGeometry:
    portal_type: str  # "door" or "window"
    x1: float
    y1: float
    x2: float
    y2: float
    associated_room: str

    # Door-specific attributes for accurate architectural swing arcs
    is_horizontal: bool = True
    hinge_x: Optional[float] = None
    hinge_y: Optional[float] = None
    swing_direction_x: Optional[float] = None
    swing_direction_y: Optional[float] = None

@dataclass
class DimensionLine:
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    is_horizontal: bool

@dataclass
class FloorPlanGeometry:
    floor_name: str
    plot_width: float
    plot_depth: float
    rooms: List[RoomGeometry] = field(default_factory=list)
    walls: List[WallGeometry] = field(default_factory=list)
    portals: List[PortalGeometry] = field(default_factory=list)
    dimensions: List[DimensionLine] = field(default_factory=list)
    has_balcony: bool = False
    svg_raw: str = ""