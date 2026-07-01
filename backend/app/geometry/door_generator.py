import math
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
from backend.app.geometry.models import Point2D, LineSegment, Wall, Room, FloorLevel, BuildingGeometry, RoomType

class Door(BaseModel):
    """Data model representing the exact computed geometry and structural metadata of an architectural door."""
    id: str
    floor: int
    room_from: str
    room_to: str
    wall_id: str
    center_point: Point2D
    start_point: Point2D
    end_point: Point2D
    width: float
    height: float
    thickness: float
    opening_direction: str  # "INWARD" or "OUTWARD"
    hinge_side: str         # "LEFT" or "RIGHT"
    door_type: str          # "MAIN_ENTRANCE", "BEDROOM", "BATHROOM", "KITCHEN", "BALCONY", "SLIDING", "DOUBLE", "SINGLE"
    swing_angle: float      # Degrees (e.g., 90.0 or 180.0)
    clearance_area: List[Point2D] = Field(default_factory=list)  # 4-point bounding polygon of the swing path

class DoorGenerator:
    """
    Deterministic architectural door planning engine. Calculates coordinates, 
    allocates clearance buffers, and embeds opening points into the wall graph.
    """
    
    CORNER_OFFSET_MM: float = 200.0  # Safe distance from corners to allow for framing and trim
    STANDARD_DOOR_HEIGHT_MM: float = 2100.0
    STANDARD_DOOR_THICKNESS_MM: float = 40.0

    @classmethod
    def calculate_door_position(cls, wall: Wall, door_width: float, prefer_center: bool = False) -> Optional[Tuple[Point2D, Point2D, Point2D]]:
        """
        Computes the start, end, and center coordinate points of a door opening 
        along a wall path, ensuring it stays within wall boundaries.
        """
        wall_length = wall.segment.length
        if wall_length < (door_width + cls.CORNER_OFFSET_MM * 2):
            # If the wall is too short, scale down the door width to fit the space
            door_width = max(700.0, wall_length - 100.0)
            if wall_length < door_width:
                return None

        dx = wall.segment.end.x - wall.segment.start.x
        dy = wall.segment.end.y - wall.segment.start.y
        
        # Calculate unit direction vector components
        ux = dx / wall_length
        uy = dy / wall_length

        if prefer_center:
            # Center the door position (ideal for Main Entrances or French/Double doors)
            start_dist = (wall_length - door_width) / 2.0
        else:
            # Shift the door near the corner start index while keeping standard framing clearance
            start_dist = cls.CORNER_OFFSET_MM

        start_pt = Point2D(
            x=wall.segment.start.x + ux * start_dist,
            y=wall.segment.start.y + uy * start_dist
        )
        end_pt = Point2D(
            x=start_pt.x + ux * door_width,
            y=start_pt.y + uy * door_width
        )
        center_pt = Point2D(
            x=start_pt.x + (ux * door_width / 2.0),
            y=start_pt.y + (uy * door_width / 2.0)
        )

        return start_pt, end_pt, center_pt

    @classmethod
    def calculate_clearance_area(cls, start_pt: Point2D, end_pt: Point2D, width: float, opening_dir: str) -> List[Point2D]:
        """Calculates a 4-point bounding polygon representing the physical space needed for the door swing path."""
        dx = end_pt.x - start_pt.x
        dy = end_pt.y - start_pt.y
        length = math.hypot(dx, dy)
        if length == 0:
            return []
            
        # Compute perpendicular normal vectors
        nx = -dy / length
        ny = dx / length
        
        # Flip direction based on inward/outward layout settings
        multiplier = 1.0 if opening_dir == "INWARD" else -1.0
        
        pt3 = Point2D(x=end_pt.x + nx * width * multiplier, y=end_pt.y + ny * width * multiplier)
        pt4 = Point2D(x=start_pt.x + nx * width * multiplier, y=start_pt.y + ny * width * multiplier)
        
        return [start_pt, end_pt, pt3, pt4]

    @classmethod
    def generate_main_doors(cls, floor_idx: int, walls: List[Wall], rooms: List[Room]) -> List[Door]:
        """Places the main entrance door on an exterior wall connected to the Living Room."""
        doors = []
        living_room = next((r for r in rooms if r.room_type == RoomType.LIVING), None)
        if not living_room:
            return doors

        # Find exterior walls connected to the living room
        for wall in walls:
            if wall.wall_type.value == "exterior" and living_room.id in wall.connected_rooms:
                pos = cls.calculate_door_position(wall, door_width=1000.0, prefer_center=True)
                if pos:
                    st, en, ce = pos
                    clearance = cls.calculate_clearance_area(st, en, 1000.0, "INWARD")
                    d = Door(
                        id=f"door_floor_{floor_idx}_main",
                        floor=floor_idx,
                        room_from="OUTSIDE",
                        room_to=living_room.id,
                        wall_id=wall.id,
                        center_point=ce,
                        start_point=st,
                        end_point=en,
                        width=1000.0,
                        height=cls.STANDARD_DOOR_HEIGHT_MM,
                        thickness=cls.STANDARD_DOOR_THICKNESS_MM,
                        opening_direction="INWARD",
                        hinge_side="LEFT",
                        door_type="MAIN_ENTRANCE",
                        swing_angle=90.0,
                        clearance_area=clearance
                    )
                    doors.append(d)
                    wall.doors.append(d.id)  # Link door reference back to the parent wall object
                    break
        return doors

    @classmethod
    def generate_internal_doors(cls, floor_idx: int, walls: List[Wall], rooms: List[Room]) -> List[Door]:
        """Generates functional interior doors connecting internal rooms based on shared walls."""
        doors = []
        counter = 1
        
        # Track which rooms are already connected to prevent creating duplicate paths
        connected_pairs = set()

        for wall in walls:
            if wall.wall_type.value in ["shared", "partition"] and len(wall.connected_rooms) == 2:
                r1_id, r2_id = wall.connected_rooms[0], wall.connected_rooms[1]
                pair_key = tuple(sorted([r1_id, r2_id]))
                if pair_key in connected_pairs:
                    continue

                r1 = next((r for r in rooms if r.id == r1_id), None)
                r2 = next((r for r in rooms if r.id == r2_id), None)
                if not r1 or not r2:
                    continue

                # Set appropriate door widths based on standard room functions
                if r1.room_type == RoomType.BATHROOM or r2.room_type == RoomType.BATHROOM:
                    d_width = 750.0
                    d_type = "BATHROOM"
                elif r1.room_type == RoomType.KITCHEN or r2.room_type == RoomType.KITCHEN:
                    d_width = 900.0
                    d_type = "KITCHEN"
                else:
                    d_width = 900.0
                    d_type = "BEDROOM"

                pos = cls.calculate_door_position(wall, door_width=d_width, prefer_center=False)
                if pos:
                    st, en, ce = pos
                    clearance = cls.calculate_clearance_area(st, en, d_width, "INWARD")
                    d = Door(
                        id=f"door_floor_{floor_idx}_int_{counter}",
                        floor=floor_idx,
                        room_from=r1_id,
                        room_to=r2_id,
                        wall_id=wall.id,
                        center_point=ce,
                        start_point=st,
                        end_point=en,
                        width=d_width,
                        height=cls.STANDARD_DOOR_HEIGHT_MM,
                        thickness=cls.STANDARD_DOOR_THICKNESS_MM,
                        opening_direction="INWARD",
                        hinge_side="RIGHT",
                        door_type=d_type,
                        swing_angle=90.0,
                        clearance_area=clearance
                    )
                    doors.append(d)
                    wall.doors.append(d.id)
                    connected_pairs.add(pair_key)
                    counter += 1
        return doors

    @classmethod
    def generate_balcony_doors(cls, floor_idx: int, walls: List[Wall], rooms: List[Room]) -> List[Door]:
        """Places weather-sealed or sliding doors on walls connecting bedrooms to attached balconies."""
        doors = []
        counter = 1
        
        for wall in walls:
            if len(wall.connected_rooms) == 2:
                r1 = next((r for r in rooms if r.id == wall.connected_rooms[0]), None)
                r2 = next((r for r in rooms if r.id == wall.connected_rooms[1]), None)
                if not r1 or not r2:
                    continue

                if (r1.room_type == RoomType.BALCONY and r2.room_type == RoomType.BEDROOM) or \
                   (r2.room_type == RoomType.BALCONY and r1.room_type == RoomType.BEDROOM):
                    
                    pos = cls.calculate_door_position(wall, door_width=1200.0, prefer_center=True)
                    if pos:
                        st, en, ce = pos
                        clearance = cls.calculate_clearance_area(st, en, 1200.0, "OUTWARD")
                        d = Door(
                            id=f"door_floor_{floor_idx}_balc_{counter}",
                            floor=floor_idx,
                            room_from=r2.id if r1.room_type == RoomType.BALCONY else r1.id,
                            room_to=r1.id if r1.room_type == RoomType.BALCONY else r2.id,
                            wall_id=wall.id,
                            center_point=ce,
                            start_point=st,
                            end_point=en,
                            width=1200.0,
                            height=cls.STANDARD_DOOR_HEIGHT_MM,
                            thickness=cls.STANDARD_DOOR_THICKNESS_MM,
                            opening_direction="OUTWARD",
                            hinge_side="LEFT",
                            door_type="SLIDING",
                            swing_angle=180.0,
                            clearance_area=clearance
                        )
                        doors.append(d)
                        wall.doors.append(d.id)
                        counter += 1
        return doors

    @classmethod
    def calculate_swing_arc(cls, door: Door, steps: int = 5) -> List[Point2D]:
        """
        Generates a sequence of 2D points outlining the door's path of travel,
        allowing the UI renderer to draw clean architectural swing arcs.
        """
        arc_points = []
        # Calculate initial radial sweep parameters
        dx = door.end_point.x - door.start_point.x
        dy = door.end_point.y - door.start_point.y
        base_angle = math.atan2(dy, dx)

        sweep_rad = math.radians(door.swing_angle)
        direction_modifier = 1.0 if door.opening_direction == "INWARD" else -1.0

        for i in range(steps + 1):
            fraction = float(i) / float(steps)
            current_angle = base_angle + (sweep_rad * fraction * direction_modifier)
            pt = Point2D(
                x=door.start_point.x + math.cos(current_angle) * door.width,
                y=door.start_point.y + math.sin(current_angle) * door.width
            )
            arc_points.append(pt)
        return arc_points

    @classmethod
    def validate_doors(cls, doors: List[Door], walls: List[Wall]) -> bool:
        """Runs validation checks to guarantee doors don't overlap or exceed wall boundaries."""
        wall_map = {w.id: w for w in walls}
        for d in doors:
            if d.wall_id not in wall_map:
                return False
            parent_wall = wall_map[d.wall_id]
            # Ensure the opening length fits within the physical wall structure
            if d.width > parent_wall.segment.length:
                return False
        return True

    @classmethod
    def export_doors(cls, doors: List[Door]) -> List[Dict[str, Any]]:
        """Serializes current door objects into structured dictionaries for API delivery."""
        return [door.dict() for door in doors]

    def execute_door_generation_pipeline(self, building: BuildingGeometry) -> Tuple[BuildingGeometry, List[Door]]:
        """Runs the complete door placement pipeline sequentially across all floors in the building model."""
        all_generated_doors: List[Door] = []

        for floor in building.floors:
            # Extract current floor wall layouts
            floor_walls = floor.rooms[0].walls if floor.rooms else []
            if not floor_walls:
                continue

            # Run deterministic placement sequence
            main_doors = self.generate_main_doors(floor.level_index, floor_walls, floor.rooms)
            internal_doors = self.generate_internal_doors(floor.level_index, floor_walls, floor.rooms)
            balcony_doors = self.generate_balcony_doors(floor.level_index, floor_walls, floor.rooms)

            floor_doors = main_doors + internal_doors + balcony_doors
            
            # Verify door geometry before completing the pass
            if self.validate_doors(floor_doors, floor_walls):
                all_generated_doors.extend(floor_doors)

        return building, all_generated_doors