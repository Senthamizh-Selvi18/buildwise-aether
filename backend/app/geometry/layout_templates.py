import math
from enum import Enum
from typing import List, Dict, Tuple
from pydantic import BaseModel, Field
from backend.app.geometry.models import Point2D, RoomType

class PlotOrientation(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

class TemplateArchetype(str, Enum):
    DUPLEX = "duplex"
    VILLA = "villa"
    ROW_HOUSE = "row_house"
    COMPACT = "compact"

class SpatialSector(str, Enum):
    NORTH_EAST = "north_east"
    NORTH_WEST = "north_west"
    SOUTH_EAST = "south_east"
    SOUTH_WEST = "south_west"
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    CENTER = "center"

class SectorBoundary(BaseModel):
    sector_type: SpatialSector
    bottom_left: Point2D
    top_right: Point2D

    @property
    def width(self) -> float:
        return self.top_right.x - self.bottom_left.x

    @property
    def height(self) -> float:
        return self.top_right.y - self.bottom_left.y

    @property
    def center(self) -> Point2D:
        return Point2D(
            x=self.bottom_left.x + (self.width / 2.0),
            y=self.bottom_left.y + (self.height / 2.0)
        )

    def contains_point(self, pt: Point2D) -> bool:
        return (self.bottom_left.x <= pt.x <= self.top_right.x and 
                self.bottom_left.y <= pt.y <= self.top_right.y)

class FootprintTemplate(BaseModel):
    archetype: TemplateArchetype
    orientation: PlotOrientation
    total_allowed_area_sqft: float
    number_of_floors: int
    plot_width_mm: float
    plot_length_mm: float
    built_width_mm: float
    built_length_mm: float
    front_setback_mm: float
    rear_setback_mm: float
    side_setback_left_mm: float
    side_setback_right_mm: float
    sectors_by_floor: Dict[int, List[SectorBoundary]] = Field(default_factory=dict)
    default_room_assignments: Dict[RoomType, SpatialSector] = Field(default_factory=dict)

class LayoutTemplateEngine:
    SQFT_TO_SQMM: float = 92903.04

    @staticmethod
    def calculate_setbacks(archetype: TemplateArchetype, width_mm: float, length_mm: float) -> Tuple[float, float, float, float]:
        """
        Computes standard architectural setbacks (front, rear, left, right) in millimeters 
        based on design archetypes to safeguard open spaces like yards and gardens.
        """
        if archetype == TemplateArchetype.ROW_HOUSE:
            return 3000.0, 1500.0, 0.0, 0.0  # Zero side setbacks for zero-lot lines
        elif archetype == TemplateArchetype.VILLA:
            return 4500.0, 3000.0, 1800.0, 1800.0  # Generous open setbacks all around
        elif archetype == TemplateArchetype.DUPLEX:
            return 3500.0, 2000.0, 1200.0, 1200.0
        else:
            return 2500.0, 1500.0, 1000.0, 1000.0

    @classmethod
    def generate_layout_envelope(
        cls, 
        target_area_sqft: float, 
        archetype: TemplateArchetype, 
        orientation: PlotOrientation = PlotOrientation.NORTH,
        floors: int = 1
    ) -> FootprintTemplate:
        """
        Calculates exact mathematical outer bounding boxes and internal operational zones 
        for a given square footage specification without using arbitrary random variables.
        """
        # Distribute target build area across floor targets
        area_per_floor_sqft = target_area_sqft / float(floors)
        area_per_floor_sqmm = area_per_floor_sqft * cls.SQFT_TO_SQMM

        # Define ideal structural aspect ratios (Length to Width ratios)
        if archetype == TemplateArchetype.ROW_HOUSE:
            aspect_ratio = 2.5  # Long and narrow plot
        elif archetype == TemplateArchetype.VILLA:
            aspect_ratio = 1.1  # More square-shaped plot
        else:
            aspect_ratio = 1.4  # Standard golden ratio configuration

        # Compute optimal built width and length dimensions
        built_width_mm = math.sqrt(area_per_floor_sqmm / aspect_ratio)
        built_length_mm = built_width_mm * aspect_ratio

        # Establish boundary setbacks
        front_sb, rear_sb, left_sb, right_sb = cls.calculate_setbacks(archetype, built_width_mm, built_length_mm)

        # Derive absolute plot bounding box requirements
        plot_width_mm = built_width_mm + left_sb + right_sb
        plot_length_mm = built_length_mm + front_sb + rear_sb

        # Create localized 3x3 programmatic spatial sectors for layout routing
        sectors_by_floor: Dict[int, List[SectorBoundary]] = {}
        
        # Origin point (0,0) starts at the inner built corner inside the setbacks
        w_third = built_width_mm / 3.0
        l_third = built_length_mm / 3.0

        for f in range(floors):
            floor_sectors = []
            
            # Subdivide the floor footprint deterministically into an active coordinate grid
            matrix_definitions = [
                (SpatialSector.SOUTH_WEST, 0.0, 0.0, w_third, l_third),
                (SpatialSector.SOUTH, w_third, 0.0, w_third * 2.0, l_third),
                (SpatialSector.SOUTH_EAST, w_third * 2.0, 0.0, built_width_mm, l_third),
                (SpatialSector.WEST, 0.0, l_third, w_third, l_third * 2.0),
                (SpatialSector.CENTER, w_third, l_third, w_third * 2.0, l_third * 2.0),
                (SpatialSector.EAST, w_third * 2.0, l_third, built_width_mm, l_third * 2.0),
                (SpatialSector.NORTH_WEST, 0.0, l_third * 2.0, w_third, built_length_mm),
                (SpatialSector.NORTH, w_third, l_third * 2.0, w_third * 2.0, built_length_mm),
                (SpatialSector.NORTH_EAST, w_third * 2.0, l_third * 2.0, built_width_mm, built_length_mm),
            ]

            for sector_id, x1, y1, x2, y2 in matrix_definitions:
                floor_sectors.append(
                    SectorBoundary(
                        sector_type=sector_id,
                        bottom_left=Point2D(x=x1, y=y1),
                        top_right=Point2D(x=x2, y=y2)
                    )
                )
            sectors_by_floor[f] = floor_sectors

        # Map architectural functional associations natively to specific grid sectors
        default_room_assignments = {
            RoomType.LIVING: SpatialSector.CENTER,
            RoomType.KITCHEN: SpatialSector.SOUTH_EAST,   # Matches standard Southeast placement configurations
            RoomType.BEDROOM: SpatialSector.SOUTH_WEST,   # Master suite anchoring zone
            RoomType.BATHROOM: SpatialSector.WEST,
            RoomType.DINING: SpatialSector.EAST,
            RoomType.STAIRS: SpatialSector.NORTH_WEST,
            RoomType.CORRIDOR: SpatialSector.CENTER,
            RoomType.BALCONY: SpatialSector.NORTH,
        }

        return FootprintTemplate(
            archetype=archetype,
            orientation=orientation,
            total_allowed_area_sqft=target_area_sqft,
            number_of_floors=floors,
            plot_width_mm=round(plot_width_mm, 2),
            plot_length_mm=round(plot_length_mm, 2),
            built_width_mm=round(built_width_mm, 2),
            built_length_mm=round(built_length_mm, 2),
            front_setback_mm=front_sb,
            rear_setback_mm=rear_sb,
            side_setback_left_mm=left_sb,
            side_setback_right_mm=right_sb,
            sectors_by_floor=sectors_by_floor,
            default_room_assignments=default_room_assignments
        )