from typing import List, Tuple
from backend.app.core.geometry.models import WallGeometry, AdjacencyEdge

class WallGenerator:
    EXTERIOR_THICKNESS = 0.8
    INTERIOR_THICKNESS = 0.4

    @staticmethod
    def generate(
        boundary_segments: List[Tuple[float, float, float, float]],
        interior_edges: List[AdjacencyEdge],
    ) -> List[WallGeometry]:
        walls: List[WallGeometry] = []

        for (x1, y1, x2, y2) in boundary_segments:
            walls.append(WallGeometry(
                x1=x1, y1=y1, x2=x2, y2=y2,
                thickness=WallGenerator.EXTERIOR_THICKNESS,
                is_exterior=True,
            ))

        for edge in interior_edges:
            walls.append(WallGeometry(
                x1=edge.x1,
                y1=edge.y1,
                x2=edge.x2,
                y2=edge.y2,
                thickness=WallGenerator.INTERIOR_THICKNESS,
                is_exterior=False
            ))

        return walls