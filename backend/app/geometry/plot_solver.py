import math
from typing import List, Dict, Any
from backend.app.schemas.floorplan import Point2D, RoomLayout, ArchitecturalElement

class ProceduralPolygonSolver:
    @staticmethod
    def generate_boundary_points(shape: str, w: float, d: float) -> List[Point2D]:
        if shape == "square":
            side = min(w, d)
            return [Point2D(x=0, y=0), Point2D(x=side, y=0), Point2D(x=side, y=side), Point2D(x=0, y=side)]
        elif shape == "triangle":
            return [Point2D(x=0, y=0), Point2D(x=w, y=0), Point2D(x=w/2, y=d)]
        elif shape == "l_shape":
            return [Point2D(x=0, y=0), Point2D(x=w, y=0), Point2D(x=w, y=d*0.4), 
                    Point2D(x=w*0.4, y=d*0.4), Point2D(x=w*0.4, y=d), Point2D(x=0, y=d)]
        elif shape == "irregular":
            return [Point2D(x=0, y=0), Point2D(x=w*0.9, y=d*0.1), Point2D(x=w, y=d*0.8), 
                    Point2D(x=w*0.5, y=d), Point2D(x=0, y=d*0.8)]
        else: # Default: rectangle
            return [Point2D(x=0, y=0), Point2D(x=w, y=0), Point2D(x=w, y=d), Point2D(x=0, y=d)]

    @classmethod
    def slice_layout(cls, shape: str, w: float, d: float, rooms: List[str], floor_index: int, mode: str) -> List[RoomLayout]:
        layout_rooms = []
        if not rooms:
            rooms = ["Living Room", "Kitchen", "Bedroom 1", "Bathroom"]
            
        # Ensure identical vertical placement across multiple floors
        if "Staircase" not in rooms:
            rooms.insert(0, "Staircase")

        # Define canvas bounding boxes
        canvas_w = w
        canvas_h = d
        if shape == "square":
            canvas_w = canvas_h = min(w, d)

        num_rooms = len(rooms)
        cols = math.ceil(math.sqrt(num_rooms))
        rows = math.ceil(num_rooms / cols)
        
        r_w = canvas_w / cols
        r_h = canvas_h / rows

        room_idx = 0
        
        # Adjust spatial orientation based on mode
        ordered_rooms = list(rooms)
        if mode == "VASTU":
            # Reorder rooms according to orientation priorities
            if "Pooja Room" in ordered_rooms:
                ordered_rooms.remove("Pooja Room")
                ordered_rooms.insert(0, "Pooja Room") # Northeast priority placement
            if "Kitchen" in ordered_rooms:
                ordered_rooms.remove("Kitchen")
                ordered_rooms.append("Kitchen") # Southeast layout placement

        for r in range(rows):
            for c in range(cols):
                if room_idx >= len(ordered_rooms):
                    break
                r_name = ordered_rooms[room_idx]
                
                x1 = c * r_w
                y1 = r * r_h
                x2 = x1 + r_w
                y2 = y1 + r_h

                # Ensure layout elements fit securely within margins
                padding = 1.5
                if shape == "triangle" and y2 > (d * 0.6):
                    x1 += padding
                    x2 -= padding
                elif shape == "l_shape" and x1 > (w * 0.4) and y1 > (d * 0.4):
                    # Move elements out of the dead zone
                    x1, x2 = 0.0, r_w
                    y1, y2 = 0.0, r_h

                area = (x2 - x1) * (y2 - y1)
                
                # Dynamic measurement generation
                elements = [
                    ArchitecturalElement(type="door", x1=x1, y1=y1, x2=x1 + 3.0, y2=y1),
                    ArchitecturalElement(type="window", x1=x1 + (r_w/2) - 2.0, y1=y2, x2=x1 + (r_w/2) + 2.0, y2=y2)
                ]

                layout_rooms.append(RoomLayout(
                    name=r_name,
                    label=f"{r_name} ({int(x2-x1)}'x{int(y2-y1)}')",
                    x1=round(x1, 1),
                    y1=round(y1, 1),
                    x2=round(x2, 1),
                    y2=round(y2, 1),
                    area_sqft=round(area, 1),
                    furniture=[],
                    elements=elements
                ))
                room_idx += 1

        return layout_rooms