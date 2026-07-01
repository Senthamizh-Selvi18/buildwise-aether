import re
import math
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict

# ─────────────────────────────────────────────────────────────────
# Core module imports — all using the CORRECT path and class names
# ─────────────────────────────────────────────────────────────────
from backend.app.core.geometry.models import (
    RoomGeometry, BoundingBox, AdjacencyEdge,
    WallGeometry, PortalGeometry, DimensionLine, FloorPlanGeometry
)
from backend.app.core.geometry.adjacency_graph import AdjacencyGraphBuilder
from backend.app.core.geometry.room_allocator import RoomAllocator
from backend.app.core.geometry.wall_generator import WallGenerator
from backend.app.core.geometry.door_generator import DoorGenerator
from backend.app.core.geometry.window_generator import WindowGenerator
from backend.app.core.geometry.dimension_generator import DimensionGenerator
from backend.app.core.geometry.svg_renderer import SVGRenderer


# ─────────────────────────────────────────────────────────────────
# Room programmes per floor (used only by the legacy prompt-based
# entry point, generate_from_prompt — kept for backward compatibility)
# ─────────────────────────────────────────────────────────────────

GROUND_FLOOR_ROOMS_BASE = ["Living Room", "Kitchen", "Dining Room", "Bathroom", "Staircase"]
GROUND_FLOOR_PARKING    = ["Parking"]
GROUND_FLOOR_GARDEN     = ["Garden / Courtyard"]

UPPER_FLOOR_ROOMS_BASE  = ["Master Bedroom", "Bedroom 2", "Bathroom", "Staircase"]
UPPER_FLOOR_BALCONY     = ["Balcony"]

# Paint palette keyed by room name keyword (applied after allocation)
ROOM_PALETTE: Dict[str, Tuple[str, str]] = {
    "living":   ("Warm Sand",       "#f5e6d3"),
    "kitchen":  ("Soft Sage",       "#d4e8d0"),
    "dining":   ("Cream White",     "#faf7f0"),
    "master":   ("Dusty Rose",      "#f0ddd8"),
    "bedroom":  ("Sky Blue",        "#d8eaf5"),
    "bathroom": ("Mint Fresh",      "#d4f0e8"),
    "toilet":   ("Mint Fresh",      "#d4f0e8"),
    "stair":    ("Light Grey",      "#e8e8e8"),
    "parking":  ("Concrete Beige",  "#e5e0d8"),
    "garden":   ("Leaf Green",      "#c8e6c0"),
    "balcony":  ("Terracotta",      "#f0d8c8"),
    "pooja":    ("Turmeric Gold",   "#f5e8c0"),
    "puja":     ("Turmeric Gold",   "#f5e8c0"),
}

DEFAULT_PAINT = ("Classic Alabaster", "#f8f8f8")

# Deterministic cost model constants (INR)
COST_PER_SQFT_BASE = 1850.0
LABOR_FRACTION      = 0.30
FINISHING_FRACTION  = 0.15
MATERIAL_FRACTION   = 1.0 - LABOR_FRACTION - FINISHING_FRACTION
MATERIAL_SPLIT = {
    "cement_steel": 0.45,
    "bricks_blocks": 0.20,
    "flooring": 0.20,
    "electrical_plumbing": 0.15,
}


# ─────────────────────────────────────────────────────────────────
# Input / Output schemas (legacy prompt-based entry point only)
# ─────────────────────────────────────────────────────────────────

@dataclass
class PipelineRequirements:
    """Structured, validated requirements extracted from a free-text user prompt."""
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
    """Full output for one layout variant (Space-Optimised or Privacy-Optimised)."""
    floor_plans:       List[FloorPlanGeometry]   # One entry per floor
    evaluation_score:  float
    metadata:          Dict[str, Any]


@dataclass
class MasterEngineResponse:
    """Root response wrapper: either clarification questions or two layout options."""
    is_clarification_needed:  bool
    clarification_questions:  List[str]
    option_a: Optional[ArchitecturalOptionResult] = None  # Space-Optimised
    option_b: Optional[ArchitecturalOptionResult] = None  # Privacy-Optimised
    errors:   List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


# ─────────────────────────────────────────────────────────────────
# Master Orchestrator
# ─────────────────────────────────────────────────────────────────

class GeometryEngine:
    """
    Master pipeline orchestrator for the BuildWise Aether Geometry Engine.

    Deterministic BSP pipeline (per floor):
        User Input → BSP Room Split (RoomAllocator) → Adjacency Graph
        → Wall Generation → Door Generation → Window Generation
        → Dimension Lines → SVG Render

    Two entry points are exposed:

      1. GeometryEngine.generate(plot_width=, plot_depth=, floors=,
         required_rooms=, generation_mode=, architectural_style=)
         — a @staticmethod returning a plain dict. This is the contract
         layout_agent.execute_procedural_generation() actually calls.
         Dynamic: room list comes directly from the caller (user input),
         not from a hardcoded template.

      2. GeometryEngine().generate_from_prompt(prompt_text)
         — legacy instance method, parses a free-text prompt into
         PipelineRequirements and returns dataclasses. Kept for backward
         compatibility with any other caller that still expects this
         shape; not used by the live /api/generate pipeline.
    """

    # ── helpers shared by both entry points ─────────────────────

    @staticmethod
    def _paint_for_room(room_name: str) -> Tuple[str, str]:
        name_lower = room_name.lower()
        for keyword, (paint_name, paint_hex) in ROOM_PALETTE.items():
            if keyword in name_lower:
                return paint_name, paint_hex
        return DEFAULT_PAINT

    @staticmethod
    def _apply_palette(rooms: List[RoomGeometry]) -> None:
        """Apply paint colours in-place based on each room's name."""
        for room in rooms:
            paint_name, paint_hex = GeometryEngine._paint_for_room(room.name)
            room.paint_name = paint_name
            room.paint_hex  = paint_hex

    @staticmethod
    def _room_list_for_floor(floor_index: int, reqs: "PipelineRequirements") -> List[str]:
        """Legacy template room list — used only by generate_from_prompt()."""
        if floor_index == 0:
            rooms = list(GROUND_FLOOR_ROOMS_BASE)
            if reqs.parking_required:
                rooms += GROUND_FLOOR_PARKING
            if reqs.garden_required:
                rooms += GROUND_FLOOR_GARDEN
        else:
            rooms = list(UPPER_FLOOR_ROOMS_BASE)
            if reqs.balcony_required:
                rooms += UPPER_FLOOR_BALCONY
        return rooms

    # ── Room semantic classification ──────────────────────────────

    # Keywords that strongly belong on the ground floor (social/service)
    _GROUND_KEYWORDS = (
        "living", "kitchen", "dining", "parking", "garden", "courtyard",
        "garage", "store", "utility", "entrance", "foyer", "lobby",
        "laundry", "servant",
    )
    # Keywords that strongly belong on upper floors (private/sleeping)
    _UPPER_KEYWORDS = (
        "bedroom", "master", "suite", "study", "family lounge",
        "balcony", "terrace", "nursery", "office", "dressing",
    )
    # Vastu directional room placement (room keyword → preferred quadrant)
    # quadrant: "NE", "SE", "SW", "NW", "N", "S", "E", "W", "centre"
    _VASTU_DIRECTION: Dict[str, str] = {
        "pooja": "NE", "puja": "NE", "prayer": "NE",
        "kitchen": "SE",
        "master": "SW",
        "bedroom": "NW",
        "living": "N",
        "dining": "W",
        "bathroom": "NW", "toilet": "NW",
        "stair": "S",
        "parking": "NW",
        "study": "NE",
        "balcony": "N",
    }

    @staticmethod
    def _room_category(room_name: str) -> str:
        """Return 'ground', 'upper', or 'any' for a given room name."""
        low = room_name.lower()
        if any(k in low for k in GeometryEngine._GROUND_KEYWORDS):
            return "ground"
        if any(k in low for k in GeometryEngine._UPPER_KEYWORDS):
            return "upper"
        # Bathrooms/stairs/pooja → flexible
        return "any"

    @staticmethod
    def _vastu_sort_key(room_name: str) -> int:
        """
        Return an integer order for Vastu-compliant room sequencing
        within a BSP split. Lower = allocated first (NE corner tendency).
        Order encodes: NE(0) → SE(1) → SW(2) → NW(3) → centre(4)
        """
        low = room_name.lower()
        order = {"NE": 0, "SE": 1, "SW": 2, "NW": 3, "N": 0, "S": 2, "E": 1, "W": 3, "centre": 4}
        for kw, direction in GeometryEngine._VASTU_DIRECTION.items():
            if kw in low:
                return order.get(direction, 4)
        return 4

    @staticmethod
    def _distribute_rooms_across_floors(
        required_rooms: List[str],
        floors: int,
        generation_mode: str = "space_efficiency",
    ) -> List[List[str]]:
        """
        Intelligently distribute rooms across floors using architectural
        conventions. Each floor gets a distinct, realistic programme.

        Ground floor priority: Living, Dining, Kitchen, Parking, Garden,
                               Pooja (Vastu: NE corner), one Bathroom, Staircase.
        Upper floor priority:  Bedrooms, Bathrooms, Balcony, Study, Staircase.
        Flexible (any floor):  Bathrooms beyond ground, Staircase (repeated).

        Vastu mode:
          - Pooja Room → ground floor first position (NE corner BSP seed).
          - Master Bedroom → last upper floor, last position (SW corner).
          - Room ordering within each floor follows Vastu direction sort key.
          - Upper floors split vertically (N-S axis) vs Adaptive horizontal.
        """
        if floors <= 1:
            rooms = list(required_rooms) or ["Living Room"]
            if generation_mode == "vastu_prioritization":
                rooms.sort(key=GeometryEngine._vastu_sort_key)
            return [rooms]

        vastu = (generation_mode == "vastu_prioritization")

        # Separate by category
        stairs    = [r for r in required_rooms if "stair" in r.lower()]
        bathrooms = [r for r in required_rooms
                     if any(k in r.lower() for k in ("bathroom", "toilet", "wc"))
                     and "stair" not in r.lower()]
        ground_rooms = [r for r in required_rooms
                        if GeometryEngine._room_category(r) == "ground"
                        and "stair" not in r.lower()
                        and not any(k in r.lower() for k in ("bathroom", "toilet", "wc"))]
        upper_rooms  = [r for r in required_rooms
                        if GeometryEngine._room_category(r) == "upper"
                        and "stair" not in r.lower()
                        and not any(k in r.lower() for k in ("bathroom", "toilet", "wc"))]
        flex_rooms   = [r for r in required_rooms
                        if GeometryEngine._room_category(r) == "any"
                        and "stair" not in r.lower()
                        and not any(k in r.lower() for k in ("bathroom", "toilet", "wc"))]

        # ── Build ground floor ─────────────────────────────────────
        ground: List[str] = []

        if vastu:
            # Pooja Room goes to NE corner — put it first so BSP allocates it there
            pooja = [r for r in flex_rooms if any(k in r.lower() for k in ("pooja", "puja", "prayer"))]
            flex_rooms = [r for r in flex_rooms if r not in pooja]
            ground = pooja + list(ground_rooms)
        else:
            ground = list(ground_rooms)

        # One bathroom always on ground
        if bathrooms:
            ground.append(bathrooms[0])
            remaining_baths = bathrooms[1:]
        else:
            ground.append("Bathroom")
            remaining_baths = []

        # Flex rooms split: first half to ground
        half = max(0, len(flex_rooms) // 2)
        ground += flex_rooms[:half]
        upper_flex = flex_rooms[half:]

        # Staircase on every floor
        if stairs:
            ground.append(stairs[0])

        if not ground:
            ground = ["Living Room", "Kitchen", "Bathroom"]

        # ── Build upper floors ─────────────────────────────────────
        n_upper = floors - 1
        floor_lists: List[List[str]] = [ground]

        if n_upper > 0:
            # Distribute bedrooms across upper floors
            beds_per = max(1, math.ceil(len(upper_rooms) / n_upper)) if upper_rooms else 0
            # Distribute remaining bathrooms
            baths_per = max(1, math.ceil(len(remaining_baths) / n_upper)) if remaining_baths else 0
            # Flex rooms for upper
            uflex_per = max(1, math.ceil(len(upper_flex) / n_upper)) if upper_flex else 0

            for uf in range(n_upper):
                floor: List[str] = []

                # Bedrooms
                if upper_rooms:
                    chunk = upper_rooms[uf * beds_per: (uf + 1) * beds_per]
                    floor += chunk if chunk else upper_rooms[-1:]
                else:
                    floor.append("Bedroom" if uf == 0 else f"Bedroom {uf + 2}")

                # Bathrooms for this upper floor
                if remaining_baths:
                    bchunk = remaining_baths[uf * baths_per: (uf + 1) * baths_per]
                    floor += bchunk if bchunk else []
                else:
                    floor.append("Bathroom")

                # Flex rooms
                if upper_flex:
                    fchunk = upper_flex[uf * uflex_per: (uf + 1) * uflex_per]
                    floor += fchunk

                # Balcony on first upper floor (if not already there)
                if uf == 0 and not any("balcony" in r.lower() for r in floor):
                    floor.append("Balcony")

                # Staircase circulation
                if stairs:
                    floor.append(stairs[0])

                if not floor:
                    floor = ["Bedroom", "Bathroom"]

                # Vastu: sort rooms by directional priority within floor
                if vastu:
                    # Master Bedroom → SW → goes last (highest sort key among bedrooms)
                    master = [r for r in floor if "master" in r.lower()]
                    others = [r for r in floor if "master" not in r.lower()]
                    others.sort(key=GeometryEngine._vastu_sort_key)
                    floor = others + master  # master last = SW corner in BSP

                floor_lists.append(floor)

        return floor_lists

    @staticmethod
    def _room_dict(room: RoomGeometry) -> Dict[str, Any]:
        b = room.bbox
        return {
            "id": room.id,
            "name": room.name,
            "bbox": {"x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2},
            "area_sqft": round(b.area, 2),
            "paint_name": room.paint_name,
            "paint_hex": room.paint_hex,
        }

    @staticmethod
    def _wall_dict(wall: WallGeometry) -> Dict[str, Any]:
        return {
            "x1": wall.x1, "y1": wall.y1, "x2": wall.x2, "y2": wall.y2,
            "thickness": wall.thickness, "is_exterior": wall.is_exterior,
        }

    @staticmethod
    def _portal_dict(portal: PortalGeometry) -> Dict[str, Any]:
        return {
            "type": portal.portal_type,
            "x1": portal.x1, "y1": portal.y1, "x2": portal.x2, "y2": portal.y2,
            "room": portal.associated_room,
        }

    @staticmethod
    def _dimension_dict(dim: DimensionLine) -> Dict[str, Any]:
        return {
            "x1": dim.x1, "y1": dim.y1, "x2": dim.x2, "y2": dim.y2,
            "label": dim.label, "is_horizontal": dim.is_horizontal,
        }

    # ── deterministic single-floor BSP pipeline (dict contract) ───

    @staticmethod
    def _build_floor_dict(
        floor_index: int,
        floor_name: str,
        plot_w: float,
        plot_d: float,
        room_names: List[str],
        bsp_mode: str,
        balcony_on_this_floor: bool,
    ) -> Dict[str, Any]:
        """
        Runs the full deterministic BSP pipeline for one floor and returns a
        plain dict shaped exactly as layout_agent._build_floor_plan() expects.

        Stage 1 — BSP room split      (RoomAllocator)
        Stage 2 — Adjacency graph     (AdjacencyGraphBuilder)
        Stage 3 — Wall generation     (WallGenerator) — exterior + interior
        Stage 4 — Door generation     (DoorGenerator) — entrance + interior doors
        Stage 5 — Window generation   (WindowGenerator) — exterior walls only
        Stage 6 — Dimension lines     (DimensionGenerator)
        Stage 7 — SVG render          (SVGRenderer)
        """
        if not room_names:
            room_names = ["Room"]

        # ── Stage 1: BSP allocation ──────────────────────────────────
        # Alternate split axis per floor so each floor has a distinct layout:
        #   Adaptive:  Ground → horizontal (rooms left/right)
        #              Upper  → vertical   (rooms front/back)
        #   Vastu:     Ground → vertical   (N-S axis for directional placement)
        #              Upper  → horizontal (E-W axis)
        # This guarantees Ground ≠ Upper visually, and Adaptive ≠ Vastu.
        if bsp_mode == "vastu_prioritization":
            is_horizontal = (floor_index % 2 == 1)   # Ground=vertical, upper=horizontal
        else:
            is_horizontal = (floor_index % 2 == 0)   # Ground=horizontal, upper=vertical

        rooms: List[RoomGeometry] = RoomAllocator.allocate(
            x=0, y=0, w=plot_w, h=plot_d,
            rooms=room_names,
            is_horizontal=is_horizontal,
            mode=bsp_mode,
        )
        GeometryEngine._apply_palette(rooms)

        # ── Stage 2: Adjacency graph (connected rooms) ───────────────
        adj_edges: List[AdjacencyEdge] = AdjacencyGraphBuilder.build(rooms)

        # ── Stage 3: Walls — exterior shell + interior partitions ────
        walls: List[WallGeometry] = WallGenerator.generate(
            plot_w=plot_w,
            plot_d=plot_d,
            interior_edges=adj_edges,
        )

        # ── Stage 4: Doors — entrance + adjacency-driven interior doors
        portals: List[PortalGeometry] = DoorGenerator.generate(
            plot_w=plot_w,
            plot_d=plot_d,
            interior_edges=adj_edges,
        )

        # ── Stage 5: Windows — exterior walls only ───────────────────
        portals += WindowGenerator.generate(
            plot_w=plot_w,
            plot_d=plot_d,
            rooms=rooms,
        )

        # ── Stage 6: Dimension lines (plot width/depth) ───────────────
        dimensions: List[DimensionLine] = DimensionGenerator.generate(
            plot_w=plot_w,
            plot_d=plot_d,
        )

        # ── Stage 7: SVG render (room labels, dims, colors included) ─
        svg_string: str = SVGRenderer.render(
            plot_w=plot_w,
            plot_d=plot_d,
            rooms=rooms,
            walls=walls,
            portals=portals,
            dimensions=dimensions,
        )

        return {
            "name": floor_name,
            "rooms": [GeometryEngine._room_dict(r) for r in rooms],
            "walls": [GeometryEngine._wall_dict(w) for w in walls],
            "portals": [GeometryEngine._portal_dict(p) for p in portals],
            "columns": [],
            "has_balcony": balcony_on_this_floor,
            "svg_raw": svg_string,
            "_dimensions_raw": dimensions,  # consumed by generate() below
        }

    # ── cost & paint & scoring (deterministic, no randomness) ─────

    @staticmethod
    def _estimate_cost(plot_w: float, plot_d: float, floors: int) -> Dict[str, Any]:
        total_sqft = plot_w * plot_d * max(1, floors)
        total_inr = round(total_sqft * COST_PER_SQFT_BASE, 2)
        materials = {
            key: round(total_inr * MATERIAL_FRACTION * frac, 2)
            for key, frac in MATERIAL_SPLIT.items()
        }
        return {
            "total_inr": total_inr,
            "materials": materials,
            "labor_inr": round(total_inr * LABOR_FRACTION, 2),
            "finishing_inr": round(total_inr * FINISHING_FRACTION, 2),
        }

    @staticmethod
    def _paint_recommendations(all_room_names: List[str]) -> List[Dict[str, Any]]:
        seen = set()
        recs = []
        for name in all_room_names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            primary_name, primary_hex = GeometryEngine._paint_for_room(name)
            recs.append({
                "room_name": name,
                "primary_name": primary_name,
                "primary_hex": primary_hex,
                "accent_name": "Charcoal Slate",
                "accent_hex": "#334155",
            })
        return recs

    @staticmethod
    def _score_layout(generation_mode: str, room_count: int, door_count: int) -> Dict[str, float]:
        vastu = 88.0 if generation_mode == "vastu_prioritization" else 72.0
        space_efficiency = round(min(98.0, 80.0 + room_count * 1.2), 1)
        circulation = round(min(95.0, 60.0 + door_count * 4.0), 1)
        return {
            "vastu": vastu,
            "space_efficiency": space_efficiency,
            "circulation": circulation,
        }

    # ── PRIMARY ENTRY POINT — matches layout_agent.py exactly ─────

    @staticmethod
    def generate(
        plot_width: float,
        plot_depth: float,
        floors: int,
        required_rooms: List[str],
        generation_mode: str = "space_efficiency",
        architectural_style: str = "modern",
    ) -> Dict[str, Any]:
        """
        Deterministic BSP geometry generation entry point.

        Called by layout_agent.LayoutEngineAgent.execute_procedural_generation()
        as: GeometryEngine.generate(plot_width=.., plot_depth=.., floors=..,
                                     required_rooms=.., generation_mode=..,
                                     architectural_style=..)

        Returns a plain dict (no dataclasses) with keys:
            floors                  -> list of floor dicts (rooms/walls/portals/svg_raw/...)
            cost_report              -> dict
            paint_recommendations    -> list of dicts
            scores                   -> dict (vastu / space_efficiency / circulation)
            dimensions               -> list of dimension-line dicts (global plot dims)
        """
        plot_w = float(plot_width)
        plot_d = float(plot_depth)
        n_floors = max(1, int(floors))

        # BSP split mode: vastu_prioritization shifts the weighted partition
        # ratio toward vastu-preferred zoning; space_efficiency uses the
        # raw weighted ratio. Anything else falls back to space_efficiency.
        bsp_mode = "vastu_prioritization" if generation_mode == "vastu_prioritization" else "space_efficiency"

        # Smart floor distribution: ground=social, upper=private, vastu-ordered when applicable
        floor_room_lists = GeometryEngine._distribute_rooms_across_floors(
            required_rooms, n_floors, generation_mode=generation_mode
        )

        floor_dicts: List[Dict[str, Any]] = []
        global_dimensions: List[DimensionLine] = []
        all_room_names: List[str] = []
        total_door_count = 0

        for idx, room_names in enumerate(floor_room_lists):
            floor_label = "Ground Floor" if idx == 0 else f"Floor {idx}"
            balcony_here = idx > 0 and any("balcony" in r.lower() for r in room_names)

            floor_dict = GeometryEngine._build_floor_dict(
                floor_index=idx,
                floor_name=floor_label,
                plot_w=plot_w,
                plot_d=plot_d,
                room_names=room_names,
                bsp_mode=bsp_mode,
                balcony_on_this_floor=balcony_here,
            )

            global_dimensions = floor_dict.pop("_dimensions_raw")
            floor_dicts.append(floor_dict)

            all_room_names.extend(room_names)
            total_door_count += sum(1 for p in floor_dict["portals"] if p["type"] == "door")

        cost_report = GeometryEngine._estimate_cost(plot_w, plot_d, n_floors)
        paint_recs = GeometryEngine._paint_recommendations(all_room_names)
        scores = GeometryEngine._score_layout(
            generation_mode=bsp_mode,
            room_count=len(all_room_names),
            door_count=total_door_count,
        )
        dimensions_data = [GeometryEngine._dimension_dict(d) for d in global_dimensions]

        return {
            "floors": floor_dicts,
            "cost_report": cost_report,
            "paint_recommendations": paint_recs,
            "scores": scores,
            "dimensions": dimensions_data,
        }

    # ── LEGACY ENTRY POINT — prompt-text based, dataclass return ───

    def parse_requirements(self, prompt: str) -> Tuple[Optional[PipelineRequirements], List[str]]:
        """
        Parses free-text user prompt into structured PipelineRequirements.
        Returns (None, [questions]) when mandatory information is missing,
        or (requirements, []) when the prompt is fully parseable.
        """
        questions   = []
        prompt_lower = prompt.lower()

        width  = 0.0
        length = 0.0

        dim_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|by)\s*(\d+(?:\.\d+)?)', prompt, re.IGNORECASE)
        if dim_match:
            width  = float(dim_match.group(1))
            length = float(dim_match.group(2))
        else:
            area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:sq\s*ft|square\s*feet)', prompt, re.IGNORECASE)
            if area_match:
                sqft   = float(area_match.group(1))
                width  = round(math.sqrt(sqft / 1.5), 1)
                length = round(width * 1.5, 1)

        if width <= 0.0 or length <= 0.0:
            questions.append("What are the exact plot dimensions in feet? (e.g. 30x50, or 1500 sq ft)")

        floors = 1
        explicit = False

        if any(k in prompt_lower for k in ("two floor", "2 floor", "g+1", "2 store", "double storey")):
            floors, explicit = 2, True
        elif any(k in prompt_lower for k in ("three floor", "3 floor", "g+2", "3 store", "triple storey")):
            floors, explicit = 3, True
        elif any(k in prompt_lower for k in ("single floor", "1 floor", "ground floor", "g+0", "one floor")):
            floors, explicit = 1, True

        if not explicit:
            questions.append("How many floors? (e.g. Ground Floor only, G+1, G+2)")

        if "vastu" not in prompt_lower:
            questions.append("Should the layout follow Vastu Shastra guidelines? (yes / no)")
        if "park" not in prompt_lower:
            questions.append("Do you need dedicated car/bike parking on the ground floor? (yes / no)")
        if "garden" not in prompt_lower and "lawn" not in prompt_lower:
            questions.append("Should we allocate space for a garden or green buffer area? (yes / no)")

        if questions:
            return None, questions

        style = "MODERN"
        if "tradition" in prompt_lower: style = "TRADITIONAL"
        elif "lux"     in prompt_lower: style = "LUXURY"
        elif "minim"   in prompt_lower: style = "MINIMAL"

        reqs = PipelineRequirements(
            site_width_ft  = width,
            site_length_ft = length,
            floors_count   = floors,
            style          = style,
            vastu_enabled  = "vastu"  in prompt_lower,
            parking_required = "no parking" not in prompt_lower,
            garden_required  = "garden" in prompt_lower or "lawn" in prompt_lower,
            balcony_required = "balcony" in prompt_lower,
        )
        return reqs, []

    def build_floor_plan(
        self,
        floor_index: int,
        reqs:        PipelineRequirements,
        mode:        str,          # "SPACE_MAXIMIZATION" | "PRIVACY"
    ) -> FloorPlanGeometry:
        """Legacy dataclass-returning single-floor pipeline (prompt-based path)."""
        W = reqs.site_width_ft
        D = reqs.site_length_ft

        floor_label = "Ground Floor" if floor_index == 0 else f"Floor {floor_index}"

        bsp_mode = "vastu_prioritization" if reqs.vastu_enabled else mode.lower()
        room_names = self._room_list_for_floor(floor_index, reqs)

        rooms: List[RoomGeometry] = RoomAllocator.allocate(
            x=0, y=0, w=W, h=D,
            rooms=room_names,
            is_horizontal=True,
            mode=bsp_mode,
        )
        self._apply_palette(rooms)

        adj_edges: List[AdjacencyEdge] = AdjacencyGraphBuilder.build(rooms)

        walls: List[WallGeometry] = WallGenerator.generate(
            plot_w=W, plot_d=D, interior_edges=adj_edges,
        )

        portals: List[PortalGeometry] = DoorGenerator.generate(
            plot_w=W, plot_d=D, interior_edges=adj_edges,
        )
        portals += WindowGenerator.generate(plot_w=W, plot_d=D, rooms=rooms)

        dimensions: List[DimensionLine] = DimensionGenerator.generate(plot_w=W, plot_d=D)

        svg_string: str = SVGRenderer.render(
            plot_w=W, plot_d=D, rooms=rooms, walls=walls,
            portals=portals, dimensions=dimensions,
        )

        return FloorPlanGeometry(
            floor_name = floor_label,
            plot_width = W,
            plot_depth = D,
            rooms      = rooms,
            walls      = walls,
            portals    = portals,
            dimensions = dimensions,
            has_balcony = reqs.balcony_required and floor_index > 0,
            svg_raw    = svg_string,
        )

    def generate_option(self, reqs: PipelineRequirements, mode: str) -> ArchitecturalOptionResult:
        """Build all floors for one layout variant and score the result (legacy path)."""
        floor_plans: List[FloorPlanGeometry] = []
        for f_idx in range(reqs.floors_count):
            floor_plans.append(self.build_floor_plan(f_idx, reqs, mode))

        score = 92.0 if mode == "SPACE_MAXIMIZATION" else 88.0

        return ArchitecturalOptionResult(
            floor_plans      = floor_plans,
            evaluation_score = score,
            metadata         = {
                "optimization_target": mode,
                "floors_generated":    reqs.floors_count,
                "vastu":               reqs.vastu_enabled,
                "style":               reqs.style,
            },
        )

    def generate_from_prompt(self, prompt_text: str) -> MasterEngineResponse:
        """
        Legacy prompt-text entry point (renamed from the old `generate` to avoid
        colliding with the new static, dict-returning `generate()` used by the
        live pipeline). Returns either clarification questions or two complete
        layout options as dataclasses.
        """
        try:
            reqs, missing = self.parse_requirements(prompt_text)

            if missing:
                return MasterEngineResponse(
                    is_clarification_needed = True,
                    clarification_questions = missing,
                )

            opt_a = self.generate_option(reqs, "SPACE_MAXIMIZATION")
            opt_b = self.generate_option(reqs, "PRIVACY")

            return MasterEngineResponse(
                is_clarification_needed = False,
                clarification_questions = [],
                option_a = opt_a,
                option_b = opt_b,
            )

        except Exception as err:
            return MasterEngineResponse(
                is_clarification_needed = False,
                clarification_questions = [],
                errors = [f"Pipeline abort: {str(err)}"],
            )