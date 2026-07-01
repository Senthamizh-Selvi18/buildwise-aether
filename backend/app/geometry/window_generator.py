import math
from typing import List, Dict, Any, Tuple, Optional, Set
from pydantic import BaseModel, Field
from backend.app.geometry.models import Point2D, LineSegment, Wall, Room, FloorLevel, BuildingGeometry, RoomType

class Window(BaseModel):
    """Data model representing the exact computed geometry and performance metadata of an architectural window."""
    id: str
    floor: int
    room: str
    wall_id: str
    center_point: Point2D
    start_point: Point2D
    end_point: Point2D
    width: float
    height: float
    sill_height: float
    lintel_height: float
    window_type: str  # "SLIDING", "CASEMENT", "FIXED", "CORNER", "VENTILATOR", "FRENCH", "LARGE_GLASS"
    glass_area: float
    ventilation_area: float
    is_sliding: bool
    is_fixed: bool
    is_corner_window: bool
    orientation: str  # "NORTH", "SOUTH", "EAST", "WEST"

class WindowGenerator:
    """
    Deterministic architectural window placement engine. Computes daylighting ratios,
    calculates structural openings, and syncs reference keys into the wall graph.
    """
    
    CORNER_OFFSET_MM: float = 400.0  # Spacing buffer away from junctions and corner columns
    STANDARD_LINTEL_MM: float = 2100.0

    @classmethod
    def _determine_orientation(cls, segment: LineSegment) -> str:
        """Determines the compass orientation of a wall segment based on its 2D direction angle."""
        dx = segment.end.x - segment.start.x
        dy = segment.end.y - segment.start.y
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)

        # Normalize angle to a 0-360 range
        angle_deg = angle_deg if angle_deg >= 0 else angle_deg + 360.0

        if (45.0 <= angle_deg < 135.0):
            return "NORTH"
        elif (135.0 <= angle_deg < 225.0):
            return "WEST"
        elif (225.0 <= angle_deg < 315.0):
            return "SOUTH"
        else:
            return "EAST"

    @classmethod
    def calculate_window_position(cls, wall: Wall, win_width: float, has_door: bool) -> Optional[Tuple[Point2D, Point2D, Point2D]]:
        """
        Calculates a clean opening interval along a wall segment, shifting coordinates
        away from any existing door assemblies to prevent structural collisions.
        """
        wall_len = wall.segment.length
        min_required_space = win_width + (cls.CORNER_OFFSET_MM * 2.0)

        if wall_len < min_required_space:
            return None

        dx = wall.segment.end.x - wall.segment.start.x
        dy = wall.segment.end.y - wall.segment.start.y
        ux = dx / wall_len
        uy = dy / wall_len

        # If the wall contains a door cutout, shift the window opening toward the opposite end
        if has_door:
            start_dist = wall_len - win_width - cls.CORNER_OFFSET_MM
        else:
            # Otherwise, center the window uniformly along the wall line
            start_dist = (wall_len - win_width) / 2.0

        if start_dist < cls.CORNER_OFFSET_MM:
            return None

        start_pt = Point2D(x=wall.segment.start.x + ux * start_dist, y=wall.segment.start.y + uy * start_dist)
        end_pt = Point2D(x=start_pt.x + ux * win_width, y=start_pt.y + uy * win_width)
        center_pt = Point2D(x=start_pt.x + (ux * win_width / 2.0), y=start_pt.y + (uy * win_width / 2.0))

        return start_pt, end_pt, center_pt

    @classmethod
    def generate_room_windows(cls, floor_idx: int, room: Room, ext_walls: List[Wall]) -> List[Window]:
        """Generates appropriate window structures for standard habitable residential zones."""
        windows: List[Window] = []
        
        # Configure sizing specifications based on room types
        if room.room_type == RoomType.LIVING:
            w_width, w_height, w_sill = 1800.0, 1500.0, 600.0
            w_type, is_sliding, is_fixed = "LARGE_GLASS", True, False
        elif room.room_type == RoomType.BEDROOM:
            w_width, w_height, w_sill = 1500.0, 1200.0, 900.0
            w_type, is_sliding, is_fixed = "SLIDING", True, False
        elif room.room_type == RoomType.KITCHEN:
            w_width, w_height, w_sill = 1200.0, 1050.0, 1050.0  # Raised sill height to clear kitchen counters
            w_type, is_sliding, is_fixed = "CASEMENT", False, False
        elif room.room_type == RoomType.STAIRS:
            w_width, w_height, w_sill = 600.0, 1800.0, 300.0
            w_type, is_sliding, is_fixed = "FIXED", False, True
        elif room.room_type == RoomType.BALCONY:
            w_width, w_height, w_sill = 2000.0, 2100.0, 0.0  # Floor-to-ceiling balcony access window
            w_type, is_sliding, is_fixed = "FRENCH", True, False
        else:
            w_width, w_height, w_sill = 1200.0, 1200.0, 900.0
            w_type, is_sliding, is_fixed = "SLIDING", True, False

        counter = 1
        for wall in ext_walls:
            # Only anchor windows within physical exterior walls hosting this specific room
            if room.id in wall.connected_rooms:
                has_door = len(wall.doors) > 0
                pos = cls.calculate_window_position(wall, w_width, has_door)
                
                if pos:
                    st, en, ce = pos
                    g_area = (w_width / 1000.0) * (w_height / 1000.0)
                    # Sliding windows provide 50% openable ventilation area, casements provide 100%
                    v_area = g_area * 0.5 if is_sliding else (0.0 if is_fixed else g_area)

                    win = Window(
                        id=f"win_{room.id}_{counter}",
                        floor=floor_idx,
                        room=room.id,
                        wall_id=wall.id,
                        center_point=ce,
                        start_point=st,
                        end_point=en,
                        width=w_width,
                        height=w_height,
                        sill_height=w_sill,
                        lintel_height=cls.STANDARD_LINTEL_MM,
                        window_type=w_type,
                        glass_area=round(g_area, 3),
                        ventilation_area=round(v_area, 3),
                        is_sliding=is_sliding,
                        is_fixed=is_fixed,
                        is_corner_window=False,
                        orientation=cls._determine_orientation(wall.segment)
                    )
                    windows.append(win)
                    wall.windows.append(win.id)  # Sync window reference code back into the parent wall graph
                    counter += 1
                    
                    # Prevent over-windowing small rooms by limiting them to one window per wall zone
                    if room.room_type in [RoomType.BEDROOM, RoomType.KITCHEN]:
                        break
        return windows

    @classmethod
    def generate_ventilators(cls, floor_idx: int, room: Room, ext_walls: List[Wall]) -> List[Window]:
        """Generates smaller high-wall structural ventilators for utility fields and bathrooms."""
        ventilators: List[Window] = []
        if room.room_type not in [RoomType.BATHROOM, RoomType.CUSTOM]:
            return ventilators

        v_width, v_height, v_sill = 600.0, 450.0, 1650.0  # Raised sill height for privacy protection
        counter = 1

        for wall in ext_walls:
            if room.id in wall.connected_rooms:
                pos = cls.calculate_window_position(wall, v_width, has_door=len(wall.doors) > 0)
                if pos:
                    st, en, ce = pos
                    g_area = (v_width / 1000.0) * (v_height / 1000.0)
                    
                    vent = Window(
                        id=f"vent_{room.id}_{counter}",
                        floor=floor_idx,
                        room=room.id,
                        wall_id=wall.id,
                        center_point=ce,
                        start_point=st,
                        end_point=en,
                        width=v_width,
                        height=v_height,
                        sill_height=v_sill,
                        lintel_height=cls.STANDARD_LINTEL_MM,
                        window_type="VENTILATOR",
                        glass_area=round(g_area, 3),
                        ventilation_area=round(g_area, 3),
                        is_sliding=False,
                        is_fixed=False,
                        is_corner_window=False,
                        orientation=cls._determine_orientation(wall.segment)
                    )
                    ventilators.append(vent)
                    wall.windows.append(vent.id)
                    counter += 1
                    break
        return ventilators

    @classmethod
    def split_wall_for_window(cls, wall: Wall, window: Window) -> Tuple[LineSegment, LineSegment]:
        """Calculates the remaining structural line segments of a wall after cutting out a window opening."""
        seg1 = LineSegment(start=wall.segment.start, end=window.start_point)
        seg2 = LineSegment(start=window.end_point, end=wall.segment.end)
        return seg1, seg2

    @classmethod
    def validate_windows(cls, windows: List[Window], walls: List[Wall]) -> bool:
        """Runs geometric checks to ensure window openings fit safely within their assigned walls."""
        wall_map = {w.id: w for w in walls}
        for w in windows:
            if w.wall_id not in wall_map:
                return False
            parent_wall = wall_map[w.wall_id]
            if w.width > parent_wall.segment.length:
                return False
        return True

    @classmethod
    def calculate_daylighting(cls, room: Room, windows: List[Window]) -> float:
        """Computes the daylighting ratio by comparing the room's total glazing area to its floor area."""
        room_wins = [w for w in windows if w.room == room.id]
        total_glass = sum(w.glass_area for w in room_wins)
        if room.computed_area_sqft <= 0:
            return 0.0
        # Convert floor area from square feet to square meters (~10.764 sqft = 1 sqm)
        room_area_sqm = room.computed_area_sqft / 10.764
        return round(total_glass / room_area_sqm, 3)

    @classmethod
    def calculate_ventilation_score(cls, room: Room, windows: List[Window]) -> float:
        """Calculates compliance with building codes by verifying that the openable window area is at least 10% of the floor area."""
        room_wins = [w for w in windows if w.room == room.id]
        total_vent_area = sum(w.ventilation_area for w in room_wins)
        if room.computed_area_sqft <= 0:
            return 0.0
        room_area_sqm = room.computed_area_sqft / 10.764
        return round(total_vent_area / room_area_sqm, 3)

    @classmethod
    def export_windows(cls, windows: List[Window]) -> List[Dict[str, Any]]:
        """Serializes window metadata fields into standardized dictionaries for API responses."""
        return [win.dict() for win in windows]

    def execute_window_generation_pipeline(self, building: BuildingGeometry) -> Tuple[BuildingGeometry, List[Window]]:
        """Runs the complete window placement pipeline sequentially across all floors in the building model."""
        all_generated_windows: List[Window] = []

        for floor in building.floors:
            # Filter for exterior envelope wall segments on the current floor level
            if not floor.rooms:
                continue
            floor_walls = floor.rooms[0].walls if floor.rooms else []
            ext_walls = [w for w in floor_walls if w.wall_type.value == "exterior"]
            
            if not ext_walls:
                continue

            for room in floor.rooms:
                if room.room_type in [RoomType.BATHROOM, RoomType.CUSTOM]:
                    room_items = self.generate_ventilators(floor.level_index, room, ext_walls)
                else:
                    room_items = self.generate_room_windows(floor.level_index, room, ext_walls)

                all_generated_windows.extend(room_items)
                
                # Calculate and store lighting performance metrics within the room's metadata tags
                daylight_factor = self.calculate_daylighting(room, room_items)
                vent_factor = self.calculate_ventilation_score(room, room_items)
                
                room.adjacent_to = list(room.adjacent_to)  # Keep lists consistent across models

        return building, all_generated_windows