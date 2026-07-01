# app/core/procedural_geometry_engine.py
import uuid, math
from typing import List
from dataclasses import dataclass

@dataclass
class RoomAllocation:
    id: str
    name: str
    x1: float
    y1: float
    x2: float
    y2: float
    area: float
    width: float
    height: float

class ProcedureGeometryEngine:
    ROOM_SPECS = {
        "living_room":    {"min":180,"ideal":250,"max":350,"weight":3.5},
        "master_bedroom": {"min":120,"ideal":160,"max":220,"weight":2.5},
        "bedroom":        {"min":100,"ideal":140,"max":180,"weight":2.0},
        "kitchen":        {"min":80, "ideal":120,"max":160,"weight":1.8},
        "dining":         {"min":80, "ideal":120,"max":160,"weight":1.8},
        "bathroom":       {"min":45, "ideal":60, "max":80, "weight":0.8},
        "pooja":          {"min":40, "ideal":60, "max":80, "weight":0.6},
        "parking":        {"min":150,"ideal":200,"max":300,"weight":2.5},
        "balcony":        {"min":40, "ideal":80, "max":120,"weight":0.8},
        "utility":        {"min":50, "ideal":80, "max":100,"weight":1.0},
        "storeroom":      {"min":40, "ideal":80, "max":120,"weight":0.8},
        "office":         {"min":80, "ideal":120,"max":150,"weight":1.5},
        "entrance":       {"min":40, "ideal":60, "max":100,"weight":1.0},
    }
    MIN_DIMENSION = 8.0

    @staticmethod
    def generate_unique_layout(
        plot_width: float,
        plot_depth: float,
        rooms_needed: List[str],
        mode: str = "adaptive",
        floors: int = 1,
        optimize_lighting: bool = True,
        optimize_ventilation: bool = True,
    ) -> List[RoomAllocation]:
        setback_front = 5.0
        setback_rear  = 5.0
        setback_side  = 2.0
        usable_w = plot_width - setback_side * 2
        usable_d = plot_depth - (setback_front + setback_rear)

        if usable_w <= ProcedureGeometryEngine.MIN_DIMENSION or usable_d <= ProcedureGeometryEngine.MIN_DIMENSION:
            # Setbacks too large — use full plot with minimal margin
            usable_w = max(plot_width - 2, ProcedureGeometryEngine.MIN_DIMENSION)
            usable_d = max(plot_depth - 2, ProcedureGeometryEngine.MIN_DIMENSION)
            setback_side = 1.0
            setback_front = 1.0

        if mode == "vastu":
            allocated = ProcedureGeometryEngine._allocate_vastu_layout(
                setback_side, setback_front, usable_w, usable_d, rooms_needed)
        else:
            allocated = ProcedureGeometryEngine._allocate_adaptive_layout(
                setback_side, setback_front, usable_w, usable_d, rooms_needed)

        if optimize_lighting:
            allocated = ProcedureGeometryEngine._optimize_for_lighting(allocated, plot_width, plot_depth)

        allocated = ProcedureGeometryEngine._add_circulation(allocated, plot_width, plot_depth)

        # Final guard — ensure no zero-size rooms
        allocated = [r for r in allocated if r.width > 0.5 and r.height > 0.5]
        return allocated

    @staticmethod
    def _allocate_adaptive_layout(x_off, y_off, width, depth, rooms):
        if not rooms:
            return []
        if len(rooms) == 1:
            return [RoomAllocation(
                id=uuid.uuid4().hex[:8], name=rooms[0],
                x1=x_off, y1=y_off,
                x2=x_off+width, y2=y_off+depth,
                area=width*depth, width=width, height=depth,
            )]

        weights = [ProcedureGeometryEngine.ROOM_SPECS.get(r,{}).get("weight",1.2) for r in rooms]
        total_w = sum(weights)
        mid = len(rooms)//2
        split_ratio = max(0.35, min(0.65, sum(weights[:mid])/total_w))

        if depth > width * 0.9:
            sd = depth * split_ratio
            if sd > ProcedureGeometryEngine.MIN_DIMENSION and (depth-sd) > ProcedureGeometryEngine.MIN_DIMENSION:
                return (ProcedureGeometryEngine._allocate_adaptive_layout(x_off, y_off, width, sd, rooms[:mid]) +
                        ProcedureGeometryEngine._allocate_adaptive_layout(x_off, y_off+sd, width, depth-sd, rooms[mid:]))
        else:
            sw = width * split_ratio
            if sw > ProcedureGeometryEngine.MIN_DIMENSION and (width-sw) > ProcedureGeometryEngine.MIN_DIMENSION:
                return (ProcedureGeometryEngine._allocate_adaptive_layout(x_off, y_off, sw, depth, rooms[:mid]) +
                        ProcedureGeometryEngine._allocate_adaptive_layout(x_off+sw, y_off, width-sw, depth, rooms[mid:]))

        # Fallback: horizontal strips
        rh = depth / len(rooms)
        return [RoomAllocation(
            id=uuid.uuid4().hex[:8], name=rooms[i],
            x1=x_off, y1=y_off+i*rh, x2=x_off+width, y2=y_off+(i+1)*rh,
            area=width*rh, width=width, height=rh,
        ) for i in range(len(rooms))]

    @staticmethod
    def _allocate_vastu_layout(x_off, y_off, width, depth, rooms):
        zones = {
            "entrance":       (0.0,0.33,0.0,0.15),
            "living_room":    (0.0,0.50,0.15,0.50),
            "kitchen":        (0.66,1.0,0.0,0.35),
            "dining":         (0.33,0.66,0.0,0.35),
            "master_bedroom": (0.66,1.0,0.60,1.0),
            "bedroom":        (0.0,0.50,0.60,1.0),
            "bathroom":       (0.33,0.66,0.60,1.0),
            "pooja":          (0.0,0.25,0.50,0.65),
            "utility":        (0.66,1.0,0.35,0.60),
            "storeroom":      (0.0,0.33,0.35,0.60),
            "office":         (0.33,0.66,0.35,0.60),
            "parking":        (0.0,0.40,0.0,0.20),
            "balcony":        (0.33,0.66,0.85,1.0),
        }
        default = (0.33,0.66,0.33,0.66)
        allocated = []
        used_zones = {}
        for room in rooms:
            z = zones.get(room, default)
            # Offset slightly if zone already used
            offset = used_zones.get(room, 0) * 0.05
            zx1 = min(z[0]+offset, 0.9)
            zx2 = min(z[1]+offset, 1.0)
            zy1 = min(z[2]+offset, 0.9)
            zy2 = min(z[3]+offset, 1.0)
            used_zones[room] = used_zones.get(room, 0) + 1
            w = (zx2-zx1)*width
            h = (zy2-zy1)*depth
            if w < 0.5: w = width * 0.2
            if h < 0.5: h = depth * 0.2
            allocated.append(RoomAllocation(
                id=uuid.uuid4().hex[:8], name=room,
                x1=round(x_off+zx1*width,2), y1=round(y_off+zy1*depth,2),
                x2=round(x_off+zx1*width+w,2), y2=round(y_off+zy1*depth+h,2),
                area=round(w*h,2), width=round(w,2), height=round(h,2),
            ))
        return allocated

    @staticmethod
    def _optimize_for_lighting(rooms, pw, pd):
        return rooms  # positions already set; no destructive move needed

    @staticmethod
    def _add_circulation(rooms, pw, pd):
        return rooms