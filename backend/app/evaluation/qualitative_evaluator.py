from typing import Dict, Any, List
import json

class QualitativeEvaluator:
    @staticmethod
    def inspect_architectural_flow(room_array: List[Dict[str, Any]]) -> Dict[str, Any]:
        has_kitchen = any("kitchen" in r["room_name"].lower() for r in room_array)
        has_living = any("living" in r["room_name"].lower() for r in room_array)
        
        score = 100
        comments = []
        
        if not has_kitchen:
            score -= 30
            comments.append("Layout lacks an explicit domestic kitchen segment.")
        if not has_living:
            score -= 20
            comments.append("Layout misses a foundational central living environment area.")
            
        return {
            "functional_score": max(0, score),
            "critique_notes": comments,
            "status": "passed" if score >= 70 else "review_required"
        }