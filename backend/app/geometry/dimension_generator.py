import math
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel
from backend.app.geometry.models import Point2D, LineSegment, Wall, Room, FloorLevel, BuildingGeometry, RoomType
from backend.app.geometry.layout_templates import FootprintTemplate
from backend.app.geometry.door_generator import Door
from backend.app.geometry.window_generator import Window

class DimensionAnnotation(BaseModel):
    """Data model representing the spatial pathing, text projection points, and metadata for a dimension line."""
    id: str
    floor: int
    type: str  # e.g., "OVERALL", "ROOM_WIDTH", "ROOM_HEIGHT", "DOOR_WIDTH", "WINDOW_WIDTH", "WALL_THICKNESS"
    start_point: Point2D
    end_point: Point2D
    offset: float
    value: float  # Absolute length value stored in millimeters (mm)
    unit: str     # "mm"
    text_position: Point2D
    arrow_start: Point2D
    arrow_end: Point2D
    orientation: str  # "HORIZONTAL" or "VERTICAL"
    associated_object: str  # Entity ID this dimension measures

class DimensionGenerator:
    """
    Deterministic geometric calculation engine for architectural dimensions.
    Derives annotation vectors directly from compiled layouts.
    """

    @staticmethod
    def mm_to_feet_inches(mm_value: float) -> str:
        """Helper to convert millimeter measurements into a traditional architectural feet-inches string format."""
        total_inches = mm_value / 25.4
        feet = int(total_inches // 12)
        inches = int(round(total_inches % 12))
        if inches == 12:
            feet += 1
            inches = 0
        return f"{feet}'-{inches}\""

    @classmethod
    def calculate_dimension_offsets(
        cls, 
        start: Point2D, 
        end: Point2D, 
        base_offset: float, 
        orientation: str
    ) -> Tuple[Point2D, Point2D, Point2D]:
        """
        Calculates the projected line coordinates and text placement point 
        by applying a perpendicular displacement vector to the dimension line.
        """
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        
        if length == 0:
            return start, start, start

        # Generate normal unit direction vectors
        nx = -dy / length
        ny = dx / length

        # Project lines outward using the specified offset values
        dim_start = Point2D(x=start.x + nx * base_offset, y=start.y + ny * base_offset)
        dim_end = Point2D(x=end.x + nx * base_offset, y=end.y + ny * base_offset)
        
        # Center the text label along the projected dimension path line
        text_pos = Point2D(
            x=(dim_start.x + dim_end.x) / 2.0 + nx * 150.0,  # Lift label 150mm off the line for legibility
            y=(dim_start.y + dim_end.y) / 2.0 + ny * 150.0
        )

        return dim_start, dim_end, text_pos

    @classmethod
    def generate_room_dimensions(cls, floor_idx: int, room: Room) -> List[DimensionAnnotation]:
        """Calculates internal width and height dimensions for an individual room using its outer boundary limits."""
        dimensions = []
        if not room.polygon:
            return dimensions

        x_coords = [p.x for p in room.polygon]
        y_coords = [p.y for p in room.polygon]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        width_val = max_x - min_x
        height_val = max_y - min_y

        # 1. Internal Width Dimension (Horizontal Axis Line)
        w_start = Point2D(x=min_x, y=min_y + 300.0)  # Offset internally by 300mm to clear physical wall intersections
        w_end = Point2D(x=max_x, y=min_y + 300.0)
        _, _, w_text = cls.calculate_dimension_offsets(w_start, w_end, 0.0, "HORIZONTAL")
        
        dimensions.append(DimensionAnnotation(
            id=f"dim_room_w_{room.id}",
            floor=floor_idx,
            type="ROOM_WIDTH",
            start_point=w_start,
            end_point=w_end,
            offset=0.0,
            value=round(width_val, 2),
            unit="mm",
            text_position=w_text,
            arrow_start=w_start,
            arrow_end=w_end,
            orientation="HORIZONTAL",
            associated_object=room.id
        ))

        # 2. Internal Height Dimension (Vertical Axis Line)
        h_start = Point2D(x=min_x + 300.0, y=min_y)
        h_end = Point2D(x=min_x + 300.0, y=max_y)
        _, _, h_text = cls.calculate_dimension_offsets(h_start, h_end, 0.0, "VERTICAL")

        dimensions.append(DimensionAnnotation(
            id=f"dim_room_h_{room.id}",
            floor=floor_idx,
            type="ROOM_HEIGHT",
            start_point=h_start,
            end_point=h_end,
            offset=0.0,
            value=round(height_val, 2),
            unit="mm",
            text_position=h_text,
            arrow_start=h_start,
            arrow_end=h_end,
            orientation="VERTICAL",
            associated_object=room.id
        ))

        return dimensions

    @classmethod
    def generate_building_dimensions(cls, floor_idx: int, floor: FloorLevel) -> List[DimensionAnnotation]:
        """Calculates overall external bounding box dimensions across a floor plan's structural perimeter."""
        dimensions = []
        if not floor.rooms:
            return dimensions

        all_x = [p.x for r in floor.rooms for p in r.polygon]
        all_y = [p.y for r in floor.rooms for p in r.polygon]
        
        if not all_x or not all_y:
            return dimensions

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        b_width = max_x - min_x
        b_height = max_y - min_y

        # Overall Exterior Horizontal Structural Span (Placed outside bottom layout profile)
        start_w = Point2D(x=min_x, y=min_y)
        end_w = Point2D(x=max_x, y=min_y)
        dim_start_w, dim_end_w, text_w = cls.calculate_dimension_offsets(start_w, end_w, -800.0, "HORIZONTAL") # Shift down 800mm to sit cleanly outside perimeter walls

        dimensions.append(DimensionAnnotation(
            id=f"dim_bldg_width_f_{floor_idx}",
            floor=floor_idx,
            type="OVERALL",
            start_point=dim_start_w,
            end_point=dim_end_w,
            offset=-800.0,
            value=round(b_width, 2),
            unit="mm",
            text_position=text_w,
            arrow_start=dim_start_w,
            arrow_end=dim_end_w,
            orientation="HORIZONTAL",
            associated_object="BUILDING"
        ))

        return dimensions

    @classmethod
    def generate_door_dimensions(cls, floor_idx: int, doors: List[Door]) -> List[DimensionAnnotation]:
        """Calculates clear opening dimensions for all structural door assemblies on the current floor plan."""
        dimensions = []
        for d in doors:
            if d.floor != floor_idx:
                continue
            
            # Use a short perpendicular offset to position the dimension line cleanly within the door frame opening path
            _, _, text_p = cls.calculate_dimension_offsets(d.start_point, d.end_point, 150.0, "HORIZONTAL")
            
            dimensions.append(DimensionAnnotation(
                id=f"dim_door_{d.id}",
                floor=floor_idx,
                type="DOOR_WIDTH",
                start_point=d.start_point,
                end_point=d.end_point,
                offset=150.0,
                value=round(d.width, 2),
                unit="mm",
                text_position=text_p,
                arrow_start=d.start_point,
                arrow_end=d.end_point,
                orientation="HORIZONTAL",
                associated_object=d.id
            ))
        return dimensions

    @classmethod
    def generate_window_dimensions(cls, floor_idx: int, windows: List[Window]) -> List[DimensionAnnotation]:
        """Calculates structural opening width annotations for all window instances on the floor plan."""
        dimensions = []
        for w in windows:
            if w.floor != floor_idx:
                continue
                
            _, _, text_p = cls.calculate_dimension_offsets(w.start_point, w.end_point, -200.0, "HORIZONTAL")
            
            dimensions.append(DimensionAnnotation(
                id=f"dim_win_{w.id}",
                floor=floor_idx,
                type="WINDOW_WIDTH",
                start_point=w.start_point,
                end_point=w.end_point,
                offset=-200.0,
                value=round(w.width, 2),
                unit="mm",
                text_position=text_p,
                arrow_start=w.start_point,
                arrow_end=w.end_point,
                orientation="HORIZONTAL",
                associated_object=w.id
            ))
        return dimensions

    @classmethod
    def generate_plot_dimensions(cls, template: FootprintTemplate) -> List[DimensionAnnotation]:
        """Generates outer dimension boundary annotations mapping site perimeter allocations directly from plot templates."""
        dimensions = []
        
        # Plot Site Boundary Width Annotation
        p_start_w = Point2D(x=0.0, y=0.0)
        p_end_w = Point2D(x=template.site_width_mm, y=0.0)
        ds_w, de_w, text_w = cls.calculate_dimension_offsets(p_start_w, p_end_w, -1500.0, "HORIZONTAL") # Shift out 1500mm to avoid conflicts with building dimensions

        dimensions.append(DimensionAnnotation(
            id="dim_plot_site_width",
            floor=0,
            type="PLOT_WIDTH",
            start_point=ds_w,
            end_point=de_w,
            offset=-1500.0,
            value=round(template.site_width_mm, 2),
            unit="mm",
            text_position=text_w,
            arrow_start=ds_w,
            arrow_end=de_w,
            orientation="HORIZONTAL",
            associated_object="PLOT"
        ))

        return dimensions

    @classmethod
    def validate_dimensions(cls, dimensions: List[DimensionAnnotation]) -> bool:
        """Runs safety compliance checks on generated dimensions to catch errors like missing targets, duplicates, or zeros."""
        seen_ids = set()
        for dim in dimensions:
            if dim.id in seen_ids:
                return False
            if dim.value <= 0.0:
                # Catch invalid geometric measurements (zero or negative lengths)
                return False
            seen_ids.add(dim.id)
        return True

    @classmethod
    def export_dimensions(cls, dimensions: List[DimensionAnnotation]) -> List[Dict[str, Any]]:
        """Converts internal dimension models into structured dictionary formats for JSON serialization."""
        serialized = []
        for d in dimensions:
            item = d.dict()
            # Append an architectural feet-inches formatted string to streamline SVG string rendering tasks
            item["formatted_text"] = cls.mm_to_feet_inches(d.value)
            serialized.append(item)
        return serialized

    def generate_dimensions(
        self, 
        building: BuildingGeometry, 
        template: FootprintTemplate, 
        doors: List[Door], 
        windows: List[Window]
    ) -> List[Dict[str, Any]]:
        """Orchestrates the entire dimensional layout analysis across all floors, checking validity before exporting."""
        all_annotations: List[DimensionAnnotation] = []

        # 1. Map external boundaries from the site template
        all_annotations.extend(cls.generate_plot_dimensions(template))

        # 2. Extract layout dimensions for each floor level
        for floor in building.floors:
            all_annotations.extend(cls.generate_building_dimensions(floor.level_index, floor))
            
            for room in floor.rooms:
                all_annotations.extend(cls.generate_room_dimensions(floor.level_index, room))

            # 3. Add door and window cutout annotations
            all_annotations.extend(cls.generate_door_dimensions(floor.level_index, doors))
            all_annotations.extend(cls.generate_window_dimensions(floor.level_index, windows))

        # 4. Verify annotation integrity
        if not cls.validate_dimensions(all_annotations):
            # Fallback filter to remove duplicates or malformed segments if validation flags an error
            clean_list = []
            seen = set()
            for d in all_annotations:
                if d.id not in seen and d.value > 0:
                    clean_list.append(d)
                    seen.add(d.id)
            all_annotations = clean_list

        return cls.export_dimensions(all_annotations)