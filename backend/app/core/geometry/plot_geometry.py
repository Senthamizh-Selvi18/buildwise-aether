"""
backend/app/core/geometry/plot_geometry.py

Builds the actual buildable PLOT OUTLINE (rectangle OR irregular polygon --
L-shape, T-shape, U-shape, corner-cut, or a fully custom user-supplied
polygon) and decomposes it into axis-aligned rectangles that the rest of
the pipeline (RoomAllocator's BSP) can allocate rooms into.

This is what makes the engine handle non-rectangular plots: instead of
always assuming a single plot_width x plot_depth rectangle, every floor is
generated from a PlotShape polygon. A plain rectangle is just the simplest
possible PlotShape, so nothing about existing rectangular-plot behaviour
changes -- irregular shapes are strictly additive.
"""

from typing import List, Optional, Tuple
from backend.app.core.geometry.models import Point, PlotShape, BoundingBox


class PlotShapeBuilder:
    TOLERANCE = 1e-6

    # ── Public entry point ──────────────────────────────────────────

    @staticmethod
    def build(
        plot_width: float,
        plot_depth: float,
        shape_type: str = "rectangle",
        cut_width: Optional[float] = None,
        cut_depth: Optional[float] = None,
        custom_points: Optional[List[Tuple[float, float]]] = None,
    ) -> PlotShape:
        """
        Builds a PlotShape polygon.

        - custom_points (if provided, 3+ points): the plot is exactly the
          polygon the user/front-end supplied -- supports ANY irregular
          shape, not just the named presets below.
        - shape_type presets ("rectangle" | "l_shape" | "t_shape" |
          "u_shape" | "corner_cut"): generated from plot_width/plot_depth
          plus an optional notch size (cut_width / cut_depth).
        - Anything unrecognised safely falls back to "rectangle" so the
          pipeline never breaks on a typo or unsupported value.
        """
        if custom_points and len(custom_points) >= 3:
            pts = [Point(float(x), float(y)) for x, y in custom_points]
            pts = PlotShapeBuilder._dedupe_closing_point(pts)
            return PlotShape(polygon=pts, shape_type="custom")

        shape_type = (shape_type or "rectangle").lower().strip().replace(" ", "_").replace("-", "_")
        w, d = float(plot_width), float(plot_depth)

        # Sensible default notch size if the caller didn't specify one,
        # always leaving at least 6ft of usable span on every side.
        cw = float(cut_width) if cut_width else min(w * 0.35, max(w - 6.0, 4.0))
        cd = float(cut_depth) if cut_depth else min(d * 0.35, max(d - 6.0, 4.0))
        cw = max(4.0, min(cw, w - 6.0)) if w > 10 else w * 0.3
        cd = max(4.0, min(cd, d - 6.0)) if d > 10 else d * 0.3

        if shape_type in ("l_shape", "l", "corner_cut", "lshaped"):
            # Notch removed from the bottom-right corner -> classic L plot.
            pts = [
                Point(0, 0), Point(w - cw, 0), Point(w - cw, d - cd),
                Point(w, d - cd), Point(w, d), Point(0, d),
            ]
            shape_type = "l_shape"

        elif shape_type in ("t_shape", "t", "tshaped"):
            top_h = max(8.0, d * 0.4)
            stem_w = max(8.0, w - cw)
            mid = w / 2.0
            pts = [
                Point(0, 0), Point(w, 0), Point(w, top_h),
                Point(mid + stem_w / 2, top_h), Point(mid + stem_w / 2, d),
                Point(mid - stem_w / 2, d), Point(mid - stem_w / 2, top_h),
                Point(0, top_h),
            ]
            shape_type = "t_shape"

        elif shape_type in ("u_shape", "u", "ushaped"):
            notch_w = max(6.0, cw)
            notch_h = max(6.0, d * 0.45)
            mid = w / 2.0
            pts = [
                Point(0, 0), Point(w, 0), Point(w, d),
                Point(mid + notch_w / 2, d), Point(mid + notch_w / 2, d - notch_h),
                Point(mid - notch_w / 2, d - notch_h), Point(mid - notch_w / 2, d),
                Point(0, d),
            ]
            shape_type = "u_shape"

        else:
            pts = [Point(0, 0), Point(w, 0), Point(w, d), Point(0, d)]
            shape_type = "rectangle"

        return PlotShape(polygon=pts, shape_type=shape_type)

    @staticmethod
    def _dedupe_closing_point(pts: List[Point]) -> List[Point]:
        if len(pts) > 1 and abs(pts[0].x - pts[-1].x) < 1e-6 and abs(pts[0].y - pts[-1].y) < 1e-6:
            return pts[:-1]
        return pts

    # ── Point-in-polygon (ray casting) ──────────────────────────────

    @staticmethod
    def _point_in_polygon(px: float, py: float, polygon: List[Point]) -> bool:
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i].x, polygon[i].y
            xj, yj = polygon[j].x, polygon[j].y
            denom = (yj - yi) if (yj - yi) != 0 else 1e-9
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / denom + xi:
                inside = not inside
            j = i
        return inside

    # ── Decompose polygon into rectangles for the BSP allocator ────

    @staticmethod
    def decompose(shape: PlotShape) -> List[BoundingBox]:
        """
        Splits the (possibly irregular) plot polygon into the minimum
        practical set of axis-aligned rectangles that, combined, cover
        exactly the buildable area -- never crossing the plot boundary.

        Works for any simple polygon: rectilinear shapes (L/T/U/corner-cut)
        decompose exactly; polygons with diagonal edges are covered by the
        largest axis-aligned rectangles that stay strictly inside the
        boundary (the true diagonal edge is still drawn exactly by the
        wall generator -- only the *room grid* is approximated).
        """
        polygon = shape.polygon
        xs = sorted(set(round(p.x, 4) for p in polygon))
        ys = sorted(set(round(p.y, 4) for p in polygon))

        if len(xs) < 2 or len(ys) < 2:
            return [shape.bounding_box]

        n_cols = len(xs) - 1
        n_rows = len(ys) - 1
        grid = [[False] * n_cols for _ in range(n_rows)]

        for r in range(n_rows):
            cy = (ys[r] + ys[r + 1]) / 2.0
            for c in range(n_cols):
                cx = (xs[c] + xs[c + 1]) / 2.0
                grid[r][c] = PlotShapeBuilder._point_in_polygon(cx, cy, polygon)

        # 1. Merge each row into maximal horizontal strips.
        row_rects: List[List[BoundingBox]] = []
        for r in range(n_rows):
            strips: List[BoundingBox] = []
            c = 0
            while c < n_cols:
                if not grid[r][c]:
                    c += 1
                    continue
                start = c
                while c < n_cols and grid[r][c]:
                    c += 1
                strips.append(BoundingBox(x1=xs[start], y1=ys[r], x2=xs[c], y2=ys[r + 1]))
            row_rects.append(strips)

        # 2. Vertically merge strips across consecutive rows that share the
        #    exact same x-extent, collapsing the grid into the minimum
        #    practical number of rectangles (an L-shape -> 2 rectangles,
        #    a plain rectangle -> 1, etc).
        merged: List[BoundingBox] = []
        consumed = [[False] * len(row_rects[r]) for r in range(n_rows)]

        for r in range(n_rows):
            for si, strip in enumerate(row_rects[r]):
                if consumed[r][si]:
                    continue
                cur = strip
                consumed[r][si] = True
                rr = r + 1
                while rr < n_rows:
                    match_idx = None
                    for sj, s2 in enumerate(row_rects[rr]):
                        if consumed[rr][sj]:
                            continue
                        if abs(s2.x1 - cur.x1) < 1e-6 and abs(s2.x2 - cur.x2) < 1e-6:
                            match_idx = sj
                            break
                    if match_idx is None:
                        break
                    s2 = row_rects[rr][match_idx]
                    cur = BoundingBox(x1=cur.x1, y1=cur.y1, x2=cur.x2, y2=s2.y2)
                    consumed[rr][match_idx] = True
                    rr += 1
                merged.append(cur)

        if not merged:
            return [shape.bounding_box]
        return merged

    # ── Boundary helpers (used by wall/door/window generators) ─────

    @staticmethod
    def boundary_segments(shape: PlotShape) -> List[Tuple[float, float, float, float]]:
        """Ordered list of (x1, y1, x2, y2) plot-perimeter edges."""
        return [(p1.x, p1.y, p2.x, p2.y) for p1, p2 in shape.edges]

    @staticmethod
    def entrance_segment(shape: PlotShape) -> Tuple[float, float, float, float]:
        """
        Picks the entrance (front) wall: the south-most (largest average y)
        horizontal boundary segment, matching the original convention of
        placing the main door on the bottom exterior wall. Falls back to
        the longest segment if no horizontal one exists (e.g. a rotated
        custom polygon).
        """
        segs = PlotShapeBuilder.boundary_segments(shape)
        horizontals = [s for s in segs if abs(s[1] - s[3]) < PlotShapeBuilder.TOLERANCE and abs(s[0] - s[2]) >= 3.0]
        if horizontals:
            return max(horizontals, key=lambda s: (s[1], abs(s[2] - s[0])))
        return max(segs, key=lambda s: ((s[0] - s[2]) ** 2 + (s[1] - s[3]) ** 2))