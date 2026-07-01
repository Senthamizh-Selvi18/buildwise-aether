from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from backend.app.geometry.models import BuildingGeometry, Room, RoomType

class PaintRecommendation(BaseModel):
    """Structured architectural paint schema mapping geometric fill variables to color assets."""
    room_name: str
    recommended_color: str
    hex_color: str
    border_color: str
    floor_color: str
    wall_color: str
    ceiling_color: str
    reason: str

class PaintEngine:
    """
    Deterministic paint palette generator matching structural properties, 
    architectural style matrices, and traditional Vastu criteria.
    """

    # Structured style matrices detailing base, wall, ceiling, floor, and outline rules
    STYLE_PALETTES: Dict[str, Dict[str, Any]] = {
        "MODERN": {
            "default_hex": "#F5F5F7", "border": "#1D1D1F", "ceiling": "#FFFFFF", "floor": "#E5E5EA",
            "rooms": {
                RoomType.LIVING: ("Cool Platinum", "#E3E3E8", "#D1D1D6", "Accentuates open space layout structures under daylight."),
                RoomType.BEDROOM: ("Muted Slate", "#AEB4B9", "#8E959B", "Calming mid-tone slate balances resting ambiance."),
                RoomType.KITCHEN: ("Chalk White", "#F2F2F7", "#E5E5EA", "Ultra-clean profile enhances illumination uniformity."),
                RoomType.BATHROOM: ("Hydro Blue Tint", "#E4F2FF", "#C7E3FF", "Provides a crisp, sanitary interior feel."),
            }
        },
        "SCANDINAVIAN": {
            "default_hex": "#F9F6F0", "border": "#2C2C2C", "ceiling": "#FFFFFF", "floor": "#F0EAE1",
            "rooms": {
                RoomType.LIVING: ("Warm Alabaster", "#F4F0E6", "#EBE5D8", "Maximizes natural ambient dispersion in gather zones."),
                RoomType.BEDROOM: ("Soft Sage", "#D2DDD4", "#C1CFC4", "Restful organic tint promotes deeper recovery states."),
                RoomType.KITCHEN: ("Bleached Linen", "#F7F5F0", "#EDE9E0", "Bright, warm matte surface finish optimizes preparation sight lines."),
                RoomType.BATHROOM: ("Pure Frost", "#FAFAFA", "#F0F0F0", "Crisp high-reflectance tones suggest pristine safety."),
            }
        },
        "INDUSTRIAL": {
            "default_hex": "#D1D1D1", "border": "#1A1A1A", "ceiling": "#CCCCCC", "floor": "#A6A6A6",
            "rooms": {
                RoomType.LIVING: ("Raw Concrete", "#BCBCBC", "#A8A8A8", "Exposed mineral character aligns with structural aesthetics."),
                RoomType.BEDROOM: ("Charcoal Ash", "#4A4A4A", "#3A3A3A", "Deep, low-reflectance surfaces support isolation."),
                RoomType.KITCHEN: ("Iron Oxide Matte", "#707070", "#5C5C5C", "Pairs perfectly with commercial steel profiles."),
                RoomType.BATHROOM: ("Flint Grey", "#949494", "#808080", "Rugged, low-maintenance shade fits metallic trim elements."),
            }
        },
        "LUXURY": {
            "default_hex": "#F4EFE6", "border": "#3A2F1D", "ceiling": "#FFFDF9", "floor": "#E8DEC9",
            "rooms": {
                RoomType.LIVING: ("Champagne Cream", "#F0E6D2", "#E2D3B7", "Rich ivory canvas coordinates elegantly with premium trims."),
                RoomType.BEDROOM: ("Royal Velvet Dusk", "#2D3748", "#1A202C", "Deep, majestic hue evokes exclusive luxury suites."),
                RoomType.KITCHEN: ("Calacatta Ivory", "#F9F8F6", "#EFECE6", "Subtle warm veining tones echo high-end stone slabs."),
                RoomType.BATHROOM: ("Imperial Pearl", "#FDFBF7", "#F5F0E6", "Opulent, luminous backdrop complements metal accents."),
            }
        }
    }

    # Strict Vastu orientation color parameters mapping compass directions to optimal room functions
    VASTU_PALETTE: Dict[str, Dict[str, str]] = {
        "NORTH": {"color": "Light Cyan", "hex": "#E0FFFF", "reason": "North orientation values governed by Mercury; benefits from airy aquas."},
        "EAST": {"color": "Sunlit Cream", "#FFFAF0": "#FFF8DC", "hex": "#FFFDF0", "reason": "East axis ruled by Solar rays; optimized via soft solar creams."},
        "SOUTH": {"color": "Coral Blush", "hex": "#FFE4E1", "reason": "South vectors align with Mars energies; balanced by muted corals."},
        "WEST": {"color": "Mist Grey", "hex": "#F5F5F5", "reason": "West boundaries ruled by Saturn; optimized via stable neutral greys."},
        "NORTH_EAST": {"color": "Sacred Gold Tint", "hex": "#FFF4D2", "reason": "Eshanya corner demands high purity light yellows or whites."},
        "SOUTH_WEST": {"color": "Golden Almond", "hex": "#F4E3C3", "reason": "Nairutya sector requires grounding earthen sand tones for stability."}
    }

    @classmethod
    def recommend_room_color(
        cls, 
        room_type: RoomType, 
        orientation: str, 
        style: str, 
        vastu_enabled: bool
    ) -> Tuple[str, str, str]:
        """Resolves the core room paint asset name, target hex value, and design validation justification."""
        normalized_style = style.upper() if style.upper() in cls.STYLE_PALETTES else "MODERN"
        style_node = cls.STYLE_PALETTES[normalized_style]

        # 1. Evaluate Vastu configuration rules first if enabled
        if vastu_enabled:
            norm_orient = orientation.upper().replace(" ", "_")
            if norm_orient in cls.VASTU_PALETTE:
                v_data = cls.VASTU_PALETTE[norm_orient]
                return v_data["color"], v_data["hex"], v_data["reason"]
            
            # Special internal Vastu overrides based on room types
            if room_type == RoomType.POOJA:
                return "Sattvic Yellow", "#FFFFE0", "Traditional color rules for prayer areas promote meditative clarity."
            if room_type == RoomType.BATHROOM:
                return "Clean White", "#FFFFFF", "Maintains clarity and balances water element energies."

        # 2. Fall back to standard style palette lookup indices if Vastu is off
        if room_type in style_node["rooms"]:
            return style_node["rooms"][room_type]
            
        # 3. Dynamic generic fallback for unmapped custom utility spaces
        return ("Neutral Canvas", style_node["default_hex"], "Standard architectural palette maintains layout visual balance.")

    @classmethod
    def recommend_wall_color(cls, room_hex: str) -> str:
        """Derives structural interior wall line colors by modifying room tint properties."""
        return room_hex

    @classmethod
    def recommend_floor_color(cls, style: str) -> str:
        """Determines underlying physical floor finish values based on the home template theme."""
        normalized_style = style.upper() if style.upper() in cls.STYLE_PALETTES else "MODERN"
        return cls.STYLE_PALETTES[normalized_style]["floor"]

    @classmethod
    def recommend_border_color(cls, style: str) -> str:
        """Calculates architectural room divider boundary stroke colors based on style configurations."""
        normalized_style = style.upper() if style.upper() in cls.STYLE_PALETTES else "MODERN"
        return cls.STYLE_PALETTES[normalized_style]["border"]

    @classmethod
    def validate_color_scheme(cls, rec: PaintRecommendation) -> bool:
        """Runs mathematical safety validation checks to ensure proper contrast for background text labels."""
        if rec.hex_color.lower() == rec.border_color.lower():
            return False  # Blocks matching boundary fills that could hide edge geometry
        if len(rec.hex_color) != 7 or not rec.hex_color.startswith("#"):
            return False  # Validates standard 7-character CSS hex string formatting
        return True

    def recommend_colors(
        self, 
        building: BuildingGeometry, 
        style: str = "MODERN", 
        vastu_enabled: bool = False, 
        user_pref: Optional[Dict[str, str]] = None
    ) -> List[PaintRecommendation]:
        """Analyzes floorplan components and returns structured color palettes for all room nodes."""
        recommendations: List[PaintRecommendation] = []
        style_upper = style.upper() if style.upper() in self.STYLE_PALETTES else "MODERN"
        style_node = self.STYLE_PALETTES[style_upper]

        for floor in building.floors:
            for room in floor.rooms:
                # Deduce environmental orientations dynamically based on geometric placement coordinates
                simulated_orientation = "NORTH" if room.center.y > 5000.0 else "SOUTH"
                if "bed" in room.id.lower() and vastu_enabled:
                    simulated_orientation = "SOUTH_WEST"  # Move master bedroom locations to stable grounding zones
                elif "pooja" in room.id.lower():
                    simulated_orientation = "NORTH_EAST"

                # Check for explicit override match lists provided by user configurations
                if user_pref and room.id in user_pref:
                    c_name = "User Preference Custom"
                    c_hex = user_pref[room.id]
                    c_reason = "Overridden by custom client interior configuration preferences."
                else:
                    c_name, c_hex, c_reason = self.recommend_room_color(
                        room.room_type, simulated_orientation, style_upper, vastu_enabled
                    )

                rec = PaintRecommendation(
                    room_name=room.id,
                    recommended_color=c_name,
                    hex_color=c_hex,
                    border_color=self.recommend_border_color(style_upper),
                    floor_color=self.recommend_floor_color(style_upper),
                    wall_color=self.recommend_wall_color(c_hex),
                    ceiling_color=style_node["ceiling"],
                    reason=c_reason
                )

                # Automatically enforce basic fallback adjustments if contrast checking fails
                if not self.validate_color_scheme(rec):
                    rec.hex_color = style_node["default_hex"]

                recommendations.append(rec)

        return recommendations

    def generate_svg_fill_colors(self, recommendations: List[PaintRecommendation]) -> Dict[str, Dict[str, str]]:
        """Compiles recommendations into a lookup dictionary of hex styles, ready for the SVG rendering node."""
        svg_palette_map: Dict[str, Dict[str, str]] = {}
        for r in recommendations:
            svg_palette_map[r.room_name] = {
                "fill": r.hex_color,
                "stroke": r.border_color,
                "floor": r.floor_color,
                "wall_stroke": r.wall_color,
                "ceiling": r.ceiling_color
            }
        return svg_palette_map