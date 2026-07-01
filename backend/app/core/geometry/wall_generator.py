from typing import List, Tuple
from backend.app.core.geometry.models import WallGeometry, AdjacencyEdge

class WallGenerator:
    """
    Generates explicit WallGeometry from the plot's perimeter and the
    Adjacency Graph. Ensures that shared interior boundaries are
    represented as single, mathematically sound partitions rather than
    overlapping borders.

    The exterior shell is now driven by the plot's actual boundary
    segments (from PlotShapeBuilder.boundary_segments) rather than a
    hardcoded 4-sided rectangle, so L-shaped / T-shaped / U-shaped /
    custom-polygon plots get a correctly-traced exterior wall outline
    instead of a bounding-box rectangle that would cut through empty
    (non-buildable) area.
    """
    EXTERIOR_THICKNESS = 0.8
    INTERIOR_THICKNESS = 0.4

    @staticmethod
    def generate(
        boundary_segments: List[Tuple[float, float, float, float]],
        interior_edges: List[AdjacencyEdge],
    ) -> List[WallGeometry]:
        walls: List[WallGeometry] = []

        # 1. Generate Exterior Structural Shell -- one wall per plot
        # boundary edge, in order, so irregular outlines (L/T/U/custom)
        # are traced exactly rather than approximated as a rectangle.
        for (x1, y1, x2, y2) in boundary_segments:
            walls.append(WallGeometry(
                x1=x1, y1=y1, x2=x2, y2=y2,
                thickness=WallGenerator.EXTERIOR_THICKNESS,
                is_exterior=True,
            ))

        # 2. Generate Interior Partitions
        # We exclusively use the Adjacency Graph to avoid double-drawing walls where rooms touch
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