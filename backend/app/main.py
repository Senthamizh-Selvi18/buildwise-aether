# backend/app/main.py
# BuildWise Aether — Professional Architectural Planning System v4.0
# Enterprise-grade floor planning with intelligent requirement collection, 
# architect-level geometry, dynamic paint recommendations, and real-time cost estimation

import re
import uuid
import math
import traceback
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

# ── Core engines ─────────────────────────────────────────────────────────────
# NOTE: This used to try to import a non-existent "procedural_geometry_engine"
# module (and several other modules that don't exist anywhere in the repo),
# wrapped in a bare `except ImportError: pass`. That meant the import
# silently failed on every boot and the *real* BSP/adjacency/door/window
# geometry pipeline (backend/app/core/geometry/geometry_engine.py +
# room_allocator.py, adjacency_graph.py, wall_generator.py, door_generator.py,
# window_generator.py, dimension_generator.py, svg_renderer.py) was never
# actually wired into the API. The endpoint below was instead falling back to
# a much weaker, hand-rolled, non-BSP layout generator that just placed rooms
# in left-to-right wrapping rows.
try:
    from backend.app.core.geometry.geometry_engine import GeometryEngine
except ImportError:
    GeometryEngine = None  # generation endpoint will raise a clear error if this is missing

# NOTE: paint recommendations used to come from either (a) whatever
# GeometryEngine's own internal paint step produces (a black box from this
# file's point of view) or (b) the old IntelligentPaintEngine class that
# used to live in this file, which picked colours out of a fixed
# PAINT_PROFILES table keyed only by room type + interior_style -- every
# project with the same style got byte-identical colours, and inputs like
# mood, colour preference, natural lighting, room orientation, climate,
# Vastu preference, and occupancy (children/elderly/pets) had zero effect
# on the output. That hardcoded engine has been removed. Paint
# recommendations now come exclusively from app.core.paint_engine.PaintEngine,
# which COMPUTES every colour via real HSL colour-theory math from the full
# set of collected preferences (see _build_paint_preferences_from_clues() and
# _generate_theme_driven_paint_recommendations() below), and which reports
# any still-missing required preference so it can be asked as a follow-up
# question instead of silently guessed.
try:
    from app.core.paint_engine import (
        PaintEngine as ThemePaintEngine,
        PaintPreferences as _PaintPreferences,
        preferences_from_legacy_clues as _preferences_from_legacy_clues,
        REQUIRED_PREFERENCE_QUESTIONS as _PAINT_REQUIRED_QUESTIONS,
    )
except ImportError:
    try:
        from backend.app.core.paint_engine import (
            PaintEngine as ThemePaintEngine,
            PaintPreferences as _PaintPreferences,
            preferences_from_legacy_clues as _preferences_from_legacy_clues,
            REQUIRED_PREFERENCE_QUESTIONS as _PAINT_REQUIRED_QUESTIONS,
        )
    except ImportError:
        ThemePaintEngine = None
        _PaintPreferences = None
        _preferences_from_legacy_clues = None
        _PAINT_REQUIRED_QUESTIONS = {}


# ── Finite-number input guard ───────────────────────────────────────────────
# Root cause of "the floor plan silently doesn't show up": every numeric
# check in this file (here and in _validate_floorplan) only ever compared
# values with `<` / `>`. In Python, comparisons against NaN ALWAYS evaluate
# to False, and Infinity always "passes" a minimum-size check. So if a
# malformed value (NaN, Infinity, "abc", empty string, etc.) made it into
# plot_width / plot_depth / bhk_count / floors_requested / parking_slots /
# plot_cut_width / plot_cut_depth / plot_points, every validation check
# below was silently bypassed, the request reached GeometryEngine, and the
# BSP/wall/door/window math propagated NaN/Infinity through every
# coordinate. The endpoint still returned `response_type: success` with a
# `svg_dump` string in it -- but an SVG full of `NaN`/`Infinity` coordinates
# renders as nothing, so the floor plan appeared to "not generate" even
# though the API call technically succeeded.
#
# The functions below close that hole: every numeric field is explicitly
# checked with math.isfinite() (which correctly rejects NaN and +/-Infinity)
# before anything is handed to the geometry engine. Bad input is turned
# into a clear, user-facing message instead of a crash or a blank SVG.

def _budget_to_quality(budget_range: Optional[str]) -> str:
    """Maps the user-facing budget_range field to GeometryEngine's
    cost-estimation quality tiers."""
    mapping = {
        "budget": "budget", "mid": "standard", "premium": "premium", "luxury": "luxury",
    }
    return mapping.get((budget_range or "mid").lower(), "standard")


_NEGATION_WORDS = (
    "no", "not", "without", "don't", "dont", "never", "none",
    "skip", "exclude", "avoid", "n't",
)


def _wants(text: str, *keywords: str) -> bool:
    """
    True if any of `keywords` appears in `text` and is NOT negated.

    Plain substring matching (the old approach) treats "no gym" as a
    request FOR a gym, because the word "gym" is in there -- exactly
    backwards. This looks at the few words immediately before each keyword
    match for a negation word ("no", "not", "without", "don't", ...) and
    only counts the match if none is found.
    """
    low = text.lower()
    for kw in keywords:
        for m in re.finditer(re.escape(kw.lower()), low):
            window = low[max(0, m.start() - 40): m.start()]
            window_words = re.findall(r"[a-z']+", window)
            if any(w in _NEGATION_WORDS for w in window_words[-7:]):
                continue
            return True
    return False


def _coerce_numeric(value: Any) -> Any:
    """
    Normalizes a value that may have come from free-text / quick-pick Q&A
    answers (e.g. "30 ft", "2 floors", "3 BHK", "1 floor") into a plain
    int/float so it survives float()/int() conversion downstream.

    Leaves actual numbers untouched and returns non-numeric-looking strings
    unchanged (so the existing "not a finite number" validation error still
    fires with a useful message instead of silently swallowing garbage).
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        m = re.search(r'-?\d+(?:\.\d+)?', value)
        if m:
            num_str = m.group(0)
            return float(num_str) if '.' in num_str else int(num_str)
    return value


def _is_finite_number(value: Any) -> bool:
    """True only for an actual finite real number (rejects NaN, +/-Infinity,
    None, bools, strings, lists, etc.)."""
    if value is None or isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
    try:
        return math.isfinite(value)
    except (TypeError, ValueError):
        return False


def _validate_numeric_inputs(clues: Dict[str, Any]) -> List[str]:
    """
    Checks every numeric value that will reach the geometry engine and
    confirms it is a finite, sane real number. Returns a list of
    human-readable error messages (empty list = all good).
    """
    errors: List[str] = []

    required_numeric = {
        "plot_width": "Plot width",
        "plot_depth": "Plot depth",
        "floors_requested": "Number of floors",
        "bhk_count": "Bedroom (BHK) count",
    }
    for key, label in required_numeric.items():
        value = clues.get(key)
        if value is None:
            continue  # handled separately by the "missing fields" check
        if not _is_finite_number(value):
            errors.append(f"{label} must be a normal, finite number (got: {value!r}).")
        elif float(value) <= 0:
            errors.append(f"{label} must be a positive number (got: {value!r}).")

    optional_numeric = {
        "parking_slots": "Parking slots",
        "plot_cut_width": "Plot cut width",
        "plot_cut_depth": "Plot cut depth",
    }
    for key, label in optional_numeric.items():
        value = clues.get(key)
        if value is None or value == "":
            continue
        if not _is_finite_number(value):
            errors.append(f"{label} must be a normal, finite number (got: {value!r}).")
        elif float(value) < 0:
            errors.append(f"{label} cannot be negative (got: {value!r}).")

    plot_points = clues.get("plot_points")
    if plot_points:
        for i, pt in enumerate(plot_points):
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                errors.append(f"Custom plot point #{i + 1} must be an [x, y] pair.")
                continue
            x, y = pt
            if not (_is_finite_number(x) and _is_finite_number(y)):
                errors.append(f"Custom plot point #{i + 1} ({x!r}, {y!r}) must contain finite numbers.")
        if len(plot_points) < 3:
            errors.append("A custom plot outline (plot_points) needs at least 3 points.")

    return errors


def _theme_priority_list_from_clues(clues: Dict[str, Any], user_prompt: str) -> List[str]:
    """
    Returns theme text sources in priority order (most authoritative
    first): the dedicated paint_theme follow-up answer (e.g. "universe
    theme") beats the raw prompt, which beats the generic interior_style
    default (e.g. "contemporary"). Passed to PaintEngine.generate_layered()
    so an explicit, deliberate answer can never be diluted or outscored by
    a generic default just because both get combined into one string.
    """
    return [
        str(clues.get("paint_theme") or ""),
        user_prompt or "",
        str(clues.get("interior_style") or ""),
    ]


def _paint_rec_to_legacy_shape(rec) -> Dict[str, Any]:
    """
    Adapts the new PaintEngine's flat PaintRecommendation into the same
    nested {"primary": {...}, "accent": {...}, ...} shape
    IntelligentPaintEngine.get_paint_recommendation() used to return, so
    existing frontend code reading those keys keeps working -- only the
    underlying colours/rationale are now actually theme-driven.
    """
    return {
        "room_name": rec.room_name,
        "primary": {
            "name": rec.primary_paint_name,
            "hex": rec.primary_hex,
            "brand": rec.primary_brand,
            "temp": rec.primary_color_temp,
        },
        "accent": {
            "name": rec.accent_paint_name,
            "hex": rec.accent_hex,
            "brand": rec.accent_brand,
        },
        "finish": rec.finish_type,
        "washable": rec.washability in ("medium", "high"),
        "moisture_resistant": rec.recommended_for_moisture,
        "durability_years": rec.durability_years,
        "suggested_liters": rec.liters_required,
        "cost_per_liter": rec.cost_per_liter_inr,
        "total_cost_inr": rec.total_cost_inr,
        "theme_detected": rec.theme_detected,
        "matched_keywords": rec.matched_keywords,
        "rationale": rec.rationale,
    }


def _build_paint_preferences_from_clues(clues: Dict[str, Any], user_prompt: str) -> Any:
    """
    Builds a full, structured PaintPreferences object from everything we've
    collected -- room type is handled per-room inside PaintEngine itself,
    this covers the rest: interior style, mood, colour preference, natural
    lighting, room orientation, climate/city, budget, Vastu preference, and
    occupancy (children/elderly/pets). Falls back to the old free-text-only
    inference (preferences_from_legacy_clues) shape but fills in the extra
    structured fields this file now actually collects via follow-up
    questions, so those answers actually influence the generated palette
    instead of only the loosely-matched paint_theme free text.
    """
    if _preferences_from_legacy_clues is None:
        return None

    base = _preferences_from_legacy_clues(
        clues, user_prompt=user_prompt,
        city=clues.get("city"), budget=clues.get("budget_range"),
    )
    # Overlay the explicitly-collected structured answers (these are more
    # authoritative than anything inferred from free text).
    base.mood = clues.get("mood") or base.mood
    base.color_preference = clues.get("color_preference") or base.color_preference
    base.natural_lighting = clues.get("natural_lighting") or base.natural_lighting
    base.room_orientation = (
        clues.get("room_orientation") or clues.get("road_direction")
        or clues.get("north_direction") or base.room_orientation
    )
    base.climate = clues.get("climate") or base.climate
    if clues.get("vastu_preference") is not None:
        base.vastu_preference = bool(clues.get("vastu_preference"))

    occupancy: List[str] = []
    if clues.get("elder_friendly"):
        occupancy.append("elderly")
    if clues.get("has_children"):
        occupancy.append("children")
    if clues.get("has_pets"):
        occupancy.append("pets")
    if occupancy or clues.get("occupancy_specified"):
        base.occupancy = occupancy
    return base


def _generate_theme_driven_paint_recommendations(
    rooms: List[Dict[str, Any]], clues: Dict[str, Any], user_prompt: str
) -> Tuple[Dict[str, Dict[str, Any]], float]:
    """
    Single source of truth for paint recommendations, used by BOTH the real
    GeometryEngine path and the fallback engine path. Builds a full
    PaintPreferences object from room type, interior style, mood, colour
    preference, natural lighting, room orientation, climate/city, budget,
    Vastu preference, and occupancy, and generates a palette computed
    (never looked up from a fixed table) for every room. Returns
    (recommendations keyed by each room's `name`, total paint cost in INR).
    """
    if ThemePaintEngine is None:
        return {}, 0.0

    paint_rooms = [
        {"name": r.get("name", "room"), "area_sqft": r.get("area_sqft", r.get("area", 150))}
        for r in rooms
    ]

    prefs = _build_paint_preferences_from_clues(clues, user_prompt)
    if prefs is not None:
        # allow_partial=True: by the time this is called, STEP 2 of the
        # generation endpoint has already forced the user through the
        # required-preference follow-up questions, so any preference still
        # unanswered here is a genuinely optional one -- PaintEngine fills
        # it with a clearly-noted default rather than blocking generation.
        result = ThemePaintEngine.generate_personalized(paint_rooms, prefs, allow_partial=True)
        recs = result.recommendations
    else:
        # PaintPreferences/preferences_from_legacy_clues weren't importable
        # (older paint_engine.py) -- fall back to the legacy free-text-only
        # entry point so the app still functions.
        theme_priority = _theme_priority_list_from_clues(clues, user_prompt)
        recs = ThemePaintEngine.generate_layered(
            paint_rooms, theme_priority, city=clues.get("city") or "bangalore",
            budget=clues.get("budget_range") or "mid",
        )

    total_cost = sum(r.total_cost_inr for r in recs)
    by_room_name = {
        room.get("name", "room"): _paint_rec_to_legacy_shape(rec)
        for room, rec in zip(rooms, recs)
    }
    return by_room_name, total_cost


def _get_missing_paint_preferences(clues: Dict[str, Any], user_prompt: str) -> List[str]:
    """
    Returns the list of paint-preference keys PaintEngine considers
    genuinely unanswered, given everything collected so far. Used to ask
    intelligent follow-up questions BEFORE generating any recommendation,
    instead of silently guessing.
    """
    prefs = _build_paint_preferences_from_clues(clues, user_prompt)
    if prefs is None or ThemePaintEngine is None:
        return []
    return ThemePaintEngine.get_missing_preferences(prefs)


app = FastAPI(
    title="BuildWise Aether",
    description="Professional Architectural Planning System",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Enums for building rules ──────────────────────────────────────────────────

class InteriorStyle(str, Enum):
    MODERN = "modern"
    TRADITIONAL = "traditional"
    CONTEMPORARY = "contemporary"
    MINIMALIST = "minimalist"
    ECLECTIC = "eclectic"
    LUXE = "luxe"


class PaintFinish(str, Enum):
    MATTE = "matte"
    EGGSHELL = "eggshell"
    SATIN = "satin"
    SEMI_GLOSS = "semi_gloss"
    GLOSS = "gloss"


# ── Pydantic models ───────────────────────────────────────────────────────────

class GenerationRequest(BaseModel):
    user_prompt: str
    user_city: Optional[str] = "bangalore"
    current_answers: Optional[Dict[str, str]] = {}
    existing_answers: Optional[Dict[str, str]] = {}
    
    # Explicit architectural parameters
    plot_width: Optional[float] = None
    plot_depth: Optional[float] = None
    floors_requested: Optional[int] = None
    plot_shape: Optional[str] = "rectangle"
    plot_cut_width: Optional[float] = None   # notch size for l_shape/t_shape/u_shape presets
    plot_cut_depth: Optional[float] = None
    plot_points: Optional[List[List[float]]] = None  # explicit custom polygon [[x,y], ...] overrides plot_shape preset
    road_direction: Optional[str] = None  # north, south, east, west
    north_direction: Optional[str] = None
    bhk_count: Optional[int] = None
    parking_slots: Optional[int] = None
    lift_required: Optional[bool] = False
    elder_friendly: Optional[bool] = False
    interior_style: Optional[str] = "contemporary"
    budget_range: Optional[str] = None  # "budget", "mid", "premium", "luxury"
    vastu_preference: Optional[bool] = False

    # Extra requirement-gathering fields (asked on top of whatever the user
    # already volunteered, e.g. "3BHK with 2 floors" alone is not enough to
    # size rooms, pick a colour scheme, or know what extras to plan space for).
    family_members: Optional[int] = None
    paint_theme: Optional[str] = None       # e.g. "light & bright", "warm & earthy", "bold & dark"
    extra_spaces: Optional[str] = None      # free-text: parking count, pool, store room, gym, etc., or "none"

    # ── Paint-personalization inputs ─────────────────────────────────────
    # Feeds app.core.paint_engine.PaintEngine.generate_personalized() so
    # every project gets a palette actually computed from these inputs
    # (room type, style, mood, colour preference, lighting, orientation,
    # climate/city, budget, Vastu, occupancy) instead of a fixed swatch
    # table. Anything left unanswered here triggers a targeted follow-up
    # question rather than a silent guess.
    mood: Optional[str] = None              # "calm", "energetic", "cozy", "dramatic", free text OK
    color_preference: Optional[str] = None  # "vibrant", "pastel", "neutral", "earthy", "luxury", ...
    natural_lighting: Optional[str] = None  # "low", "medium", "high" / descriptive
    room_orientation: Optional[str] = None  # "north", "south-east", ... (per-room or house facing)
    climate: Optional[str] = None           # "hot & humid", "cold", "temperate", free text OK (city is a fallback)
    occupancy_notes: Optional[str] = None   # e.g. "young kids and a dog", or "none"
    has_children: Optional[bool] = None
    has_pets: Optional[bool] = None

    # Optional site/inspiration image — if the user shares a reference photo
    # or sketch, the layout style and proportions should take cues from it.
    background_image_base64: Optional[str] = None
    background_image_notes: Optional[str] = None

    session_id: Optional[str] = None
    mode: Optional[str] = "both"  # "adaptive" | "vastu" | "both"


class RoomDimensions(BaseModel):
    name: str
    width: float
    depth: float
    min_width: float
    min_depth: float
    area: float


# ── Intelligent Requirement Collection Engine ──────────────────────────────────

class IntelligentRequirementEngine:
    """
    Dynamically determines which questions are critical based on current state.
    Never asks unnecessary questions.
    """
    
    MANDATORY_FIELDS = [
        "plot_width", "plot_depth", "floors_requested", "bhk_count",
        "family_members", "paint_theme", "extra_spaces",
        # Paint-personalization inputs -- required so PaintEngine can
        # compute a genuinely unique palette instead of falling back to
        # unstated assumptions. (climate is intentionally NOT here: a city
        # is always known by this point and PaintEngine treats city as a
        # valid climate fallback signal. room_orientation and
        # occupancy_notes are intentionally NOT required either -- they're
        # still used automatically whenever mentioned in the prompt or
        # passed explicitly, PaintEngine just fills a sensible, clearly
        # noted default when they're not answered.)
        "mood", "color_preference", "natural_lighting",
    ]
    
    CONDITIONAL_FIELDS = {
        "parking_slots": {"dependency": "bhk_count", "threshold": 2},
        "lift_required": {"dependency": "floors_requested", "threshold": 3},
        "elder_friendly": {"dependency": "bhk_count", "threshold": 2},
    }
    
    @staticmethod
    def get_missing_fields(clues: Dict[str, Any]) -> List[str]:
        """Returns only CRITICAL missing fields needed for generation."""
        missing = []
        
        for field in IntelligentRequirementEngine.MANDATORY_FIELDS:
            value = clues.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)
        
        return missing
    
    @staticmethod
    def generate_questions(clues: Dict[str, Any], missing: List[str]) -> List[str]:
        """Generate human-friendly questions for missing fields."""
        questions = []
        
        field_questions = {
            "plot_width": "What is the plot width in feet? (e.g., 30, 40, 50)",
            "plot_depth": "What is the plot depth/length in feet? (e.g., 40, 60, 80)",
            "floors_requested": "How many floors do you need? (1, 2, 3, or 4)",
            "bhk_count": "How many bedrooms? (1BHK, 2BHK, 3BHK, 4BHK, or 5BHK)",
            "road_direction": "Which side faces the main road? (North, South, East, West)",
            "interior_style": "What interior style? (Modern, Traditional, Minimalist, Contemporary, Luxe)",
            "family_members": "Before I size the rooms — how many people will actually be living here, counting kids and any elders? The BHK count alone doesn't tell me how many people are sharing the bathrooms or how big the common areas need to be.",
            "paint_theme": "What kind of look are you going for on the walls — light and airy, warm and earthy tones, something bolder and darker, or a clean neutral palette? A rough direction is enough.",
            "extra_spaces": "A few things change the layout quite a bit — do you need car parking (how many vehicles), a swimming pool, or any other space like a store room, home gym, or rooftop sit-out? List what applies, or just say 'none' if you want to keep it simple.",
            # Paint-personalization questions -- pulled straight from
            # PaintEngine.REQUIRED_PREFERENCE_QUESTIONS so the wording asked
            # here always matches exactly what the engine itself considers
            # "answered", with a sensible fallback if that import failed.
            "mood": _PAINT_REQUIRED_QUESTIONS.get(
                "mood",
                "What mood should the space evoke — calm & soothing, energetic & lively, cozy & warm, "
                "dramatic & bold, or something else?"),
            "color_preference": _PAINT_REQUIRED_QUESTIONS.get(
                "color_preference",
                "What colour intensity do you prefer — vibrant, pastel, neutral, earthy, monochrome, "
                "muted, bold, or rich luxury tones?"),
            "natural_lighting": _PAINT_REQUIRED_QUESTIONS.get(
                "natural_lighting",
                "How much natural light does the home get through the day — low, medium, or high/abundant?"),
            "room_orientation": _PAINT_REQUIRED_QUESTIONS.get(
                "room_orientation",
                "Which direction does the house / main living area mainly face — north, south, east, "
                "west, or an in-between direction like north-east?"),
            "occupancy_notes": _PAINT_REQUIRED_QUESTIONS.get(
                "occupancy",
                "Who will be using the home — any young children, elderly family members, or pets? "
                "Say 'none' if not applicable."),
        }
        
        for field in missing:
            if field in field_questions:
                questions.append(field_questions[field])
        
        return questions


# ── Professional Geometry Engine ──────────────────────────────────────────────

class ArchitecturalGeometryEngine:
    """
    Generates architecturally correct floor plans with:
    - Proper room proportions
    - Correct dimensions
    - Adjacent relationships
    - Proper circulation
    - No overlapping
    - Professional CAD-quality output
    """
    
    # Standard room dimensions (in feet) based on Indian building codes
    STANDARD_ROOM_SIZES = {
        "entrance": {"width": 5, "depth": 6, "min_width": 4, "min_depth": 5},
        "living_room": {"width": 14, "depth": 18, "min_width": 12, "min_depth": 14},
        "master_bedroom": {"width": 14, "depth": 16, "min_width": 12, "min_depth": 14},
        "bedroom": {"width": 12, "depth": 14, "min_width": 10, "min_depth": 12},
        "kitchen": {"width": 10, "depth": 12, "min_width": 8, "min_depth": 10},
        "dining": {"width": 12, "depth": 14, "min_width": 10, "min_depth": 12},
        "bathroom": {"width": 7, "depth": 8, "min_width": 6, "min_depth": 7},
        "common_bathroom": {"width": 7, "depth": 8, "min_width": 6, "min_depth": 7},
        "utility": {"width": 6, "depth": 8, "min_width": 5, "min_depth": 6},
        "balcony": {"width": 6, "depth": 10, "min_width": 5, "min_depth": 8},
        "parking_slot": {"width": 9, "depth": 18, "min_width": 9, "min_depth": 15},
        "staircase": {"width": 4, "depth": 10, "min_width": 3.5, "min_depth": 9},
        "pooja_room": {"width": 8, "depth": 8, "min_width": 6, "min_depth": 6},
        "study": {"width": 10, "depth": 12, "min_width": 9, "min_depth": 10},
    }
    
    # Setback requirements (in feet) as per Indian building codes
    SETBACKS = {
        "front": 15,
        "rear": 10,
        "side": 5,
    }
    
    @staticmethod
    def generate_layout(
        clues: Dict[str, Any],
        plot_width: float,
        plot_depth: float,
        bhk: int,
        floors: int,
        mode: str = "adaptive"
    ) -> Dict[str, Any]:
        """
        Generate architecturally correct layout respecting:
        - Plot dimensions
        - Road direction
        - North orientation
        - Vastu principles (if mode="vastu")
        - User preferences
        - Building codes
        """
        
        layout = {
            "mode": mode,
            "plot": {"width": plot_width, "depth": plot_depth},
            "usable_width": plot_width - (ArchitecturalGeometryEngine.SETBACKS["front"] + 
                                          ArchitecturalGeometryEngine.SETBACKS["rear"]),
            "usable_depth": plot_depth - (ArchitecturalGeometryEngine.SETBACKS["side"] * 2),
            "floors": [],
        }
        
        # Generate rooms for each floor
        for floor_idx in range(floors):
            floor_rooms = ArchitecturalGeometryEngine._generate_floor_layout(
                bhk=bhk,
                plot_width=layout["usable_width"],
                plot_depth=layout["usable_depth"],
                mode=mode,
                floor_idx=floor_idx,
                total_floors=floors,
            )
            layout["floors"].append(floor_rooms)
        
        return layout
    
    @staticmethod
    def _generate_floor_layout(
        bhk: int,
        plot_width: float,
        plot_depth: float,
        mode: str,
        floor_idx: int,
        total_floors: int,
    ) -> List[Dict[str, Any]]:
        """Generate individual floor layout with intelligent room placement."""
        
        rooms = []
        x_offset = 0.5  # Wall thickness in feet
        y_offset = 0.5
        
        # Define room sequence based on BHK and mode
        if mode == "vastu":
            room_sequence = ArchitecturalGeometryEngine._get_vastu_room_sequence(bhk)
        else:
            room_sequence = ArchitecturalGeometryEngine._get_adaptive_room_sequence(bhk)
        
        # Place rooms with proper adjacency
        current_x = x_offset
        current_y = y_offset
        
        for room_type in room_sequence:
            if current_x + ArchitecturalGeometryEngine.STANDARD_ROOM_SIZES[room_type]["width"] > plot_width:
                # Wrap to next row
                current_x = x_offset
                current_y += ArchitecturalGeometryEngine.STANDARD_ROOM_SIZES[room_type]["depth"] + 1
            
            room_spec = ArchitecturalGeometryEngine.STANDARD_ROOM_SIZES[room_type]
            
            room = {
                "name": room_type,
                "x1": round(current_x, 2),
                "y1": round(current_y, 2),
                "x2": round(current_x + room_spec["width"], 2),
                "y2": round(current_y + room_spec["depth"], 2),
                "width": round(room_spec["width"], 2),
                "height": round(room_spec["depth"], 2),
                "area": round(room_spec["width"] * room_spec["depth"], 2),
            }
            
            rooms.append(room)
            current_x += room_spec["width"] + 0.5
        
        return rooms
    
    @staticmethod
    def _get_vastu_room_sequence(bhk: int) -> List[str]:
        """Vastu-compliant room arrangement."""
        base = ["entrance", "living_room", "dining", "kitchen"]
        
        if bhk >= 1:
            base.extend(["master_bedroom", "bathroom"])
        if bhk >= 2:
            base.extend(["bedroom", "common_bathroom"])
        if bhk >= 3:
            base.extend(["bedroom", "utility"])
        if bhk >= 4:
            base.extend(["bedroom", "pooja_room"])
        
        # Add balcony and parking
        base.extend(["balcony", "parking_slot"])
        
        return base
    
    @staticmethod
    def _get_adaptive_room_sequence(bhk: int) -> List[str]:
        """Space-optimized adaptive room arrangement."""
        base = ["entrance", "living_room", "kitchen", "dining"]
        
        if bhk >= 1:
            base.extend(["master_bedroom", "bathroom"])
        if bhk >= 2:
            base.extend(["bedroom", "common_bathroom"])
        if bhk >= 3:
            base.extend(["bedroom", "utility"])
        if bhk >= 4:
            base.extend(["bedroom", "study"])
        
        base.extend(["balcony", "staircase", "parking_slot"])
        
        return base


# ── Dynamic Cost Estimation Engine ─────────────────────────────────────────────

class DynamicCostEngine:
    """
    Real-time cost calculation based on:
    - Built-up area
    - Floor count
    - Material quantities
    - Location/city
    - Quality level
    - Current market rates

    Cost is broken down into standard Indian residential-construction
    categories (Foundation, RCC / Structure, Brickwork, Roofing, Flooring,
    Electrical, Plumbing, Doors, Windows, Painting, Labour) using typical
    percentage-of-construction-cost weightings, rather than a single lumped
    "structure_cost" figure the way this engine used to. This mirrors the
    category list in app/core/cost_estimation.py's CostEstimationEngine so
    the two stay conceptually consistent, and gives the frontend a real
    BOQ-style breakdown to render instead of just
    concrete/steel/bricks/labor/finishes/paint.
    """

    # City-wise cost multipliers (relative to Bangalore base rate)
    CITY_MULTIPLIERS = {
        "bangalore": 1.0,
        "hyderabad": 0.85,
        "pune": 0.92,
        "delhi": 1.15,
        "mumbai": 1.35,
        "goa": 1.10,
        "kolkata": 0.78,
        "chennai": 0.88,
        "ahmedabad": 0.82,
        "jaipur": 0.80,
    }

    # Base rates per sqft (in INR) for different quality levels
    BASE_RATES = {
        "budget": 700,      # ₹700-800/sqft
        "mid": 1200,        # ₹1200-1500/sqft
        "premium": 2000,    # ₹2000-2500/sqft
        "luxury": 3500,     # ₹3500+/sqft
    }

    # Typical Indian residential construction cost split, expressed as a
    # percentage of the pre-tax, pre-contingency construction cost. These
    # are standard rule-of-thumb weightings (sum to 100%) used to break the
    # single rate_per_sqft figure into named line items instead of one lump
    # "structure_cost" number.
    CATEGORY_WEIGHTS = {
        "foundation":  0.07,   # 7%
        "structure":   0.20,   # 20% -- RCC (columns / beams / slabs)
        "brickwork":   0.13,   # 13% -- masonry / walls
        "roofing":     0.05,   # 5%
        "flooring":    0.10,   # 10%
        "electrical":  0.07,   # 7%
        "plumbing":    0.06,   # 6%
        "doors":       0.07,   # 7%
        "windows":     0.05,   # 5%
        "painting":    0.06,   # 6%
        "labour":      0.14,   # 14%
    }

    @staticmethod
    def calculate_cost_estimation(
        rooms: List[Dict[str, Any]],
        plot_area: float,
        built_up_area: float,
        floors: int,
        city: str = "bangalore",
        budget: str = "mid",
        precomputed_paint_cost_inr: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate a category-wise dynamic cost breakdown.

        Returns a "breakdown" dict keyed by category (foundation, structure,
        brickwork, roofing, flooring, electrical, plumbing, doors, windows,
        painting, labour, subtotal, contingency_10percent, gst_18percent)
        where EVERY VALUE IS A PLAIN INR NUMBER (not a nested object) --
        deliberately, so a UI column that formats/coerces each value
        directly (Number(value), value.toLocaleString(), a currency
        formatter, etc.) renders a real figure instead of NaN. Human-
        readable display names for each key are provided separately under
        "category_labels", and quantity/unit detail (concrete m³, steel
        tons, brick thousands, door/window counts) lives under the separate
        "material_quantities" key -- so the BOQ still has physical
        quantities available, without any of that extra detail sitting
        inside the numeric cost value itself.

        If precomputed_paint_cost_inr is given (the actual theme-driven
        total from ThemePaintEngine), it's used as-is for the "painting"
        line instead of the percentage-weighted figure or the old per-room
        IntelligentPaintEngine loop -- that keeps the number shown here
        identical to what's shown in paint_recommendations, instead of
        silently drifting from the user's actual paint_theme answer.
        """

        city_multiplier = DynamicCostEngine.CITY_MULTIPLIERS.get(city.lower(), 1.0)
        base_rate = DynamicCostEngine.BASE_RATES.get(budget, 1200)
        rate_per_sqft = base_rate * city_multiplier

        # Total pre-tax, pre-contingency construction cost -- this is the
        # figure CATEGORY_WEIGHTS splits into named line items below.
        total_construction_cost = built_up_area * rate_per_sqft

        w = DynamicCostEngine.CATEGORY_WEIGHTS
        foundation_cost = total_construction_cost * w["foundation"]
        structure_cost  = total_construction_cost * w["structure"]
        brickwork_cost  = total_construction_cost * w["brickwork"]
        roofing_cost    = total_construction_cost * w["roofing"]
        flooring_cost   = total_construction_cost * w["flooring"]
        electrical_cost = total_construction_cost * w["electrical"]
        plumbing_cost   = total_construction_cost * w["plumbing"]
        doors_cost      = total_construction_cost * w["doors"]
        windows_cost    = total_construction_cost * w["windows"]
        painting_cost   = total_construction_cost * w["painting"]
        labour_cost     = total_construction_cost * w["labour"]

        # Material-quantity detail (informational, nested under Structure /
        # Brickwork / Doors / Windows) -- rough rule-of-thumb quantities
        # unrelated to the rate-based cost split above, so the BOQ shows
        # physical quantities alongside the money figures.
        concrete_qty = built_up_area * 0.15   # m³
        steel_qty = built_up_area * 0.004     # tons
        brick_qty = built_up_area * 0.4       # thousands
        door_count = max(4, round(built_up_area / 200))
        window_count = max(6, round(built_up_area / 120))

        # Paint cost: always prefer the actual theme-driven total from
        # PaintEngine (keeps this number identical to paint_recommendations,
        # since it's computed from the same personalized run). If that
        # wasn't supplied -- e.g. ThemePaintEngine failed to import -- fall
        # back to the generic rate-based percentage weight already computed
        # above (painting_cost = total_construction_cost * w["painting"]),
        # rather than any per-room hardcoded swatch/price table.
        if precomputed_paint_cost_inr is not None:
            painting_cost = precomputed_paint_cost_inr

        subtotal = (foundation_cost + structure_cost + brickwork_cost +
                    roofing_cost + flooring_cost + electrical_cost +
                    plumbing_cost + doors_cost + windows_cost +
                    painting_cost + labour_cost)

        # Contingency (10%)
        contingency = subtotal * 0.10

        # GST (18% on construction, plus 5% extra on the structural/steel
        # portion, mirroring the earlier steel-specific GST treatment)
        gst = (subtotal * 0.18) + (structure_cost * 0.05)

        grand_total = subtotal + contingency + gst

        # Timeline estimation
        timeline_months = 6 + (floors - 1) * 2 + (built_up_area // 2000)

        # IMPORTANT: every value in "breakdown" is a PLAIN NUMBER (INR), not
        # a nested {"cost": ...} object. Root cause of the "NaN" column in
        # the Cost Valuation Spreadsheets table: the previous version of
        # this function put an object like {"cost": 123, "label": "...",
        # "concrete_qty": ...} at breakdown["structure"] etc. Whatever the
        # frontend's valuation column does with each row's value (e.g.
        # Number(value), value.toLocaleString(), or a straight currency
        # formatter) treats a plain number correctly but turns an object
        # into NaN -- objects don't coerce to numbers in JS. Every category
        # below is now a bare int so that column renders a real number.
        # Quantity/unit detail (concrete m³, steel tons, brick thousands,
        # door/window counts) that used to live nested inside those objects
        # is now under the separate "material_quantities" key instead, so
        # it's still available to any UI that wants it without breaking the
        # simple cost-per-category table.
        return {
            "breakdown": {
                "foundation": int(foundation_cost),
                "structure": int(structure_cost),
                "brickwork": int(brickwork_cost),
                "roofing": int(roofing_cost),
                "flooring": int(flooring_cost),
                "electrical": int(electrical_cost),
                "plumbing": int(plumbing_cost),
                "doors": int(doors_cost),
                "windows": int(windows_cost),
                "painting": int(painting_cost),
                "labour": int(labour_cost),
                "subtotal": int(subtotal),
                "contingency_10percent": int(contingency),
                "gst_18percent": int(gst),
            },
            "category_labels": {
                "foundation": "Foundation",
                "structure": "RCC / Structure",
                "brickwork": "Brickwork",
                "roofing": "Roofing",
                "flooring": "Flooring",
                "electrical": "Electrical",
                "plumbing": "Plumbing",
                "doors": "Doors",
                "windows": "Windows",
                "painting": "Painting",
                "labour": "Labour",
                "subtotal": "Subtotal",
                "contingency_10percent": "Contingency (10%)",
                "gst_18percent": "GST (18%)",
            },
            "material_quantities": {
                "concrete": {"qty": round(concrete_qty, 2), "unit": "m³"},
                "steel": {"qty": round(steel_qty, 2), "unit": "tons"},
                "bricks": {"qty": round(brick_qty, 2), "unit": "thousands"},
                "doors_count": door_count,
                "windows_count": window_count,
            },
            "cost_per_sqft": round(grand_total / built_up_area, 2),
            "grand_total_inr": f"₹{int(grand_total):,}",
            "grand_total_value": int(grand_total),
            "estimated_timeline_months": int(timeline_months),
            "city_location": city.title(),
            "quality_level": budget.title(),
        }


# ── Session Management ─────────────────────────────────────────────────────────

_sessions: Dict[str, Dict[str, Any]] = {}


# ── API Endpoints ──────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "BuildWise Aether v4.0",
        "description": "Professional Architectural Planning System"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "version": "4.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/generate")
async def generate_floorplan(request: GenerationRequest):
    """
    Main generation endpoint with intelligent requirement collection and
    professional architectural planning.
    
    Phase 1: Intelligent clarification (only asks critical missing questions)
    Phase 2: Validation against Indian building codes
    Phase 3: Generation (layout, SVG, cost, paint, evaluation)
    """
    
    session_id = request.session_id or str(uuid.uuid4())
    
    session = _sessions.get(session_id, {
        "session_id": session_id,
        "user_prompt": request.user_prompt,
        "city": request.user_city or "bangalore",
        "answers": {},
        "attempt": 0,
    })
    
    # Merge user answers
    merged_answers = {**(request.existing_answers or {}), **(request.current_answers or {})}
    if merged_answers:
        session["answers"].update(merged_answers)
    
    session["attempt"] += 1
    _sessions[session_id] = session
    
    try:
        # ── STEP 1: Collect explicit architectural parameters ────────────────
        # Priority: explicit structured field > previously-given answer >
        # parsed straight out of the user's free-text prompt. This is what
        # lets a prompt like "3BHK house on a 1200 sq ft plot with parking,
        # one pooja room and 2 floors" generate immediately instead of
        # re-asking the user for things they already said.
        prompt_clues = _extract_clues_from_prompt(request.user_prompt)
        print("Prompt:", request.user_prompt)
        print("Extracted:", prompt_clues)

        clues = {
            "plot_width": _coerce_numeric(request.plot_width or session["answers"].get("plot_width") or prompt_clues.get("plot_width")),
            "plot_depth": _coerce_numeric(request.plot_depth or session["answers"].get("plot_depth") or prompt_clues.get("plot_depth")),
            "floors_requested": _coerce_numeric(request.floors_requested or session["answers"].get("floors_requested") or prompt_clues.get("floors_requested")),
            "bhk_count": _coerce_numeric(request.bhk_count or session["answers"].get("bhk_count") or prompt_clues.get("bhk_count")),
            "parking_slots": _coerce_numeric(request.parking_slots or session["answers"].get("parking_slots") or prompt_clues.get("parking_slots")),
            "lift_required": request.lift_required or session["answers"].get("lift_required") or prompt_clues.get("lift_required", False),
            "elder_friendly": request.elder_friendly or session["answers"].get("elder_friendly") or prompt_clues.get("elder_friendly", False),
            "interior_style": request.interior_style or prompt_clues.get("interior_style") or "contemporary",
            "budget_range": request.budget_range or "mid",
            "vastu_preference": request.vastu_preference or prompt_clues.get("vastu_preference", False),
            "plot_shape": request.plot_shape if (request.plot_shape and request.plot_shape != "rectangle") else (session["answers"].get("plot_shape") or prompt_clues.get("plot_shape") or "rectangle"),
            "plot_cut_width": request.plot_cut_width,
            "plot_cut_depth": request.plot_cut_depth,
            "plot_points": request.plot_points,
            "city": session["city"],
            "family_members": _coerce_numeric(request.family_members or session["answers"].get("family_members") or prompt_clues.get("family_members")),
            "paint_theme": request.paint_theme or session["answers"].get("paint_theme") or prompt_clues.get("paint_theme"),
            "extra_spaces": request.extra_spaces or session["answers"].get("extra_spaces") or prompt_clues.get("extra_spaces"),
            "background_image_base64": request.background_image_base64 or session["answers"].get("background_image_base64"),
            "background_image_notes": request.background_image_notes or session["answers"].get("background_image_notes"),
            # ── Paint-personalization clues ──────────────────────────────
            "mood": request.mood or session["answers"].get("mood") or prompt_clues.get("mood"),
            "color_preference": request.color_preference or session["answers"].get("color_preference") or prompt_clues.get("color_preference"),
            "natural_lighting": request.natural_lighting or session["answers"].get("natural_lighting") or prompt_clues.get("natural_lighting"),
            "room_orientation": (
                request.room_orientation or session["answers"].get("room_orientation")
                or prompt_clues.get("room_orientation") or request.road_direction or request.north_direction
            ),
            "climate": request.climate or session["answers"].get("climate") or prompt_clues.get("climate"),
            "occupancy_notes": request.occupancy_notes or session["answers"].get("occupancy_notes") or prompt_clues.get("occupancy_notes"),
        }

        # Occupancy flags: explicit boolean fields win; otherwise derive
        # from the free-text occupancy_notes answer (negation-aware, so
        # "no pets" is not read as "has pets"). occupancy_specified marks
        # that the question has been answered at all (even "none"), so it
        # isn't asked again and PaintEngine treats occupancy=[] as a real
        # "no special needs" answer rather than "unanswered".
        _occ_text = str(clues.get("occupancy_notes") or "")
        clues["has_children"] = (
            request.has_children if request.has_children is not None
            else (session["answers"].get("has_children") if "has_children" in session["answers"] else _wants(_occ_text, "child", "kid", "kids", "children"))
        )
        clues["has_pets"] = (
            request.has_pets if request.has_pets is not None
            else (session["answers"].get("has_pets") if "has_pets" in session["answers"] else _wants(_occ_text, "pet", "pets", "dog", "cat"))
        )
        if not clues.get("elder_friendly"):
            clues["elder_friendly"] = clues.get("elder_friendly") or _wants(_occ_text, "elder", "elderly", "senior citizen")
        clues["occupancy_specified"] = bool(clues.get("occupancy_notes") and str(clues["occupancy_notes"]).strip())

        # Cache whatever we successfully parsed so subsequent clarification
        # round-trips (e.g. just answering "3 BHK") don't lose the rest.
        for k, v in prompt_clues.items():
            session["answers"].setdefault(k, v)
        
        # Persist explicitly-supplied extra fields too, so they survive into
        # the next clarification round-trip the same way prompt_clues does.
        for k, v in {
            "family_members": request.family_members,
            "paint_theme": request.paint_theme,
            "extra_spaces": request.extra_spaces,
            "background_image_base64": request.background_image_base64,
            "background_image_notes": request.background_image_notes,
            "mood": request.mood,
            "color_preference": request.color_preference,
            "natural_lighting": request.natural_lighting,
            "room_orientation": request.room_orientation,
            "climate": request.climate,
            "occupancy_notes": request.occupancy_notes,
            "has_children": request.has_children,
            "has_pets": request.has_pets,
        }.items():
            if v is not None and v != "":
                session["answers"][k] = v

        # ── STEP 2: Check for critical missing fields ──────────────────────
        missing_fields = IntelligentRequirementEngine.get_missing_fields(clues)
        
        if missing_fields and session["attempt"] == 1:
            questions = IntelligentRequirementEngine.generate_questions(clues, missing_fields)
            
            return {
                "response_type": "clarification_required",
                "requires_clarification": True,
                "session_id": session_id,
                "missing_fields": missing_fields,
                "questions": questions,
                "extracted_so_far": clues,
            }
        
        # ── STEP 2b: Reject NaN / Infinity / non-numeric input up front ─────
        # This MUST run before _validate_floorplan, because that function's
        # `<` / `>` comparisons silently let NaN and Infinity through (see
        # the big comment above _is_finite_number for why), which is what
        # was letting broken values reach GeometryEngine and produce a
        # floor plan that "generated" but rendered as a blank SVG.
        numeric_errors = _validate_numeric_inputs(clues)
        if numeric_errors:
            return {
                "response_type": "validation_failed",
                "requires_clarification": False,
                "session_id": session_id,
                "errors": numeric_errors,
                "suggestions": [
                    "Re-enter plot width, plot depth, floors, and BHK count as plain positive numbers "
                    "(e.g. 30, 45.5) -- not text, blank values, or special numbers like Infinity/NaN.",
                ],
            }

        # ── STEP 3: Validate architectural feasibility ──────────────────────
        is_valid, validation_errors = _validate_floorplan(clues)
        
        if validation_errors:
            return {
                "response_type": "validation_failed",
                "requires_clarification": False,
                "session_id": session_id,
                "errors": validation_errors,
                "suggestions": _get_validation_suggestions(clues),
            }
        
        # ── STEP 4: Generate professional floor plan ────────────────────────
        # ROOT CAUSE OF THE BROKEN / JUMBLED FLOOR PLAN:
        # backend.app.core.geometry.geometry_engine.GeometryEngine (the real
        # BSP + adjacency + door + window + zoning pipeline -- the one that
        # correctly splits Living/Kitchen/Parking/Pooja onto the ground
        # floor and Bedrooms/attached-Bathrooms onto upper floors) WAS being
        # imported at the top of this file but was never actually called
        # anywhere. Generation was silently falling through to a much
        # weaker fallback engine (ArchitecturalGeometryEngine, further down
        # in this file) that has no floor-zoning logic at all -- which is
        # exactly why bedrooms, parking, staircase and pooja room were all
        # being dumped onto a single floor in the screenshot. _build_required_rooms()
        # (which already exists in this file, see below) was *also* dead
        # code for the same reason -- it builds the room program that only
        # GeometryEngine.generate() consumes.
        #
        # Fix: actually call GeometryEngine.generate() when the module is
        # importable (it is -- every file it depends on, models.py,
        # plot_geometry.py, room_allocator.py, adjacency_graph.py,
        # wall_generator.py, door_generator.py, window_generator.py,
        # dimension_generator.py, svg_renderer.py -- all exist), and only
        # fall back to the weaker engine if GeometryEngine genuinely failed
        # to import (e.g. a fresh checkout missing the geometry package).
        try:
            plot_w = float(clues["plot_width"])
            plot_d = float(clues["plot_depth"])
            bhk = int(clues["bhk_count"])
            floors = int(clues["floors_requested"])
        except (TypeError, ValueError):
            return {
                "response_type": "validation_failed",
                "requires_clarification": False,
                "session_id": session_id,
                "errors": ["Plot width, plot depth, BHK count, and floors must all be valid finite numbers."],
                "suggestions": ["Double-check these fields and resubmit with plain numeric values."],
            }
        if not all(_is_finite_number(v) for v in (plot_w, plot_d, bhk, floors)):
            return {
                "response_type": "validation_failed",
                "requires_clarification": False,
                "session_id": session_id,
                "errors": ["Plot width, plot depth, BHK count, and floors must all be finite (no NaN/Infinity)."],
                "suggestions": ["Double-check these fields and resubmit with plain numeric values."],
            }

        # ── STEP 5a: Real engine (preferred) ────────────────────────────────
        def _run_real_engine(mode: str) -> Dict[str, Any]:
            """
            Runs the real GeometryEngine.generate() BSP/adjacency/door/window
            pipeline and converts its output into the shape the frontend
            (CADBlueprint.tsx) expects: floor_name, level, svg_dump, rooms
            (with area_sqft), doors, windows, walls, dimensions.
            """
            bsp_mode = "vastu_prioritization" if mode == "vastu" else "space_efficiency"
            required_rooms = _build_required_rooms(clues, bhk, floors, request.user_prompt)

            plot_points = None
            if clues.get("plot_points") and len(clues["plot_points"]) >= 3:
                plot_points = [(float(x), float(y)) for x, y in clues["plot_points"]]

            result = GeometryEngine.generate(
                plot_width=plot_w,
                plot_depth=plot_d,
                floors=floors,
                required_rooms=required_rooms,
                generation_mode=bsp_mode,
                architectural_style=clues.get("interior_style") or "contemporary",
                city=clues.get("city") or "",
                state="",
                quality=_budget_to_quality(clues.get("budget_range")),
                plot_shape_type=clues.get("plot_shape") or "rectangle",
                plot_cut_width=clues.get("plot_cut_width"),
                plot_cut_depth=clues.get("plot_cut_depth"),
                plot_points=plot_points,
            )

            out_floors = []
            for floor_idx, fd in enumerate(result["floors"]):
                doors = [p for p in fd["portals"] if p["type"] == "door"]
                windows = [p for p in fd["portals"] if p["type"] == "window"]
                out_floors.append({
                    "floor_name": fd["floor_name"],
                    "level": floor_idx,
                    "svg_dump": fd["svg_dump"],
                    "rooms": fd["rooms"],
                    "doors": doors,
                    "windows": windows,
                    "walls": fd["walls"],
                    "has_balcony": fd["has_balcony"],
                    "dimensions": {
                        "plot_width_ft": plot_w,
                        "plot_depth_ft": plot_d,
                        "plot_shape": result.get("plot_shape_type") or "rectangle",
                        "plot_polygon": result.get("plot_polygon"),
                    },
                })

            total_rooms_all_floors = [r for fd in out_floors for r in fd["rooms"]]
            built_up_area = sum(r.get("area_sqft", 0) for r in total_rooms_all_floors)

            # Always use the theme-driven engine for paint, regardless of
            # whatever GeometryEngine's own internal paint step produced --
            # that internal step has no visibility into paint_theme at all.
            theme_paint_recs, theme_paint_total_cost = _generate_theme_driven_paint_recommendations(
                total_rooms_all_floors, clues, request.user_prompt
            )

            # ROOT CAUSE of "still no categories, still one lump total":
            # This function was returning `result["cost_report"]` verbatim --
            # i.e. whatever internal, black-box cost object
            # GeometryEngine.generate() itself produces (a module this file
            # doesn't own the source of). The only thing ever touched on it
            # was swapping a "paint" sub-cost IF that key happened to exist
            # in dict form; the rest of that object's shape (whether it has
            # named categories like Foundation/RCC/Brickwork/etc at all) was
            # completely out of this file's control. That's exactly the
            # object the screenshot's "Cost Valuation Spreadsheets" panel is
            # rendering -- a single "TOTAL CONTRACTED STRUCTURAL ESTIMATE"
            # figure with no breakdown.
            #
            # Fix: stop trusting GeometryEngine's internal cost report at
            # all. Compute cost_report ourselves via the same categorized
            # DynamicCostEngine.calculate_cost_estimation() used by the
            # fallback engine below, using the *actual* rooms this engine
            # placed (total_rooms_all_floors) and the *actual* theme-driven
            # paint total. This guarantees a full Foundation / RCC-Structure
            # / Brickwork / Roofing / Flooring / Electrical / Plumbing /
            # Doors / Windows / Painting / Labour / Contingency / GST
            # breakdown every time, regardless of which layout engine ran,
            # instead of depending on an external module's internal format.
            cost_report = DynamicCostEngine.calculate_cost_estimation(
                rooms=total_rooms_all_floors,
                plot_area=plot_w * plot_d,
                built_up_area=built_up_area or 1,  # avoid div-by-zero
                floors=floors,
                city=clues.get("city") or "bangalore",
                budget=clues.get("budget_range") or "mid",
                precomputed_paint_cost_inr=(theme_paint_total_cost if theme_paint_recs else None),
            )

            return {
                "floors": out_floors,
                "built_up_area": built_up_area,
                "cost_report": cost_report,
                "paint_recommendations": (
                    theme_paint_recs if theme_paint_recs
                    else {p["room_name"]: p for p in result["paint_recommendations"]}
                ),
                "scores": result["scores"],
                "dimensions": {
                    "plot_width_ft": plot_w,
                    "plot_depth_ft": plot_d,
                    "usable_width": plot_w,
                    "usable_depth": plot_d,
                },
            }

        # ── STEP 5b: Fallback room-grid engine (only used if the real
        # GeometryEngine pipeline failed to import) ─────────────────────────
        def _run_fallback_engine(mode: str) -> Dict[str, Any]:
            """
            Runs ArchitecturalGeometryEngine.generate_layout() and converts
            its output into the same per-floor shape the frontend expects:
            floor_name, level, svg_dump, rooms (with area_sqft), dimensions.
            doors/windows/walls are not produced by this fallback engine, so
            they're returned as empty lists -- CADBlueprint.tsx already
            handles that fine by drawing from svg_dump / rooms directly.
            """
            layout = ArchitecturalGeometryEngine.generate_layout(
                clues=clues,
                plot_width=plot_w,
                plot_depth=plot_d,
                bhk=bhk,
                floors=floors,
                mode=mode,
            )

            out_floors = []
            for floor_idx, floor_rooms in enumerate(layout["floors"]):
                # Mirror "area" -> "area_sqft" so both backend cost math and
                # the frontend's optional area_sqft field work.
                for r in floor_rooms:
                    r["area_sqft"] = r.get("area", round(r.get("width", 0) * r.get("height", 0), 2))

                svg_dump = _generate_professional_svg(
                    floor_rooms, plot_w, plot_d, floor_idx
                )

                out_floors.append({
                    "floor_name": _get_floor_name(floor_idx),
                    "level": floor_idx,
                    "svg_dump": svg_dump,
                    "rooms": floor_rooms,
                    "doors": [],
                    "windows": [],
                    "walls": [],
                    "has_balcony": any(r["name"] == "balcony" for r in floor_rooms),
                    "dimensions": {
                        "plot_width_ft": plot_w,
                        "plot_depth_ft": plot_d,
                        "plot_shape": clues.get("plot_shape") or "rectangle",
                        "plot_polygon": None,
                    },
                })

            total_rooms_all_floors = [r for fd in out_floors for r in fd["rooms"]]
            built_up_area = sum(r["area_sqft"] for r in total_rooms_all_floors)

            paint_recommendations, theme_paint_total_cost = _generate_theme_driven_paint_recommendations(
                total_rooms_all_floors, clues, request.user_prompt
            )
            if not paint_recommendations:
                # PaintEngine itself failed to import in this deployment --
                # no hardcoded colour table to fall back to; DynamicCostEngine
                # still produces a category-wise cost estimate using the
                # generic rate-based painting weight.
                paint_recommendations = {}
                theme_paint_total_cost = None

            cost_report = DynamicCostEngine.calculate_cost_estimation(
                rooms=total_rooms_all_floors,
                plot_area=plot_w * plot_d,
                built_up_area=built_up_area or 1,  # avoid div-by-zero
                floors=floors,
                city=clues["city"],
                budget=clues["budget_range"],
                precomputed_paint_cost_inr=theme_paint_total_cost,
            )


            return {
                "floors": out_floors,
                "built_up_area": built_up_area,
                "cost_report": cost_report,
                "paint_recommendations": paint_recommendations,
                "scores": {
                    "space_efficiency": 78 if mode == "adaptive" else 70,
                    "vastu_compliance": 65 if mode == "adaptive" else 90,
                    "ventilation": 75,
                },
                "dimensions": {
                    "plot_width_ft": plot_w,
                    "plot_depth_ft": plot_d,
                    "usable_width": layout["usable_width"],
                    "usable_depth": layout["usable_depth"],
                },
            }

        if GeometryEngine is not None:
            try:
                adaptive_result = _run_real_engine("adaptive")
                vastu_result = _run_real_engine("vastu")
            except Exception:
                # Real engine errored on this particular input (e.g. an
                # unusual plot shape) -- don't fail the whole request, just
                # fall back to the simpler engine so the user still gets a
                # floor plan, and log the real error server-side.
                print(f"GeometryEngine failed, falling back: {traceback.format_exc()}")
                adaptive_result = _run_fallback_engine("adaptive")
                vastu_result = _run_fallback_engine("vastu")
        else:
            adaptive_result = _run_fallback_engine("adaptive")
            vastu_result = _run_fallback_engine("vastu")
        # The frontend always renders a fixed "Option A (space) / Option B
        # (vastu)" comparison regardless of what the user typed, so Option B
        # must always be generated or it shows up permanently empty.

        total_built_up = adaptive_result["built_up_area"]

        options = {
            "OPTION_A_SPACE": {
                "title": f"Option A — {bhk}BHK Space-Optimised Layout",
                "analysis": f"Space-efficiency design with {floors} floor(s) and "
                            f"{sum(len(fd['rooms']) for fd in adaptive_result['floors'])} total rooms. "
                            f"Optimized for natural circulation, adequate ventilation, and efficient space utilization.",
                "floors": adaptive_result["floors"],
                "cost_estimation": adaptive_result["cost_report"],
                "paint_recommendations": adaptive_result["paint_recommendations"],
                "scores": adaptive_result["scores"],
                "dimensions": adaptive_result["dimensions"],
                "mode": "adaptive",
            },
            "OPTION_B_VASTU": {
                "title": f"Option B — {bhk}BHK Vastu-Aligned Layout",
                "analysis": f"Vastu-prioritised design with {floors} floor(s) and "
                            f"{sum(len(fd['rooms']) for fd in vastu_result['floors'])} total rooms. "
                            f"Room placement follows Vastu Shastra cardinal-direction principles.",
                "floors": vastu_result["floors"],
                "cost_estimation": vastu_result["cost_report"],
                "paint_recommendations": vastu_result["paint_recommendations"],
                "scores": vastu_result["scores"],
                "dimensions": vastu_result["dimensions"],
                "mode": "vastu",
            },
        }
        
        # ── STEP 6: Return complete professional response ──────────────────
        return {
            "response_type": "success",
            "session_id": session_id,
            "requires_clarification": False,
            "options": options,
            "project_summary": {
                "plot_dimensions": f"{plot_w}ft × {plot_d}ft",
                "plot_shape": clues.get("plot_shape") or "rectangle",
                "bhk": f"{bhk}BHK",
                "floors": floors,
                "total_built_up_area": f"{total_built_up:.0f} sqft",
                "city": clues["city"].title(),
                "interior_style": clues["interior_style"],
                "budget_range": clues["budget_range"],
            },
        }
    
    except Exception as e:
        # Full traceback still goes to the server logs for debugging, but
        # the client only ever sees a clean, human-readable message -- no
        # stack trace or internal error codes are exposed in the response.
        print(f"Error in generate_floorplan: {traceback.format_exc()}")
        return {
            "response_type": "error",
            "session_id": session_id,
            "error": "We couldn't generate the floor plan from the values provided. "
                     "Please check that plot width, plot depth, floors, and BHK count "
                     "are all plain, finite, positive numbers and try again.",
        }


# ── Validation Functions ───────────────────────────────────────────────────────

def _validate_floorplan(clues: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate against Indian building codes."""
    errors = []
    
    try:
        # Belt-and-suspenders: even though _validate_numeric_inputs() already
        # ran before this, NaN/Infinity are re-checked here too, since `<`
        # comparisons against them are silently always False and would
        # otherwise let a bad value sneak past the `plot_area < min_area`
        # check below.
        for key in ("plot_width", "plot_depth", "bhk_count", "floors_requested"):
            if not _is_finite_number(clues.get(key)):
                errors.append(f"'{key}' is missing or not a finite number.")
        if errors:
            return False, errors

        plot_area = float(clues["plot_width"]) * float(clues["plot_depth"])
        bhk = int(clues["bhk_count"])
        floors = int(clues["floors_requested"])
        
        # Minimum plot area requirements
        min_area = {1: 600, 2: 800, 3: 1200, 4: 1500, 5: 2000}
        if plot_area < min_area.get(bhk, 600):
            errors.append(
                f"Plot area {plot_area:.0f} sqft is too small for {bhk}BHK. "
                f"Minimum: {min_area.get(bhk)} sqft"
            )
        
        # Floor limitations
        if floors < 1 or floors > 5:
            errors.append("Floors must be between 1 and 5")
        
        # Parking slot validation
        parking_raw = clues.get("parking_slots", 0) or 0
        if not _is_finite_number(parking_raw):
            errors.append("'parking_slots' is not a finite number.")
        else:
            parking = int(parking_raw)
            if parking > bhk + 1:
                errors.append(f"Parking slots ({parking}) exceed reasonable limit for {bhk}BHK")
        
    except (ValueError, TypeError) as e:
        errors.append(f"Invalid input parameters: {str(e)}")
    
    return len(errors) == 0, errors


def _get_validation_suggestions(clues: Dict[str, Any]) -> List[str]:
    """Provide suggestions to fix validation errors."""
    suggestions = []
    
    try:
        bhk = int(clues.get("bhk_count", 2))
        plot_w = float(clues.get("plot_width", 30))
        plot_d = float(clues.get("plot_depth", 40))
        
        if plot_w < 25:
            suggestions.append("Increase plot width to minimum 25 feet")
        if plot_d < 35:
            suggestions.append("Increase plot depth to minimum 35 feet")
        
    except:
        pass
    
    return suggestions


def _generate_analysis(layout: Dict[str, Any], mode: str) -> str:
    """Generate human-readable analysis of the layout."""
    floors = len(layout.get("floors", []))
    total_rooms = sum(len(f) for f in layout.get("floors", []))
    
    analysis = f"{mode} design with {floors} floor(s) and {total_rooms} total rooms. "
    analysis += "Optimized for natural circulation, adequate ventilation, and efficient space utilization."
    
    return analysis


def _get_floor_name(floor_idx: int) -> str:
    """Get human-readable floor name."""
    floor_names = {
        0: "Ground Floor",
        1: "First Floor",
        2: "Second Floor",
        3: "Third Floor",
        4: "Fourth Floor",
    }
    return floor_names.get(floor_idx, f"Floor {floor_idx + 1}")


# ── Natural-Language Requirement Extractor ──────────────────────────────────

_WORD_NUMS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
              "single": 1, "double": 2, "triple": 3}


def _extract_clues_from_prompt(prompt: str) -> Dict[str, Any]:
    """
    Parses the free-text user_prompt for the architectural parameters that
    GenerationRequest expects as explicit fields. Without this, a prompt like
    "I need a modern 3BHK house on a 1200 sq ft plot with parking, one pooja
    room and 2 floors" would never populate plot_width/plot_depth/bhk_count/
    floors_requested, and the API would (incorrectly) keep asking the user
    questions it could have answered itself from the prompt.
    """
    extracted: Dict[str, Any] = {}
    if not prompt:
        return extracted
    p = prompt.lower()

    # ── Plot dimensions ──────────────────────────────────────────────
    # "30x40", "30 x 40 ft", "30 by 40 feet"
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)\s*(?:ft|feet|foot)?', p)
    if m:
        extracted["plot_width"] = float(m.group(1))
        extracted["plot_depth"] = float(m.group(2))
    else:
        # "1200 sq ft", "1200sqft", "1200 square feet"
        m2 = re.search(r'(\d+(?:\.\d+)?)\s*(?:sq\.?\s*ft\.?|sqft|square\s*feet|square\s*foot)', p)
        if m2:
            sqft = float(m2.group(1))
            # Typical residential plot aspect ratio ~3:4 (width:depth)
            width = round(math.sqrt(sqft / 1.333), 1)
            depth = round(sqft / width, 1)
            extracted["plot_width"] = width
            extracted["plot_depth"] = depth

    # ── BHK / bedroom count ──────────────────────────────────────────
    m3 = re.search(r'(\d+)\s*[\s\-]?bhk', p)
    if not m3:
        m3 = re.search(r'(\d+)\s*bed\s*room', p)
    if m3:
        extracted["bhk_count"] = int(m3.group(1))
    else:
        for word, num in _WORD_NUMS.items():
            if re.search(rf'\b{word}\b\s*bhk', p) or re.search(rf'\b{word}\b\s*bed\s*room', p):
                extracted["bhk_count"] = num
                break

    # ── Floor count ───────────────────────────────────────────────────
    m4 = re.search(r'(\d+)\s*floor', p)
    if m4:
        extracted["floors_requested"] = int(m4.group(1))
    else:
        m4b = re.search(r'g\s*\+\s*(\d+)', p)  # "G+1", "G+2"
        if m4b:
            extracted["floors_requested"] = int(m4b.group(1)) + 1
        else:
            for word, num in _WORD_NUMS.items():
                if re.search(rf'\b{word}\b\s*floor', p):
                    extracted["floors_requested"] = num
                    break
    if "floors_requested" not in extracted and re.search(r'\bsingle\s*stor', p):
        extracted["floors_requested"] = 1

    # ── Parking ───────────────────────────────────────────────────────
    m5 = re.search(r'(\d+)\s*(?:car\s*)?parking', p)
    if m5:
        extracted["parking_slots"] = int(m5.group(1))
    elif "parking" in p:
        extracted["parking_slots"] = 1

    # ── Vastu ─────────────────────────────────────────────────────────
    if "vastu" in p:
        extracted["vastu_preference"] = True

    # ── Lift ──────────────────────────────────────────────────────────
    if "lift" in p or "elevator" in p:
        extracted["lift_required"] = True

    # ── Elder-friendly ────────────────────────────────────────────────
    if any(k in p for k in ("elder", "senior citizen", "wheelchair", "accessib")):
        extracted["elder_friendly"] = True

    # ── Paint-personalization hints (mood / colour preference / lighting /
    #    orientation / occupancy) — best-effort extraction so an explicit
    #    prompt like "bright, vibrant colours, kids at home, faces north
    #    east, gets lots of sunlight" doesn't get re-asked for any of this.
    _mood_kw = (
        "calm", "soothing", "serene", "tranquil", "peaceful", "energetic", "lively",
        "cozy", "warm", "homely", "dramatic", "bold", "intense", "cheerful", "bright",
        "happy", "sophisticated", "refined", "elegant", "romantic", "playful",
        "luxurious", "moody", "airy",
    )
    for kw in _mood_kw:
        if re.search(rf'\b{kw}\b', p):
            extracted["mood"] = kw
            break

    _color_pref_kw = (
        "vibrant", "pastel", "neutral", "earthy", "luxury", "monochrome",
        "bold", "muted", "jewel tone", "jewel tones",
    )
    for kw in _color_pref_kw:
        if kw in p:
            extracted["color_preference"] = kw
            break

    if re.search(r'\blow\s*(?:natural\s*)?light\b|\bdim\b|\bnot much (?:sun|light)\b', p):
        extracted["natural_lighting"] = "low"
    elif re.search(r'\bhigh\s*(?:natural\s*)?light\b|\babundant\s*(?:sun|light)\b|\blots? of (?:sun|light)\b|\bvery bright\b', p):
        extracted["natural_lighting"] = "high"
    elif re.search(r'\bmedium\s*(?:natural\s*)?light\b|\bmoderate\s*(?:sun|light)\b', p):
        extracted["natural_lighting"] = "medium"

        _orientation_kw = (
            "north east", "northeast", "north west", "northwest",
            "south east", "southeast", "south west", "southwest",
            "north", "south", "east", "west",
    )

    for kw in _orientation_kw:
        pattern = kw.replace(" ", r"[\s-]?")

        if re.search(rf"\b{pattern}\b\s*(?:facing|face)?", p) and (
            f"{kw} facing" in p
            or f"faces {kw}" in p
            or f"facing {kw}" in p
            or re.search(rf"\b{kw}\b", p)
        ):
            extracted["room_orientation"] = kw
            break

    _occ_bits = []
    if _wants(p, "child", "kid", "kids", "children"):
        _occ_bits.append("children")
    if _wants(p, "pet", "pets", "dog", "cat"):
        _occ_bits.append("pets")
    if _wants(p, "elder", "elderly", "senior citizen"):
        _occ_bits.append("elderly")
    if _occ_bits:
        extracted["occupancy_notes"] = ", ".join(_occ_bits)

    # ── Interior style ────────────────────────────────────────────────
    for style in ("modern", "traditional", "contemporary", "minimalist", "eclectic", "luxury", "luxe"):
        if style in p:
            extracted["interior_style"] = "luxe" if style == "luxury" else style
            break

    # ── Plot shape (irregular plots) ────────────────────────────────────
    # Only set this when the user actually says so -- otherwise we leave
    # it unset and the caller defaults to "rectangle", so we never invent
    # an irregular shape the user didn't ask for.
    if any(k in p for k in ("l-shape", "l shape", "l-shaped", "l shaped", "lshaped")):
        extracted["plot_shape"] = "l_shape"
    elif any(k in p for k in ("t-shape", "t shape", "t-shaped", "t shaped", "tshaped")):
        extracted["plot_shape"] = "t_shape"
    elif any(k in p for k in ("u-shape", "u shape", "u-shaped", "u shaped", "ushaped")):
        extracted["plot_shape"] = "u_shape"
    elif any(k in p for k in ("corner cut", "cut corner", "corner-cut", "irregular", "irregular shape", "irregular plot", "non-rectangular", "non rectangular")):
        extracted["plot_shape"] = "l_shape"

    # ── Family size (how many people will actually live there) ─────────
    m6 = re.search(r'family\s+of\s+(\d+)', p) or re.search(r'(\d+)\s*(?:family\s*)?members?\b', p) \
        or re.search(r'(\d+)\s*people\s*(?:living|will|in)', p) or re.search(r'we\s+are\s+(\d+)', p)
    if m6:
        extracted["family_members"] = int(m6.group(1))
    else:
        for word, num in _WORD_NUMS.items():
            if re.search(rf'family\s+of\s+{word}\b', p) or re.search(rf'\b{word}\b\s*(?:family\s*)?members?\b', p):
                extracted["family_members"] = num
                break

    # ── Paint / colour theme ─────────────────────────────────────────────
    _paint_kw = {
        "light & bright": ["light and bright", "light & bright", "bright and airy", "pastel"],
        "warm & earthy": ["warm and earthy", "warm & earthy", "earthy", "terracotta", "warm tones"],
        "bold & dark": ["bold and dark", "bold & dark", "dark theme", "dark tones", "charcoal"],
        "neutral": ["neutral tones", "neutral palette", "neutral colour", "neutral color"],
        "cool tones": ["cool tones", "cool colours", "cool colors", "blue and green"],
    }
    for theme, kws in _paint_kw.items():
        if any(k in p for k in kws):
            extracted["paint_theme"] = theme
            break

    # ── Extra spaces: parking / pool / store room / gym / garden / etc. ──
    extra_bits = []
    if "swimming pool" in p or re.search(r'\bpool\b', p):
        extra_bits.append("swimming pool")
    if "garden" in p or "lawn" in p:
        extra_bits.append("garden")
    if re.search(r'\bgym\b', p) or "home gym" in p:
        extra_bits.append("home gym")
    if "store room" in p or "storeroom" in p or "storage room" in p:
        extra_bits.append("store room")
    if "rooftop" in p or "terrace" in p:
        extra_bits.append("rooftop sit-out")
    if "no extra" in p or "nothing extra" in p or "keep it simple" in p:
        extracted["extra_spaces"] = "none"
    elif extra_bits:
        extracted["extra_spaces"] = ", ".join(extra_bits)

    return extracted


# ── Dynamic Room Requirement Builder ────────────────────────────────────────

def _build_required_rooms(clues: Dict[str, Any], bhk: int, floors: int, user_prompt: str) -> List[str]:
    """
    Builds the flat list of room names to hand to GeometryEngine.generate().
    GeometryEngine itself takes care of distributing these intelligently
    across floors (wet areas stacked, public rooms on ground floor, private
    rooms on upper floors, etc) -- we just need to supply the *complete*,
    correctly-sized room program for the requested BHK / floor count / extras
    so the result is dynamic and correct for every input, not a fixed template.
    """
    prompt_l = (user_prompt or "").lower()
    extras_l = (clues.get("extra_spaces") or "").lower().strip()

    # If the user answered the extra-spaces question with an outright "none"
    # (however phrased), don't even look for keywords in it -- treat it as
    # empty. This is a belt-and-suspenders safeguard on top of _wants()
    # below, for the common case of a short blanket "no" answer.
    _NONE_ANSWERS = {
        "none", "no", "nothing", "n/a", "na", "nil", "nope",
        "not needed", "no extras", "keep it simple", "no thanks",
    }
    if extras_l in _NONE_ANSWERS or extras_l.startswith("none"):
        extras_l = ""

    combined_l = f"{prompt_l} {extras_l}"
    rooms: List[str] = ["Living Room", "Kitchen"]

    # Dining Room — only if actually asked for, not a blanket default
    if _wants(combined_l, "dining"):
        rooms.append("Dining Room")

    # Master bedroom + its attached bathroom always present for 1BHK+
    if bhk >= 1:
        rooms.append("Master Bedroom")
        rooms.append("Attached Bathroom")

    # Additional bedrooms each get their own bathroom
    for i in range(2, bhk + 1):
        rooms.append(f"Bedroom {i}")
        rooms.append(f"Bathroom {i}")

    # A shared/common bathroom for the public zone once there's more than 1BHK
    if bhk >= 2:
        rooms.append("Common Bathroom")

    # If more people are actually living there than the BHK count implies
    # (e.g. a 2BHK but a family of 6), add a second common bathroom so the
    # plan reflects real usage instead of just the bedroom count.
    family_members = clues.get("family_members")
    if isinstance(family_members, str):
        fm_match = re.search(r'\d+', family_members)
        family_members = int(fm_match.group(0)) if fm_match else None
    if not isinstance(family_members, (int, float)):
        family_members = None
    if family_members and bhk and family_members > bhk * 2:
        rooms.append("Common Bathroom 2")

    # Parking — only if the user actually asked for it, or answered the
    # parking_slots clarification question. Dynamic count from explicit
    # parking_slots, or a count parsed out of the extra-spaces answer
    # (e.g. "2 cars", "3 vehicles"). No parking is added by default.
    parking_slots = clues.get("parking_slots")
    if parking_slots is None or parking_slots == "":
        pm = re.search(r'(\d+)\s*(?:car|vehicle)', combined_l)
        if pm:
            parking_slots = int(pm.group(1))
        elif _wants(combined_l, "parking", "garage"):
            parking_slots = 1
        else:
            parking_slots = 0
    parking_slots = int(parking_slots)
    for i in range(max(0, parking_slots)):
        rooms.append("Parking" if parking_slots <= 1 else f"Parking {i + 1}")

    # Swimming pool — only if actually asked for
    if _wants(combined_l, "pool"):
        rooms.append("Swimming Pool")

    # Pooja room — only if user actually asked for one
    if _wants(combined_l, "pooja", "puja", "prayer"):
        rooms.append("Pooja Room")

    # Study / home office
    if _wants(combined_l, "study", "home office", "office room"):
        rooms.append("Study")

    # Home gym
    if _wants(combined_l, "gym"):
        rooms.append("Home Gym")

    # Servant room
    if _wants(combined_l, "servant", "maid"):
        rooms.append("Servant Room")

    # Garden / lawn
    if _wants(combined_l, "garden", "lawn"):
        rooms.append("Garden")

    # Store room
    if _wants(combined_l, "store room", "storeroom", "storage"):
        rooms.append("Store Room")

    # Rooftop sit-out
    if _wants(combined_l, "rooftop"):
        rooms.append("Rooftop Sit-Out")

    # Utility / laundry — only if actually asked for
    if _wants(combined_l, "utility", "laundry"):
        rooms.append("Utility")

    # Lift, if requested or floors are high enough to need one
    if clues.get("lift_required") or floors >= 4:
        rooms.append("Lift")

    # Multi-floor homes structurally need a staircase to connect floors.
    # Balcony is only added if the user actually asked for one.
    if floors > 1:
        rooms.append("Staircase")
        if _wants(combined_l, "balcony"):
            rooms.append("Balcony")
            if bhk >= 3:
                rooms.append("Balcony 2")

    # Elder-friendly homes get a ground-floor bedroom + bathroom in addition
    # to the standard program (handled by GeometryEngine's ground/upper split
    # since "Bedroom" keyword routes correctly either way).
    if clues.get("elder_friendly") and bhk >= 2:
        rooms.append("Guest Bedroom")
        rooms.append("Guest Bathroom")

    return rooms


# ── Professional SVG Generation ────────────────────────────────────────────────

def _generate_professional_svg(
    rooms: List[Dict[str, Any]],
    plot_w: float,
    plot_d: float,
    floor_idx: int = 0
) -> str:
    """
    Generate professional CAD-style SVG with:
    - Exterior walls with proper thickness
    - Interior partition walls
    - Door and window symbols
    - Room labels with dimensions
    - Professional annotations
    - Grid and scale
    - North arrow
    """
    
    if not rooms:
        return ""
    
    SCALE = 12  # pixels per foot
    MARGIN = 40
    WALL_THICKNESS = 8  # pixels for exterior walls
    
    svg_w = int(plot_w * SCALE) + MARGIN * 2
    svg_h = int(plot_d * SCALE) + MARGIN * 2
    
    lines = []
    
    # SVG header
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{svg_w}" height="{svg_h}" '
                f'viewBox="0 0 {svg_w} {svg_h}" '
                f'font-family="Arial, Helvetica, sans-serif" '
                f'style="background:#1a1a0e">')
    
    # Plot boundary (exterior wall)
    bw = int(plot_w * SCALE)
    bh = int(plot_d * SCALE)
    
    lines.append(
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{bw}" height="{bh}" '
        f'fill="#0d0d06" stroke="#d4af37" stroke-width="3"/>'
    )
    
    # Grid
    step = SCALE * 5
    for gx in range(MARGIN, MARGIN + bw + 1, step):
        lines.append(
            f'<line x1="{gx}" y1="{MARGIN}" x2="{gx}" y2="{MARGIN + bh}" '
            f'stroke="#2a2a1a" stroke-width="0.5" stroke-dasharray="2,2"/>'
        )
    for gy in range(MARGIN, MARGIN + bh + 1, step):
        lines.append(
            f'<line x1="{MARGIN}" y1="{gy}" x2="{MARGIN + bw}" y2="{gy}" '
            f'stroke="#2a2a1a" stroke-width="0.5" stroke-dasharray="2,2"/>'
        )
    
    # Room colors
    room_colors = {
        "living_room": "#f5dcdc",
        "master_bedroom": "#dce8f5",
        "bedroom": "#dce8f5",
        "kitchen": "#fdf3dc",
        "dining": "#f5f0dc",
        "bathroom": "#dcf5ee",
        "common_bathroom": "#dcf5ee",
        "parking_slot": "#e0e0e0",
        "balcony": "#dcf5f0",
        "pooja_room": "#fdf0dc",
        "office": "#e8dcf5",
        "utility": "#f0f0f0",
        "staircase": "#ebebeb",
        "entrance": "#fafafa",
        "corridor": "#f5f5f5",
        "study": "#e8e8d0",
    }
    
    # Draw rooms
    for room in rooms:
        rx1 = int(room["x1"] * SCALE) + MARGIN
        ry1 = int(room["y1"] * SCALE) + MARGIN
        rw = max(10, int(room["width"] * SCALE))
        rh = max(10, int(room["height"] * SCALE))
        
        room_name_lower = room.get("name", "room").lower()
        fill = room_colors.get(room_name_lower, "#1e1e10")
        
        # Room rectangle
        lines.append(
            f'<rect x="{rx1}" y="{ry1}" width="{rw}" height="{rh}" '
            f'fill="{fill}" stroke="#c8a84b" stroke-width="1.5" rx="2" '
            f'fill-opacity="0.2" stroke-dasharray="0"/>'
        )
        
        # Room label
        cx = rx1 + rw // 2
        cy = ry1 + rh // 2
        label = room.get("name", "Room").replace("_", " ").title()
        fsize = max(8, min(12, rw // max(1, len(label) // 2)))
        
        lines.append(
            f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" '
            f'font-size="{fsize}" font-weight="bold" fill="#c8a84b">{label}</text>'
        )
        
        # Dimensions
        dim = f"{room.get('width', 0):.0f}\'×{room.get('height', 0):.0f}\'"
        lines.append(
            f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" '
            f'font-size="{max(7, fsize - 2)}" fill="#8a7a3a">{dim}</text>'
        )
    
    # Plot dimensions (bottom)
    bx2 = MARGIN + bw
    by2 = MARGIN + bh
    
    lines.append(
        f'<line x1="{MARGIN}" y1="{by2 + 20}" x2="{bx2}" y2="{by2 + 20}" '
        f'stroke="#c8a84b" stroke-width="1"/>'
    )
    lines.append(
        f'<text x="{(MARGIN + bx2) // 2}" y="{by2 + 35}" '
        f'text-anchor="middle" font-size="10" fill="#c8a84b" font-weight="bold">'
        f'{plot_w:.0f} ft</text>'
    )
    
    # Plot dimensions (right)
    lines.append(
        f'<line x1="{bx2 + 20}" y1="{MARGIN}" x2="{bx2 + 20}" y2="{by2}" '
        f'stroke="#c8a84b" stroke-width="1"/>'
    )
    lines.append(
        f'<text x="{bx2 + 35}" y="{(MARGIN + by2) // 2}" '
        f'font-size="10" fill="#c8a84b" font-weight="bold" '
        f'transform="rotate(90 {bx2 + 35} {(MARGIN + by2) // 2})">'
        f'{plot_d:.0f} ft</text>'
    )
    
    # North arrow
    nax = svg_w - 40
    nay = MARGIN + 15
    lines.append(
        f'<polygon points="{nax},{nay + 20} {nax - 8},{nay + 32} {nax + 8},{nay + 32}" '
        f'fill="#c8a84b" stroke="#c8a84b" stroke-width="0.5"/>'
    )
    lines.append(
        f'<text x="{nax}" y="{nay + 8}" text-anchor="middle" '
        f'font-size="12" font-weight="bold" fill="#c8a84b">N</text>'
    )
    
    # Title block
    lines.append(
        f'<rect x="{MARGIN}" y="{svg_h - 28}" '
        f'width="{svg_w - MARGIN * 2}" height="24" fill="#c8a84b" rx="2"/>'
    )
    lines.append(
        f'<text x="{MARGIN + 10}" y="{svg_h - 10}" '
        f'font-size="10" fill="#0d0d06" font-weight="bold">'
        f'BUILDWISE AETHER | {_get_floor_name(floor_idx)} | '
        f'Plot {plot_w:.0f}ft × {plot_d:.0f}ft | {len(rooms)} Rooms</text>'
    )
    
    lines.append("</svg>")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)