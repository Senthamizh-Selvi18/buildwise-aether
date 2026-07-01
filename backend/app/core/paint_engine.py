# app/core/paint_engine.py
#
# Generative Paint Recommendation Engine (v2)
# ─────────────────────────────────────────────────────────────────────────
# WHY THIS EXISTS
# The previous engine (see git history) picked colours from a fixed
# THEME_LIBRARY of ~20 hardcoded named swatches ("Cosmic Navy #0b1026",
# "Sage Leaf #9caf88", ...). Two different projects that matched the same
# theme keyword always got byte-identical colours, and any input that
# wasn't one of ~20 pre-written theme names silently fell back to a
# generic "modern" palette. That is not personalization -- it's a lookup
# table wearing a personalization costume.
#
# This engine instead COMPUTES colour, every time, from the actual
# project inputs:
#   room type, interior style, mood, colour preference, natural lighting,
#   room orientation, climate/city, budget, Vastu preference, occupancy
#   (children / elderly / pets)
#
# It does this with real colour theory (HSL hue/saturation/lightness
# math via `colorsys`), not a swatch table:
#   - each input contributes a small, explainable nudge to a hue/
#     saturation/lightness vector (mood sets the emotional hue anchor,
#     colour-preference sets saturation/lightness range, style adds a
#     hue lean + contrast character, natural light and orientation
#     compensate for the room's actual daylight, Vastu -- when opted
#     in -- blends in the direction's traditional hue association,
#     climate adjusts for perceived warmth/coolness and humidity,
#     occupancy adjusts brightness/contrast/durability for safety).
#   - a project+room specific hash seeds a small, deterministic jitter
#     so two rooms -- or two projects -- are never forced into identical
#     output just because their categorical inputs matched.
#   - wall / ceiling / accent / trim are derived from that one base
#     colour using real colour-harmony relationships (analogous /
#     complementary offsets, tint/shade), not picked from a second
#     "accent colours" table.
#
# If the caller hasn't supplied enough preference to make a personalized
# call (see REQUIRED_PREFERENCE_QUESTIONS below), the engine refuses to
# guess silently -- PaintEngine.generate() returns status="needs_input"
# with the specific follow-up questions to ask, instead of generating a
# recommendation built on an unstated assumption.

from __future__ import annotations

import colorsys
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

Swatch = Tuple[float, float, float]  # (hue 0-360, saturation 0-100, lightness 0-100)


# ── Public data model ───────────────────────────────────────────────────

@dataclass
class PaintPreferences:
    interior_style: Optional[str] = None       # "modern", "scandinavian", "bohemian", free text OK
    mood: Optional[str] = None                 # "calm", "energetic", "cozy", "dramatic", free text OK
    color_preference: Optional[str] = None      # "vibrant", "pastel", "neutral", "earthy", "luxury", ...
    natural_lighting: Optional[str] = None       # "low", "medium", "high" / descriptive
    room_orientation: Optional[str] = None       # "north", "south-east", ... (per-room or house facing)
    climate: Optional[str] = None               # "hot & humid", "cold", "temperate", free text OK
    city: Optional[str] = None                  # used as a climate fallback signal, and for the brand/cost tier note
    budget: Optional[str] = None                # "economy"/"budget", "mid"/"standard", "premium", "luxury"
    vastu_preference: Optional[bool] = None      # None = unanswered (tri-state, unlike a plain bool)
    occupancy: Optional[List[str]] = None        # e.g. ["children","elderly","pets"]; [] = explicitly none
    extra_notes: Optional[str] = None            # any other free text (adds a small personalization nudge)


@dataclass
class SurfaceColor:
    hex: str
    name: str
    hue: float
    saturation: float
    lightness: float
    temperature: str  # "warm" | "cool" | "neutral"


@dataclass
class PaintRecommendation:
    room_name: str
    wall: SurfaceColor
    ceiling: SurfaceColor
    accent: SurfaceColor
    trim: SurfaceColor
    wall_finish: str
    ceiling_finish: str
    accent_finish: str
    trim_finish: str
    washability: str
    durability_years: int
    moisture_resistant: bool
    coverage_sqft_per_liter: float
    liters_required: float
    cost_per_liter_inr: float
    total_cost_inr: float
    brand_tier: str
    rationale: str

    # ── Legacy field names (kept so this file is a drop-in replacement for
    #    the older PaintEngine -- any caller still reading rec.primary_hex,
    #    rec.finish_type, rec.recommended_for_moisture, etc. keeps working
    #    without main.py needing any changes at all) ─────────────────────
    primary_paint_name: str = ""
    primary_brand: str = ""
    primary_hex: str = ""
    primary_color_temp: str = ""
    accent_paint_name: str = ""
    accent_brand: str = ""
    accent_hex: str = ""
    finish_type: str = ""
    recommended_for_moisture: bool = False
    theme_detected: str = ""
    matched_keywords: List[str] = field(default_factory=list)

    def _fill_legacy_aliases(self) -> "PaintRecommendation":
        self.primary_paint_name = self.wall.name
        self.primary_brand = self.brand_tier
        self.primary_hex = self.wall.hex
        self.primary_color_temp = self.wall.temperature
        self.accent_paint_name = self.accent.name
        self.accent_brand = self.brand_tier
        self.accent_hex = self.accent.hex
        self.finish_type = self.wall_finish
        self.recommended_for_moisture = self.moisture_resistant
        return self


@dataclass
class PaintEngineResult:
    status: str  # "ok" | "needs_input"
    recommendations: List[PaintRecommendation] = field(default_factory=list)
    missing_preferences: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None


# ── Required preferences & the questions used to fill gaps ─────────────

REQUIRED_PREFERENCE_QUESTIONS: Dict[str, str] = {
    "interior_style": "What interior style are you going for — modern, traditional, minimalist, "
                       "industrial, scandinavian, bohemian, rustic, coastal, art deco, or luxury?",
    "mood": "What mood should the space evoke — calm & soothing, energetic & lively, cozy & warm, "
            "dramatic & bold, cheerful & bright, sophisticated, romantic, playful, or serene?",
    "color_preference": "What colour intensity do you prefer — vibrant, pastel, neutral, earthy, "
                         "monochrome, muted, bold, or rich luxury tones?",
    "natural_lighting": "How much natural light does this space get through the day — low, "
                         "medium, or high/abundant?",
    "room_orientation": "Which direction does this room mainly face — north, south, east, west, "
                         "or an in-between direction like north-east?",
    "climate": "What's the climate like where you're building — hot & humid, hot & dry, cold, "
               "or moderate/temperate? (Your city name works too.)",
    "budget": "What's your paint budget tier — economy, standard/mid-range, premium, or luxury?",
    "vastu_preference": "Should the colour choices follow Vastu Shastra directional guidelines? (yes/no)",
    "occupancy": "Who will be using this space — any young children, elderly family members, or "
                 "pets? (Say 'none' if not applicable.)",
}


# ── Colour-theory input tables ───────────────────────────────────────────
# IMPORTANT: these are not finished colours. Every entry is a small
# NUMERIC NUDGE (hue degrees / saturation points / lightness points) that
# gets blended together mathematically. The actual hex colour is always
# computed at the end via HSL->RGB, never looked up.

# mood -> (hue_anchor_degrees, saturation_delta, lightness_delta)
MOOD_HUE_ANCHORS: Dict[str, Swatch] = {
    "calm": (195, -14, 10), "soothing": (195, -14, 11), "serene": (200, -17, 12),
    "tranquil": (198, -15, 11), "peaceful": (150, -10, 10),
    "energetic": (24, 22, -6), "lively": (18, 24, -6), "vibrant mood": (335, 26, -8),
    "cozy": (28, 10, 5), "warm": (30, 8, 6), "homely": (32, 8, 6),
    "dramatic": (255, 16, -20), "bold": (350, 20, -12), "intense": (5, 18, -16),
    "cheerful": (45, 18, 8), "bright": (48, 15, 9), "happy": (44, 17, 8),
    "sophisticated": (230, -6, -10), "refined": (235, -8, -8), "elegant": (262, -4, -6),
    "romantic": (335, 6, 8), "playful": (165, 15, 5),
    "luxurious": (270, 10, -8), "moody": (250, 12, -18), "airy": (200, -12, 16),
}

# interior style -> {hue_bias_degrees(optional), saturation_multiplier, contrast_character}
STYLE_PROFILES: Dict[str, Dict[str, Any]] = {
    "modern": {"hue_bias": None, "sat_mult": 0.85, "contrast": "medium"},
    "contemporary": {"hue_bias": None, "sat_mult": 0.85, "contrast": "medium"},
    "minimalist": {"hue_bias": None, "sat_mult": 0.40, "contrast": "low"},
    "traditional": {"hue_bias": 32, "sat_mult": 0.90, "contrast": "medium"},
    "industrial": {"hue_bias": None, "sat_mult": 0.30, "contrast": "high"},
    "scandinavian": {"hue_bias": 205, "sat_mult": 0.30, "contrast": "low"},
    "bohemian": {"hue_bias": 32, "sat_mult": 1.20, "contrast": "high"},
    "boho": {"hue_bias": 32, "sat_mult": 1.20, "contrast": "high"},
    "rustic": {"hue_bias": 36, "sat_mult": 0.75, "contrast": "medium"},
    "farmhouse": {"hue_bias": 40, "sat_mult": 0.60, "contrast": "medium"},
    "coastal": {"hue_bias": 195, "sat_mult": 0.60, "contrast": "low"},
    "luxe": {"hue_bias": 268, "sat_mult": 0.80, "contrast": "high"},
    "luxury": {"hue_bias": 268, "sat_mult": 0.80, "contrast": "high"},
    "eclectic": {"hue_bias": None, "sat_mult": 1.10, "contrast": "high"},
    "japandi": {"hue_bias": 60, "sat_mult": 0.30, "contrast": "low"},
    "art deco": {"hue_bias": 46, "sat_mult": 0.90, "contrast": "high"},
    "mid-century": {"hue_bias": 30, "sat_mult": 0.80, "contrast": "medium"},
}

# colour preference -> {sat_mult, light_shift, accent_sat_boost, hue_bias(optional)}
COLOR_PREFERENCE_PROFILES: Dict[str, Dict[str, Any]] = {
    "vibrant": {"sat_mult": 1.50, "light_shift": -5, "accent_sat_boost": 28, "hue_bias": None},
    "pastel": {"sat_mult": 0.50, "light_shift": 22, "accent_sat_boost": 5, "hue_bias": None},
    "neutral": {"sat_mult": 0.22, "light_shift": 8, "accent_sat_boost": 8, "hue_bias": None},
    "earthy": {"sat_mult": 0.68, "light_shift": -2, "accent_sat_boost": 10, "hue_bias": 36},
    "luxury": {"sat_mult": 0.85, "light_shift": -6, "accent_sat_boost": 16, "hue_bias": 46},
    "monochrome": {"sat_mult": 0.05, "light_shift": 0, "accent_sat_boost": 0, "hue_bias": None},
    "bold": {"sat_mult": 1.60, "light_shift": -10, "accent_sat_boost": 30, "hue_bias": None},
    "muted": {"sat_mult": 0.40, "light_shift": 5, "accent_sat_boost": 5, "hue_bias": None},
    "jewel tones": {"sat_mult": 1.30, "light_shift": -16, "accent_sat_boost": 25, "hue_bias": None},
}

# room-orientation -> the traditional Vastu-Shastra hue association for that
# direction (used ONLY when vastu_preference is True), plus a one-line
# rationale fragment. Hue values reflect the conventional colour family
# recommended for each direction; low-saturation/near-white directions are
# encoded with a neutral hue and handled by the lightness/saturation math.
VASTU_DIRECTION_HUE: Dict[str, Tuple[float, str]] = {
    "north": (120, "green tones, associated with growth and prosperity"),
    "north east": (200, "light blue/white, keeping the sacred Ishaan corner pure and airy"),
    "northeast": (200, "light blue/white, keeping the sacred Ishaan corner pure and airy"),
    "east": (48, "soft white/light tones, associated with health and vitality"),
    "south east": (18, "light orange/pink, associated with energy (Agni corner)"),
    "southeast": (18, "light orange/pink, associated with energy (Agni corner)"),
    "south": (350, "warm pink/red undertones, used sparingly for balance"),
    "south west": (34, "earthy brown/beige tones, for grounding and stability"),
    "southwest": (34, "earthy brown/beige tones, for grounding and stability"),
    "west": (212, "blue/grey tones, associated with calm and reflection"),
    "north west": (46, "warm white/cream tones, supporting relationships and movement"),
    "northwest": (46, "warm white/cream tones, supporting relationships and movement"),
}

# orientation -> daylight-compensation nudge (hue_bias(optional), lightness_delta, note)
# Independent of Vastu: purely about balancing the *colour temperature of the
# actual daylight* the room receives.
ORIENTATION_LIGHT_ADJUST: Dict[str, Tuple[Optional[float], float, str]] = {
    "north": (35, 4, "warmed slightly to offset the cool, indirect north light"),
    "north east": (35, 4, "warmed slightly to offset the cool, indirect light"),
    "northeast": (35, 4, "warmed slightly to offset the cool, indirect light"),
    "south": (205, -3, "cooled slightly to balance the strong, warm south-facing sun"),
    "south west": (205, -4, "cooled slightly to offset intense warm afternoon sun"),
    "southwest": (205, -4, "cooled slightly to offset intense warm afternoon sun"),
    "east": (40, 2, "kept gently warm to complement soft morning light"),
    "south east": (30, 1, "kept warm-neutral to suit bright morning-to-noon light"),
    "southeast": (30, 1, "kept warm-neutral to suit bright morning-to-noon light"),
    "west": (215, -2, "cooled slightly to offset strong, warm evening glare"),
    "north west": (60, 2, "kept warm-neutral for balanced late-day light"),
    "northwest": (60, 2, "kept warm-neutral for balanced late-day light"),
}

# natural lighting descriptor -> (lightness_delta, saturation_delta, note)
NATURAL_LIGHT_ADJUST: Dict[str, Tuple[float, float, str]] = {
    "low": (10, -6, "brightened and slightly desaturated to compensate for limited daylight"),
    "dim": (11, -7, "brightened and slightly desaturated to compensate for limited daylight"),
    "medium": (2, 0, "kept close to true tone since daylight is moderate"),
    "moderate": (2, 0, "kept close to true tone since daylight is moderate"),
    "high": (-4, 4, "allowed to carry a touch more depth since the room is naturally bright"),
    "abundant": (-5, 5, "allowed to carry a touch more depth and saturation given the abundant daylight"),
    "bright": (-4, 4, "allowed to carry a touch more depth since the room is naturally bright"),
}

# climate descriptor -> (hue_bias(optional), lightness_delta, note)
CLIMATE_ADJUST: Dict[str, Tuple[Optional[float], float, str]] = {
    "hot": (205, 3, "leaned cooler and slightly lighter to feel refreshing in a hot climate"),
    "tropical": (205, 3, "leaned cooler and slightly lighter to feel refreshing in a tropical climate"),
    "humid": (205, 2, "leaned cooler to feel airy in a humid climate; finish upgraded for moisture resistance"),
    "coastal": (200, 3, "leaned cooler and airy to suit a coastal climate; finish upgraded for humidity"),
    "dry": (35, -1, "leaned slightly warmer, suited to a hot & dry climate"),
    "desert": (35, -1, "leaned slightly warmer, suited to an arid climate"),
    "cold": (30, -2, "leaned warmer and a touch deeper for a cold-climate, cocooning feel"),
    "hilly": (30, -1, "leaned warmer to suit a cooler hill climate"),
    "mountain": (30, -1, "leaned warmer to suit a cooler hill/mountain climate"),
    "temperate": (None, 0, "left balanced since the climate is moderate"),
    "moderate": (None, 0, "left balanced since the climate is moderate"),
}

# fallback city -> climate keyword, only used if `climate` wasn't given but `city` was
CITY_CLIMATE_HINTS: Dict[str, str] = {
    "mumbai": "humid", "chennai": "humid", "kochi": "humid", "goa": "humid",
    "kolkata": "humid", "bhubaneswar": "humid", "vizag": "humid", "visakhapatnam": "humid",
    "delhi": "hot", "jaipur": "dry", "ahmedabad": "dry", "nagpur": "hot",
    "bangalore": "temperate", "bengaluru": "temperate", "pune": "temperate",
    "hyderabad": "hot", "chandigarh": "cold", "shimla": "cold", "manali": "cold",
    "dehradun": "hilly", "ooty": "hilly", "coimbatore": "temperate",
}

# room type -> functional nudge (hue_offset_degrees, saturation_delta, lightness_delta).
# IMPORTANT: hue_offset is RELATIVE (added directly to whatever hue the
# mood/style/colour-preference/etc. inputs already computed), not an
# absolute hue to blend toward. That's what keeps a project's rooms
# reading as one coordinated palette (an interior designer's "family of
# colours") while still guaranteeing every room type lands on a distinct,
# recognisable member of that family instead of near-identical near-white
# variants. Offsets and deltas are deliberately non-zero and non-trivial
# for every room type -- kept architecturally sensible: e.g. pooja rooms
# lean toward purity/warm-gold, kitchens/bathrooms lean fresher/cooler,
# bedrooms lean calmer, entrances/dining lean warm and welcoming.
ROOM_TYPE_NUDGE: Dict[str, Tuple[Optional[float], float, float]] = {
    "living_room": (0, 3, 0),
    "kitchen": (22, 10, -3),
    "bathroom": (48, 8, 5), "common_bathroom": (48, 8, 5), "guest_bathroom": (48, 8, 5),
    "bedroom": (-28, -6, 5), "master_bedroom": (-28, -4, 5), "guest_bedroom": (-32, -7, 5),
    "pooja": (58, -8, 12), "pooja_room": (58, -8, 12),
    "office": (-16, 2, -2), "study": (-16, 2, -2),
    "dining": (14, 9, 1),
    "entrance": (9, 11, -2),
    "corridor": (-12, -3, 4), "staircase": (-9, -2, 5),
    "home_gym": (30, 18, -6), "utility": (-20, -1, 3),
    "storeroom": (-24, -8, 2), "store_room": (-24, -8, 2),
    "servant_room": (-18, -5, 3), "balcony": (46, 6, 4),
    "parking": (-34, -10, -2), "parking_slot": (-34, -10, -2),
}

# room type -> functional finish/washability/moisture baseline (structural,
# not colour -- what the surface NEEDS regardless of theme)
ROOM_FUNCTIONAL_PROFILE: Dict[str, Dict[str, Any]] = {
    "living_room": {"finish": "satin", "washability": "medium", "moisture": False},
    "kitchen": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "bedroom": {"finish": "matte", "washability": "low", "moisture": False},
    "master_bedroom": {"finish": "matte", "washability": "low", "moisture": False},
    "guest_bedroom": {"finish": "matte", "washability": "low", "moisture": False},
    "bathroom": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "common_bathroom": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "guest_bathroom": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "pooja": {"finish": "satin", "washability": "low", "moisture": False},
    "pooja_room": {"finish": "satin", "washability": "low", "moisture": False},
    "office": {"finish": "matte", "washability": "low", "moisture": False},
    "study": {"finish": "matte", "washability": "low", "moisture": False},
    "dining": {"finish": "satin", "washability": "medium", "moisture": False},
    "entrance": {"finish": "satin", "washability": "high", "moisture": False},
    "corridor": {"finish": "satin", "washability": "medium", "moisture": False},
    "utility": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "storeroom": {"finish": "matte", "washability": "medium", "moisture": True},
    "store_room": {"finish": "matte", "washability": "medium", "moisture": True},
    "parking": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "parking_slot": {"finish": "semi-gloss", "washability": "high", "moisture": True},
    "balcony": {"finish": "satin", "washability": "high", "moisture": True},
    "staircase": {"finish": "satin", "washability": "medium", "moisture": False},
    "home_gym": {"finish": "satin", "washability": "high", "moisture": False},
    "servant_room": {"finish": "matte", "washability": "low", "moisture": False},
}
DEFAULT_FUNCTIONAL_PROFILE = ROOM_FUNCTIONAL_PROFILE["living_room"]

FINISH_ORDER = ["matte", "eggshell", "satin", "semi-gloss", "gloss"]

# pricing / brand tier -- NOT colour data, purely cost modelling
BASE_COST_PER_LITER_INR = 380.0
BUDGET_MULTIPLIERS = {"economy": 0.6, "budget": 0.6, "standard": 1.0, "mid": 1.0,
                       "premium": 1.5, "luxury": 2.0}
BUDGET_BRANDS = {"economy": "Berger EasyClean", "budget": "Berger EasyClean",
                  "standard": "Asian Paints Apex", "mid": "Asian Paints Apex",
                  "premium": "Asian Paints Royale", "luxury": "Nippon Paint Premium"}


# ── Small colour-math helpers ────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _blend_hue(base: float, target: float, weight: float) -> float:
    """Circular blend toward `target` by `weight` (0-1), taking the shortest
    way around the 360° hue wheel."""
    diff = ((target - base + 180) % 360) - 180
    return (base + diff * weight) % 360


def _hash_to_hue(text: str) -> float:
    """Deterministically turns arbitrary free text into a hue value, so
    creative/unrecognised style or mood words still produce a real,
    consistent (never silently-defaulted) colour lean."""
    digest = hashlib.sha256(text.strip().lower().encode("utf-8")).digest()
    return (digest[0] / 255.0) * 360.0


def _match_keyword(text: Optional[str], table: Dict[str, Any]) -> Tuple[Optional[str], Any]:
    """Longest-key substring match of `text` against `table`'s keys."""
    if not text:
        return None, None
    low = text.lower()
    best_key, best_val, best_len = None, None, 0
    for key, val in table.items():
        if key in low and len(key) > best_len:
            best_key, best_val, best_len = key, val, len(key)
    return best_key, best_val


def _is_warm_hue(h: float) -> bool:
    h = h % 360
    return h < 75 or h > 320


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    h = h % 360
    s = _clamp(s, 0, 100)
    l = _clamp(l, 0, 100)
    r, g, b = colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


_HUE_FAMILY_BANDS = [
    (15, "Red"), (40, "Terracotta"), (60, "Amber"), (90, "Gold"), (140, "Olive"),
    (165, "Green"), (195, "Teal"), (220, "Sky Blue"), (255, "Blue"), (280, "Indigo"),
    (310, "Violet"), (335, "Magenta"), (355, "Rose"), (360, "Red"),
]


def _hue_family(h: float) -> str:
    h = h % 360
    for upper, name in _HUE_FAMILY_BANDS:
        if h <= upper:
            return name
    return "Red"


def _surface_name(h: float, s: float, l: float) -> str:
    """Builds a descriptive paint name FROM the computed HSL numbers,
    rather than looking a finished name up in a swatch table."""
    warm = _is_warm_hue(h)
    if s < 10:
        if l > 88:
            return "Warm White" if warm else "Cloud White"
        if l > 68:
            return "Soft Ivory" if warm else "Cool Grey"
        if l > 42:
            return "Warm Greige" if warm else "Stone Grey"
        if l > 22:
            return "Charcoal"
        return "Deep Charcoal"

    family = _hue_family(h)
    if l > 85:
        light_word = "Pale"
    elif l > 68:
        light_word = "Soft"
    elif l > 48:
        light_word = "Dusty" if s < 45 else "Warm"
    elif l > 28:
        light_word = "Deep"
    else:
        light_word = "Rich Dark"

    sat_word = ""
    if s >= 72:
        sat_word = "Vivid"
    elif s < 25:
        sat_word = "Muted"

    parts = [p for p in [light_word, sat_word, family] if p]
    return " ".join(parts)


def _surface(h: float, s: float, l: float) -> SurfaceColor:
    return SurfaceColor(
        hex=_hsl_to_hex(h, s, l),
        name=_surface_name(h, s, l),
        hue=round(h, 1), saturation=round(_clamp(s, 0, 100), 1), lightness=round(_clamp(l, 0, 100), 1),
        temperature="warm" if _is_warm_hue(h) else "cool",
    )


# ── Preference gap-checking ──────────────────────────────────────────────

def get_missing_preferences(prefs: PaintPreferences) -> List[str]:
    """Returns the keys (into REQUIRED_PREFERENCE_QUESTIONS) of every
    required preference that hasn't actually been answered yet."""
    missing: List[str] = []

    def _blank(v: Optional[str]) -> bool:
        return v is None or not str(v).strip()

    if _blank(prefs.interior_style):
        missing.append("interior_style")
    if _blank(prefs.mood):
        missing.append("mood")
    if _blank(prefs.color_preference):
        missing.append("color_preference")
    if _blank(prefs.natural_lighting):
        missing.append("natural_lighting")
    if _blank(prefs.room_orientation):
        missing.append("room_orientation")
    if _blank(prefs.climate) and _blank(prefs.city):
        missing.append("climate")
    if _blank(prefs.budget):
        missing.append("budget")
    if prefs.vastu_preference is None:
        missing.append("vastu_preference")
    if prefs.occupancy is None:
        missing.append("occupancy")

    return missing


def generate_followup_questions(missing: List[str]) -> List[str]:
    return [REQUIRED_PREFERENCE_QUESTIONS[m] for m in missing if m in REQUIRED_PREFERENCE_QUESTIONS]


def _infer_preferences_from_texts(
    texts_in_priority_order: List[str],
    city: Optional[str] = None,
    budget: Optional[str] = None,
) -> PaintPreferences:
    """
    Builds a best-effort PaintPreferences from a list of free-text strings
    in priority order (e.g. [paint_theme_answer, user_prompt,
    interior_style_default]) -- the shape the OLD engine's
    generate()/generate_layered() accepted. Matches mood / style / colour
    -preference keywords out of the combined text; anything not
    recognisable as a keyword still nudges the result via a deterministic
    text hash (see _hash_to_hue) rather than being dropped, so creative
    input like "universe theme" still produces a distinct, real palette.
    """
    combined = " ".join(t for t in texts_in_priority_order if t)
    mood_key, _ = _match_keyword(combined, MOOD_HUE_ANCHORS)
    style_key, _ = _match_keyword(combined, STYLE_PROFILES)
    pref_key, _ = _match_keyword(combined, COLOR_PREFERENCE_PROFILES)

    interior_style = style_key
    if not interior_style:
        for t in reversed(texts_in_priority_order):
            if t and t.strip():
                interior_style = t.strip()
                break
    interior_style = interior_style or "contemporary"

    return PaintPreferences(
        interior_style=interior_style,
        mood=mood_key or combined or "calm",
        color_preference=pref_key or "neutral",
        natural_lighting="medium",
        room_orientation=None,
        climate=None,
        city=city,
        budget=budget or "mid",
        vastu_preference=False,
        occupancy=[],
        extra_notes=combined,
    )


# ── Core generation ──────────────────────────────────────────────────────

class PaintEngine:

    @staticmethod
    def get_missing_preferences(prefs: PaintPreferences) -> List[str]:
        return get_missing_preferences(prefs)

    @staticmethod
    def generate_followup_questions(missing: List[str]) -> List[str]:
        return generate_followup_questions(missing)

    @staticmethod
    def generate_personalized(
        rooms: List[Dict[str, Any]],
        preferences: "PaintPreferences | Dict[str, Any]",
        allow_partial: bool = False,
    ) -> PaintEngineResult:
        """
        Full-control entry point. `rooms`: [{"name": "master_bedroom", "area_sqft": 180}, ...].

        If required preferences are missing and allow_partial is False (the
        default), returns status="needs_input" with the exact follow-up
        questions to ask -- it will NOT guess a palette on unstated
        assumptions. Pass allow_partial=True only when the caller has
        already decided to proceed with sensible, explicitly-noted
        defaults for anything unanswered.

        (See generate() / generate_layered() below for simpler,
        always-succeeds entry points compatible with older callers.)
        """
        prefs = preferences if isinstance(preferences, PaintPreferences) else PaintPreferences(**(preferences or {}))

        missing = get_missing_preferences(prefs)
        if missing and not allow_partial:
            return PaintEngineResult(
                status="needs_input",
                missing_preferences=missing,
                follow_up_questions=generate_followup_questions(missing),
            )

        defaults_used: List[str] = []
        if "interior_style" in missing:
            prefs.interior_style = "contemporary"; defaults_used.append("interior style (assumed contemporary)")
        if "mood" in missing:
            prefs.mood = "calm"; defaults_used.append("mood (assumed calm)")
        if "color_preference" in missing:
            prefs.color_preference = "neutral"; defaults_used.append("colour preference (assumed neutral)")
        if "natural_lighting" in missing:
            prefs.natural_lighting = "medium"; defaults_used.append("natural lighting (assumed medium)")
        if "room_orientation" in missing:
            defaults_used.append("room orientation (not specified — daylight compensation skipped)")
        if "climate" in missing:
            defaults_used.append("climate (not specified — using city/default)")
        if "budget" in missing:
            prefs.budget = "mid"; defaults_used.append("budget (assumed mid-range)")
        if "vastu_preference" in missing:
            prefs.vastu_preference = False; defaults_used.append("Vastu alignment (assumed not required)")
        if "occupancy" in missing:
            prefs.occupancy = []; defaults_used.append("occupancy (assumed no special needs stated)")

        budget_key = (prefs.budget or "mid").lower()
        multiplier = BUDGET_MULTIPLIERS.get(budget_key, 1.0)
        brand = BUDGET_BRANDS.get(budget_key, "Asian Paints Apex")
        cost_per_liter = round(BASE_COST_PER_LITER_INR * multiplier, 0)

        recs: List[PaintRecommendation] = []
        for room in rooms:
            recs.append(PaintEngine._build_room_recommendation(room, prefs, cost_per_liter, brand, defaults_used))

        total_l = sum(r.liters_required for r in recs)
        total_c = sum(r.total_cost_inr for r in recs)
        summary = {
            "total_liters_required": round(total_l, 1),
            "total_cost_inr": round(total_c, 0),
            "average_cost_per_liter": round(total_c / total_l, 0) if total_l else 0,
            "room_count": len(recs),
            "assumptions_used": defaults_used,
        }
        return PaintEngineResult(status="ok", recommendations=recs, summary=summary)

    # ── Legacy-compatible entry points ──────────────────────────────────
    # These match the OLD PaintEngine's method names/signatures exactly
    # (generate_layered(rooms, texts_in_priority_order, city, budget) and
    # generate(rooms, theme_text, city, budget), both returning a plain
    # List[PaintRecommendation]) so this file is a drop-in replacement:
    # existing callers (e.g. main.py's ThemePaintEngine.generate_layered(...))
    # keep working unchanged, they just get generated-not-looked-up colours
    # now. They never return "needs_input" -- any preference they can't
    # infer from the free text is filled with a sensible, noted default.

    @staticmethod
    def generate_layered(
        rooms: List[Dict[str, Any]],
        texts_in_priority_order: List[str],
        city: str = "bangalore",
        budget: str = "mid",
    ) -> List[PaintRecommendation]:
        prefs = _infer_preferences_from_texts(texts_in_priority_order, city=city, budget=budget)
        result = PaintEngine.generate_personalized(rooms, prefs, allow_partial=True)
        return result.recommendations

    @staticmethod
    def generate(
        rooms: List[Dict[str, Any]],
        theme_text: str,
        city: str = "bangalore",
        budget: str = "mid",
    ) -> List[PaintRecommendation]:
        return PaintEngine.generate_layered(rooms, [theme_text], city=city, budget=budget)

    @staticmethod
    def estimate_total_paint_cost(recs: List[PaintRecommendation]) -> Dict[str, Any]:
        total_l = sum(r.liters_required for r in recs)
        total_c = sum(r.total_cost_inr for r in recs)
        return {
            "total_liters_required": round(total_l, 1),
            "total_cost_inr": round(total_c, 0),
            "average_cost_per_liter": round(total_c / total_l, 0) if total_l else 0,
            "room_count": len(recs),
        }

    # ── internals ─────────────────────────────────────────────────────

    @staticmethod
    def _seed_bytes(prefs: PaintPreferences, room_name: str) -> bytes:
        seed_str = "|".join([
            str(prefs.interior_style), str(prefs.mood), str(prefs.color_preference),
            str(prefs.natural_lighting), str(prefs.room_orientation), str(prefs.climate),
            str(prefs.city), str(prefs.budget), str(prefs.vastu_preference),
            ",".join(sorted(prefs.occupancy or [])), str(prefs.extra_notes), room_name,
        ])
        return hashlib.sha256(seed_str.encode("utf-8")).digest()

    @staticmethod
    def _base_hsl(room_name: str, prefs: PaintPreferences) -> Tuple[float, float, float, float, List[str]]:
        """Computes the room's base wall hue/saturation/lightness by
        blending every preference signal, and returns the accent
        saturation boost + a list of human-readable reasoning notes."""
        hue, sat, light = 210.0, 30.0, 78.0
        notes: List[str] = []
        accent_sat_boost = 20.0

        # mood
        mood_key, mood_vec = _match_keyword(prefs.mood, MOOD_HUE_ANCHORS)
        if mood_vec:
            hue = _blend_hue(hue, mood_vec[0], 0.55)
            sat += mood_vec[1]
            light += mood_vec[2]
            notes.append(f"mood '{prefs.mood}' set the emotional colour anchor")
        elif prefs.mood:
            hue = _blend_hue(hue, _hash_to_hue(prefs.mood), 0.4)
            notes.append(f"custom mood '{prefs.mood}' translated into a bespoke hue")

        # interior style
        style_key, style_profile = _match_keyword(prefs.interior_style, STYLE_PROFILES)
        if style_profile:
            if style_profile.get("hue_bias") is not None:
                hue = _blend_hue(hue, style_profile["hue_bias"], 0.25)
            sat *= style_profile.get("sat_mult", 1.0)
            notes.append(f"'{style_key}' style shaped the saturation/contrast character")
        elif prefs.interior_style:
            hue = _blend_hue(hue, _hash_to_hue(prefs.interior_style), 0.15)

        # colour preference
        pref_key, pref_profile = _match_keyword(prefs.color_preference, COLOR_PREFERENCE_PROFILES)
        if pref_profile:
            sat *= pref_profile.get("sat_mult", 1.0)
            light += pref_profile.get("light_shift", 0)
            accent_sat_boost = pref_profile.get("accent_sat_boost", 20.0)
            if pref_profile.get("hue_bias") is not None:
                hue = _blend_hue(hue, pref_profile["hue_bias"], 0.30)
            notes.append(f"'{prefs.color_preference}' colour preference set the intensity range")

        # Vastu vs plain daylight-orientation compensation
        if prefs.vastu_preference and prefs.room_orientation:
            v_key, v_val = _match_keyword(prefs.room_orientation, VASTU_DIRECTION_HUE)
            if v_val:
                hue = _blend_hue(hue, v_val[0], 0.45)
                notes.append(f"aligned toward Vastu-recommended {v_val[1]} for the {v_key} direction")
        elif prefs.room_orientation:
            o_key, o_val = _match_keyword(prefs.room_orientation, ORIENTATION_LIGHT_ADJUST)
            if o_val:
                if o_val[0] is not None:
                    hue = _blend_hue(hue, o_val[0], 0.15)
                light += o_val[1]
                notes.append(o_val[2])

        # natural lighting
        nl_key, nl_val = _match_keyword(prefs.natural_lighting, NATURAL_LIGHT_ADJUST)
        if nl_val:
            light += nl_val[0]
            sat += nl_val[1]
            notes.append(nl_val[2])

        # climate (explicit, else inferred from city)
        climate_text = prefs.climate or ""
        if not climate_text and prefs.city:
            climate_text = CITY_CLIMATE_HINTS.get(prefs.city.strip().lower(), "")
        c_key, c_val = _match_keyword(climate_text, CLIMATE_ADJUST)
        if c_val:
            if c_val[0] is not None:
                hue = _blend_hue(hue, c_val[0], 0.12)
            light += c_val[1]
            notes.append(c_val[2])

        # room-type functional nudge -- ADDITIVE offset (keeps this room's
        # hue a distinct member of the same coordinated family the mood/
        # style/preference math already built, rather than pulling toward
        # an unrelated absolute hue).
        room_key = room_name.lower().replace(" ", "_")
        _rk, r_val = _match_keyword(room_key, {k: v for k, v in ROOM_TYPE_NUDGE.items()}) \
            if room_key not in ROOM_TYPE_NUDGE else (room_key, ROOM_TYPE_NUDGE[room_key])
        if r_val:
            if r_val[0] is not None:
                hue = (hue + r_val[0]) % 360
            sat += r_val[1]
            light += r_val[2]

        # occupancy: children / elderly / pets
        occ = [o.lower() for o in (prefs.occupancy or [])]
        if any("child" in o or "kid" in o for o in occ):
            light += 3
            notes.append("brightened slightly for a household with children")
        if any("elder" in o or "senior" in o for o in occ):
            light = max(light, 55)
            notes.append("kept reflective enough, with stronger wall-to-trim contrast, for easier visibility for elderly residents")
        if any("pet" in o for o in occ):
            light -= 4
            notes.append("nudged a touch deeper and paired with a hard-wearing finish to hide everyday marks from pets")

        # extra free-text nudge (very light touch, doesn't override structured prefs)
        if prefs.extra_notes:
            hue = _blend_hue(hue, _hash_to_hue(prefs.extra_notes), 0.08)

        # per-project + per-room deterministic jitter so no two rooms/projects
        # collapse to identical output purely because their categories matched
        seed = PaintEngine._seed_bytes(prefs, room_name)
        hue = (hue + (seed[0] / 255.0 - 0.5) * 20) % 360
        sat += (seed[1] / 255.0 - 0.5) * 12
        light += (seed[2] / 255.0 - 0.5) * 8

        # Visibility floor: even a strongly desaturated colour-preference
        # (pastel/neutral/monochrome/muted) should still let each room's
        # hue read as a distinct, faint tint rather than every room
        # flattening to the same near-white/near-grey. Real low-saturation
        # colour, unlike literal white/grey, still carries a visible hue.
        sat = max(sat, 11.0)

        sat = _clamp(sat, 6, 92)
        light = _clamp(light, 18, 94)
        return hue, sat, light, accent_sat_boost, notes

    @staticmethod
    def _finish_for_room(room_key: str, prefs: PaintPreferences, humid: bool) -> Tuple[str, str, bool, str, int]:
        profile = ROOM_FUNCTIONAL_PROFILE.get(room_key, DEFAULT_FUNCTIONAL_PROFILE)
        finish = profile["finish"]
        washability = profile["washability"]
        moisture_needed = bool(profile["moisture"]) or humid

        finish_notes = []
        idx = FINISH_ORDER.index(finish)

        if moisture_needed and idx < FINISH_ORDER.index("semi-gloss"):
            idx = FINISH_ORDER.index("semi-gloss")
            finish_notes.append("upgraded finish for moisture/humidity resistance")

        occ = [o.lower() for o in (prefs.occupancy or [])]
        if any("pet" in o or "child" in o or "kid" in o for o in occ) and idx < FINISH_ORDER.index("satin"):
            idx = FINISH_ORDER.index("satin")
            washability = "medium" if washability == "low" else washability
            finish_notes.append("raised to at least satin for easy cleaning with children/pets at home")

        if any("elder" in o or "senior" in o for o in occ) and idx > FINISH_ORDER.index("satin") \
                and room_key in ("bedroom", "master_bedroom", "guest_bedroom", "living_room"):
            idx = FINISH_ORDER.index("satin")
            finish_notes.append("capped at satin (no gloss) to avoid glare for elderly residents")

        finish = FINISH_ORDER[idx]
        durability = 8 if washability == "high" else (6 if washability == "medium" else 5)
        if humid:
            durability = max(3, durability - 1)

        return finish, washability, moisture_needed, "; ".join(finish_notes), durability

    @staticmethod
    def _build_room_recommendation(
        room: Dict[str, Any], prefs: PaintPreferences, cost_per_liter: float, brand: str,
        defaults_used: List[str],
    ) -> PaintRecommendation:
        name_raw = room.get("name", "room")
        room_key = name_raw.lower().replace(" ", "_")
        area = room.get("area_sqft", room.get("area", 150))

        hue, sat, light, accent_sat_boost, notes = PaintEngine._base_hsl(name_raw, prefs)

        # accent: complementary for vibrant/bold/dramatic intents, analogous otherwise
        pref_key, _ = _match_keyword(prefs.color_preference, COLOR_PREFERENCE_PROFILES)
        mood_key, _ = _match_keyword(prefs.mood, MOOD_HUE_ANCHORS)
        use_complement = pref_key in ("vibrant", "bold", "jewel tones") or mood_key in ("dramatic", "bold", "moody")
        accent_offset = 150 if use_complement else 35
        accent_hue = (hue + accent_offset) % 360
        accent_sat = _clamp(sat + accent_sat_boost, 25, 95)
        accent_light = _clamp(light - 28, 16, 55)

        ceiling_hue = hue
        ceiling_sat = max(3, sat * 0.15)
        ceiling_light = _clamp(light + 14, 82, 96)

        trim_hue = hue
        trim_sat = max(3, sat * 0.08)
        trim_light = _clamp(light + 20, 88, 97)

        wall = _surface(hue, sat, light)
        ceiling = _surface(ceiling_hue, ceiling_sat, ceiling_light)
        accent = _surface(accent_hue, accent_sat, accent_light)
        trim = _surface(trim_hue, trim_sat, trim_light)

        climate_text = prefs.climate or ""
        if not climate_text and prefs.city:
            climate_text = CITY_CLIMATE_HINTS.get(prefs.city.strip().lower(), "")
        humid = "humid" in climate_text.lower() or "coastal" in climate_text.lower() \
            or "tropical" in climate_text.lower()

        wall_finish, washability, moisture_needed, finish_note, durability = \
            PaintEngine._finish_for_room(room_key, prefs, humid)
        ceiling_finish = "matte"
        trim_finish = "gloss" if (prefs.budget or "").lower() in ("premium", "luxury") else "semi-gloss"
        accent_finish = "eggshell" if pref_key in ("pastel", "neutral", "muted") else "satin"
        if room_key in ("kitchen", "bathroom", "common_bathroom", "guest_bathroom"):
            accent_finish = "semi-gloss"

        coverage = 85.0
        liters = max(1.0, round(area / coverage, 1))
        total_cost = round(liters * cost_per_liter, 0)

        reasoning_bits = [
            f"Wall in {wall.name} ({wall.hex}) and ceiling in {ceiling.name} ({ceiling.hex}) "
            f"were computed from {', '.join(notes) if notes else 'the stated preferences'}.",
            f"Accent in {accent.name} ({accent.hex}) uses a "
            f"{'complementary' if use_complement else 'analogous'} hue relationship to the wall "
            f"for {'a striking contrast' if use_complement else 'a cohesive, layered look'}.",
            f"Trim in {trim.name} ({trim.hex}) stays a near-neutral, slightly {trim.temperature} "
            f"tint of the wall colour for a clean edge.",
            f"{name_raw.replace('_', ' ').title()} gets a {wall_finish} wall finish ({washability} "
            f"washability, ~{durability}-year durability)"
            + (f" — {finish_note}." if finish_note else "."),
        ]
        if moisture_needed:
            reasoning_bits.append("Moisture/anti-fungal protection recommended given room type/climate.")
        if defaults_used:
            reasoning_bits.append(
                "Note: generated with default assumptions for " + "; ".join(defaults_used) +
                " — provide these for a fully tailored result."
            )
        rationale = " ".join(reasoning_bits)

        theme_detected = pref_key or mood_key or (prefs.interior_style or "generated")
        matched_keywords = [k for k in (pref_key, mood_key, prefs.interior_style) if k]

        rec = PaintRecommendation(
            room_name=name_raw.replace("_", " ").title(),
            wall=wall, ceiling=ceiling, accent=accent, trim=trim,
            wall_finish=wall_finish, ceiling_finish=ceiling_finish,
            accent_finish=accent_finish, trim_finish=trim_finish,
            washability=washability, durability_years=durability,
            moisture_resistant=moisture_needed,
            coverage_sqft_per_liter=coverage, liters_required=liters,
            cost_per_liter_inr=cost_per_liter, total_cost_inr=total_cost,
            brand_tier=brand, rationale=rationale,
            theme_detected=theme_detected, matched_keywords=matched_keywords,
        )
        return rec._fill_legacy_aliases()


# ── Convenience adapter for legacy-shaped callers ───────────────────────
# main.py's existing code passes free-text answers/clues rather than a
# structured PaintPreferences object. This adapter maps that legacy shape
# onto the new structured model on a best-effort basis, WITHOUT
# reintroducing a hardcoded colour table -- it only sets preference
# fields, all colour computation still happens above.

def preferences_from_legacy_clues(
    clues: Dict[str, Any],
    user_prompt: Optional[str] = None,
    city: Optional[str] = None,
    budget: Optional[str] = None,
) -> PaintPreferences:
    paint_theme_text = str(clues.get("paint_theme") or "")
    combined_free_text = " ".join(filter(None, [paint_theme_text, user_prompt or ""]))

    occupancy: List[str] = []
    if clues.get("elder_friendly"):
        occupancy.append("elderly")
    if clues.get("has_children"):
        occupancy.append("children")
    if clues.get("has_pets"):
        occupancy.append("pets")

    vastu_pref = clues.get("vastu_preference")
    if vastu_pref is not None:
        vastu_pref = bool(vastu_pref)

    return PaintPreferences(
        interior_style=clues.get("interior_style"),
        mood=clues.get("mood") or (combined_free_text or None),
        color_preference=clues.get("color_preference") or (paint_theme_text or None),
        natural_lighting=clues.get("natural_lighting"),
        room_orientation=clues.get("room_orientation") or clues.get("road_direction") or clues.get("north_direction"),
        climate=clues.get("climate"),
        city=city or clues.get("city"),
        budget=budget or clues.get("budget_range"),
        vastu_preference=vastu_pref,
        occupancy=occupancy if occupancy or clues.get("occupancy_specified") else (clues.get("occupancy")),
        extra_notes=user_prompt,
    )


def generate_recommendations_from_user_input(
    user_prompt: str,
    rooms: List[Dict[str, Any]],
    answers: Optional[Dict[str, str]] = None,
    city: str = "bangalore",
    budget: str = "mid",
) -> List[PaintRecommendation]:
    """Drop-in convenience wrapper mirroring the OLD function's name,
    signature, and return type (a plain List[PaintRecommendation]), now
    backed entirely by the generative engine."""
    clues = dict(answers or {})
    prefs = preferences_from_legacy_clues(clues, user_prompt=user_prompt, city=city, budget=budget)
    result = PaintEngine.generate_personalized(rooms, prefs, allow_partial=True)
    return result.recommendations


def fetch_swatches(theme_text: str, room_names: Optional[List[str]] = None) -> Dict[str, Dict[str, str]]:
    """
    Quick base/accent hex preview per room for ANY theme text, for a live
    colour-preview UI before running the full generate() cost/finish
    calculation. Kept for compatibility with older callers.
    """
    room_names = room_names or ["Living Room", "Master Bedroom"]
    prefs = _infer_preferences_from_texts([theme_text])
    rooms = [{"name": n, "area_sqft": 150} for n in room_names]
    result = PaintEngine.generate_personalized(rooms, prefs, allow_partial=True)
    return {
        rec.room_name: {"base": rec.wall.hex, "accent": rec.accent.hex}
        for rec in result.recommendations
    }


if __name__ == "__main__":
    # Sanity check: same room type, several different preference sets ->
    # should produce visibly different, non-hardcoded palettes.
    room_set = [{"name": "living_room", "area_sqft": 220}, {"name": "master_bedroom", "area_sqft": 180},
                {"name": "kitchen", "area_sqft": 120}, {"name": "bathroom", "area_sqft": 55}]

    scenarios = [
        PaintPreferences(interior_style="scandinavian", mood="calm", color_preference="pastel",
                          natural_lighting="low", room_orientation="north", climate="cold",
                          city="chandigarh", budget="mid", vastu_preference=False, occupancy=["children"]),
        PaintPreferences(interior_style="luxury", mood="dramatic", color_preference="jewel tones",
                          natural_lighting="high", room_orientation="south", climate="hot & humid",
                          city="mumbai", budget="luxury", vastu_preference=False, occupancy=[]),
        PaintPreferences(interior_style="traditional", mood="serene", color_preference="earthy",
                          natural_lighting="medium", room_orientation="north east", climate="temperate",
                          city="bangalore", budget="premium", vastu_preference=True, occupancy=["elderly", "pets"]),
    ]

    for i, prefs in enumerate(scenarios, 1):
        print("=" * 78)
        print(f"SCENARIO {i}: {prefs}")
        result = PaintEngine.generate_personalized(room_set, prefs)
        if result.status == "needs_input":
            print("  NEEDS INPUT:", result.follow_up_questions)
            continue
        for r in result.recommendations:
            print(f"  {r.room_name:14s} wall={r.wall.name:18s}{r.wall.hex}  "
                  f"accent={r.accent.name:16s}{r.accent.hex}  finish={r.wall_finish}")
        print("  ", result.summary)

    print("=" * 78)
    print("MISSING-INPUT DEMO (nothing supplied):")
    empty_result = PaintEngine.generate_personalized(room_set, PaintPreferences())
    print("  status:", empty_result.status)
    for q in empty_result.follow_up_questions:
        print("  -", q)

    print("=" * 78)
    print("LEGACY-COMPATIBLE CALL DEMO (old generate_layered signature):")
    legacy_recs = PaintEngine.generate_layered(
        room_set, ["universe theme", "3BHK house with a cosmic universe theme", "contemporary"],
        city="bangalore", budget="premium",
    )
    for r in legacy_recs:
        print(f"  {r.room_name:14s} primary={r.primary_paint_name:18s}{r.primary_hex}  "
              f"accent={r.accent_paint_name:16s}{r.accent_hex}  finish={r.finish_type}  "
              f"cost=Rs.{r.total_cost_inr:.0f}")
    print("  ", PaintEngine.estimate_total_paint_cost(legacy_recs))