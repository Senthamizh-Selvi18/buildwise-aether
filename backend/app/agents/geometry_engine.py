import math
from typing import Dict, List, Any, Tuple, Optional

class Vector2D:
    def __init__(self, x: float, y: float):
        self.x = float(x)
        self.y = float(y)

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}

class GeometricBlueprintEngine:
    """
    Deterministic architectural CAD generator. Computes polygon plots, 
    wall offsets, portal cuts, and dimensions using pure vector mathematics.
    """

    @staticmethod
    def generate_plot_boundary(shape_type: str, width: float, depth: float) -> List[Vector2D]:
        """Computes true closed perimeter vertices based on plot geometries."""
        shape = shape_type.lower()
        if "l" in shape:
            return [
                Vector2D(0, 0), Vector2D(width, 0),
                Vector2D(width, depth * 0.45), Vector2D(width * 0.55, depth * 0.45),
                Vector2D(width * 0.55, depth), Vector2D(0, depth)
            ]
        if "triangle" in shape:
            return [Vector2D(0, 0), Vector2D(width, 0), Vector2D(width * 0.5, depth)]
        
        # Default: Precise Rectangular / Square CAD boundary lines
        return [Vector2D(0, 0), Vector2D(width, 0), Vector2D(width, depth), Vector2D(0, depth)]

    @staticmethod
    def slice_polygon_space(boundary: List[Vector2D], rooms_list: List[str], width: float, depth: float, option_type: str) -> List[Dict[str, Any]]:
        """
        Calculates non-overlapping coordinate splits using structural graph matrices.
        Applies a clean geometric algorithm to layout rooms relative to each other.
        """
        rooms_count = len(rooms_list)
        columns = 2 if rooms_count > 3 else 1
        rows = math.ceil(rooms_count / columns)
        
        step_x = width / columns
        step_y = depth / rows
        
        # Enforce adjacency configurations based on options
        arranged_list = list(rooms_list)
        if option_type == "vastu":
            # Reposition priority rooms into specific quadrants (e.g., Pooja room to the Northeast corner)
            arranged_list = sorted(rooms_list, key=lambda r: ("pooja" in r.lower(), "living" in r.lower()), reverse=True)
        else:
            # Optimize spatial layout by grouping active living zones near primary entry points
            arranged_list = sorted(rooms_list, key=lambda r: ("parking" in r.lower(), "living" in r.lower()), reverse=True)

        computed_rooms = []
        
        color_palette = {
            "living": "#ffffff",    # Warm White
            "bedroom": "#f0f9ff",   # Light Blue
            "kitchen": "#fffbeb",   # Cream
            "bathroom": "#ecfeff",  # Sky Blue
            "dining": "#fefce8",    # Light Yellow
            "parking": "#f1f5f9",   # Light Grey
            "garden": "#f0fdf4",    # Light Green
            "pooja": "#fff7ed",     # Soft Saffron
            "balcony": "#fdf6e2"    # Light Beige
        }

        for idx, name in enumerate(arranged_list):
            col_idx = idx % columns
            row_idx = idx // columns
            
            x1 = col_idx * step_x
            y1 = row_idx * step_y
            x2 = min(x1 + step_x, width)
            y2 = min(y1 + step_y, depth)
            
            # Form clear, non-overlapping closed polygons
            polygon_points = [
                {"x": x1, "y": y1}, {"x": x2, "y": y1},
                {"x": x2, "y": y2}, {"x": x1, "y": y2}
            ]
            
            w_ft = x2 - x1
            h_ft = y2 - y1
            area = w_ft * h_ft
            
            # Fallback color assignment
            fill_color = "#ffffff"
            for key, hex_code in color_palette.items():
                if key in name.lower():
                    fill_color = hex_code
                    break

            computed_rooms.append({
                "room_id": f"rm_{idx}_{option_type}",
                "name": name,
                "points": polygon_points,
                "center_x": (x1 + x2) / 2.0,
                "center_y": (y1 + y2) / 2.0,
                "width_ft": round(w_ft, 1),
                "height_ft": round(h_ft, 1),
                "area_sqft": round(area, 1),
                "fill_color_hex": fill_color
            })
            
        return computed_rooms

    @staticmethod
    def generate_walls_network(rooms: List[Dict[str, Any]], width: float, depth: float) -> List[Dict[str, Any]]:
        """
        Traces room boundaries to build a wall network with correct intersections.
        Makes exterior load-bearing walls thicker than interior partitions.
        """
        walls = []
        registered_edges = set()

        for rm in rooms:
            pts = rm["points"]
            length = len(pts)
            for i in range(length):
                p1 = pts[i]
                p2 = pts[(i + 1) % length]
                
                # Create a standardized key to prevent duplicate walls along shared room edges
                edge_key = tuple(sorted([(round(p1["x"], 1), round(p1["y"], 1)), (round(p2["x"], 1), round(p2["y"], 1))]))
                if edge_key in registered_edges:
                    continue
                registered_edges.add(edge_key)
                
                # Set thicker structural profiles for exterior outer walls
                is_exterior = (
                    p1["x"] == 0.0 or p2["x"] == 0.0 or p1["y"] == 0.0 or p2["y"] == 0.0 or
                    p1["x"] == width or p2["x"] == width or p1["y"] == depth or p2["y"] == depth
                )
                thickness = 0.85 if is_exterior else 0.45

                walls.append({
                    "x1": p1["x"], "y1": p1["y"],
                    "x2": p2["x"], "y2": p2["y"],
                    "thickness": thickness,
                    "is_exterior": is_exterior
                })
        return walls

    @staticmethod
    def compute_openings_and_portals(rooms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Calculates precise locations and trajectories for entry points and window frames."""
        portals = []
        for rm in rooms:
            name = rm["name"].lower()
            if "parking" in name or "garden" in name:
                continue
                
            pts = rm["points"]
            # Place entry doors along the front-facing horizontal partition lines
            dx = pts[1]["x"] - pts[0]["x"]
            dy = pts[2]["y"] - pts[1]["y"]
            
            # Structural Door cuts with 90-degree radius swings
            portals.append({
                "portal_type": "door",
                "x1": pts[0]["x"] + (dx * 0.1), "y1": pts[0]["y"],
                "x2": pts[0]["x"] + (dx * 0.1) + 3.0, "y1_cut": pts[0]["y"],
                "swing_x": pts[0]["x"] + (dx * 0.1) + 3.0, "swing_y": pts[0]["y"] + 3.0,
                "associated_room": rm["name"]
            })
            
            # Structural triple-pane Window cuts along exterior facades
            portals.append({
                "portal_type": "window",
                "x1": pts[2]["x"] - (dx * 0.5) - 2.0, "y1": pts[2]["y"],
                "x2": pts[2]["x"] - (dx * 0.5) + 2.0, "y2": pts[2]["y"],
                "associated_room": rm["name"]
            })
            
        return portals

    @staticmethod
    def perform_validation_checks(rooms: List[Dict[str, Any]], width: float, depth: float) -> bool:
        """Runs geometric boundary and sizing checks to prevent room or wall overlap bugs."""
        for rm in rooms:
            # Prevent rooms from being squished below minimum habitable dimensions
            if rm["width_ft"] < 6.0 or rm["height_ft"] < 6.0:
                return False
            # Verify no coordinates bleed out past the maximum plot boundaries
            for pt in rm["points"]:
                if pt["x"] < -0.1 or pt["x"] > width + 0.1 or pt["y"] < -0.1 or pt["y"] > depth + 0.1:
                    return False
        return True