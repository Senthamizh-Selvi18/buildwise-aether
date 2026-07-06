from typing import List
from backend.app.core.geometry.models import DimensionLine

class DimensionGenerator:
    OFFSET = 8.0

    @staticmethod
    def generate(plot_w: float, plot_d: float) -> List[DimensionLine]:
        dimensions: List[DimensionLine] = []

        dimensions.append(DimensionLine(
            x1=0,
            y1=-DimensionGenerator.OFFSET,
            x2=plot_w,
            y2=-DimensionGenerator.OFFSET,
            label=f"WIDTH: {plot_w}'",
            is_horizontal=True
        ))

        dimensions.append(DimensionLine(
            x1=-DimensionGenerator.OFFSET,
            y1=0,
            x2=-DimensionGenerator.OFFSET,
            y2=plot_d,
            label=f"DEPTH: {plot_d}'",
            is_horizontal=False
        ))

        return dimensions