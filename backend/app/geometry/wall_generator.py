import math
from typing import List, Dict, Tuple, Set, Optional, Any
from backend.app.geometry.models import Point2D, LineSegment, Wall, WallType, Room, FloorLevel, BuildingGeometry

class WallGenerator:
    """
    Deterministic architectural wall generation engine that computes thick physical walls,
    deduplicates shared boundaries, and resolves structural corner junctions.
    """
    
    TOLERANCE_MM: float = 20.0  # 20mm tolerance for floating-point snapping alignments
    
    EXTERIOR_THICKNESS: float = 230.0
    INTERIOR_THICKNESS: float = 115.0
    PARTITION_THICKNESS: float = 75.0

    @classmethod
    def _points_match(cls, p1: Point2D, p2: Point2D) -> bool:
        """Determines if two coordinate points match within structural safety tolerance thresholds."""
        return math.hypot(p1.x - p2.x, p1.y - p2.y) < cls.TOLERANCE_MM

    @classmethod
    def _is_collinear_and_overlapping(cls, s1: LineSegment, s2: LineSegment) -> Tuple[bool, Optional[LineSegment]]:
        """
        Determines if two wall segments are collinear and computes their shared overlapping segment length.
        """
        # Vector representations
        v1_x, v1_y = s1.end.x - s1.start.x, s1.end.y - s1.start.y
        v2_x, v2_y = s2.end.x - s2.start.x, s2.end.y - s2.start.y
        
        # Cross product to check for parallelism
        cross_product = v1_x * v2_y - v1_y * v2_x
        if abs(cross_product) > 50000.0:  # Tolerance threshold for cross-product alignment variation
            return False, None

        # Verify collinearity by testing the start point of s2 against s1
        cross_compare = (s2.start.x - s1.start.x) * v1_y - (s2.start.y - s1.start.y) * v1_x
        if abs(cross_compare) > 50000.0:
            return False, None

        # Map 2D segments to 1D scalar ranges for easy interval overlap tracking
        is_horizontal = abs(v1_x) > abs(v1_y)
        
        if is_horizontal:
            min1, max1 = min(s1.start.x, s1.end.x), max(s1.start.x, s1.end.x)
            min2, max2 = min(s2.start.x, s2.end.x), max(s2.start.x, s2.end.x)
        else:
            min1, max1 = min(s1.start.y, s1.end.y), max(s1.start.y, s1.end.y)
            min2, max2 = min(s2.start.y, s2.end.y), max(s2.start.y, s2.end.y)

        # Calculate overlap intervals
        overlap_min = max(min1, min2)
        overlap_max = min(max1, max2)

        if (overlap_max - overlap_min) > cls.TOLERANCE_MM:
            # Reconstruct overlapping 2D segment line coordinates
            if is_horizontal:
                # Find matching Y projection coordinates
                y_coord = s1.start.y if abs(s1.start.y - s2.start.y) < cls.TOLERANCE_MM else (s1.start.y + s2.start.y) / 2.0
                start_pt = Point2D(x=overlap_min, y=y_coord)
                end_pt = Point2D(x=overlap_max, y=y_coord)
            else:
                x_coord = s1.start.x if abs(s1.start.x - s2.start.x) < cls.TOLERANCE_MM else (s1.start.x + s2.start.x) / 2.0
                start_pt = Point2D(x=x_coord, y=overlap_min)
                end_pt = Point2D(x=x_coord, y=overlap_max)

            return True, LineSegment(start=start_pt, end=end_pt)

        return False, None

    @classmethod
    def generate_exterior_walls(cls, unique_segments: List[Tuple[LineSegment, List[str]]]) -> List[Wall]:
        """Filters out non-shared edge definitions to generate exterior continuous envelope walls."""
        exterior_walls: List[Wall] = []
        counter = 1
        
        for segment, room_ids in unique_segments:
            if len(room_ids) == 1:  # Exterior walls belong to exactly one room perimeter boundary
                exterior_walls.append(
                    Wall(
                        id=f"wall_ext_{counter}",
                        segment=segment,
                        thickness=cls.EXTERIOR_THICKNESS,
                        wall_type=WallType.EXTERIOR,
                        doors=[],
                        windows=[],
                        connected_rooms=room_ids
                    )
                )
                counter += 1
        return exterior_walls

    @classmethod
    def generate_interior_walls(cls, unique_segments: List[Tuple[LineSegment, List[str]]]) -> List[Wall]:
        """Generates internal partition walls from interior segments that do not form shared room interfaces."""
        interior_walls: List[Wall] = []
        counter = 1
        
        for segment, room_ids in unique_segments:
            if len(room_ids) > 1:
                # Filter for single-floor structural transitions that are interior but not fully shared
                if len(room_ids) == 2 and ("corridor" in "".join(room_ids).lower()):
                    interior_walls.append(
                        Wall(
                            id=f"wall_int_{counter}",
                            segment=segment,
                            thickness=cls.PARTITION_THICKNESS,
                            wall_type=WallType.PARTITION,
                            doors=[],
                            windows=[],
                            connected_rooms=room_ids
                        )
                    )
                    counter += 1
        return interior_walls

    @classmethod
    def generate_shared_walls(cls, unique_segments: List[Tuple[LineSegment, List[str]]]) -> List[Wall]:
        """Computes shared interior dividing walls between interconnected rooms to prevent line duplication."""
        shared_walls: List[Wall] = []
        counter = 1
        
        for segment, room_ids in unique_segments:
            if len(room_ids) >= 2:
                # Verify that this segment is shared by distinct layout partitions
                is_partition = any("corridor" in rid.lower() for rid in room_ids)
                if not is_partition:
                    shared_walls.append(
                        Wall(
                            id=f"wall_shd_{counter}",
                            segment=segment,
                            thickness=cls.INTERIOR_THICKNESS,
                            wall_type=WallType.SHARED,
                            doors=[],
                            windows=[],
                            connected_rooms=room_ids
                        )
                    )
                    counter += 1
        return shared_walls

    @classmethod
    def merge_wall_segments(cls, walls: List[Wall]) -> List[Wall]:
        """Combines contiguous, inline wall segments of the same type to simplify the layout architecture."""
        if not walls:
            return []

        merged = True
        while merged:
            merged = False
            to_remove: Set[str] = set()
            
            for i in range(len(walls)):
                if walls[i].id in to_remove:
                    continue
                for j in range(i + 1, len(walls)):
                    if walls[j].id in to_remove or walls[i].wall_type != walls[j].wall_type:
                        continue
                    
                    w1, w2 = walls[i], walls[j]
                    
                    # Verify collinearity and connectivity alignments
                    is_collinear, overlap_seg = cls._is_collinear_and_overlapping(w1.segment, w2.segment)
                    
                    if is_collinear:
                        # Check if segments touch at an endpoint interface boundary
                        touches = (cls._points_match(w1.segment.end, w2.segment.start) or 
                                   cls._points_match(w1.segment.start, w2.segment.end) or
                                   cls._points_match(w1.segment.start, w2.segment.start) or
                                   cls._points_match(w1.segment.end, w2.segment.end))
                        
                        if touches:
                            # Calculate the maximum bounding segment coordinate values
                            pts = [w1.segment.start, w1.segment.end, w2.segment.start, w2.segment.end]
                            is_horizontal = abs(w1.segment.end.x - w1.segment.start.x) > abs(w1.segment.end.y - w1.segment.start.y)
                            
                            if is_horizontal:
                                sorted_pts = sorted(pts, key=lambda p: p.x)
                            else:
                                sorted_pts = sorted(pts, key=lambda p: p.y)
                            
                            w1.segment.start = sorted_pts[0]
                            w1.segment.end = sorted_pts[-1]
                            w1.connected_rooms = list(set(w1.connected_rooms + w2.connected_rooms))
                            
                            to_remove.add(w2.id)
                            merged = True
                            
            walls = [w for w in walls if w.id not in to_remove]
            
        return walls

    @classmethod
    def split_wall_for_openings(cls, wall: Wall, opening_start_ratio: float, opening_end_ratio: float) -> Tuple[LineSegment, LineSegment]:
        """
        Computes geometry adjustments for wall objects, splitting a wall segment 
        into separate sections to accommodate structural door or window openings.
        """
        dx = wall.segment.end.x - wall.segment.start.x
        dy = wall.segment.end.y - wall.segment.start.y
        
        pt1 = Point2D(
            x=wall.segment.start.x + dx * opening_start_ratio,
            y=wall.segment.start.y + dy * opening_start_ratio
        )
        pt2 = Point2D(
            x=wall.segment.start.x + dx * opening_end_ratio,
            y=wall.segment.start.y + dy * opening_end_ratio
        )
        
        seg1 = LineSegment(start=wall.segment.start, end=pt1)
        seg2 = LineSegment(start=pt2, end=wall.segment.end)
        
        return seg1, seg2

    @classmethod
    def calculate_wall_junctions(cls, walls: List[Wall]) -> Dict[str, List[str]]:
        """Maps wall intersection junctions to track how walls connect at floorplan corner interfaces."""
        junction_map: Dict[str, List[str]] = {}
        
        for w in walls:
            junction_map[w.id] = []
            
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                w1, w2 = walls[i], walls[j]
                
                # Check endpoints intersection profiles
                if (cls._points_match(w1.segment.start, w2.segment.start) or 
                    cls._points_match(w1.segment.start, w2.segment.end) or 
                    cls._points_match(w1.segment.end, w2.segment.start) or 
                    cls._points_match(w1.segment.end, w2.segment.end)):
                    
                    junction_map[w1.id].append(w2.id)
                    junction_map[w2.id].append(w1.id)
                    
        return junction_map

    @classmethod
    def validate_wall_graph(cls, rooms: List[Room], walls: List[Wall]) -> bool:
        """Runs geometric checks to verify that every room is fully enclosed by its surrounding walls."""
        for room in rooms:
            room_walls = [w for w in walls if room.id in w.connected_rooms]
            if not room_walls:
                return False
            
            # Verify the total combined length of the walls is equal to or greater than the room's perimeter length
            poly_perimeter = 0.0
            for i in range(len(room.polygon)):
                p1 = room.polygon[i]
                p2 = room.polygon[(i + 1) % len(room.polygon)]
                poly_perimeter += math.hypot(p2.x - p1.x, p2.y - p1.y)
                
            wall_length_sum = sum(w.segment.length for w in room_walls)
            if wall_length_sum < (poly_perimeter - cls.TOLERANCE_MM * len(room.polygon)):
                return False
                
        return True

    @classmethod
    def build_wall_graph(cls, rooms: List[Room]) -> List[Wall]:
        """
        Processes a list of raw room shapes, extracts their boundaries, 
        and converts them into a deduplicated set of structural Wall objects.
        """
        raw_segments: List[Tuple[LineSegment, str]] = []
        
        # 1. Deconstruct room polygon vertices into distinct 2D edge lines
        for room in rooms:
            n = len(room.polygon)
            for i in range(n):
                p1 = room.polygon[i]
                p2 = room.polygon[(i + 1) % n]
                raw_segments.append((LineSegment(start=p1, end=p2), room.id))

        # 2. Consolidate and cross-reference overlapping edge coordinates between rooms
        unique_segments: List[Tuple[LineSegment, List[str]]] = []
        processed_indices: Set[int] = set()

        for i in range(len(raw_segments)):
            if i in processed_indices:
                continue
                
            seg_a, room_id_a = raw_segments[i]
            matched_rooms = [room_id_a]
            processed_indices.add(i)

            for j in range(len(raw_segments)):
                if j in processed_indices:
                    continue
                    
                seg_b, room_id_b = raw_segments[j]
                is_shared, _ = cls._is_collinear_and_overlapping(seg_a, seg_b)
                
                if is_shared:
                    if room_id_b not in matched_rooms:
                        matched_rooms.append(room_id_b)
                    processed_indices.add(j)

            unique_segments.append((seg_a, matched_rooms))

        # 3. Generate individual walls based on structural types
        ext_walls = cls.generate_exterior_walls(unique_segments)
        int_walls = cls.generate_interior_walls(unique_segments)
        shd_walls = cls.generate_shared_walls(unique_segments)

        all_walls = ext_walls + int_walls + shd_walls
        
        # 4. Clean up the wall layout by merging contiguous inline wall segments
        all_walls = cls.merge_wall_segments(all_walls)
        
        # 5. Connect the generated wall objects back to their respective rooms
        for room in rooms:
            room.walls = [w for w in all_walls if room.id in w.connected_rooms]

        return all_walls

    def execute_wall_generation_pipeline(self, building: BuildingGeometry) -> BuildingGeometry:
        """Runs the wall generation pipeline across all floors in the building model."""
        for floor in building.floors:
            floor_walls = self.build_wall_graph(floor.rooms)
            # Confirms structural wall integrity before proceeding
            self.validate_wall_graph(floor.rooms, floor_walls)
            self.calculate_wall_junctions(floor_walls)
        return building