import math
from typing import List, Dict, Any, Tuple, Optional
from backend.app.geometry.models import BuildingGeometry, Room, Wall, Point2D, LineSegment
from backend.app.geometry.layout_templates import FootprintTemplate
from backend.app.geometry.door_generator import Door
from backend.app.geometry.window_generator import Window
from backend.app.geometry.dimension_generator import DimensionAnnotation

class SVGRenderer:
    """
    Deterministic architectural vector rendering engine. Transforms calculated
    building geometry matrices directly into production-grade CAD-style SVG floorplans.
    """

    def __init__(self, scale_factor: float = 0.05, padding: float = 2000.0):
        """
        Initializes the rendering canvas limits.
        scale_factor: Modulates geometric units into balanced viewport layout spaces.
        padding: Standard margins applied to avoid line clipping along outer boundary edges.
        """
        self.scale: float = scale_factor
        self.pad: float = padding

    def _coord(self, pt: Point2D) -> Tuple[float, float]:
        """Translates real structural millimeters into clean pixel spacing offsets for the SVG layout canvas."""
        return (pt.x + self.pad) * self.scale, (pt.y + self.pad) * self.scale

    def render_room_polygon(self, room: Room, paint_color: str, stroke_color: str) -> str:
        """Translates complex structural polygon meshes into a clean filled SVG polygon vector path."""
        if not room.polygon:
            return ""
        
        pts_str = " ".join(f"{self._coord(p)[0]},{self._coord(p)[1]}" for p in room.polygon)
        
        # Calculate polygon center to center room text cleanly
        x_coords = [p.x for p in room.polygon]
        y_coords = [p.y for p in room.polygon]
        cx, cy = (min(x_coords) + max(x_coords)) / 2.0, (min(y_coords) + max(y_coords)) / 2.0
        txt_x, txt_y = self._coord(Point2D(x=cx, y=cy))

        svg = f'  <polygon points="{pts_str}" fill="{paint_color}" stroke="{stroke_color}" stroke-width="1.5" opacity="0.85" />\n'
        # Append clear, scannable architectural text labeling inside the room boundary
        svg += f'  <text x="{txt_x}" y="{txt_y}" font-family="Arial, Helvetica, sans-serif" font-size="14" font-weight="bold" fill="#2C3E50" text-anchor="middle" dominant-baseline="middle">{room.id.split("_")[0].upper()}</text>\n'
        return svg

    def render_wall(self, wall: Wall) -> str:
        """Renders structural wall lines with distinct stroke weights to differentiate exterior and interior components."""
        x1, y1 = self._coord(wall.segment.start)
        x2, y2 = self._coord(wall.segment.end)
        
        # Apply thicker strokes for external envelope segments to maintain blueprint conventions
        if wall.wall_type.value == "exterior":
            stroke_w = 4.0
            color = "#111111"
        else:
            stroke_w = 2.0
            color = "#555555"

        return f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="round" />\n'

    def render_door(self, door: Door) -> str:
        """Renders highly descriptive CAD door openings complete with linear panels and 90-degree swing arc vectors."""
        x1, y1 = self._coord(door.start_point)
        x2, y2 = self._coord(door.end_point)
        
        dx = door.end_point.x - door.start_point.x
        dy = door.end_point.y - door.start_point.y
        length = math.hypot(dx, dy)
        
        if length == 0:
            return ""

        ux, uy = dx / length, dy / length
        
        # Compute the open door panel geometry projecting outwards perpendicular at 90 degrees
        px = door.start_point.x - uy * length
        py = door.start_point.y + ux * length
        x_p, y_p = self._coord(Point2D(x=px, y=py))

        # Clear structural aperture guide lines
        svg = f'  \n'
        svg += f'  <line x1="{x1}" y1="{y1}" x2="{x_p}" y2="{y_p}" stroke="#C0392B" stroke-width="2" />\n'
        
        # Generate the architectural circular sweep projection path
        r_px = length * self.scale
        svg += f'  <path d="M {x2} {y2} A {r_px} {r_px} 0 0 0 {x_p} {y_p}" fill="none" stroke="#C0392B" stroke-width="1.2" stroke-dasharray="3,3" />\n'
        return svg

    def render_window(self, window: Window) -> str:
        """Renders standard architectural parallel multi-line frame markers representing window placements."""
        x1, y1 = self._coord(window.start_point)
        x2, y2 = self._coord(window.end_point)
        
        dx = window.end_point.x - window.start_point.x
        dy = window.end_point.y - window.start_point.y
        length = math.hypot(dx, dy)
        
        if length == 0:
            return ""

        ux, uy = dx / length, dy / length
        offset_distance = 60.0  # Separate framing panes by a 60mm offset gap
        
        ox = -uy * offset_distance
        oy = ux * offset_distance

        w1_s_x, w1_s_y = self._coord(Point2D(x=window.start_point.x + ox, y=window.start_point.y + oy))
        w1_e_x, w1_e_y = self._coord(Point2D(x=window.end_point.x + ox, y=window.end_point.y + oy))
        
        w2_s_x, w2_s_y = self._coord(Point2D(x=window.start_point.x - ox, y=window.start_point.y - oy))
        w2_e_x, w2_e_y = self._coord(Point2D(x=window.end_point.x - ox, y=window.end_point.y - oy))

        svg = f'  \n'
        svg += f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#2980B9" stroke-width="1" />\n'
        svg += f'  <line x1="{w1_s_x}" y1="{w1_s_y}" x2="{w1_e_x}" y2="{w1_e_y}" stroke="#2980B9" stroke-width="1.5" />\n'
        svg += f'  <line x1="{w2_s_x}" y1="{w2_s_y}" x2="{w2_e_x}" y2="{w2_e_y}" stroke="#2980B9" stroke-width="1.5" />\n'
        
        # Add quick hash marks for standard ventilators
        if window.window_type == "VENTILATOR":
            cx, cy = self._coord(window.center_point)
            svg += f'  <line x1="{cx - 5}" y1="{cy - 5}" x2="{cx + 5}" y2="{cy + 5}" stroke="#2980B9" stroke-width="1" />\n'
            
        return svg

    def render_dimensions(self, annotations: List[Dict[str, Any]]) -> str:
        """Draws dimension line spans, tick marks, and legible distance labels directly from computed inputs."""
        svg = "  \n"
        for dim in annotations:
            # Parse coordinate positions from input mappings safely
            s_pt = Point2D(x=dim["start_point"]["x"], y=dim["start_point"]["y"])
            e_pt = Point2D(x=dim["end_point"]["x"], y=dim["end_point"]["y"])
            t_pt = Point2D(x=dim["text_position"]["x"], y=dim["text_position"]["y"])
            
            x1, y1 = self._coord(s_pt)
            x2, y2 = self._coord(e_pt)
            tx, ty = self._coord(t_pt)
            
            val_str = dim.get("formatted_text", f"{dim['value']} mm")

            # Main Dimension Line
            svg += f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#7F8C8D" stroke-width="1" />\n'
            # Left Tick
            svg += f'  <line x1="{x1 - 4}" y1="{y1 + 4}" x2="{x1 + 4}" y2="{y1 - 4}" stroke="#7F8C8D" stroke-width="1.5" />\n'
            # Right Tick
            svg += f'  <line x1="{x2 - 4}" y1="{y1 + 4}" x2="{x2 + 4}" y2="{y1 - 4}" stroke="#7F8C8D" stroke-width="1.5" />\n'
            # Text Value String Label
            svg += f'  <text x="{tx}" y="{ty}" font-family="Courier, monospace" font-size="11" fill="#7F8C8D" text-anchor="middle" dominant-baseline="middle">{val_str}</text>\n'
            
        return svg

    def render_plot(self, template: FootprintTemplate) -> str:
        """Renders bounding boundary profiles along with layout setback tracking references."""
        x0, y0 = self._coord(Point2D(x=0.0, y=0.0))
        xw, yw = self._coord(Point2D(x=template.site_width_mm, y=template.site_length_mm))
        
        w_px = xw - x0
        h_px = yw - y0

        svg = "  \n"
        svg += f'  <rect x="{x0}" y="{y0}" width="{w_px}" height="{h_px}" fill="none" stroke="#27AE60" stroke-width="2.5" stroke-dasharray="8,4" />\n'
        
        # Map internal building limit guides inside setback boundaries
        x_sb, y_sb = self._coord(Point2D(x=template.left_setback_mm, y=template.rear_setback_mm))
        xw_sb, yw_sb = self._coord(Point2D(x=template.site_width_mm - template.right_setback_mm, y=template.site_length_mm - template.front_setback_mm))
        
        svg += f'  <rect x="{x_sb}" y="{y_sb}" width="{xw_sb - x_sb}" height="{yw_sb - y_sb}" fill="none" stroke="#BDC3C7" stroke-width="1" stroke-dasharray="4,4" />\n'
        return svg

    def render_title_block(self, floor_idx: int, width: float, height: float) -> str:
        """Injects a minimalist blueprint metadata card block directly inside bottom-right workspace limits."""
        bx = width - 260.0
        by = height - 130.0
        
        svg = "  \n"
        svg += f'  <g transform="translate({bx}, {by})">\n'
        svg += '    <rect width="240" height="110" fill="#FFFFFF" stroke="#2C3E50" stroke-width="1.5" rx="4" />\n'
        svg += f'    <text x="15" y="25" font-family="Arial" font-size="13" font-weight="bold" fill="#2C3E50">BUILDWISE AETHER ENGINE</text>\n'
        svg += f'    <text x="15" y="48" font-family="Arial" font-size="11" fill="#7F8C8D">Floorplan: Level 0{floor_idx} Blueprint</text>\n'
        svg += '    <text x="15" y="68" font-family="Arial" font-size="11" fill="#7F8C8D">Scale: 1 : 20 Metric (Metric/Imperial)</text>\n'
        svg += '    <text x="15" y="88" font-family="Arial" font-size="10" fill="#95A5A6" font-style="italic">Project Date: Year 2026</text>\n'
        svg += '  </g>\n'
        return svg

    def render_scale(self, x: float, y: float) -> str:
        """Draws a clean mathematical pixel distance layout ruler block inside the frame."""
        svg = "  \n"
        svg += f'  <g transform="translate({x}, {y})">\n'
        svg += '    <line x1="0" y1="0" x2="100" y2="0" stroke="#2C3E50" stroke-width="3" />\n'
        svg += '    <line x1="0" y1="-4" x2="0" y2="4" stroke="#2C3E50" stroke-width="1.5" />\n'
        svg += '    <line x1="50" y1="-4" x2="50" y2="4" stroke="#2C3E50" stroke-width="1.5" />\n'
        svg += '    <line x1="100" y1="-4" x2="100" y2="4" stroke="#2C3E50" stroke-width="1.5" />\n'
        svg += '    <text x="0" y="-8" font-family="Arial" font-size="9" fill="#2C3E50" text-anchor="middle">0m</text>\n'
        svg += '    <text x="50" y="-8" font-family="Arial" font-size="9" fill="#2C3E50" text-anchor="middle">1.0m</text>\n'
        svg += '    <text x="100" y="-8" font-family="Arial" font-size="9" fill="#2C3E50" text-anchor="middle">2.0m</text>\n'
        svg += '  </g>\n'
        return svg

    def render_north_arrow(self, x: float, y: float) -> str:
        """Plots a minimalist, high-contrast structural compass symbol indexing directional orientation."""
        svg = "  \n"
        svg += f'  <g transform="translate({x}, {y})">\n'
        svg += '    <circle cx="0" cy="0" r="18" fill="none" stroke="#2C3E50" stroke-width="1.2" />\n'
        svg += '    <polygon points="0,-22 -6,-4 0,-10" fill="#2C3E50" />\n'
        svg += '    <polygon points="0,-22 6,-4 0,-10" fill="#BDC3C7" />\n'
        svg += '    <text x="0" y="28" font-family="Arial" font-size="11" font-weight="bold" fill="#2C3E50" text-anchor="middle">N</text>\n'
        svg += '  </g>\n'
        return svg

    def render_floor(
        self, 
        floor_idx: int, 
        building: BuildingGeometry, 
        template: FootprintTemplate,
        doors: List[Door], 
        windows: List[Window], 
        dimensions: List[Dict[str, Any]], 
        paint_map: Dict[str, Dict[str, str]]
    ) -> str:
        """Compiles individual component nodes into a unified, responsive SVG file layout string."""
        if floor_idx >= len(building.floors):
            return ""

        floor_data = building.floors[floor_idx]
        
        # Calculate dynamic Canvas boundary fields wrapping around target template structures
        max_canvas_w = (template.site_width_mm + (self.pad * 2.0)) * self.scale
        max_canvas_h = (template.site_length_mm + (self.pad * 2.0)) * self.scale

        # Open structural wrapper nodes
        svg_output = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {max_canvas_w} {max_canvas_h}" width="100%" height="100%" style="background-color: #FAFAFA;">\n'
        svg_output += f'  <style> text {{ select-style: none; cursor: default; }} </style>\n'
        
        # Step 1: Render structural template boundaries
        svg_output += self.render_plot(template)

        # Step 2: Render polygonal room structures complete with layout color fills
        for room in floor_data.rooms:
            style = paint_map.get(room.id, {"fill": "#F2F4F4", "stroke": "#7F8C8D"})
            svg_output += self.render_room_polygon(room, style["fill"], style["stroke"])

        # Step 3: Draw structural physical walls over background fills
        if floor_data.rooms:
            for wall in floor_data.rooms[0].walls:
                svg_output += self.render_wall(wall)

        # Step 4: Layer architectural aperture nodes over structural openings
        floor_doors = [d for d in doors if d.floor == floor_idx]
        for door in floor_doors:
            svg_output += self.render_door(door)

        floor_windows = [w for w in windows if w.floor == floor_idx]
        for window in floor_windows:
            svg_output += self.render_window(window)

        # Step 5: Embed technical annotation dimension layers
        floor_dims = [d for d in dimensions if d["floor"] == floor_idx or d["associated_object"] == "PLOT"]
        svg_output += self.render_dimensions(floor_dims)

        # Step 6: Render administrative layout widget accessories
        svg_output += self.render_north_arrow(50.0 + (self.pad * self.scale), 60.0 + (self.pad * self.scale))
        svg_output += self.render_scale(50.0 + (self.pad * self.scale), max_canvas_h - 40.0)
        svg_output += self.render_title_block(floor_idx, max_canvas_w, max_canvas_h)

        svg_output += "</svg>\n"
        return svg_output

    def render_complete_floorplan(
        self, 
        building: BuildingGeometry, 
        template: FootprintTemplate,
        doors: List[Door], 
        windows: List[Window], 
        dimensions: List[Dict[str, Any]], 
        paint_map: Dict[str, Dict[str, str]]
    ) -> List[str]:
        """Iterates through and compiles independent blueprint vector outputs for every floor in the building."""
        blueprints: List[str] = []
        for idx in range(len(building.floors)):
            svg_str = self.render_floor(idx, building, template, doors, windows, dimensions, paint_map)
            if svg_str:
                blueprints.append(svg_str)
        return blueprints

    def export_svg(self, svg_content: str, file_path: str) -> bool:
        """Utility function to write the generated SVG content to a file for system deployment handles."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            return True
        except IOError:
            return False