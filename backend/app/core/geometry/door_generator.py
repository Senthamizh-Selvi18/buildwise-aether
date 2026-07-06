from typing import List, Dict, Optional, Tuple
from backend.app.core.geometry.models import PortalGeometry, AdjacencyEdge, RoomGeometry


class DoorGenerator:
    STANDARD_DOOR_WIDTH = 3.0
    WALL_CLEARANCE = 0.5

    CIRCULATION_KEYWORDS = (
        "living", "hall", "dining", "corridor", "foyer", "lounge",
        "family", "entrance", "lobby",
    )

    DIRECT_CONNECT_PAIRS = [
        ("bedroom", "bathroom"), ("master", "bathroom"), ("suite", "bathroom"),
        ("guest", "bathroom"),
        ("kitchen", "dining"), ("kitchen", "utility"), ("kitchen", "store"),
        ("kitchen", "servant"),
        ("stair", "living"), ("stair", "hall"), ("stair", "corridor"),
        ("stair", "dining"), ("stair", "family"),
        ("lift", "stair"), ("lift", "living"), ("lift", "corridor"),
        ("parking", "entrance"), ("parking", "living"), ("parking", "foyer"),
        ("servant", "kitchen"), ("study", "bedroom"), ("study", "master"),
        ("pooja", "living"), ("pooja", "hall"), ("pooja", "foyer"),
        ("balcony", "bedroom"), ("balcony", "master"), ("balcony", "living"),
    ]

    @staticmethod
    def _is_circulation(name: str) -> bool:
        low = name.lower()
        return any(k in low for k in DoorGenerator.CIRCULATION_KEYWORDS)

    @staticmethod
    def _should_connect(name_a: str, name_b: str) -> bool:
        if DoorGenerator._is_circulation(name_a) or DoorGenerator._is_circulation(name_b):
            return True
        la, lb = name_a.lower(), name_b.lower()
        for kw_a, kw_b in DoorGenerator.DIRECT_CONNECT_PAIRS:
            if (kw_a in la and kw_b in lb) or (kw_b in la and kw_a in lb):
                return True
        return False

    @staticmethod
    def _door_for_edge(edge: AdjacencyEdge) -> PortalGeometry:
        if edge.is_horizontal:
            mid_x = (edge.x1 + edge.x2) / 2
            d_x1 = mid_x - (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            d_x2 = mid_x + (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            return PortalGeometry(
                portal_type="door",
                x1=d_x1, y1=edge.y1, x2=d_x2, y2=edge.y1,
                associated_room=edge.room_a_id,
                is_horizontal=True,
                hinge_x=d_x1, hinge_y=edge.y1,
                swing_direction_x=1.0, swing_direction_y=-1.0,
            )
        else:
            mid_y = (edge.y1 + edge.y2) / 2
            d_y1 = mid_y - (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            d_y2 = mid_y + (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            return PortalGeometry(
                portal_type="door",
                x1=edge.x1, y1=d_y1, x2=edge.x1, y2=d_y2,
                associated_room=edge.room_a_id,
                is_horizontal=False,
                hinge_x=edge.x1, hinge_y=d_y1,
                swing_direction_x=-1.0, swing_direction_y=1.0,
            )

    @staticmethod
    def _entrance_door(entrance_segment: Tuple[float, float, float, float]) -> PortalGeometry:
        ex1, ey1, ex2, ey2 = entrance_segment
        if abs(ey1 - ey2) < 1e-6:
            cx = (ex1 + ex2) / 2
            d_x1 = cx - (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            d_x2 = cx + (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            return PortalGeometry(
                portal_type="door",
                x1=d_x1, y1=ey1, x2=d_x2, y2=ey1,
                associated_room="Entrance",
                is_horizontal=True,
                hinge_x=d_x1, hinge_y=ey1,
                swing_direction_x=1.0, swing_direction_y=-1.0,
            )
        else:
            cy = (ey1 + ey2) / 2
            d_y1 = cy - (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            d_y2 = cy + (DoorGenerator.STANDARD_DOOR_WIDTH / 2)
            return PortalGeometry(
                portal_type="door",
                x1=ex1, y1=d_y1, x2=ex1, y2=d_y2,
                associated_room="Entrance",
                is_horizontal=False,
                hinge_x=ex1, hinge_y=d_y1,
                swing_direction_x=-1.0, swing_direction_y=1.0,
            )

    @staticmethod
    def generate(
        entrance_segment: Tuple[float, float, float, float],
        interior_edges: List[AdjacencyEdge],
        rooms: Optional[List[RoomGeometry]] = None,
    ) -> List[PortalGeometry]:
        portals: List[PortalGeometry] = []
        name_by_id: Dict[str, str] = {r.id: r.name for r in (rooms or [])}

        portals.append(DoorGenerator._entrance_door(entrance_segment))

        viable_edges = [
            e for e in interior_edges
            if e.length >= (DoorGenerator.STANDARD_DOOR_WIDTH + DoorGenerator.WALL_CLEARANCE * 2)
        ]

        connected_room_ids: set = set()

        for edge in viable_edges:
            name_a = name_by_id.get(edge.room_a_id, "")
            name_b = name_by_id.get(edge.room_b_id, "")
            if name_by_id and not DoorGenerator._should_connect(name_a, name_b):
                continue
            portals.append(DoorGenerator._door_for_edge(edge))
            connected_room_ids.add(edge.room_a_id)
            connected_room_ids.add(edge.room_b_id)

        if rooms:
            for room in rooms:
                if room.id in connected_room_ids:
                    continue
                candidates = [
                    e for e in viable_edges
                    if room.id in (e.room_a_id, e.room_b_id)
                ]
                if not candidates:
                    continue
                best_edge = max(candidates, key=lambda e: e.length)
                portals.append(DoorGenerator._door_for_edge(best_edge))
                connected_room_ids.add(best_edge.room_a_id)
                connected_room_ids.add(best_edge.room_b_id)

        return portals