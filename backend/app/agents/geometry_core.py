import math
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger("BuildWiseAether.GeometryCore")

class Vector2D:
    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)

    def to_dict(self) -> Dict[str, float]:
        return {"x": round(self.x, 2), "y": round(self.y, 2)}

class GeometryCADEngine:
    """
    Deterministic procedural vector engineering CAD engine. 
    Computes organic spatial subdivisions, wall line weights, door cuts, 
    and external window openings based on site perimeters.
    """

    @staticmethod
    def compute_plot_polygon(shape_type: str, width: float, depth: float) -> List[Vector2D]:
        """Calculates precise closed vertices matching custom lot boundary configurations."""
        st = shape_type.lower()
        if "l" in st:
            return [
                Vector2D(0, 0), Vector2D(width, 0),
                Vector2D(width, depth * 0.45), Vector2D(width * 0.55, depth * 0.45),
                Vector2D(width * 0.55, depth), Vector2D(0, depth)
            ]
        if "u" in st:
            return [
                Vector2D(0, 0), Vector2D(width, 0), Vector2D(width, depth),
                Vector2D(width * 0.75, depth), Vector2D(width * 0.75, depth * 0.45),
                Vector2D(width * 0.25, depth * 0.45), Vector2D(width * 0.25, depth), Vector2D(0, depth)
            ]
        if "triangle" in st:
            return [Vector2D(0, 0), Vector2D(width, 0), Vector2D(width * 0.5, depth)]
        if "irregular" in st or "polygon" in st or "corner" in st:
            return [
                Vector2D(0, 0), Vector2D(width * 0.85, 0),
                Vector2D(width, depth * 0.35), Vector2D(width * 0.9, depth),
                Vector2D(width * 0.15, depth * 0.85)
            ]
        
        # Default: Rectangle / Square CAD site bounds
        return [Vector2D(0, 0), Vector2D(width, 0), Vector2D(width, depth), Vector2D(0, depth)]

    @staticmethod
    def partition_architectural_poly(rooms_list: List[str], width: float, depth: float, layout_mode: str) -> List[Dict[str, Any]]:
        """
        Subdivides the site layout using dynamic offsets to create natural, non-aligned rooms.
        Arranges sequential access paths matching architectural human circulation rules.
        """
        count = len(rooms_list)
        
        # Human Circulation Sequence: Entrance -> Living -> Dining -> Kitchen -> Bedrooms -> Bathrooms
        priority_order = ["parking", "garden", "living", "dining", "kitchen", "stair", "bedroom", "bath"]
        if layout_mode == "vastu":
            priority_order = ["pooja", "living", "dining", "kitchen", "bedroom", "bath", "parking", "garden"]

        ordered_sequence = []
        for tag in priority_order:
            for rm in rooms_list:
                if tag in rm.lower() and rm not in ordered_sequence:
                    ordered_sequence.append(rm)
        for rm in rooms_list:
            if rm not in ordered_sequence:
                ordered_sequence.append(rm)

        columns = 2 if count > 3 else 1
        rows = math.ceil(count / columns)
        base_w = width / columns
        base_h = depth / rows

        computed_rooms = []
        for idx, name in enumerate(ordered_sequence):
            c_idx = idx % columns
            r_idx = idx // columns
            
            # Break uniform alignments using computational offsets to mimic an authentic manual CAD drawing
            shift_x = 4.5 if (idx % 3 == 1 and columns > 1) else 0.0
            shift_y = 3.5 if (idx % 2 == 1 and rows > 1) else 0.0

            x1 = max(0.0, c_idx * base_w + shift_x)
            y1 = max(0.0, r_idx * base_h + shift_y)
            x2 = min(width, x1 + base_w)
            y2 = min(depth, y1 + base_h)
            
            # Form asymmetric room steps (e.g., extend common dining zones or tuck bathrooms back)
            if "dining" in name.lower() and columns > 1:
                x2 = min(width, x2 + 4.0)
            if "bath" in name.lower() and rows > 1:
                y1 = min(y2 - 6.5, y1 + 2.5)

            pts = [{"x": x1, "y": y1}, {"x": x2, "y": y1}, {"x": x2, "y": y2}, {"x": x1, "y": y2}]
            rw = x2 - x1
            rh = y2 - y1

            computed_rooms.append({
                "room_id": f"cad_poly_{idx}_{layout_mode}",
                "name": name,
                "points": pts,
                "center_x": (x1 + x2) / 2.0,
                "center_y": (y1 + y2) / 2.0,
                "width_ft": round(rw, 1),
                "height_ft": round(rh, 1),
                "area_sqft": round(rw * rh, 1)
            })

        return computed_rooms

    @staticmethod
    def build_wall_network_graphs(rooms: List[Dict[str, Any]], width: float, depth: float) -> List[Dict[str, Any]]:
        """ Traces room boundaries to build wall networks using proper thick/thin configurations. """
        walls = []
        registered_edges = set()

        for rm in rooms:
            pts = rm["points"]
            le = len(pts)
            for i in range(le):
                p1 = pts[i]
                p2 = pts[(i + 1) % le]

                edge_hash = tuple(sorted([(round(p1["x"], 1), round(p1["y"], 1)), (round(p2["x"], 1), round(p2["y"], 1))]))
                if edge_hash in registered_edges:
                    continue
                registered_edges.add(edge_hash)

                # Classify edge type: outer boundaries receive thick lines, internal structural walls stay thin
                is_ext = (
                    p1["x"] <= 0.1 or p2["x"] <= 0.1 or p1["y"] <= 0.1 or p2["y"] <= 0.1 or
                    abs(p1["x"] - width) <= 0.1 or abs(p2["x"] - width) <= 0.1 or
                    abs(p1["y"] - depth) <= 0.1 or abs(p2["y"] - depth) <= 0.1
                )
                thickness = 0.90 if is_ext else 0.35

                walls.append({
                    "x1": p1["x"], "y1": p1["y"],
                    "x2": p2["x"], "y2": p2["y"],
                    "thickness": thickness,
                    "is_exterior": is_ext
                })
        return walls

    @staticmethod
    def slice_openings_and_arcs(rooms: List[Dict[str, Any]], walls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ Computes precise gaps and trajectories for logical structural doorways and exterior casements. """
        portals = []
        for rm in rooms:
            lbl = rm["name"].lower()
            if "parking" in lbl or "garden" in lbl:
                continue

            pts = rm["points"]
            rx1, ry1 = pts[0]["x"], pts[0]["y"]
            rx2, ry2 = pts[2]["x"], pts[2]["y"]
            dx = rx2 - rx1
            dy = ry2 - ry1

            # Inward Door gaps and matching swing trajectories
            portals.append({
                "portal_type": "door",
                "x1": rx1 + (dx * 0.12), "y1": ry1,
                "x2": rx1 + (dx * 0.12) + 3.0, "y2": ry1,
                "swing_x": rx1 + (dx * 0.12) + 3.0, "swing_y": ry1 + 3.0,
                "width_ft": 3.0,
                "swing_arc_path": f"M {rx1 + (dx * 0.12) + 3.0} {ry1} A 3.0 3.0 0 0 1 {rx1 + (dx * 0.12)} {ry1 + 3.0}",
                "associated_room": rm["name"]
            })

            # Align double/triple pane windows strictly with exterior walls
            is_exterior_top = (ry1 == 0.0)
            portals.append({
                "portal_type": "window",
                "x1": rx1 + (dx * 0.35), "y1": ry1 if is_exterior_top else ry2,
                "x2": rx1 + (dx * 0.35) + 5.0, "y2": ry1 if is_exterior_top else ry2,
                "width_ft": 5.0,
                "associated_room": rm["name"]
            })

        return portals

    @staticmethod
    def generate_cad_dimension_lines(rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ Generates precise, non-overlapping dimension lines and labels for clear readability. """
        dimension_lines = []
        for rm in rooms:
            pts = rm["points"]
            x1, y1 = pts[0]["x"], pts[0]["y"]
            x2, y2 = pts[2]["x"], pts[2]["y"]

            dimension_lines.append({
                "line_type": "horizontal_dimension",
                "x1": x1, "y1": y1 - 1.5,
                "x2": x2, "y2": y1 - 1.5,
                "text_x": (x1 + x2) / 2.0, "text_y": y1 - 2.2,
                "label": f"{int(rm['width_ft'])}'-0\""
            })

            dimension_lines.append({
                "line_type": "vertical_dimension",
                "x1": x1 - 1.5, "y1": y1,
                "x2": x1 - 1.5, "y2": y2,
                "text_x": x1 - 2.2, "text_y": (y1 + y2) / 2.0,
                "label": f"{int(rm['height_ft'])}'-0\""
            })
            
        return dimension_lines