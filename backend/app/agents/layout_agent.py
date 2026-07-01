"""
backend/app/agents/layout_agent.py

Multi-agent integration layer for BuildWise Aether.

Wires the deterministic BSP GeometryEngine
(backend/app/core/geometry/geometry_engine.py) to the LayoutOptionPayload
schema that main.py and the frontend expect.

The method main.py calls:
    layout_agent.execute_procedural_generation(req_analysis, mode=...)

Returns:
    LayoutOptionPayload  (floors → List[FloorPlan] with svg_dump populated)
"""

import uuid
from typing import Any, Dict, List

from backend.app.core.geometry.geometry_engine import GeometryEngine
from backend.app.schemas.floorplan import (
    LayoutOptionPayload,
    FloorPlan,
    RoomLayout,
    StructuralWall,
    ArchitecturePortal,
    StructuralColumn,
    CostReportSchema,
    PaintRecommendationSchema,
    Point2D,
)

# ── Singleton geometry engine ─────────────────────────────────────────────────
_engine = GeometryEngine()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_floor_plan(floor_raw: Dict[str, Any]) -> FloorPlan:
    """
    Convert one raw floor dict from GeometryEngine.generate() into
    the FloorPlan schema that Canvas2D.tsx reads.

    Key mapping:
        floor_raw["svg_raw"]  →  FloorPlan.svg_dump   (Canvas2D reads svg_dump)
        floor_raw["name"]     →  FloorPlan.floor_name
    """
    rooms: List[RoomLayout] = []
    for r in floor_raw.get("rooms", []):
        b = r["bbox"]
        rooms.append(RoomLayout(
            name        = r["name"],
            label       = r["name"],
            x1          = b["x1"],
            y1          = b["y1"],
            x2          = b["x2"],
            y2          = b["y2"],
            area_sqft   = r.get("area_sqft", round((b["x2"]-b["x1"])*(b["y2"]-b["y1"]), 2)),
            fill_color_hex = r.get("paint_hex", "#f8f8f8"),
            paint_name  = r.get("paint_name", "Classic Alabaster"),
            points      = [
                Point2D(x=b["x1"], y=b["y1"]),
                Point2D(x=b["x2"], y=b["y1"]),
                Point2D(x=b["x2"], y=b["y2"]),
                Point2D(x=b["x1"], y=b["y2"]),
            ],
        ))

    walls: List[StructuralWall] = [
        StructuralWall(
            x1=w["x1"], y1=w["y1"], x2=w["x2"], y2=w["y2"],
            thickness=w["thickness"], is_exterior=w["is_exterior"]
        )
        for w in floor_raw.get("walls", [])
    ]

    portals: List[ArchitecturePortal] = [
        ArchitecturePortal(
            portal_type    = p.get("type", "door"),
            x1             = p["x1"], y1=p["y1"],
            x2             = p["x2"], y2=p["y2"],
            associated_room= p.get("room", ""),
        )
        for p in floor_raw.get("portals", [])
    ]

    columns: List[StructuralColumn] = [
        StructuralColumn(x=c["x"], y=c["y"])
        for c in floor_raw.get("columns", [])
    ]

    return FloorPlan(
        floor_name  = floor_raw["name"],
        rooms       = rooms,
        walls       = walls,
        portals     = portals,
        columns     = columns,
        has_balcony = floor_raw.get("has_balcony", False),
        svg_dump    = floor_raw.get("svg_raw", ""),  # ← KEY: svg_raw → svg_dump
    )


def _build_cost_report(cost_raw: Dict[str, Any]) -> CostReportSchema:
    return CostReportSchema(
        total_estimated_cost_inr = cost_raw.get("total_inr", 0.0),
        material_breakdown       = cost_raw.get("materials", {}),
        labor_cost_inr           = cost_raw.get("labor_inr", 0.0),
        finishing_cost_inr       = cost_raw.get("finishing_inr", 0.0),
    )


def _build_paint_recs(paint_raw: List[Dict]) -> List[PaintRecommendationSchema]:
    return [
        PaintRecommendationSchema(
            room_name         = p.get("room_name", ""),
            primary_color_name= p.get("primary_name", ""),
            primary_color_hex = p.get("primary_hex", "#ffffff"),
            accent_color_name = p.get("accent_name", "Charcoal Slate"),
            accent_color_hex  = p.get("accent_hex", "#334155"),
        )
        for p in paint_raw
    ]


# ── Public agent class ────────────────────────────────────────────────────────

class LayoutEngineAgent:
    """
    Multi-agent orchestrator for BuildWise Aether layout generation.
    Called by main.py as:
        layout_agent.execute_procedural_generation(req_analysis, mode=...)
    """

    def execute_procedural_generation(
        self,
        req_analysis: Dict[str, Any],
        mode: str = "space_efficiency",
    ) -> LayoutOptionPayload:
        """
        Run the full geometry pipeline for one layout variant and return
        a LayoutOptionPayload whose FloorPlan.svg_dump fields are populated
        and ready for Canvas2D.tsx to render via dangerouslySetInnerHTML.

        req_analysis keys (set by RequirementsAgent):
            plot_width      float  (feet)
            plot_depth      float  (feet)
            floors          int
            required_rooms  List[str]
            style           str    e.g. "modern"
        """
        # ── Extract parameters from req_analysis ──────────────────
        plot_w  = float(req_analysis.get("plot_width",  req_analysis.get("width",  30.0)))
        plot_d  = float(req_analysis.get("plot_depth",  req_analysis.get("depth",  50.0)))
        floors  = int(  req_analysis.get("floors",      req_analysis.get("floors_requested", 1)))
        rooms   = req_analysis.get("required_rooms", req_analysis.get("rooms", [
            "Staircase", "Living Room", "Kitchen", "Bathroom", "Bedroom 1"
        ]))
        style   = req_analysis.get("style", "modern")

        # ── Run the geometry engine ───────────────────────────────
        raw = GeometryEngine.generate(
            plot_width        = plot_w,
            plot_depth        = plot_d,
            floors            = floors,
            required_rooms    = rooms,
            generation_mode   = mode,
            architectural_style = style,
        )

        # ── Map raw output → schema ───────────────────────────────
        floor_plans  = [_build_floor_plan(f) for f in raw.get("floors", [])]
        cost_report  = _build_cost_report(raw.get("cost_report", {}))
        paint_recs   = _build_paint_recs(raw.get("paint_recommendations", []))
        scores       = raw.get("scores", {})
        dims         = raw.get("dimensions", [])

        option_id    = "OPTION_A_SPACE" if mode == "space_efficiency" else "OPTION_B_VASTU"
        display_name = "Space-Optimised Layout" if mode == "space_efficiency" else "Vastu-Optimised Layout"

        # Also populate svg_floorplans list (used by some frontend panels)
        svg_list = [fp.svg_dump for fp in floor_plans]

        return LayoutOptionPayload(
            option_id              = option_id,
            display_name           = display_name,
            floors                 = floor_plans,
            vastu_score            = scores.get("vastu", 75.0),
            vastu_report           = [],
            style_applied          = style,
            paint_palette          = {},
            space_utilization_score= scores.get("space_efficiency", 90.0),
            circulation_score      = scores.get("circulation", 85.0),
            wasted_area_score      = 5.0,
            explanation            = f"{display_name} generated for {plot_w}x{plot_d} ft plot, {floors} floor(s).",
            svg_floorplans         = svg_list,
            cost_estimation        = cost_report,
            paint_recommendations  = paint_recs,
            dimensions_data        = dims,
            evaluation_details     = None,
        )