from typing import List
from backend.app.core.geometry.models import DimensionLine

class DimensionGenerator:
    """
    Computes architectural dimension lines and labels for professional CAD rendering.
    Positions global plot dimensions outside the exterior walls to prevent overlap.

    Dimensions are taken from the plot's bounding box (its overall envelope
    width/depth), which is well-defined for rectangular AND irregular plots
    alike -- it's simply the smallest rectangle a regular OR irregular plot
    polygon fits inside.
    """
    OFFSET = 8.0  # Distance in feet outside the plot boundary

    @staticmethod
    def generate(plot_w: float, plot_d: float) -> List[DimensionLine]:
        dimensions: List[DimensionLine] = []

        # 1. Total Plot Width (Top)
        dimensions.append(DimensionLine(
            x1=0,
            y1=-DimensionGenerator.OFFSET,
            x2=plot_w,
            y2=-DimensionGenerator.OFFSET,
            label=f"WIDTH: {plot_w}'",
            is_horizontal=True
        ))
        
        # 2. Total Plot Depth (Left)
        dimensions.append(DimensionLine(
            x1=-DimensionGenerator.OFFSET,
            y1=0,
            x2=-DimensionGenerator.OFFSET,
            y2=plot_d,
            label=f"DEPTH: {plot_d}'",
            is_horizontal=False
        ))

        return dimensions