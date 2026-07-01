# app/core/cost_estimation.py
from typing import Dict, Tuple
from dataclasses import dataclass

@dataclass
class CostBreakdown:
    foundation_cost: float = 0
    rcc_cost: float = 0
    brickwork_cost: float = 0
    roofing_cost: float = 0
    flooring_cost: float = 0
    electrical_cost: float = 0
    plumbing_cost: float = 0
    doors_cost: float = 0
    windows_cost: float = 0
    painting_cost: float = 0
    labour_cost: float = 0
    contingency_cost: float = 0
    total_cost: float = 0

class CostEstimationEngine:
    CITY_MULT = {
        "bangalore":1.15,"delhi":1.20,"mumbai":1.35,"hyderabad":1.10,
        "pune":1.12,"chennai":1.08,"kolkata":0.95,"ahmedabad":1.05,
        "default":1.0,
    }
    COMPLEXITY_MULT = {"economy":0.85,"standard":1.0,"premium":1.25,"luxury":1.50}
    STYLE_MULT = {"modern":1.10,"traditional":0.95,"luxury":1.40,"minimal":0.90,
                  "industrial":1.15,"scandinavian":1.12,"contemporary":1.08}

    @staticmethod
    def estimate(
        built_up_area: float,
        floors: int,
        wall_lengths: float,
        city: str = "default",
        complexity: str = "standard",
        style: str = "modern",
        num_doors: int = 0,
        num_windows: int = 0,
        window_area: float = 0,
    ) -> Tuple[CostBreakdown, Dict]:
        b = CostBreakdown()
        cm = CostEstimationEngine.CITY_MULT.get(city.lower(), 1.0)
        xm = CostEstimationEngine.COMPLEXITY_MULT.get(complexity.lower(), 1.0)
        sm = CostEstimationEngine.STYLE_MULT.get(style.lower(), 1.0)
        mult = cm * xm * sm

        base_rcc        = 1000
        base_flooring   = 220
        base_electrical = 40
        base_plumbing   = 35
        base_painting   = 16
        base_labour     = 350
        base_door       = 14000
        base_window     = 1600

        b.foundation_cost  = built_up_area * 180 * mult
        b.rcc_cost         = built_up_area * floors * base_rcc * mult
        b.brickwork_cost   = wall_lengths * 10 * 650 * mult
        b.roofing_cost     = built_up_area * base_rcc * 0.3 * mult
        b.flooring_cost    = built_up_area * floors * base_flooring * mult
        b.electrical_cost  = built_up_area * floors * base_electrical * mult
        b.plumbing_cost    = built_up_area * floors * base_plumbing * mult

        if num_doors == 0:
            num_doors = max(4, int(built_up_area / 200))
        b.doors_cost = num_doors * base_door * mult

        if window_area == 0:
            window_area = built_up_area * 0.12
        b.windows_cost  = window_area * base_window * mult
        b.painting_cost = built_up_area * floors * base_painting * mult
        b.labour_cost   = built_up_area * floors * base_labour * cm * xm

        subtotal = (b.foundation_cost + b.rcc_cost + b.brickwork_cost +
                    b.roofing_cost + b.flooring_cost + b.electrical_cost +
                    b.plumbing_cost + b.doors_cost + b.windows_cost +
                    b.painting_cost + b.labour_cost)
        b.contingency_cost = subtotal * 0.12
        b.total_cost = subtotal + b.contingency_cost

        boq = {
            "summary": {
                "built_up_area": built_up_area,
                "floors": floors,
                "cost_per_sqft": round(b.total_cost / max(1, built_up_area), 0),
                "total_estimated_cost_inr": round(b.total_cost, 0),
                "city": city,
                "complexity": complexity,
                "style": style,
            },
            "breakdown": {
                "Foundation": round(b.foundation_cost, 0),
                "RCC": round(b.rcc_cost, 0),
                "Brickwork": round(b.brickwork_cost, 0),
                "Roofing": round(b.roofing_cost, 0),
                "Flooring": round(b.flooring_cost, 0),
                "Electrical": round(b.electrical_cost, 0),
                "Plumbing": round(b.plumbing_cost, 0),
                "Doors": round(b.doors_cost, 0),
                "Windows": round(b.windows_cost, 0),
                "Painting": round(b.painting_cost, 0),
                "Labour": round(b.labour_cost, 0),
                "Contingency": round(b.contingency_cost, 0),
            },
            "grand_total_inr": round(b.total_cost, 0),
        }
        return b, boq

    @staticmethod
    def cost_per_sqft(total: float, area: float) -> float:
        return total / area if area > 0 else 0