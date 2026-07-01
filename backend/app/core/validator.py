# app/core/validator.py
from typing import Tuple, List, Dict, Optional
from backend.app.core.requirement_extractor import RequirementClues

class ValidationEngine:
    MIN_PLOT_WIDTH = 15
    MIN_PLOT_DEPTH = 20
    MIN_PLOT_AREA  = 400
    MAX_GROUND_COVERAGE = 0.6
    DEFAULT_FRONT_SETBACK = 5
    DEFAULT_REAR_SETBACK  = 5
    DEFAULT_SIDE_SETBACK  = 2

    @staticmethod
    def validate(clues: RequirementClues) -> Tuple[bool, List[str], List[str]]:
        errors, warnings = [], []

        if not clues.plot_width or not clues.plot_depth:
            errors.append("CRITICAL: Plot dimensions are mandatory.")
            return False, errors, warnings

        if clues.plot_width < ValidationEngine.MIN_PLOT_WIDTH:
            errors.append(f"Plot width {clues.plot_width}ft below minimum {ValidationEngine.MIN_PLOT_WIDTH}ft.")
        if clues.plot_depth < ValidationEngine.MIN_PLOT_DEPTH:
            errors.append(f"Plot depth {clues.plot_depth}ft below minimum {ValidationEngine.MIN_PLOT_DEPTH}ft.")

        plot_area = clues.plot_width * clues.plot_depth
        if plot_area < ValidationEngine.MIN_PLOT_AREA:
            errors.append(f"Plot area {plot_area} sq.ft below minimum {ValidationEngine.MIN_PLOT_AREA} sq.ft.")

        if not clues.bhk_count:
            errors.append("CRITICAL: Bedroom count is mandatory.")
            return False, errors, warnings

        if not clues.floors:
            clues.floors = 1

        total_sw = (ValidationEngine.DEFAULT_FRONT_SETBACK + ValidationEngine.DEFAULT_REAR_SETBACK
                    + ValidationEngine.DEFAULT_SIDE_SETBACK * 2)
        if clues.plot_width <= total_sw:
            errors.append(f"Plot width insufficient for setbacks (need >{total_sw}ft).")

        avg_per_bhk = 400
        min_required = clues.bhk_count * avg_per_bhk
        if plot_area < min_required:
            suggested = max(1, int(plot_area / avg_per_bhk))
            warnings.append(f"{clues.bhk_count}BHK may be cramped in {plot_area} sq.ft. Suggest {suggested}BHK.")

        if clues.elder_friendly and clues.floors and clues.floors > 1 and not clues.has_lift:
            warnings.append("Elder-friendly on multi-story should include a lift.")

        if clues.rental_portion and clues.bhk_count < 2:
            errors.append("Rental portion requires at least 2BHK.")

        return len(errors) == 0, errors, warnings

    @staticmethod
    def suggest_alternatives(clues: RequirementClues, errors: List[str]) -> Dict:
        recs = []
        plot_area = (clues.plot_width or 0) * (clues.plot_depth or 0)
        for error in errors:
            if "width" in error.lower():
                recs.append(f"Increase plot width to at least {ValidationEngine.MIN_PLOT_WIDTH + ValidationEngine.DEFAULT_SIDE_SETBACK * 2}ft.")
            if "bhk" in error.lower() or "bedroom" in error.lower():
                recs.append(f"Reduce bedrooms to {max(1, int(plot_area / 400))} for comfort.")
            if "rental" in error.lower():
                recs.append("Increase to 2BHK or more for a rental unit.")
        return {"recommendations": recs}