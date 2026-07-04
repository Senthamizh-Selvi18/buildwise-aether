"""
backend/app/core/geometry/adjacency_graph.py

Builds the Adjacency Graph: the list of shared-wall segments between every
pair of rooms on a floor. This is the one module every other piece of the
pipeline depends on but that was missing from the deployment:

    geometry_engine.py  -> from .adjacency_graph import AdjacencyGraphBuilder
    wall_generator.py   -> consumes the AdjacencyEdge list to draw interior
                            partitions (so shared walls aren't drawn twice)
    door_generator.py   -> consumes the AdjacencyEdge list to decide where
                            interior doors can go (edge.length, edge.is_horizontal,
                            edge.room_a_id / room_b_id)

Because geometry_engine.py imports this module at the top level, its
absence raises an ImportError the moment `backend.app.core.geometry
.geometry_engine` is imported -- which is exactly what main.py's
`try: from backend.app.core.geometry.geometry_engine import GeometryEngine
except ImportError: GeometryEngine = None` guard was silently swallowing.
The result: the real BSP + adjacency + Vastu + zoning pipeline never ran on
a single request -- everything fell through to main.py's much simpler
fallback layout generator instead, even though every *other* file this
engine needs (models, plot_geometry, room_allocator, wall_generator,
door_generator, window_generator, dimension_generator, svg_renderer) was
already present and correct.

Algorithm: for every pair of rooms on a floor, check whether one room's
right edge touches the other's left edge (vertical shared wall) or one
room's bottom edge touches the other's top edge (horizontal shared wall).
"Touches" allows a small floating-point tolerance (BSP splits are exact,
but downstream rounding can introduce sub-epsilon drift). The overlapping
span along that shared line becomes the AdjacencyEdge -- and only if that
overlap is long enough to plausibly fit a door (MIN_SHARED_LENGTH), so two
rooms that merely share a single corner point don't produce a degenerate
zero-length "wall".
"""

from typing import List
from backend.app.core.geometry.models import RoomGeometry, AdjacencyEdge


class AdjacencyGraphBuilder:
    # Two edges within this distance (feet) are treated as the same line --
    # BSP partitioning is exact, but this guards against float drift from
    # repeated split-ratio arithmetic.
    TOLERANCE = 0.05

    # Minimum overlapping length (feet) for a shared boundary to count as a
    # real adjacency worth drawing a wall/door for. Two rooms that only
    # touch at a corner (near-zero overlap) are not "adjacent" in any
    # architecturally useful sense.
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

                # ── Vertical shared wall (one room's right edge == the
                # other's left edge) ────────────────────────────────────
                if abs(ba.x2 - bb.x1) < tol:
                    edge = AdjacencyGraphBuilder._vertical_edge(room_a, room_b, ba.x2, ba, bb)
                    if edge is not None:
                        edges.append(edge)
                elif abs(bb.x2 - ba.x1) < tol:
                    edge = AdjacencyGraphBuilder._vertical_edge(room_b, room_a, bb.x2, bb, ba)
                    if edge is not None:
                        edges.append(edge)

                # ── Horizontal shared wall (one room's bottom edge == the
                # other's top edge) ─────────────────────────────────────
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
                        shared_x: float, b_left, b_right) -> "AdjacencyEdge | None":
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
                          shared_y: float, b_top, b_bottom) -> "AdjacencyEdge | None":
        x_lo = max(b_top.x1, b_bottom.x1)
        x_hi = min(b_top.x2, b_bottom.x2)
        if (x_hi - x_lo) < AdjacencyGraphBuilder.MIN_SHARED_LENGTH:
            return None
        return AdjacencyEdge(
            room_a_id=top_room.id, room_b_id=bottom_room.id,
            x1=x_lo, y1=shared_y, x2=x_hi, y2=shared_y,
            is_horizontal=True,
        )