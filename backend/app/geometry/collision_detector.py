from typing import List, Dict, Any, Tuple, Optional
from backend.app.geometry.models import Point2D, LineSegment, Room, FloorLevel, BuildingGeometry, RoomType
from backend.app.geometry.layout_templates import FootprintTemplate
from backend.app.geometry.adjacency_graph import ArchitecturalAdjacencyGraph

class CollisionDetector:
    """
    Deterministic geometry validation engine executing spatial intersection metrics,
    setback evaluations, and circulation validation across multi-floor floorplans.
    """

    @staticmethod
    def _orientation(p: Point2D, q: Point2D, r: Point2D) -> int:
        """Helper to find the orientation of an ordered triplet (p, q, r). 0=Collinear, 1=Clockwise, 2=Counterclockwise."""
        val = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)
        if abs(val) < 1e-9:
            return 0
        return 1 if val > 0 else 2

    @staticmethod
    def _on_segment(p: Point2D, q: Point2D, r: Point2D) -> bool:
        """Helper to check if point q lies on line segment pr."""
        return (min(p.x, r.x) <= q.x <= max(p.x, r.x) and 
                min(p.y, r.y) <= q.y <= max(p.y, r.y))

    @classmethod
    def detect_wall_collision(cls, segment1: LineSegment, segment2: LineSegment) -> bool:
        """
        Determines whether two line segments cross each other using explicit 
        2D orientation testing, ensuring physical walls never cross.
        """
        p1, q1 = segment1.start, segment1.end
        p2, q2 = segment2.start, segment2.end

        o1 = cls._orientation(p1, q1, p2)
        o2 = cls._orientation(p1, q1, q2)
        o3 = cls._orientation(p2, q2, p1)
        o4 = cls._orientation(p2, q2, q1)

        # General case intersection criteria
        if o1 != o2 and o3 != o4:
            return True

        # Special collinear scenarios
        if o1 == 0 and cls._on_segment(p1, p2, q1): return True
        if o2 == 0 and cls._on_segment(p1, q2, q1): return True
        if o3 == 0 and cls._on_segment(p2, p1, q2): return True
        if o4 == 0 and cls._on_segment(p2, q1, q2): return True

        return False

    @classmethod
    def is_point_inside_polygon(cls, point: Point2D, polygon: List[Point2D]) -> bool:
        """Validates if a point is within a polygon via ray-casting."""
        n = len(polygon)
        if n < 3:
            return False

        inside = False
        p1x, p1y = polygon[0].x, polygon[0].y
        for i in range(n + 1):
            p2x, p2y = polygon[i % n].x, polygon[i % n].y
            if point.y > min(p1y, p2y):
                if point.y <= max(p1y, p2y):
                    if point.x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (point.y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or point.x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    @classmethod
    def detect_polygon_overlap(cls, poly1: List[Point2D], poly2: List[Point2D]) -> bool:
        """
        Scans two multi-point polygons to verify if they intersect, using intersecting 
        segments and vertex injection metrics to ensure rooms don't overlap.
        """
        # Edge Intersection Check
        for i in range(len(poly1)):
            seg1 = LineSegment(start=poly1[i], end=poly1[(i + 1) % len(poly1)])
            for j in range(len(poly2)):
                seg2 = LineSegment(start=poly2[j], end=poly2[(j + 1) % len(poly2)])
                if cls.detect_wall_collision(seg1, seg2):
                    # Check if the intersection is just a shared outer edge alignment
                    # Real intersections cross line bounds instead of merely matching endpoint values
                    o1 = cls._orientation(seg1.start, seg1.end, seg2.start)
                    o2 = cls._orientation(seg1.start, seg1.end, seg2.end)
                    if o1 != 0 or o2 != 0:
                        return True

        # Check if Poly1 is entirely nested within Poly2
        if cls.is_point_inside_polygon(poly1[0], poly2):
            return True
        # Check if Poly2 is entirely nested within Poly1
        if cls.is_point_inside_polygon(poly2[0], poly1):
            return True

        return False

    @classmethod
    def detect_room_overlap(cls, room1: Room, room2: Room) -> Optional[Dict[str, Any]]:
        """Evaluates whether two room entities conflict spatially on the same floor level."""
        if cls.detect_polygon_overlap(room1.polygon, room2.polygon):
            return {
                "issue_type": "ROOM_OVERLAP",
                "severity": "CRITICAL",
                "affected_rooms": [room1.id, room2.id],
                "description": f"Spatial overlap identified between Room '{room1.name}' and Room '{room2.name}'.",
                "recommended_fix": f"Shift the layout coordinate tracking vectors of '{room2.name}' outward to clear bounds."
            }
        return None

    @classmethod
    def detect_outside_plot(cls, room: Room, template: FootprintTemplate) -> bool:
        """Checks if a room boundary expands beyond the built dimensions."""
        for pt in room.polygon:
            if pt.x < 0.0 or pt.x > template.built_width_mm:
                return True
            if pt.y < 0.0 or pt.y > template.built_length_mm:
                return True
        return False

    @classmethod
    def detect_invalid_polygon(cls, room: Room) -> bool:
        """Checks for geometric malformations like zero-area footprints or corrupted point structures."""
        if len(room.polygon) < 4:
            return True
        
        # Calculate polygon area via the shoelace algorithm
        n = len(room.polygon)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += room.polygon[i].x * room.polygon[j].y
            area -= room.polygon[j].x * room.polygon[i].y
        area = abs(area) / 2.0
        
        if area <= 100.0:  # Triggers if a room's area falls below 100 square millimeters
            return True

        # Check for self-intersecting polygon profiles
        for i in range(n):
            s1 = LineSegment(start=room.polygon[i], end=room.polygon[(i + 1) % n])
            for j in range(i + 2, n):
                if (j + 1) % n == i:
                    continue
                s2 = LineSegment(start=room.polygon[j], end=room.polygon[(j + 1) % n])
                if cls.detect_wall_collision(s1, s2):
                    return True

        return False

    @classmethod
    def validate_setbacks(cls, room: Room, template: FootprintTemplate) -> List[Dict[str, Any]]:
        """Verifies if core rooms encroach onto designated setback spaces."""
        issues = []
        # External open yards (Garden/Parking) are allowed to extend into setback zones
        if room.room_type in [RoomType.GARDEN, RoomType.PARKING]:
            return []

        for pt in room.polygon:
            # Check front setback boundaries
            if pt.y < template.front_setback_mm:
                issues.append({
                    "issue_type": "SETBACK_ENCROACHMENT",
                    "severity": "HIGH",
                    "affected_rooms": [room.id],
                    "description": f"Room '{room.name}' encroaches into the front setback zone ({template.front_setback_mm}mm).",
                    "recommended_fix": "Increase the offset of the room layout along the Y-axis."
                })
                break
        return issues

    @classmethod
    def detect_dead_space(cls, floor: FloorLevel) -> List[Dict[str, Any]]:
        """Identifies empty gaps or unallocated spaces between rooms within the building footprint."""
        issues = []
        # Checks for unallocated interior gaps by comparing the total room area against the bounding envelope
        min_x = min(p.x for r in floor.rooms for p in r.polygon) if floor.rooms else 0
        max_x = max(p.x for r in floor.rooms for p in r.polygon) if floor.rooms else 0
        min_y = min(p.y for r in floor.rooms for p in r.polygon) if floor.rooms else 0
        max_y = max(p.y for r in floor.rooms for p in r.polygon) if floor.rooms else 0

        bounding_area = (max_x - min_x) * (max_y - min_y)
        if bounding_area <= 0:
            return []

        total_room_area = 0.0
        for r in floor.rooms:
            # Approximate simple rectangular area
            rx = max(p.x for p in r.polygon) - min(p.x for p in r.polygon)
            ry = max(p.y for p in r.polygon) - min(p.y for p in r.polygon)
            total_room_area += rx * ry

        if (bounding_area - total_room_area) > 25000000.0:  # Triggers if unallocated space exceeds 25 square meters
            issues.append({
                "issue_type": "DEAD_SPACE_DETECTED",
                "severity": "LOW",
                "affected_rooms": [],
                "description": "Internal layout optimization threshold alert: Noticeable unallocated spaces found between wall layouts.",
                "recommended_fix": "Expand the dimensions of adjacent rooms or circulation corridors to utilize empty space."
            })
        return issues

    @classmethod
    def validate_accessibility(cls, floor: FloorLevel, graph: ArchitecturalAdjacencyGraph) -> List[Dict[str, Any]]:
        """Checks for inaccessible rooms or disconnected layout paths on the floor level."""
        issues = []
        floor_room_ids = {r.id for r in floor.rooms}

        for r in floor.rooms:
            # Verify if every room node has active edge vectors mapped inside the topology list
            neighbors = graph.adjacency_list.get(r.id, set())
            if not neighbors and r.room_type not in [RoomType.GARDEN, RoomType.PARKING]:
                issues.append({
                    "issue_type": "INACCESSIBLE_ROOM",
                    "severity": "CRITICAL",
                    "affected_rooms": [r.id],
                    "description": f"Room '{r.name}' is isolated and has no door access routes mapped to the floorplan.",
                    "recommended_fix": "Connect this room node to a central corridor or adjacent hall within the layout topology."
                })
        return issues

    @classmethod
    def validate_circulation(cls, floor: FloorLevel, graph: ArchitecturalAdjacencyGraph) -> List[Dict[str, Any]]:
        """Enforces functional circulation paths (e.g., ensuring kitchens connect to dining areas)."""
        issues = []
        for r in floor.rooms:
            neighbors = graph.adjacency_list.get(r.id, set())
            neighbor_types = {graph.nodes[nid].room_type for nid in neighbors if nid in graph.nodes}

            if r.room_type == RoomType.KITCHEN:
                if not any(t in neighbor_types for t in ["dining", "corridor", "living"]):
                    issues.append({
                        "issue_type": "CIRCULATION_FAULT",
                        "severity": "HIGH",
                        "affected_rooms": [r.id],
                        "description": f"Kitchen '{r.name}' is isolated from the main living and dining circulation zones.",
                        "recommended_fix": "Adjust the layout to share a wall boundary with the dining or living area."
                    })
            
            if r.room_type == RoomType.BALCONY:
                if not any(t in neighbor_types for t in ["bedroom", "living"]):
                    issues.append({
                        "issue_type": "CIRCULATION_FAULT",
                        "severity": "MEDIUM",
                        "affected_rooms": [r.id],
                        "description": f"Balcony '{r.name}' must be directly accessible from a bedroom or the living area.",
                        "recommended_fix": "Re-anchor the balcony coordinate footprint to attach directly to a bedroom wall layout."
                    })
        return issues

    @classmethod
    def validate_floor(cls, floor: FloorLevel, template: FootprintTemplate, graph: ArchitecturalAdjacencyGraph) -> List[Dict[str, Any]]:
        """Runs validation checks across all spatial elements on a specific floor level."""
        issues = []

        # 1. Check for spatial overlap conflicts between rooms
        for i in range(len(floor.rooms)):
            for j in range(i + 1, len(floor.rooms)):
                overlap_issue = cls.detect_room_overlap(floor.rooms[i], floor.rooms[j])
                if overlap_issue:
                    issues.append(overlap_issue)

        # 2. Check individual room geometry structures
        for room in floor.rooms:
            if cls.detect_invalid_polygon(room):
                issues.append({
                    "issue_type": "INVALID_POLYGON",
                    "severity": "CRITICAL",
                    "affected_rooms": [room.id],
                    "description": f"Room '{room.name}' has an invalid polygon profile or a zero-area configuration.",
                    "recommended_fix": "Recompute the polygon layout bounding path points using non-zero dimensions."
                })

            if cls.detect_outside_plot(room, template):
                issues.append({
                    "issue_type": "OUT_OF_PLOT_BOUNDS",
                    "severity": "CRITICAL",
                    "affected_rooms": [room.id],
                    "description": f"Room '{room.name}' expands past the outer building envelope lines.",
                    "recommended_fix": "Scale down the room's dimensions or shift its position inward to sit inside plot lines."
                })

            # Check setback compliance metrics
            issues.extend(cls.validate_setbacks(room, template))

        # 3. Check structural circulation path mappings
        issues.extend(cls.detect_dead_space(floor))
        issues.extend(cls.validate_accessibility(floor, graph))
        issues.extend(cls.validate_circulation(floor, graph))

        return issues

    @classmethod
    def validate_complete_layout(cls, building: BuildingGeometry, template: FootprintTemplate, graph: ArchitecturalAdjacencyGraph) -> Dict[str, Any]]:
        """
        Runs comprehensive validation checks across all building levels, 
        verifying multi-floor rules like staircase placement.
        """
        all_issues = []

        for floor in building.floors:
            all_issues.extend(cls.validate_floor(floor, template, graph))

        # Multi-floor specific validation rule checking (e.g., verifying stacked staircase alignment)
        if len(building.floors) > 1:
            staircase_positions = {}
            for floor in building.floors:
                for r in floor.rooms:
                    if r.room_type == RoomType.STAIRS:
                        staircase_positions[floor.level_index] = r.centroid

            # Verify vertical alignment coordinates match up across floors
            if len(staircase_positions) >= 2:
                levels = sorted(list(staircase_positions.keys()))
                for idx in range(len(levels) - 1):
                    p1 = staircase_positions[levels[idx]]
                    p2 = staircase_positions[levels[idx + 1]]
                    if p1.distance_to(p2) > 1500.0:  # Triggers if the drift variance exceeds 1.5 meters
                        all_issues.append({
                            "issue_type": "VERTICAL_STAIRCASE_MISALIGNMENT",
                            "severity": "HIGH",
                            "affected_rooms": [],
                            "description": f"Staircase alignment drift error identified between Floor level {levels[idx]} and level {levels[idx+1]}.",
                            "recommended_fix": "Align the staircase center points to a shared vertical axis coordinates coordinate system."
                        })

        return cls.generate_collision_report(all_issues)

    @staticmethod
    def generate_collision_report(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compiles identified layout issues into a structured validation report schema."""
        critical_count = sum(1 for i in issues if i["severity"] == "CRITICAL")
        high_count = sum(1 for i in issues if i["severity"] == "HIGH")
        
        is_buildable = (critical_count == 0 and high_count == 0)

        return {
            "status": "PASSED" if is_buildable else "FAILED",
            "summary": {
                "total_issues": len(issues),
                "critical_severity_errors": critical_count,
                "high_severity_warnings": high_count,
                "is_structurally_buildable": is_buildable
            },
            "issues": issues
        }