from enum import Enum
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from backend.app.geometry.models import BuildingGeometry, Room, Wall
from backend.app.geometry.door_generator import Door
from backend.app.geometry.window_generator import Window

class QualityTier(str, Enum):
    ECONOMY = "ECONOMY"
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"
    LUXURY = "LUXURY"

class CityTier(str, Enum):
    METRO = "METRO"         # Mumbai, Delhi, Bangalore, Chennai, etc. (High index)
    TIER_2 = "TIER_2"       # Pune, Hyderabad, Ahmedabad, Jaipur, etc. (Base index)
    TIER_3 = "TIER_3"       # Smaller urban zones, rural-urban fringes (Lower index)

class CostReport(BaseModel):
    """Unified configuration payload detailing itemized real-estate construction estimations in INR."""
    built_up_area_sqft: float
    construction_cost_per_sqft: float
    foundation_cost: float
    plinth_cost: float
    structural_frame_cost: float  # Columns and Beams
    wall_cost: float
    roof_cost: float
    flooring_cost: float
    door_cost: float
    window_cost: float
    electrical_cost: float
    plumbing_cost: float
    painting_cost: float
    finishing_cost: float
    waterproofing_cost: float
    labour_cost: float
    contingency_cost: float
    gst: float
    grand_total: float
    currency: str = "INR"

class CostEngine:
    """
    Deterministic quantity takeoff and cost estimation processor.
    Derives itemized bills of materials directly from layout spatial coordinates.
    """

    # Base cost index matrices per square foot in INR (2026 Indian Market Averages)
    BASE_RATES_PER_SQFT: Dict[QualityTier, float] = {
        QualityTier.ECONOMY: 1400.0,
        QualityTier.STANDARD: 1800.0,
        QualityTier.PREMIUM: 2400.0,
        QualityTier.LUXURY: 3600.0
    }

    CITY_MULTIPLIERS: Dict[CityTier, float] = {
        CityTier.METRO: 1.25,
        CityTier.TIER_2: 1.00,
        CityTier.TIER_3: 0.85
    }

    STANDARD_FLOOR_HEIGHT_MM: float = 3000.0  # Standard 3-meter floor height parameter

    @classmethod
    def calculate_wall_cost(cls, walls: List[Wall], tier: QualityTier, city_mult: float) -> float:
        """Calculates total masonry wall structural costs based on total running length and quality constants."""
        total_surface_area_sqm = 0.0
        for wall in walls:
            length_m = wall.segment.length / 1000.0
            height_m = cls.STANDARD_FLOOR_HEIGHT_MM / 1000.0
            total_surface_area_sqm += (length_m * height_m)

        # Map brickwork/blockwork pricing per square meter
        rate_per_sqm = 950.0
        if tier == QualityTier.STANDARD:
            rate_per_sqm = 1250.0
        elif tier == QualityTier.PREMIUM:
            rate_per_sqm = 1650.0
        elif tier == QualityTier.LUXURY:
            rate_per_sqm = 2300.0

        return round(total_surface_area_sqm * rate_per_sqm * city_mult, 2)

    @classmethod
    def calculate_flooring_cost(cls, rooms: List[Room], tier: QualityTier, city_mult: float) -> float:
        """Computes subfloor prep, screed, tile, or marble material supply and install metrics."""
        total_area_sqft = sum(room.computed_area_sqft for room in rooms)
        
        # Indian tile/marble rates per sqft
        rate_per_sqft = 70.0  # Ceramic/Vitrified basic
        if tier == QualityTier.STANDARD:
            rate_per_sqft = 120.0  # Premium Vitrified Tiles
        elif tier == QualityTier.PREMIUM:
            rate_per_sqft = 220.0  # Low-tier Indian Marble / Engineered wood
        elif tier == QualityTier.LUXURY:
            rate_per_sqft = 450.0  # Imported Italian Marble / Solid Hardwood

        return round(total_area_sqft * rate_per_sqft * city_mult, 2)

    @classmethod
    def calculate_roof_cost(cls, footprint_area_sqft: float, tier: QualityTier, city_mult: float) -> float:
        """Computes structural concrete slab pouring, reinforcement detailing, and shuttering fees."""
        rate_per_sqft = 220.0
        if tier == QualityTier.STANDARD:
            rate_per_sqft = 300.0
        elif tier == QualityTier.PREMIUM:
            rate_per_sqft = 420.0
        elif tier == QualityTier.LUXURY:
            rate_per_sqft = 650.0

        return round(footprint_area_sqft * rate_per_sqft * city_mult, 2)

    @classmethod
    def calculate_door_cost(cls, doors: List[Door], tier: QualityTier) -> float:
        """Evaluates hardware specification levels to compute complete system fitting costs."""
        total_cost = 0.0
        for door in doors:
            # Differentiate based on architectural scope types
            if door.door_type == "MAIN_ENTRANCE":
                base_door_rate = 18000.0
            elif door.door_type in ["SLIDING", "DOUBLE"]:
                base_door_rate = 14000.0
            elif door.door_type == "BATHROOM":
                base_door_rate = 6000.0
            else:
                base_door_rate = 9500.0

            # Quality multipliers
            if tier == QualityTier.ECONOMY:
                total_cost += base_door_rate * 0.8
            elif tier == QualityTier.STANDARD:
                total_cost += base_door_rate * 1.0
            elif tier == QualityTier.PREMIUM:
                total_cost += base_door_rate * 1.5
            elif tier == QualityTier.LUXURY:
                total_cost += base_door_rate * 2.8

        return round(total_cost, 2)

    @classmethod
    def calculate_window_cost(cls, windows: List[Window], tier: QualityTier) -> float:
        """Determines framing cost structures based on architectural aperture sizes."""
        total_cost = 0.0
        for win in windows:
            area_sqft = (win.width / 304.8) * (win.height / 304.8)
            
            # Rate per square foot for framing systems (Aluminium / UPVC)
            rate_per_sqft = 250.0
            if tier == QualityTier.STANDARD:
                rate_per_sqft = 450.0
            elif tier == QualityTier.PREMIUM:
                rate_per_sqft = 750.0
            elif tier == QualityTier.LUXURY:
                rate_per_sqft = 1400.0

            total_cost += (area_sqft * rate_per_sqft)
        return round(total_cost, 2)

    @classmethod
    def calculate_paint_cost(cls, walls: List[Wall], tier: QualityTier, city_mult: float) -> float:
        """Calculates double-coat internal wall coating costs based on wall surface profiles."""
        total_surface_area_sqft = 0.0
        for wall in walls:
            length_ft = (wall.segment.length / 25.4) / 12.0
            height_ft = (cls.STANDARD_FLOOR_HEIGHT_MM / 25.4) / 12.0
            total_surface_area_sqft += (length_ft * height_ft * 2.0)  # Dual faces calculated

        rate_per_sqft = 15.0  # Basic Tractor Emulsion
        if tier == QualityTier.STANDARD:
            rate_per_sqft = 28.0  # Premium Apcolite
        elif tier == QualityTier.PREMIUM:
            rate_per_sqft = 45.0  # Royale Luxury Silks
        elif tier == QualityTier.LUXURY:
            rate_per_sqft = 85.0  # Specialized textures / Import lines

        return round(total_surface_area_sqft * rate_per_sqft * city_mult, 2)

    @classmethod
    def calculate_labour_cost(cls, built_up_area_sqft: float, tier: QualityTier, city_mult: float) -> float:
        """Calculates human resource deployment costs using built-up footprint tracking metrics."""
        rate_per_sqft = 250.0
        if tier == QualityTier.STANDARD:
            rate_per_sqft = 350.0
        elif tier == QualityTier.PREMIUM:
            rate_per_sqft = 480.0
        elif tier == QualityTier.LUXURY:
            rate_per_sqft = 700.0

        return round(built_up_area_sqft * rate_per_sqft * city_mult, 2)

    @classmethod
    def calculate_total(cls, breakdown: Dict[str, float], gst_percentage: float = 18.0) -> Tuple[float, float]:
        """Sums up itemized sub-costs to determine contingency limits and final gross sums."""
        sub_total = sum(breakdown.values())
        contingency = round(sub_total * 0.05, 2)  # Fixed 5% project safety margin buffer
        taxable_amount = sub_total + contingency
        gst_amount = round(taxable_amount * (gst_percentage / 100.0), 2)
        grand_total = round(taxable_amount + gst_amount, 2)
        return contingency, gst_amount, grand_total

    def generate_cost_breakdown(
        self, 
        building: BuildingGeometry, 
        doors: List[Door], 
        windows: List[Window], 
        quality: QualityTier = QualityTier.STANDARD, 
        city: CityTier = CityTier.TIER_2,
        gst_percent: float = 18.0
    ) -> CostReport:
        """Analyzes spatial profiles to compile an itemized Indian construction cost breakdown report."""
        
        # 1. Deduce spatial metrics directly from geometry
        all_rooms: List[Room] = []
        all_walls: List[Wall] = []
        for floor in building.floors:
            all_rooms.extend(floor.rooms)
            if floor.rooms:
                all_walls.extend(floor.rooms[0].walls)

        built_up_area_sqft = sum(room.computed_area_sqft for room in all_rooms)
        # Handle zero cases gracefully for initial schema evaluation passes
        if built_up_area_sqft <= 0:
            built_up_area_sqft = 1200.0

        city_mult = self.CITY_MULTIPLIERS.get(city, 1.0)
        base_rate = self.BASE_RATES_PER_SQFT.get(quality, 1800.0)
        target_cost_per_sqft = base_rate * city_mult

        # 2. Extract itemized material profiles from geometry
        walls_cost = self.calculate_wall_cost(all_walls, quality, city_mult)
        flooring_cost = self.calculate_flooring_cost(all_rooms, quality, city_mult)
        roof_cost = self.calculate_roof_cost(built_up_area_sqft / len(building.floors if building.floors else [1]), quality, city_mult)
        doors_cost = self.calculate_door_cost(doors, quality)
        windows_cost = self.calculate_window_cost(windows, quality)
        paint_cost = self.calculate_paint_cost(all_walls, quality, city_mult)
        labour_cost = self.calculate_labour_cost(built_up_area_sqft, quality, city_mult)

        # 3. Factor standard architectural breakdowns by cross-referencing total area
        foundation_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.10), 2)   # 10% structural load weight
        plinth_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.04), 2)       # 4% ground level beam tie
        frame_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.16), 2)        # 16% reinforced pillars
        elec_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.06), 2)         # 6% wiring and conduit grids
        plumb_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.06), 2)        # 6% fixture and supply lines
        finishing_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.08), 2)    # 8% carpentry
        waterproof_cost = round(built_up_area_sqft * (target_cost_per_sqft * 0.02), 2)   # 2% damp-proof coarse handling

        # 4. Synthesize cost ledger entries
        core_ledger = {
            "walls": walls_cost,
            "flooring": flooring_cost,
            "roof": roof_cost,
            "doors": doors_cost,
            "windows": windows_cost,
            "painting": paint_cost,
            "labour": labour_cost,
            "foundation": foundation_cost,
            "plinth": plinth_cost,
            "frame": frame_cost,
            "electrical": elec_cost,
            "plumbing": plumb_cost,
            "finishing": finishing_cost,
            "waterproofing": waterproof_cost
        }

        contingency, gst_amount, grand_total = self.calculate_total(core_ledger, gst_percent)

        return CostReport(
            built_up_area_sqft=round(built_up_area_sqft, 2),
            construction_cost_per_sqft=round(grand_total / built_up_area_sqft, 2),
            foundation_cost=foundation_cost,
            plinth_cost=plinth_cost,
            structural_frame_cost=frame_cost,
            wall_cost=walls_cost,
            roof_cost=roof_cost,
            flooring_cost=flooring_cost,
            door_cost=doors_cost,
            window_cost=windows_cost,
            electrical_cost=elec_cost,
            plumbing_cost=plumb_cost,
            painting_cost=paint_cost,
            finishing_cost=finishing_cost,
            waterproofing_cost=waterproof_cost,
            labour_cost=labour_cost,
            contingency_cost=contingency,
            gst=gst_amount,
            grand_total=grand_total,
            currency="INR"
        )