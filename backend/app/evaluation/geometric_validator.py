from typing import List, Dict, Any, Tuple

class GeometricValidator:
    """
    High-Performance coordinate alignment audit matrix logic engine.
    """
    def audit_collisions(self, room_coordinates: List[Dict[str, Any]]) -> Tuple[bool, int, List[str]]:
        infractions = []
        overlap_flag = False
        
        if not room_coordinates:
            return False, 100, []

        for i in range(len(room_coordinates)):
            r1 = room_coordinates[i]
            # Validate individual bounding box dimensions
            if (r1["x2"] <= r1["x1"]) or (r1["y2"] <= r1["y1"]):
                infractions.append(f"Room '{r1['room_name']}' layout bounds are inverted or structurally collapsed.")
                overlap_flag = True
                
            for j in range(i + 1, len(room_coordinates)):
                r2 = room_coordinates[j]
                
                # Check for geometric rectangle intersections
                horizontal_overlap = not (r1["x2"] <= r2["x1"] or r1["x1"] >= r2["x2"])
                vertical_overlap = not (r1["y2"] <= r2["y1"] or r1["y1"] >= r2["y2"])
                
                if horizontal_overlap and vertical_overlap:
                    overlap_flag = True
                    infractions.append(f"Geometric collision detected between room block '{r1['room_name']}' and '{r2['room_name']}'.")

        calculated_score = max(0, 100 - (len(infractions) * 20))
        return overlap_flag, calculated_score, infractions