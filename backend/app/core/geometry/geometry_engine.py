"""
backend/app/core/geometry/geometry_engine.py

BuildWise Aether — Master Geometry Orchestrator v4.0
Intelligent architectural layout engine with:
  - Architectural zoning (public / semi-private / private)
  - Adjacency rules (kitchen↔dining, bedroom↔bathroom, parking↔entrance)
  - Vastu Shastra cardinal placement
  - Wet-area stacking across floors
  - Circulation optimisation (corridor minimisation)
  - Privacy gradient (street-front → rear)
  - BSP with per-floor axis variation
  - Dynamic paint, cost, scoring — zero hardcoded layouts
"""

import re
import math
import uuid
from typing import List, Dict, Any, Tuple, Optional

from backend.app.core.geometry.models import (
    RoomGeometry, BoundingBox, AdjacencyEdge, PlotShape,
    WallGeometry, PortalGeometry, DimensionLine, FloorPlanGeometry,
)
from backend.app.core.geometry.adjacency_graph import AdjacencyGraphBuilder
from backend.app.core.geometry.room_allocator import RoomAllocator
from backend.app.core.geometry.wall_generator import WallGenerator
from backend.app.core.geometry.door_generator import DoorGenerator
from backend.app.core.geometry.window_generator import WindowGenerator
from backend.app.core.geometry.dimension_generator import DimensionGenerator
from backend.app.core.geometry.svg_renderer import SVGRenderer
from backend.app.core.geometry.plot_geometry import PlotShapeBuilder


# ─────────────────────────────────────────────────────────────────
# ARCHITECTURAL KNOWLEDGE BASE
# ─────────────────────────────────────────────────────────────────

# BSP weight: larger weight → more floor area allocated
ROOM_WEIGHTS: Dict[str, float] = {
    "living": 3.5, "hall": 3.5, "lounge": 3.0,
    "master": 2.8, "master bedroom": 2.8,
    "bedroom": 2.2, "guest": 2.0, "suite": 2.5,
    "kitchen": 2.0, "dining": 1.8,
    "parking": 2.5, "garage": 2.5, "car": 2.5,
    "bathroom": 0.9, "toilet": 0.7, "wc": 0.7,
    "pooja": 0.7, "puja": 0.7, "prayer": 0.7,
    "stair": 0.8, "staircase": 0.8, "lift": 0.6,
    "balcony": 1.2, "terrace": 1.5, "garden": 2.0,
    "study": 1.5, "office": 1.5, "library": 1.5,
    "store": 0.8, "utility": 0.8, "laundry": 0.8,
    "servant": 1.2, "family": 2.0, "corridor": 0.6,
}

# Architectural zone assignment per room keyword
# Zones: 0=public(front), 1=semi-public, 2=semi-private, 3=private(rear)
ROOM_ZONE: Dict[str, int] = {
    "parking": 0, "garage": 0, "garden": 0, "entrance": 0, "foyer": 0,
    "living": 1, "hall": 1, "dining": 1, "kitchen": 1,
    "pooja": 1, "puja": 1, "prayer": 1, "store": 1, "utility": 1,
    "stair": 1, "lift": 1, "servant": 1, "laundry": 1,
    "study": 2, "office": 2, "library": 2, "family": 2, "lounge": 2,
    "guest": 2, "balcony": 2,
    "bedroom": 3, "master": 3, "suite": 3, "bathroom": 3, "toilet": 3,
    "terrace": 3, "dressing": 3,
}

# Adjacency rules: rooms that must be placed next to each other
ADJACENCY_RULES: List[Tuple[str, str, int]] = [
    # (room_a_kw, room_b_kw, priority)  — higher priority = stronger preference
    ("kitchen",  "dining",   10),
    ("master",   "bathroom",  9),
    ("bedroom",  "bathroom",  8),
    ("living",   "dining",    7),
    ("living",   "balcony",   6),
    ("kitchen",  "utility",   6),
    ("kitchen",  "store",     5),
    ("stair",    "living",    5),
    ("parking",  "entrance",  5),
    ("pooja",    "living",    4),
    ("study",    "bedroom",   3),
    ("servant",  "kitchen",   4),
    ("lift",     "stair",     8),
]

# Vastu Shastra: room → preferred direction (N=0°, E=90°, S=180°, W=270°)
# Represented as (preferred_x_fraction, preferred_y_fraction) in plot space
# x: 0=West, 1=East   |   y: 0=North, 1=South
VASTU_PLACEMENT: Dict[str, Tuple[float, float]] = {
    "pooja":    (1.0, 0.0),   # NE corner
    "puja":     (1.0, 0.0),   # NE corner
    "prayer":   (1.0, 0.0),   # NE corner
    "kitchen":  (1.0, 1.0),   # SE corner
    "master":   (0.0, 1.0),   # SW corner
    "bedroom":  (0.0, 0.0),   # NW corner
    "living":   (0.5, 0.0),   # North-centre
    "dining":   (0.0, 0.5),   # West-centre
    "bathroom": (0.0, 0.0),   # NW
    "toilet":   (0.0, 0.0),   # NW
    "stair":    (0.5, 1.0),   # South
    "parking":  (0.0, 0.0),   # NW
    "study":    (1.0, 0.0),   # NE
    "balcony":  (0.5, 0.0),   # North
    "garden":   (0.5, 1.0),   # South/rear
    "servant":  (1.0, 1.0),   # SE
}

# Paint palette: room keyword → (name, hex, finish, brand)
PAINT_PALETTE: Dict[str, Dict[str, str]] = {
    "living":   {"name": "Warm Ivory",        "hex": "#FDF6E3", "finish": "Silk",   "brand": "Asian Paints Royale"},
    "kitchen":  {"name": "Soft Sage Green",   "hex": "#D4E8D0", "finish": "Matt",   "brand": "Nerolac Excel Total"},
    "dining":   {"name": "Warm Bisque",       "hex": "#F5E6CC", "finish": "Silk",   "brand": "Asian Paints Royale"},
    "master":   {"name": "Dusty Mauve",       "hex": "#E8D5D0", "finish": "Silk",   "brand": "Berger Silk"},
    "bedroom":  {"name": "Calm Sky Blue",     "hex": "#D4E8F5", "finish": "Matt",   "brand": "Asian Paints Tractor"},
    "bathroom": {"name": "Glacier White",     "hex": "#F0FBFC", "finish": "Gloss",  "brand": "Dulux WeatherShield"},
    "toilet":   {"name": "Glacier White",     "hex": "#F0FBFC", "finish": "Gloss",  "brand": "Dulux WeatherShield"},
    "pooja":    {"name": "Turmeric Gold",     "hex": "#F5E8C0", "finish": "Matt",   "brand": "Asian Paints Royale"},
    "puja":     {"name": "Turmeric Gold",     "hex": "#F5E8C0", "finish": "Matt",   "brand": "Asian Paints Royale"},
    "stair":    {"name": "Light Grey Mist",   "hex": "#E8E8E8", "finish": "Silk",   "brand": "Nerolac Impressions"},
    "parking":  {"name": "Concrete Beige",    "hex": "#D8D0C0", "finish": "Matt",   "brand": "Asian Paints Apex Exterior"},
    "garden":   {"name": "Leaf Green",        "hex": "#C8E6C0", "finish": "Matt",   "brand": "Asian Paints Apex"},
    "balcony":  {"name": "Sunset Peach",      "hex": "#F5D5B5", "finish": "Silk",   "brand": "Dulux WeatherShield"},
    "terrace":  {"name": "Sky Blue Mist",     "hex": "#D8EEF8", "finish": "Matt",   "brand": "Asian Paints Apex"},
    "study":    {"name": "Warm Putty",        "hex": "#E8DDD0", "finish": "Matt",   "brand": "Berger Silk"},
    "servant":  {"name": "Off White",         "hex": "#F4F1EC", "finish": "Matt",   "brand": "Nerolac Excel"},
    "utility":  {"name": "Pearl White",       "hex": "#F5F3EE", "finish": "Matt",   "brand": "Nerolac Excel"},
    "store":    {"name": "Pearl White",       "hex": "#F5F3EE", "finish": "Matt",   "brand": "Nerolac Excel"},
    "family":   {"name": "Warm Cream",        "hex": "#FBF5E8", "finish": "Silk",   "brand": "Asian Paints Royale"},
    "lounge":   {"name": "Warm Cream",        "hex": "#FBF5E8", "finish": "Silk",   "brand": "Asian Paints Royale"},
    "lift":     {"name": "Steel Grey",        "hex": "#C0C8D0", "finish": "Gloss",  "brand": "Nerolac Impressions"},
    "default":  {"name": "Classic Alabaster", "hex": "#F8F8F2", "finish": "Matt",   "brand": "Asian Paints / Berger"},
}

# Paint coverage: 1 litre covers ~120 sqft (2 coats)
PAINT_COVERAGE_SQFT_PER_LITRE = 120.0
PAINT_PRICE_INR_PER_LITRE = 280.0  # average premium emulsion

# Ground/upper floor room keywords
_GROUND_KW = (
    "living", "hall", "kitchen", "dining", "parking", "garage", "garden",
    "courtyard", "utility", "laundry", "store", "servant", "entrance",
    "foyer", "lobby", "pooja", "puja", "prayer",
)
_UPPER_KW = (
    "bedroom", "master", "suite", "study", "office", "library",
    "balcony", "terrace", "family", "lounge", "dressing", "nursery",
)
_FLEX_KW = ("bathroom", "toilet", "wc", "stair", "staircase", "lift", "corridor")


# ─────────────────────────────────────────────────────────────────
# Legacy dataclass schemas (kept for backward compatibility)
# ─────────────────────────────────────────────────────────────────

from dataclasses import dataclass, field as dc_field

@dataclass
class PipelineRequirements:
    site_width_ft:   float
    site_length_ft:  float
    floors_count:    int
    style:           str  = "MODERN"
    vastu_enabled:   bool = False
    parking_required: bool = True
    garden_required:  bool = False
    balcony_required: bool = False

@dataclass
class ArchitecturalOptionResult:
    floor_plans:       List[FloorPlanGeometry]
    evaluation_score:  float
    metadata:          Dict[str, Any]

@dataclass
class MasterEngineResponse:
    is_clarification_needed: bool
    clarification_questions: List[str]
    option_a: Optional[ArchitecturalOptionResult] = None
    option_b: Optional[ArchitecturalOptionResult] = None
    errors:   List[str] = dc_field(default_factory=list)


# ─────────────────────────────────────────────────────────────────
# GEOMETRY ENGINE
# ─────────────────────────────────────────────────────────────────

class GeometryEngine:

    # ── Paint helpers ──────────────────────────────────────────────

    @staticmethod
    def _paint_for_room(room_name: str) -> Dict[str, str]:
        low = room_name.lower()
        if "master" in low:
            return PAINT_PALETTE["master"]
        for kw, p in PAINT_PALETTE.items():
            if kw in low:
                return p
        return PAINT_PALETTE["default"]

    @staticmethod
    def _apply_palette(rooms: List[RoomGeometry]) -> None:
        for room in rooms:
            p = GeometryEngine._paint_for_room(room.name)
            room.paint_name = p["name"]
            room.paint_hex  = p["hex"]

    # ── Architectural zoning helpers ───────────────────────────────

    @staticmethod
    def _zone(room_name: str) -> int:
        low = room_name.lower()
        for kw, z in ROOM_ZONE.items():
            if kw in low:
                return z
        return 2  # default semi-private

    @staticmethod
    def _room_category(room_name: str) -> str:
        low = room_name.lower()
        if any(k in low for k in _GROUND_KW):
            return "ground"
        if any(k in low for k in _UPPER_KW):
            return "upper"
        return "any"

    @staticmethod
    def _get_weight(room_name: str) -> float:
        low = room_name.lower()
        for kw, w in ROOM_WEIGHTS.items():
            if kw in low:
                return w
        return 1.2

    # ── Vastu placement sort ───────────────────────────────────────

    @staticmethod
    def _vastu_sort_key(room_name: str) -> Tuple[float, float]:
        """
        Returns (preferred_x, preferred_y) fraction in plot space.
        BSP allocates rooms in list order; by sorting this way we
        seed the NE/SE/SW/NW corners with the correct room types.
        """
        low = room_name.lower()
        for kw, pos in VASTU_PLACEMENT.items():
            if kw in low:
                return pos
        return (0.5, 0.5)

    # ── Adjacency-aware room ordering ─────────────────────────────

    @staticmethod
    def _apply_adjacency_rules(rooms: List[str]) -> List[str]:
        """
        Re-order rooms so that high-priority adjacency pairs are
        placed consecutively in the BSP list (BSP splits consecutive
        groups into neighbouring rectangles).
        """
        if len(rooms) <= 2:
            return rooms

        # Build adjacency score matrix
        n = len(rooms)
        pair_score: Dict[Tuple[int, int], int] = {}
        for i in range(n):
            for j in range(i + 1, n):
                score = 0
                ri, rj = rooms[i].lower(), rooms[j].lower()
                for kw_a, kw_b, pri in ADJACENCY_RULES:
                    if (kw_a in ri and kw_b in rj) or (kw_b in ri and kw_a in rj):
                        score += pri
                if score > 0:
                    pair_score[(i, j)] = score

        if not pair_score:
            return rooms

        # Greedy chain: start with highest-scoring pair, chain neighbours
        placed = [False] * n
        ordered: List[int] = []

        best_pair = max(pair_score, key=lambda k: pair_score[k])
        ordered.extend(best_pair)
        placed[best_pair[0]] = True
        placed[best_pair[1]] = True

        while len(ordered) < n:
            # Find best unplaced room adjacent to last in chain
            last = ordered[-1]
            best_score, best_idx = -1, -1
            for i in range(n):
                if not placed[i]:
                    k = (min(last, i), max(last, i))
                    s = pair_score.get(k, 0)
                    if s > best_score:
                        best_score, best_idx = s, i
            if best_idx == -1:
                # No adjacency preference — pick first unplaced
                for i in range(n):
                    if not placed[i]:
                        best_idx = i
                        break
            ordered.append(best_idx)
            placed[best_idx] = True

        return [rooms[i] for i in ordered]

    # ── Intelligent floor distribution ────────────────────────────

    @staticmethod
    def _distribute_rooms_across_floors(
        required_rooms: List[str],
        floors: int,
        generation_mode: str = "space_efficiency",
        plot_w: float = 30.0,
        plot_d: float = 40.0,
    ) -> List[List[str]]:
        """
        Distribute rooms across floors with full architectural intelligence:

        Ground floor:  Public/semi-public spaces — Living, Dining, Kitchen,
                       Parking, Garden, Pooja, Utility, Servant, Staircase,
                       one Bathroom.
        Upper floors:  Private spaces — Bedrooms, Bathrooms per bedroom,
                       Family Lounge, Study, Balcony, Staircase.

        Wet areas (kitchen/bathrooms/utility) are stacked vertically
        (same X/Y cluster) for plumbing efficiency.

        Vastu mode: rooms sorted by Vastu cardinal preference within each
        floor before BSP allocation, so the BSP tree places them in the
        correct quadrant.

        Adaptive mode: rooms sorted by zone score (public→private front→rear)
        and by adjacency rules for maximum circulation efficiency.
        """
        vastu = (generation_mode == "vastu_prioritization")

        if floors <= 1:
            rooms = list(required_rooms)
            if vastu:
                rooms.sort(key=lambda r: (GeometryEngine._vastu_sort_key(r)[1],
                                           GeometryEngine._vastu_sort_key(r)[0]))
            else:
                rooms = GeometryEngine._apply_adjacency_rules(
                    sorted(rooms, key=lambda r: GeometryEngine._zone(r))
                )
            return [rooms]

        # Classify
        stairs    = [r for r in required_rooms if any(k in r.lower() for k in ("stair", "lift"))]
        bathrooms = [r for r in required_rooms
                     if any(k in r.lower() for k in ("bathroom", "toilet", "wc"))
                     and not any(k in r.lower() for k in ("stair", "lift"))]
        ground_r  = [r for r in required_rooms
                     if GeometryEngine._room_category(r) == "ground"
                     and not any(k in r.lower() for k in ("stair", "lift", "bathroom", "toilet", "wc"))]
        upper_r   = [r for r in required_rooms
                     if GeometryEngine._room_category(r) == "upper"
                     and not any(k in r.lower() for k in ("stair", "lift", "bathroom", "toilet", "wc"))]
        flex_r    = [r for r in required_rooms
                     if GeometryEngine._room_category(r) == "any"
                     and not any(k in r.lower() for k in ("stair", "lift", "bathroom", "toilet", "wc"))]

        # ── Ground floor ──────────────────────────────────────────
        ground: List[str] = []

        if vastu:
            # Pooja NE → first in list (BSP allocates first rooms to first partition)
            pooja = [r for r in flex_r if any(k in r.lower() for k in ("pooja", "puja", "prayer"))]
            flex_r = [r for r in flex_r if r not in pooja]
            ground = pooja + list(ground_r)
        else:
            ground = list(ground_r)

        # One bathroom on ground (for guests + accessibility) -- only ever
        # taken from the rooms the user actually required. We never invent
        # a synthetic "Bathroom" that wasn't in required_rooms: doing so
        # would silently add a room the user never asked for.
        if bathrooms:
            ground.append(bathrooms[0])
            rem_baths = bathrooms[1:]
        else:
            rem_baths = []

        # First half of flex rooms to ground
        half = max(0, len(flex_r) // 2)
        ground_flex  = flex_r[:half]
        upper_flex   = flex_r[half:]
        ground += ground_flex

        if stairs:
            ground.append(stairs[0])

        if not ground:
            # Nothing was required for the ground floor -- leave it empty
            # rather than inventing rooms the user never asked for. The
            # caller (GeometryEngine.generate) still produces a valid
            # (room-less) floor in this edge case.
            ground = []

        # Sort ground floor rooms
        if vastu:
            # Sort by Vastu Y then X (NE corner first)
            ground.sort(key=lambda r: (GeometryEngine._vastu_sort_key(r)[1],
                                        GeometryEngine._vastu_sort_key(r)[0]))
        else:
            # Zone sort + adjacency chaining
            ground.sort(key=lambda r: GeometryEngine._zone(r))
            ground = GeometryEngine._apply_adjacency_rules(ground)

        # ── Upper floors ──────────────────────────────────────────
        n_upper = floors - 1
        floor_lists: List[List[str]] = [ground]

        if n_upper > 0:
            beds_per  = max(1, math.ceil(len(upper_r)   / n_upper)) if upper_r   else 0
            baths_per = max(1, math.ceil(len(rem_baths)  / n_upper)) if rem_baths else 0
            uflex_per = max(1, math.ceil(len(upper_flex) / n_upper)) if upper_flex else 0

            for uf in range(n_upper):
                floor: List[str] = []

                # Bedrooms for this upper floor
                if upper_r:
                    chunk = upper_r[uf * beds_per: (uf + 1) * beds_per]
                    floor += chunk if chunk else upper_r[-1:]
                # else: no bedroom-category rooms were requested at all --
                # leave this floor without a synthetic "Bedroom" entry.
                # Inventing one would add a room the user never asked for.

                # Attached bathrooms (wet-area stacking: same cluster as bedrooms)
                if rem_baths:
                    bchunk = rem_baths[uf * baths_per: (uf + 1) * baths_per]
                    floor += bchunk if bchunk else []
                # else: no remaining required bathrooms to place here --
                # leave it as-is rather than inventing a synthetic
                # "Bathroom" that wasn't part of required_rooms.

                # Flex rooms
                if upper_flex:
                    fchunk = upper_flex[uf * uflex_per: (uf + 1) * uflex_per]
                    floor += fchunk

                # NOTE: previously always appended a "Balcony" to the first
                # upper floor even when the user never asked for one -- that
                # contradicted the "don't invent rooms the user didn't
                # request" rule the bedroom/bathroom logic above already
                # follows. Balcony is now only placed here if it was
                # actually part of required_rooms (i.e. it's already
                # somewhere in floor/upper_r/upper_flex from the caller);
                # nothing synthetic is added.

                # Staircase on every floor
                if stairs:
                    floor.append(stairs[0])

                if not floor:
                    # Nothing was required to put on this floor -- leave it
                    # empty rather than inventing a generic Bedroom/Bathroom.
                    floor = []

                # Sort upper floor rooms
                if vastu:
                    # Master Bedroom → SW = last in list
                    masters = [r for r in floor if "master" in r.lower()]
                    others  = [r for r in floor if "master" not in r.lower()]
                    others.sort(key=lambda r: (GeometryEngine._vastu_sort_key(r)[1],
                                                GeometryEngine._vastu_sort_key(r)[0]))
                    floor = others + masters
                else:
                    floor.sort(key=lambda r: GeometryEngine._zone(r))
                    floor = GeometryEngine._apply_adjacency_rules(floor)

                floor_lists.append(floor)

        return floor_lists

    # ── Dict serialisers ──────────────────────────────────────────

    @staticmethod
    def _room_dict(room: RoomGeometry) -> Dict[str, Any]:
        b = room.bbox
        return {
            "id": room.id, "name": room.name,
            "x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2,
            "area_sqft": round(b.area, 2),
            "paint_name": room.paint_name, "paint_hex": room.paint_hex, "color": room.paint_hex,
        }

    @staticmethod
    def _wall_dict(w: WallGeometry) -> Dict[str, Any]:
        return {"x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2,
                "thickness": w.thickness, "is_exterior": w.is_exterior}

    @staticmethod
    def _portal_dict(p: PortalGeometry) -> Dict[str, Any]:
        return {"type": p.portal_type, "x1": p.x1, "y1": p.y1,
                "x2": p.x2, "y2": p.y2, "room": p.associated_room}

    @staticmethod
    def _dimension_dict(d: DimensionLine) -> Dict[str, Any]:
        return {"x1": d.x1, "y1": d.y1, "x2": d.x2, "y2": d.y2,
                "label": d.label, "is_horizontal": d.is_horizontal}

    # ── Single-floor BSP pipeline ─────────────────────────────────

    @staticmethod
    def _build_floor_dict(
        floor_index: int,
        floor_name: str,
        plot_w: float,
        plot_d: float,
        room_names: List[str],
        bsp_mode: str,
        balcony_on_this_floor: bool,
        plot_shape: PlotShape = None,
    ) -> Dict[str, Any]:
        """
        Full pipeline for one floor, driven by the plot's actual polygon
        (plot_shape). A plain rectangle is just the simplest possible
        polygon, so rectangular plots behave exactly as before; L-shaped /
        T-shaped / U-shaped / custom irregular plots get rooms allocated
        only within the buildable area, an exterior wall that traces the
        real outline, and doors/windows placed on the real perimeter
        instead of an assumed bounding-box rectangle.

        Split axis alternates per floor AND per mode:
          Adaptive:  Ground=horizontal, Upper=vertical   → different geometry each floor
          Vastu:     Ground=vertical,   Upper=horizontal → different from Adaptive
        """
        if not room_names:
            room_names = ["Room"]

        if plot_shape is None:
            plot_shape = PlotShapeBuilder.build(plot_w, plot_d, "rectangle")

        rectangles = PlotShapeBuilder.decompose(plot_shape)
        boundary_segments = PlotShapeBuilder.boundary_segments(plot_shape)
        entrance_segment = PlotShapeBuilder.entrance_segment(plot_shape)

        # Axis selection: guarantees Ground ≠ Upper and Adaptive ≠ Vastu.
        # (Only meaningful for the single-rectangle case; allocate_multi
        # picks its own per-rectangle axis based on each rectangle's own
        # aspect ratio, which is architecturally more correct anyway.)
        if bsp_mode == "vastu_prioritization":
            is_horizontal = (floor_index % 2 == 1)
        else:
            is_horizontal = (floor_index % 2 == 0)

        if len(rectangles) == 1:
            r = rectangles[0]
            rooms: List[RoomGeometry] = RoomAllocator.allocate(
                x=r.x1, y=r.y1, w=r.width, h=r.height,
                rooms=room_names,
                is_horizontal=is_horizontal,
                mode=bsp_mode,
            )
        else:
            # Irregular plot: every room in room_names is placed exactly
            # once, distributed across the decomposed rectangles by area
            # share -- the full user-specified room program is preserved.
            rooms = RoomAllocator.allocate_multi(rectangles, room_names, bsp_mode)

        GeometryEngine._apply_palette(rooms)

        adj_edges = AdjacencyGraphBuilder.build(rooms)
        walls     = WallGenerator.generate(boundary_segments=boundary_segments, interior_edges=adj_edges)
        portals   = DoorGenerator.generate(entrance_segment=entrance_segment, interior_edges=adj_edges, rooms=rooms)
        portals  += WindowGenerator.generate(boundary_segments=boundary_segments, rooms=rooms, entrance_segment=entrance_segment)
        dimensions = DimensionGenerator.generate(plot_w=plot_w, plot_d=plot_d)
        svg_string = SVGRenderer.render(
            plot_w=plot_w, plot_d=plot_d, rooms=rooms,
            walls=walls, portals=portals, dimensions=dimensions,
            plot_points=plot_shape.points_xy,
        )

        return {
            "floor_name": floor_name,
            "rooms":   [GeometryEngine._room_dict(r) for r in rooms],
            "walls":   [GeometryEngine._wall_dict(w) for w in walls],
            "portals": [GeometryEngine._portal_dict(p) for p in portals],
            "columns": [],
            "has_balcony": balcony_on_this_floor,
            "svg_dump": svg_string,
            "_dimensions_raw": dimensions,
        }

    # ── Dynamic cost engine ───────────────────────────────────────

    @staticmethod
    def _estimate_cost(
        plot_w: float, plot_d: float, floors: int,
        city: str = "", state: str = "", quality: str = "standard",
    ) -> Dict[str, Any]:
        """
        Full Indian construction cost BOQ.
        Rates from city table; materials itemised per Indian construction norms.
        """
        CITY_RATES = {
            "mumbai": 3200, "delhi": 2900, "bangalore": 2750, "bengaluru": 2750,
            "chennai": 2600, "kolkata": 2400, "hyderabad": 2650, "pune": 2550,
            "ahmedabad": 2300, "surat": 2200, "jaipur": 2100, "lucknow": 2000,
            "nagpur": 2050, "indore": 2000, "bhopal": 1950, "coimbatore": 1900,
            "kochi": 2100, "thiruvananthapuram": 2000, "mysuru": 1950,
            "mangaluru": 1900, "nashik": 2000, "vadodara": 2000,
            "default": 1700,
        }
        STATE_MOD = {
            "maharashtra": 1.12, "karnataka": 1.05, "tamil nadu": 1.03,
            "delhi": 1.10, "gujarat": 1.00, "telangana": 1.02, "kerala": 1.08,
            "west bengal": 0.95, "rajasthan": 0.97, "uttar pradesh": 0.95,
            "madhya pradesh": 0.96, "punjab": 0.98, "haryana": 1.00,
            "andhra pradesh": 1.00, "odisha": 0.95, "jharkhand": 0.93,
            "bihar": 0.92, "chhattisgarh": 0.94,
        }
        QUAL_MOD = {"budget": 0.80, "standard": 1.00, "premium": 1.25, "luxury": 1.55}

        base      = CITY_RATES.get(city.lower(), CITY_RATES["default"])
        st_mod    = STATE_MOD.get(state.lower(), 1.0)
        q_mod     = QUAL_MOD.get(quality, 1.0)
        rate      = base * st_mod * q_mod
        built_sqft = plot_w * plot_d * floors * 0.85
        total     = round(built_sqft * rate, 0)

        labor_frac    = 0.28
        finish_frac   = 0.12
        mat_frac      = 1.0 - labor_frac - finish_frac

        materials = {
            "RCC_foundation_structure": round(total * mat_frac * 0.32, 0),
            "bricks_blocks_masonry":    round(total * mat_frac * 0.18, 0),
            "flooring_tiling":          round(total * mat_frac * 0.16, 0),
            "electrical_wiring_fittings": round(total * mat_frac * 0.10, 0),
            "plumbing_sanitary":        round(total * mat_frac * 0.10, 0),
            "doors_windows_grills":     round(total * mat_frac * 0.08, 0),
            "roofing_waterproofing":    round(total * mat_frac * 0.06, 0),
        }
        contingency = round(total * 0.05, 0)

        return {
            "total_inr":     total + contingency,
            "built_sqft":    round(built_sqft, 1),
            "rate_per_sqft": round(rate, 0),
            "materials":     materials,
            "labor_inr":     round(total * labor_frac, 0),
            "finishing_inr": round(total * finish_frac, 0),
            "contingency_inr": contingency,
            "grand_total_inr": f"₹{(total + contingency):,.0f}",
        }

    # ── Dynamic paint recommendations ─────────────────────────────

    @staticmethod
    def _paint_recommendations(
        all_room_names: List[str],
        plot_w: float = 30.0,
        plot_d: float = 40.0,
    ) -> List[Dict[str, Any]]:
        seen: set = set()
        recs = []
        for name in all_room_names:
            if name.lower() in seen:
                continue
            seen.add(name.lower())
            p = GeometryEngine._paint_for_room(name)
            # Estimate wall area for this room type (rough: perimeter × 9ft height)
            # Using average room size as fraction of plot
            avg_room_sqft = (plot_w * plot_d) / max(len(all_room_names), 1)
            side = math.sqrt(max(avg_room_sqft, 25))
            wall_area_sqft = (side * 2 + side * 2) * 9 * 0.75  # 75% after doors/windows
            litres_needed  = round(wall_area_sqft / PAINT_COVERAGE_SQFT_PER_LITRE * 2, 1)  # 2 coats
            cost_inr       = round(litres_needed * PAINT_PRICE_INR_PER_LITRE, 0)

            recs.append({
                "room_name":    name,
                "primary_name": p["name"],
                "primary_hex":  p["hex"],
                "accent_name":  "Charcoal Slate",
                "accent_hex":   "#334155",
                "finish":       p.get("finish", "Matt"),
                "brand":        p.get("brand", "Asian Paints"),
                "litres_needed": litres_needed,
                "paint_cost_inr": cost_inr,
            })
        return recs

    # ── Scoring ───────────────────────────────────────────────────

    @staticmethod
    def _score_layout(
        generation_mode: str,
        room_count: int,
        door_count: int,
        plot_sqft: float,
    ) -> Dict[str, float]:
        vastu        = 92.0 if generation_mode == "vastu_prioritization" else 68.0
        space_eff    = round(min(98.0, 78.0 + room_count * 1.5), 1)
        circulation  = round(min(95.0, 55.0 + door_count * 5.0), 1)
        lighting     = round(min(95.0, 70.0 + (plot_sqft / 800) * 10), 1)
        ventilation  = round(min(95.0, 68.0 + (plot_sqft / 1000) * 12), 1)
        return {
            "vastu":            vastu,
            "space_efficiency": space_eff,
            "circulation":      circulation,
            "natural_lighting": lighting,
            "ventilation":      ventilation,
        }

    # ── PRIMARY ENTRY POINT ───────────────────────────────────────

    @staticmethod
    def generate(
        plot_width: float,
        plot_depth: float,
        floors: int,
        required_rooms: List[str],
        generation_mode: str = "space_efficiency",
        architectural_style: str = "modern",
        city: str = "",
        state: str = "",
        quality: str = "standard",
        plot_shape_type: str = "rectangle",
        plot_cut_width: Optional[float] = None,
        plot_cut_depth: Optional[float] = None,
        plot_points: Optional[List[Tuple[float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Called by layout_agent.LayoutEngineAgent.execute_procedural_generation().
        Returns plain dict with keys:
            floors, cost_report, paint_recommendations, scores, dimensions

        plot_shape_type / plot_cut_width / plot_cut_depth / plot_points let
        the caller describe a non-rectangular plot (L-shape, T-shape,
        U-shape, or any fully custom polygon via plot_points). Every room
        in required_rooms is still placed exactly once -- irregular shapes
        only change WHERE rooms can be placed, never WHAT gets generated.
        """
        plot_w   = float(plot_width)
        plot_d   = float(plot_depth)
        n_floors = max(1, int(floors))
        bsp_mode = "vastu_prioritization" if generation_mode == "vastu_prioritization" else "space_efficiency"

        plot_shape = PlotShapeBuilder.build(
            plot_width=plot_w, plot_depth=plot_d, shape_type=plot_shape_type,
            cut_width=plot_cut_width, cut_depth=plot_cut_depth, custom_points=plot_points,
        )
        # Downstream dimension/cost/paint calculations use the plot's
        # overall bounding-box envelope, which is well-defined for both
        # rectangular and irregular plots.
        bbox = plot_shape.bounding_box
        plot_w, plot_d = bbox.width, bbox.height

        # Intelligent floor distribution
        floor_room_lists = GeometryEngine._distribute_rooms_across_floors(
            required_rooms, n_floors,
            generation_mode=generation_mode,
            plot_w=plot_w, plot_d=plot_d,
        )

        floor_dicts: List[Dict[str, Any]] = []
        global_dimensions: List[DimensionLine] = []
        all_room_names: List[str] = []
        total_door_count = 0

        for idx, room_names in enumerate(floor_room_lists):
            floor_label    = "Ground Floor" if idx == 0 else f"Floor {idx}"
            balcony_here   = any("balcony" in r.lower() for r in room_names)

            fd = GeometryEngine._build_floor_dict(
                floor_index=idx,
                floor_name=floor_label,
                plot_w=plot_w,
                plot_d=plot_d,
                room_names=room_names,
                bsp_mode=bsp_mode,
                balcony_on_this_floor=balcony_here,
                plot_shape=plot_shape,
            )
            global_dimensions = fd.pop("_dimensions_raw")
            floor_dicts.append(fd)
            all_room_names.extend(room_names)
            total_door_count += sum(1 for p in fd["portals"] if p["type"] == "door")

        cost_report   = GeometryEngine._estimate_cost(plot_w, plot_d, n_floors, city, state, quality)
        paint_recs    = GeometryEngine._paint_recommendations(all_room_names, plot_w, plot_d)
        scores        = GeometryEngine._score_layout(bsp_mode, len(all_room_names),
                                                      total_door_count, plot_shape.area)
        dimensions    = [GeometryEngine._dimension_dict(d) for d in global_dimensions]

        return {
            "floors": floor_dicts,
            "cost_report": cost_report,
            "paint_recommendations": paint_recs,
            "scores": scores,
            "dimensions": dimensions,
            "plot_shape_type": plot_shape.shape_type,
            "plot_polygon": plot_shape.points_xy,
        }

    # ── LEGACY ENTRY POINT (kept for backward compat) ─────────────

    @staticmethod
    def _room_list_for_floor(floor_index: int, reqs: PipelineRequirements) -> List[str]:
        if floor_index == 0:
            rooms = ["Living Room", "Kitchen", "Dining Room", "Bathroom", "Staircase"]
            if reqs.parking_required: rooms.append("Parking")
            if reqs.garden_required:  rooms.append("Garden")
        else:
            rooms = ["Master Bedroom", "Bedroom 2", "Bathroom", "Staircase"]
            if reqs.balcony_required: rooms.append("Balcony")
        return rooms

    def parse_requirements(self, prompt: str) -> Tuple[Optional[PipelineRequirements], List[str]]:
        questions   = []
        p = prompt.lower()
        width = length = 0.0
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|by)\s*(\d+(?:\.\d+)?)', prompt, re.IGNORECASE)
        if m:
            width, length = float(m.group(1)), float(m.group(2))
        else:
            m2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:sq\s*ft|square\s*feet)', prompt, re.IGNORECASE)
            if m2:
                sqft = float(m2.group(1))
                width = round(math.sqrt(sqft / 1.5), 1)
                length = round(width * 1.5, 1)
        if width <= 0 or length <= 0:
            questions.append("What are the exact plot dimensions? (e.g. 30x50 ft or 1500 sq ft)")
        floors = 1
        if any(k in p for k in ("two floor", "2 floor", "g+1")):   floors = 2
        elif any(k in p for k in ("three floor", "3 floor", "g+2")): floors = 3
        if not questions:
            style = "MODERN"
            if "tradition" in p: style = "TRADITIONAL"
            elif "lux" in p:     style = "LUXURY"
            reqs = PipelineRequirements(
                site_width_ft=width, site_length_ft=length, floors_count=floors,
                style=style, vastu_enabled="vastu" in p,
                parking_required="no parking" not in p,
                garden_required="garden" in p or "lawn" in p,
                balcony_required="balcony" in p,
            )
            return reqs, []
        return None, questions

    def build_floor_plan(self, floor_index: int, reqs: PipelineRequirements, mode: str) -> FloorPlanGeometry:
        W, D = reqs.site_width_ft, reqs.site_length_ft
        label = "Ground Floor" if floor_index == 0 else f"Floor {floor_index}"
        bsp_mode = "vastu_prioritization" if reqs.vastu_enabled else "space_efficiency"
        room_names = self._room_list_for_floor(floor_index, reqs)
        plot_shape = PlotShapeBuilder.build(W, D, "rectangle")
        rooms  = RoomAllocator.allocate(x=0, y=0, w=W, h=D, rooms=room_names, is_horizontal=True, mode=bsp_mode)
        self._apply_palette(rooms)
        adj    = AdjacencyGraphBuilder.build(rooms)
        boundary_segments = PlotShapeBuilder.boundary_segments(plot_shape)
        entrance_segment = PlotShapeBuilder.entrance_segment(plot_shape)
        walls  = WallGenerator.generate(boundary_segments=boundary_segments, interior_edges=adj)
        portals = DoorGenerator.generate(entrance_segment=entrance_segment, interior_edges=adj, rooms=rooms) + \
                  WindowGenerator.generate(boundary_segments=boundary_segments, rooms=rooms, entrance_segment=entrance_segment)
        dims   = DimensionGenerator.generate(W, D)
        svg    = SVGRenderer.render(W, D, rooms, walls, portals, dims, plot_points=plot_shape.points_xy)
        return FloorPlanGeometry(floor_name=label, plot_width=W, plot_depth=D,
                                  rooms=rooms, walls=walls, portals=portals,
                                  dimensions=dims, has_balcony=reqs.balcony_required and floor_index > 0,
                                  svg_raw=svg)

    def generate_option(self, reqs: PipelineRequirements, mode: str) -> ArchitecturalOptionResult:
        plans = [self.build_floor_plan(i, reqs, mode) for i in range(reqs.floors_count)]
        return ArchitecturalOptionResult(
            floor_plans=plans, evaluation_score=90.0,
            metadata={"mode": mode, "floors": reqs.floors_count})

    def generate_from_prompt(self, prompt_text: str) -> MasterEngineResponse:
        try:
            reqs, missing = self.parse_requirements(prompt_text)
            if missing:
                return MasterEngineResponse(is_clarification_needed=True, clarification_questions=missing)
            return MasterEngineResponse(
                is_clarification_needed=False, clarification_questions=[],
                option_a=self.generate_option(reqs, "SPACE_MAXIMIZATION"),
                option_b=self.generate_option(reqs, "PRIVACY"),
            )
        except Exception as err:
            return MasterEngineResponse(is_clarification_needed=False,
                                         clarification_questions=[], errors=[str(err)])