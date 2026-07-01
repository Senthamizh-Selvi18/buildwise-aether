from typing import List, Tuple
from backend.app.schemas.floorplan import FloorPlan

class VastuAgent:
    def assess_compliance(self, floors: List[FloorPlan]) -> Tuple[float, List[str]]:
        report = []
        deductions = 0.0
        
        if not floors:
            return 100.0, ["Empty footprint layout sequence initialized."]

        g_floor = floors[0]
        has_staircase = False
        
        for rm in g_floor.rooms:
            name = rm.name.lower()
            # Calculate geometric midpoint center lines
            mid_x = (rm.x1 + rm.x2) / 2
            mid_y = (rm.y1 + rm.y2) / 2
            
            if "staircase" in name:
                has_staircase = True

            if "pooja" in name:
                if mid_x < 20.0 and mid_y < 20.0:
                    report.append("PASS: Pooja Room correctly located in the auspicious Ishanya (Northeast) quadrant.")
                else:
                    deductions += 15.0
                    report.append("INFRACTION: Pooja Room misplaced out of Northeast corner quadrant boundaries.")
                    
            if "kitchen" in name:
                if mid_x > 20.0 and mid_y > 20.0:
                    report.append("PASS: Kitchen positioned within Agni (Southeast) fire element location matrix.")
                else:
                    deductions += 15.0
                    report.append("INFRACTION: Kitchen situated outside of standard Southeast zoning boundaries.")

        if not has_staircase:
            report.append("WARNING: Multi-tier access grid requires an active structural staircase track configuration.")
            
        final_score = max(100.0 - deductions, 40.0)
        return final_score, report