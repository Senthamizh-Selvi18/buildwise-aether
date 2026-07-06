from typing import List, Tuple
from backend.app.core.geometry.models import PortalGeometry, RoomGeometry

class WindowGenerator:
    STANDARD_WINDOW_WIDTH = 4.0
    MIN_WALL_LENGTH = 6.0
    TOLERANCE = 0.1

    NO_WINDOW_KEYWORDS = ("stair", "lift", "parking", "garage")

    @staticmethod
    def _edge_on_boundary(
        ex1: float, ey1: float, ex2: float, ey2: float,
        boundary_segments: List[Tuple[float, float, float, float]],
        tol: float,
    ) -> bool:
        edge_horizontal = abs(ey1 - ey2) < tol
        edge_vertical = abs(ex1 - ex2) < tol
        for (bx1, by1, bx2, by2) in boundary_segments:
            if edge_horizontal and abs(by1 - by2) < tol and abs(by1 - ey1) < tol:
                lo, hi = min(bx1, bx2), max(bx1, bx2)
                elo, ehi = min(ex1, ex2), max(ex1, ex2)
                if elo >= lo - tol and ehi <= hi + tol:
                    return True
            if edge_vertical and abs(bx1 - bx2) < tol and abs(bx1 - ex1) < tol:
                lo, hi = min(by1, by2), max(by1, by2)
                elo, ehi = min(ey1, ey2), max(ey1, ey2)
                if elo >= lo - tol and ehi <= hi + tol:
                    return True
        return False

    @staticmethod
    def generate(
        boundary_segments: List[Tuple[float, float, float, float]],
        rooms: List[RoomGeometry],
        entrance_segment: Tuple[float, float, float, float] = None,
    ) -> List[PortalGeometry]:
        portals: List[PortalGeometry] = []

        entrance_exclusion = None
        if entrance_segment is not None:
            ex1, ey1, ex2, ey2 = entrance_segment
            if abs(ey1 - ey2) < WindowGenerator.TOLERANCE:
                center = (ex1 + ex2) / 2
                entrance_exclusion = ("h", ey1, center - 2.5, center + 2.5)
            elif abs(ex1 - ex2) < WindowGenerator.TOLERANCE:
                center = (ey1 + ey2) / 2
                entrance_exclusion = ("v", ex1, center - 2.5, center + 2.5)

        for r in rooms:
            if any(kw in r.name.lower() for kw in WindowGenerator.NO_WINDOW_KEYWORDS):
                continue

            b = r.bbox
            w = b.width
            h = b.height

            candidate_edges = [
                (True,  b.x1, b.y1, b.x2, b.y1, (b.x1 + b.x2) / 2),
                (True,  b.x1, b.y2, b.x2, b.y2, (b.x1 + b.x2) / 2),
                (False, b.x1, b.y1, b.x1, b.y2, (b.y1 + b.y2) / 2),
                (False, b.x2, b.y1, b.x2, b.y2, (b.y1 + b.y2) / 2),
            ]

            for is_horizontal, ex1, ey1, ex2, ey2, mid in candidate_edges:
                span = w if is_horizontal else h
                if span < WindowGenerator.MIN_WALL_LENGTH:
                    continue
                if not WindowGenerator._edge_on_boundary(ex1, ey1, ex2, ey2, boundary_segments, WindowGenerator.TOLERANCE):
                    continue

                half = WindowGenerator.STANDARD_WINDOW_WIDTH / 2
                win_start = mid - half
                win_end = mid + half

                if entrance_exclusion is not None:
                    kind, fixed, ex_lo, ex_hi = entrance_exclusion
                    if (is_horizontal and kind == "h" and abs(ey1 - fixed) < WindowGenerator.TOLERANCE) or \
                       (not is_horizontal and kind == "v" and abs(ex1 - fixed) < WindowGenerator.TOLERANCE):
                        overlap = not (win_end <= ex_lo or win_start >= ex_hi)
                        if overlap:
                            continue

                if is_horizontal:
                    portals.append(PortalGeometry(
                        portal_type="window",
                        x1=win_start, y1=ey1, x2=win_end, y2=ey1,
                        associated_room=r.id, is_horizontal=True,
                    ))
                else:
                    portals.append(PortalGeometry(
                        portal_type="window",
                        x1=ex1, y1=win_start, x2=ex1, y2=win_end,
                        associated_room=r.id, is_horizontal=False,
                    ))

        return portals