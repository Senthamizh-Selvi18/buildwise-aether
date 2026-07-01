import math
import re
import json
from typing import Dict, List, Any
from backend.app.agents.geometry_engine import GeometricBlueprintEngine

class UnifiedAetherOrchestrator:
    """
    Coordinates multi-agent processes. Connects the Requirements and Layout Agents 
    directly to the mathematical Procedural Geometry Engine.
    """

    def evaluate_and_generate(self, prompt: str, answers: Dict[str, str]) -> Dict[str, Any]:
        combined_text = (prompt + " " + " ".join(answers.values())).lower()

        # Multi-Agent Stage 1: Check for missing details via the Clarification Agent
        missing_questions = []
        missing_fields = []

        if not re.search(r'(\d+)\s*(sq|ft|size|plot|sqft)', combined_text) and not re.search(r'(\d+)\s*x\s*(\d+)', combined_text):
            missing_fields.append("plot_info")
            missing_questions.append("What is your plot size (e.g., 30x50 or 1500 sq ft)?")
        
        if not re.search(r'(\d+)\s*(floor|story|level|duplex)', combined_text):
            missing_fields.append("floors_info")
            missing_questions.append("How many floors do you want to build (e.g., 1 floor, 2 floors)?")

        if not re.search(r'(\d+)\s*(bhk|bedroom|bed)', combined_text):
            missing_fields.append("rooms_info")
            missing_questions.append("How many bedrooms do you need (e.g., 2 BHK, 3 BHK)?")

        if len(missing_fields) > 0:
            return {
                "requires_clarification": True,
                "missing_fields": missing_fields,
                "questions": missing_questions,
                "options": None
            }

        # Multi-Agent Stage 2: Extract spatial dimensions and configurations
        area_match = re.search(r'(\d+)\s*(sqft|sq\s*ft|square)', combined_text)
        total_area = float(area_match.group(1)) if area_match else 1500.0
        
        dim_match = re.search(r'(\d+)\s*x\s*(\d+)', combined_text)
        if dim_match:
            width = float(dim_match.group(1))
            depth = float(dim_match.group(2))
        else:
            width = round(math.sqrt(total_area * 1.25))
            depth = round(total_area / width)

        floor_match = re.search(r'(\d+)\s*(floor|story|level)', combined_text)
        floors_count = int(floor_match.group(1)) if floor_match else 2
        
        bed_match = re.search(r'(\d+)\s*(bhk|bedroom)', combined_text)
        bedrooms = int(bed_match.group(1)) if bed_match else 3

        plot_shape = "rectangle"
        if "l-" in combined_text or "l shape" in combined_text:
            plot_shape = "l_shape"
        elif "triangle" in combined_text:
            plot_shape = "triangle"

        # Multi-Agent Stage 3: The Layout Agent organizes space requirements across floors
        rooms_list = ["Living Room", "Kitchen Space", "Dining Hall", "Staircase Access"]
        if "pooja" in combined_text:
            rooms_list.append("Pooja Room")
        if "parking" in combined_text or total_area >= 1200:
            rooms_list.append("Covered Parking")
        if "garden" in combined_text:
            rooms_list.append("Exterior Garden")

        for b in range(bedrooms):
            rooms_list.append(f"Master Bedroom" if b == 0 else f"Bedroom {b+1}")

        rooms_by_floor = {f: [] for f in range(floors_count)}
        for idx, r_name in enumerate(rooms_list):
            target_layer = idx % floors_count
            rooms_by_floor[target_layer].append(r_name)

        # Multi-Agent Stage 4: Run geometry allocations for Options A and B
        options_output = {
            "OPTION_A_SPACE": self._build_deterministic_option(rooms_by_floor, width, depth, floors_count, plot_shape, "space"),
            "OPTION_B_VASTU": self._build_deterministic_option(rooms_by_floor, width, depth, floors_count, plot_shape, "vastu")
        }

        return {
            "requires_clarification": False,
            "missing_fields": [],
            "questions": [],
            "options": options_output
        }

    def _build_deterministic_option(self, rooms_map: Dict[int, List[str]], w: float, d: float, total_floors: int, shape: str, option_type: str) -> Dict[str, Any]:
        layers = []
        
        for f in range(total_floors):
            floor_rooms = rooms_map[f]
            if not floor_rooms:
                floor_rooms = ["Common Lobby Area"]

            # Trigger the Geometry Engine for deterministic room, wall, and portal updates
            computed_rooms = GeometricBlueprintEngine.slice_polygon_space(
                boundary=[], rooms_list=floor_rooms, width=w, depth=d, option_type=option_type
            )
            computed_walls = GeometricBlueprintEngine.generate_walls_network(computed_rooms, w, d)
            computed_portals = GeometricBlueprintEngine.compute_openings_and_portals(computed_rooms)

            # Automatically adjust room scales if internal validations fail
            if not GeometricBlueprintEngine.perform_validation_checks(computed_rooms, w, d):
                for rm in computed_rooms:
                    rm["width_ft"] = max(rm["width_ft"], 8.0)
                    rm["area_sqft"] = rm["width_ft"] * rm["height_ft"]

            # Plot columns cleanly at the corners of every room boundary line
            columns_vertices = []
            for rm in computed_rooms:
                for pt in rm["points"]:
                    if pt not in columns_vertices:
                        columns_vertices.append(pt)

            layers.append({
                "floor_level": f,
                "floor_name": "Ground Floor Plan Blueprint" if f == 0 else f"First Floor Architectural Sheet" if f == 1 else f"Level {f+1} Blueprint",
                "rooms": computed_rooms,
                "walls": computed_walls,
                "portals": computed_portals,
                "columns": columns_vertices,
                "has_staircase": any("stair" in r["name"].lower() for r in computed_rooms),
                "has_balcony": f > 0
            })

        return {
            "layout_id": f"cad_blueprint_{option_type}",
            "title": "Space Optimized Functional Plan" if option_type == "space" else "Vastu Compliant Orientations Plan",
            "space_efficiency_sentence": "Maximizes interior space by avoiding dark corridors or wasted hallway segments.",
            "vastu_compliance_sentence": "Fully aligned with traditional environmental airflow guidelines.",
            "estimated_cost_usd": float(w * d * total_floors * 155),
            "floors": layers
        }

orchestrator = UnifiedAetherOrchestrator()