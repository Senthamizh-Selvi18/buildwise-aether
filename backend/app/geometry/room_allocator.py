import math
from typing import List, Dict, Tuple, Any, Optional
from backend.app.geometry.models import Point2D, Room, RoomType, Wall, LineSegment, WallType, FloorLevel, BuildingGeometry
from backend.app.geometry.layout_templates import FootprintTemplate, SpatialSector, SectorBoundary
from backend.app.geometry.adjacency_graph import ArchitecturalAdjacencyGraph

class RoomAllocator:
    """
    Deterministic spatial geometry allocator that translates graph relationships 
    into exact coordinate polygons across multiple floor levels.
    """
    SQMM_TO_SQFT: float = 1.0 / 92903.04
    SQFT_TO_SQMM: float = 92903.04

    def __init__(self, template: FootprintTemplate, graph: ArchitecturalAdjacencyGraph, vastu_enabled: bool = True):
        self.template: FootprintTemplate = template
        self.graph: ArchitecturalAdjacencyGraph = graph
        self.vastu_enabled: bool = vastu_enabled

    def calculate_room_sizes(self, room_nodes: List[Any], total_available_area_mm2: float) -> Dict[str, Tuple[float, float]]:
        """
        Calculates proportional millimeter target dimensions for a set of rooms based on 
        architectural constraints, preventing negative sizes or disproportionate aspect ratios.
        """
        sizes: Dict[str, Tuple[float, float]] = {}
        if not room_nodes:
            return sizes

        total_target_sqft = sum(float(node.metadata.get("target_area_sqft", 150.0)) for node in room_nodes)
        if total_target_sqft <= 0:
            total_target_sqft = len(room_nodes) * 150.0

        for node in room_nodes:
            target_sqft = float(node.metadata.get("target_area_sqft", 150.0))
            # Proportional area split of the available envelope floor plate
            allocated_area_mm2 = (target_sqft / total_target_sqft) * total_available_area_mm2
            
            # Enforce architectural minimum bounds (9000000 mm2 = 9 m2 ~ 100 sqft)
            allocated_area_mm2 = max(allocated_area_mm2, 9000000.0)
            
            # Maintain standard golden aspect ratios for room geometry (approx 1.2 to 1.4)
            width = math.sqrt(allocated_area_mm2 / 1.3)
            length = width * 1.3
            sizes[node.room_id] = (round(width, 2), round(length, 2))
            
        return sizes

    def _determine_target_sector(self, room_type_str: str) -> SpatialSector:
        """Determines the specific layout sector for a room type using deterministic Vastu mapping mappings."""
        try:
            r_type = RoomType(room_type_str.lower())
        except ValueError:
            return SpatialSector.CENTER

        if self.vastu_enabled:
            if r_type == RoomType.KITCHEN:
                return SpatialSector.SOUTH_EAST
            elif r_type in [RoomType.BEDROOM, RoomType.CUSTOM] and "master" in room_type_str:
                return SpatialSector.SOUTH_WEST
            elif r_type == RoomType.LIVING:
                return SpatialSector.CENTER
            elif r_type == RoomType.DINING:
                return SpatialSector.EAST
            elif r_type == RoomType.BATHROOM:
                return SpatialSector.WEST
            elif r_type == RoomType.STAIRS:
                return SpatialSector.NORTH_WEST
            elif r_type == RoomType.GARDEN:
                return SpatialSector.NORTH_EAST
            elif r_type == RoomType.PARKING:
                return SpatialSector.SOUTH

        return self.template.default_room_assignments.get(r_type, SpatialSector.CENTER)

    def generate_room_polygons(self, floor_index: int, room_nodes: List[Any], sizes: Dict[str, Tuple[float, float]]) -> List[Room]:
        """
        Generates initial 4-point bounding vertex loops for rooms by placing them deterministically 
        within designated operational layout coordinates.
        """
        allocated_rooms: List[Room] = []
        sectors: List[SectorBoundary] = self.template.sectors_by_floor.get(floor_index, [])
        
        # Index sectors by type for rapid geometric retrieval
        sector_map: Dict[SpatialSector, SectorBoundary] = {s.sector_type: s for s in sectors}
        
        # Tracks how many rooms have been placed inside each sector to stagger placement layout
        sector_counters: Dict[SpatialSector, int] = {s.sector_type: 0 for s in sectors}

        for node in room_nodes:
            target_sector = self._determine_target_sector(node.room_type)
            boundary = sector_map.get(target_sector, sector_map.get(SpatialSector.CENTER))
            
            if not boundary:
                continue

            r_width, r_length = sizes.get(node.room_id, (3000.0, 4000.0))
            
            # Constrain dimensions to prevent them from breaking the outer walls
            r_width = min(r_width, boundary.width * 0.95)
            r_length = min(r_length, boundary.height * 0.95)

            # Calculate offsets within the sector boundary based on previous allocations
            count = sector_counters[boundary.sector_type]
            offset_x = count * 200.0
            offset_y = count * 200.0
            
            start_x = boundary.bottom_left.x + offset_x
            start_y = boundary.bottom_left.y + offset_y
            
            # Clamp placement coordinates safely inside the target zone boundaries
            if start_x + r_width > boundary.top_right.x:
                start_x = boundary.top_right.x - r_width
            if start_y + r_length > boundary.top_right.y:
                start_y = boundary.top_right.y - r_length

            start_x = max(start_x, boundary.bottom_left.x)
            start_y = max(start_y, boundary.bottom_left.y)

            # Formulate counter-clockwise closed polygon loop coordinates
            polygon = [
                Point2D(x=start_x, y=start_y),
                Point2D(x=start_x + r_width, y=start_y),
                Point2D(x=start_x + r_width, y=start_y + r_length),
                Point2D(x=start_x, y=start_y + r_length)
            ]

            computed_area = (r_width * r_length) * self.SQMM_TO_SQFT
            
            # Pick a deterministic architectural fill color based on room functions
            color_palette = {
                "living": "#F5F5DC", "dining": "#E6F2F2", "kitchen": "#FFE4E1",
                "bedroom": "#E6F0FA", "bathroom": "#F0F8FF", "stairs": "#ECECEC",
                "corridor": "#FAFAFA", "parking": "#EAEAEA", "garden": "#E8F5E9"
            }
            assigned_color = color_palette.get(node.room_type, "#FFFFFF")

            # Extract structural adjacencies directly from graph topology edges
            adjacencies = list(self.graph.adjacency_list.get(node.room_id, set()))

            allocated_rooms.append(
                Room(
                    id=node.room_id,
                    name=node.name,
                    room_type=RoomType(node.room_type) if node.room_type in RoomType.__members__.values() else RoomType.CUSTOM,
                    polygon=polygon,
                    target_area_sqft=float(node.metadata.get("target_area_sqft", 150.0)),
                    computed_area_sqft=round(computed_area, 2),
                    color_hex=assigned_color,
                    adjacent_to=adjacencies,
                    walls=[]
                )
            )
            sector_counters[boundary.sector_type] += 1

        return allocated_rooms

    def resolve_collisions(self, rooms: List[Room]) -> List[Room]:
        """
        Processes bounding vectors iteratively to shift overlapping coordinates away 
        from one another, maintaining a clear internal grid system.
        """
        if not rooms:
            return rooms

        # Simple iterative spatial separation pass
        for _ in range(3):
            for i in range(len(rooms)):
                for j in range(len(rooms)):
                    if i == j:
                        continue
                    
                    r1 = rooms[i]
                    r2 = rooms[j]

                    # Extract coordinates bounding properties from bounding polygon layouts
                    min_x1 = min(p.x for p in r1.polygon)
                    max_x1 = max(p.x for p in r1.polygon)
                    min_y1 = min(p.y for p in r1.polygon)
                    max_y1 = max(p.y for p in r1.polygon)

                    min_x2 = min(p.x for p in r2.polygon)
                    max_x2 = max(p.x for p in r2.polygon)
                    min_y2 = min(p.y for p in r2.polygon)
                    max_y2 = max(p.y for p in r2.polygon)

                    # Evaluate bounding boxes intersect conditions
                    overlap_x = min(max_x1, max_x2) - max(min_x1, min_x2)
                    overlap_y = min(max_y1, max_y2) - max(min_y1, min_y2)

                    if overlap_x > 0 and overlap_y > 0:
                        # Shift along the smaller overlap dimension to minimize layout distortion
                        if overlap_x < overlap_y:
                            shift = overlap_x / 2.0 + 10.0
                            if min_x1 < min_x2:
                                for p in r1.polygon: p.x -= shift
                                for p in r2.polygon: p.x += shift
                            else:
                                for p in r1.polygon: p.x += shift
                                for p in r2.polygon: p.x -= shift
                        else:
                            shift = overlap_y / 2.0 + 10.0
                            if min_y1 < min_y2:
                                for p in r1.polygon: p.y -= shift
                                for p in r2.polygon: p.y += shift
                            else:
                                for p in r1.polygon: p.y += shift
                                for p in r2.polygon: p.y -= shift
        return rooms

    def optimize_layout(self, rooms: List[Room]) -> List[Room]:
        """
        Snaps spatial boundaries together to establish unified shared interior walls 
        and eliminate empty spaces between adjacent zones.
        """
        for i in range(len(rooms)):
            for j in range(len(rooms)):
                if i == j:
                    continue
                r1 = rooms[i]
                r2 = rooms[j]

                min_x1, max_x1 = min(p.x for p in r1.polygon), max(p.x for p in r1.polygon)
                min_y1, max_y1 = min(p.y for p in r1.polygon), max(p.y for p in r1.polygon)
                min_x2, max_x2 = min(p.x for p in r2.polygon), max(p.x for p in r2.polygon)
                min_y2, max_y2 = min(p.y for p in r2.polygon), max(p.y for p in r2.polygon)

                # Snap close vertical wall structures within a 350mm tolerance range
                if abs(max_x1 - min_x2) < 350.0 and not (max_y1 <= min_y2 or min_y1 >= max_y2):
                    for p in r1.polygon:
                        if abs(p.x - max_x1) < 1.0: p.x = min_x2
                if abs(min_x1 - max_x2) < 350.0 and not (max_y1 <= min_y2 or min_y1 >= max_y2):
                    for p in r1.polygon:
                        if abs(p.x - min_x1) < 1.0: p.x = max_x2

                # Snap close horizontal wall structures within a 350mm tolerance range
                if abs(max_y1 - min_y2) < 350.0 and not (max_x1 <= min_x2 or min_x1 >= max_x2):
                    for p in r1.polygon:
                        if abs(p.y - max_y1) < 1.0: p.y = min_y2
                if abs(min_y1 - max_y2) < 350.0 and not (max_x1 <= min_x2 or min_x1 >= max_x2):
                    for p in r1.polygon:
                        if abs(p.y - min_y1) < 1.0: p.y = max_y2

        # Recalculate room areas following snapping operations to keep data accurate
        for room in rooms:
            min_x, max_x = min(p.x for p in room.polygon), max(p.x for p in room.polygon)
            min_y, max_y = min(p.y for p in room.polygon), max(p.y for p in room.polygon)
            room.computed_area_sqft = round(((max_x - min_x) * (max_y - min_y)) * self.SQMM_TO_SQFT, 2)

        return rooms

    def scale_rooms(self, rooms: List[Room]) -> List[Room]:
        """Ensures all generated coordinates scale proportionally within the template envelopes."""
        for room in rooms:
            for p in room.polygon:
                p.x = max(0.0, min(p.x, self.template.built_width_mm))
                p.y = max(0.0, min(p.y, self.template.built_length_mm))
        return rooms

    def validate_layout(self, rooms: List[Room]) -> bool:
        """Runs validation checks to ensure no room contains negative dimensions or inverted vertex points."""
        for room in rooms:
            if len(room.polygon) < 4:
                return False
            min_x, max_x = min(p.x for p in room.polygon), max(p.x for p in room.polygon)
            min_y, max_y = min(p.y for p in room.polygon), max(p.y for p in room.polygon)
            if (max_x - min_x) <= 0 or (max_y - min_y) <= 0:
                return False
        return True

    def allocate_floor(self, floor_index: int) -> List[Room]:
        """Executes the allocation pipeline sequence for a single targeted floor index plane."""
        # Isolate nodes associated with the targeted floor index plane
        floor_nodes = [node for node in self.graph.nodes.values() if node.floor_index == floor_index]
        if not floor_nodes:
            return []

        total_floor_space_mm2 = self.template.built_width_mm * self.template.built_length_mm
        
        sizes = self.calculate_room_sizes(floor_nodes, total_floor_space_mm2)
        rooms = self.generate_room_polygons(floor_index, floor_nodes, sizes)
        rooms = self.resolve_collisions(rooms)
        rooms = self.optimize_layout(rooms)
        rooms = self.scale_rooms(rooms)
        
        self.validate_layout(rooms)
        return rooms

    def allocate_rooms(self, project_id: str) -> BuildingGeometry:
        """
        Master orchestrator execution method compiling rooms across all requested floors 
        into a complete BuildingGeometry payload.
        """
        building_floors: List[FloorLevel] = []
        total_accumulated_area = 0.0

        for f_idx in range(self.template.number_of_floors):
            allocated_floor_rooms = self.allocate_floor(f_idx)
            
            # Compute floor boundary definitions
            bl_point = Point2D(x=0.0, y=0.0)
            tr_point = Point2D(x=self.template.built_width_mm, y=self.template.built_length_mm)
            
            floor_area_sqft = sum(r.computed_area_sqft for r in allocated_floor_rooms)
            total_accumulated_area += floor_area_sqft

            building_floors.append(
                FloorLevel(
                    level_index=f_idx,
                    rooms=allocated_floor_rooms,
                    circulation_paths=[],
                    dimensions=[],
                    bounding_box=(bl_point, tr_point)
                )
            )

        return BuildingGeometry(
            project_id=project_id,
            floors=building_floors,
            total_area_sqft=round(total_accumulated_area, 2),
            external_features={},
            svg_payload=None
        )