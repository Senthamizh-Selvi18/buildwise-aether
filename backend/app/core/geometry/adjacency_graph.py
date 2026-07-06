from typing import List
from backend.app.core.geometry.models import RoomGeometry, AdjacencyEdge


class AdjacencyGraphBuilder:
    TOLERANCE = 0.05
    MIN_SHARED_LENGTH = 2.5

    @staticmethod
    def build(rooms: List[RoomGeometry]) -> List[AdjacencyEdge]:
        edges: List[AdjacencyEdge] = []
        n = len(rooms)
        tol = AdjacencyGraphBuilder.TOLERANCE

        for i in range(n):
            for j in range(i + 1, n):
                room_a, room_b = rooms[i], rooms[j]
                ba, bb = room_a.bbox, room_b.bbox

                if abs(ba.x2 - bb.x1) < tol:
                    edge = AdjacencyGraphBuilder._vertical_edge(room_a, room_b, ba.x2, ba, bb)
                    if edge is not None:
                        edges.append(edge)
                elif abs(bb.x2 - ba.x1) < tol:
                    edge = AdjacencyGraphBuilder._vertical_edge(room_b, room_a, bb.x2, bb, ba)
                    if edge is not None:
                        edges.append(edge)

                if abs(ba.y2 - bb.y1) < tol:
                    edge = AdjacencyGraphBuilder._horizontal_edge(room_a, room_b, ba.y2, ba, bb)
                    if edge is not None:
                        edges.append(edge)
                elif abs(bb.y2 - ba.y1) < tol:
                    edge = AdjacencyGraphBuilder._horizontal_edge(room_b, room_a, bb.y2, bb, ba)
                    if edge is not None:
                        edges.append(edge)

        return edges

    @staticmethod
    def _vertical_edge(left_room: RoomGeometry, right_room: RoomGeometry,
                        shared_x: float, b_left, b_right):
        y_lo = max(b_left.y1, b_right.y1)
        y_hi = min(b_left.y2, b_right.y2)
        if (y_hi - y_lo) < AdjacencyGraphBuilder.MIN_SHARED_LENGTH:
            return None
        return AdjacencyEdge(
            room_a_id=left_room.id, room_b_id=right_room.id,
            x1=shared_x, y1=y_lo, x2=shared_x, y2=y_hi,
            is_horizontal=False,
        )

    @staticmethod
    def _horizontal_edge(top_room: RoomGeometry, bottom_room: RoomGeometry,
                          shared_y: float, b_top, b_bottom):
        x_lo = max(b_top.x1, b_bottom.x1)
        x_hi = min(b_top.x2, b_bottom.x2)
        if (x_hi - x_lo) < AdjacencyGraphBuilder.MIN_SHARED_LENGTH:
            return None
        return AdjacencyEdge(
            room_a_id=top_room.id, room_b_id=bottom_room.id,
            x1=x_lo, y1=shared_y, x2=x_hi, y2=shared_y,
            is_horizontal=True,
        )