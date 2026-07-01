# app/core/requirement_extractor.py
# Sourced from document index 2 — no changes to class logic
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class RequirementClues:
    plot_width: Optional[float] = None
    plot_depth: Optional[float] = None
    bhk_count: Optional[int] = None
    floors: Optional[int] = None
    has_parking: Optional[bool] = None
    parking_vehicles: Optional[int] = None
    has_balcony: Optional[bool] = None
    has_terrace: Optional[bool] = None
    has_garden: Optional[bool] = None
    has_pooja: Optional[bool] = None
    has_office: Optional[bool] = None
    has_guest_bedroom: Optional[bool] = None
    has_utility: Optional[bool] = None
    has_storeroom: Optional[bool] = None
    has_lift: Optional[bool] = None
    parking_type: Optional[str] = None
    interior_style: Optional[str] = None
    paint_style: Optional[str] = None
    budget_category: Optional[str] = None
    elder_friendly: Optional[bool] = None
    attached_bathrooms: Optional[bool] = None
    future_expansion: Optional[bool] = None
    rental_portion: Optional[bool] = None
    swimming_pool: Optional[bool] = None


class RequirementExtractor:
    STYLE_KEYWORDS = {
        "modern": ["modern", "contemporary", "minimalist", "clean", "sleek"],
        "traditional": ["traditional", "classic", "colonial", "heritage"],
        "luxury": ["luxury", "premium", "high-end", "opulent"],
        "minimal": ["minimal", "minimalist", "simple", "zen"],
        "industrial": ["industrial", "loft", "warehouse", "raw"],
        "scandinavian": ["scandinavian", "nordic", "hygge"],
    }
    PAINT_STYLES = {
        "light": ["light", "bright", "pale", "soft", "pastel"],
        "dark": ["dark", "bold", "deep", "charcoal"],
        "neutral": ["neutral", "beige", "gray", "taupe"],
        "warm": ["warm", "orange", "terracotta", "earthy"],
        "cool": ["cool", "blue", "green", "teal"],
    }
    BUDGET_CATEGORIES = {
        "economy": ["economy", "budget", "basic", "affordable"],
        "standard": ["standard", "normal", "regular", "average"],
        "premium": ["premium", "high", "upscale", "quality"],
        "luxury": ["luxury", "exclusive", "bespoke"],
    }

    @staticmethod
    def extract(user_prompt: str) -> Tuple[RequirementClues, List[str]]:
        prompt_lower = user_prompt.lower()
        clues = RequirementClues()
        questions = []

        # Plot dimensions
        for pattern in [r'(\d+)\s*[x×\*]\s*(\d+)', r'(\d+)\s*feet\s*[x×]\s*(\d+)\s*feet']:
            match = re.search(pattern, prompt_lower)
            if match:
                d1, d2 = float(match.group(1)), float(match.group(2))
                clues.plot_width = max(d1, d2)
                clues.plot_depth = min(d1, d2)
                break
        if not clues.plot_width:
            questions.append("What is your plot size? (e.g., 30x40 feet)")

        # BHK
        bhk = re.search(r'(\d+)\s*bhk|(\d+)\s*bed', prompt_lower)
        if bhk:
            clues.bhk_count = int(bhk.group(1) or bhk.group(2))
        if not clues.bhk_count:
            questions.append("How many bedrooms? (e.g., 2BHK, 3BHK)")

        # Floors
        if "single" in prompt_lower and "floor" in prompt_lower:
            clues.floors = 1
        elif "double" in prompt_lower and "floor" in prompt_lower:
            clues.floors = 2
        else:
            fm = re.search(r'(\d+)\s*(?:floor|storey|story)', prompt_lower)
            if fm:
                clues.floors = int(fm.group(1))
        if not clues.floors:
            questions.append("How many floors?")

        # Parking
        clues.has_parking = "parking" in prompt_lower
        if clues.has_parking:
            pm = re.search(r'(\d+)\s*(?:car|vehicle)', prompt_lower)
            clues.parking_vehicles = int(pm.group(1)) if pm else 1
            clues.parking_type = "covered" if "covered" in prompt_lower else (
                "open" if "open" in prompt_lower else None)

        # Optional rooms
        clues.has_balcony   = "balcony" in prompt_lower
        clues.has_terrace   = "terrace" in prompt_lower or "roof" in prompt_lower
        clues.has_garden    = "garden" in prompt_lower
        clues.has_pooja     = any(k in prompt_lower for k in ["pooja", "puja", "prayer"])
        clues.has_office    = any(k in prompt_lower for k in ["office", "work space", "work from home"])
        clues.has_guest_bedroom = "guest" in prompt_lower
        clues.has_utility   = any(k in prompt_lower for k in ["utility", "laundry"])
        clues.has_storeroom = any(k in prompt_lower for k in ["store", "storage", "pantry"])
        clues.has_lift      = any(k in prompt_lower for k in ["lift", "elevator"])
        clues.attached_bathrooms = any(k in prompt_lower for k in ["attached", "en-suite", "ensuite"])
        clues.elder_friendly     = any(k in prompt_lower for k in ["elder", "senior", "aged"])
        clues.future_expansion   = any(k in prompt_lower for k in ["future", "expansion", "extend"])
        clues.rental_portion     = any(k in prompt_lower for k in ["rental", "income", "tenant"])
        clues.swimming_pool      = any(k in prompt_lower for k in ["pool", "swimming"])

        # Style / paint / budget
        for style, kws in RequirementExtractor.STYLE_KEYWORDS.items():
            if any(k in prompt_lower for k in kws):
                clues.interior_style = style
                break
        for paint, kws in RequirementExtractor.PAINT_STYLES.items():
            if any(k in prompt_lower for k in kws):
                clues.paint_style = paint
                break
        for budget, kws in RequirementExtractor.BUDGET_CATEGORIES.items():
            if any(k in prompt_lower for k in kws):
                clues.budget_category = budget
                break

        return clues, questions

    @staticmethod
    def consolidate_answers(clues: RequirementClues, answers: Dict[str, str]) -> RequirementClues:
        for question, answer in {k: v.lower() for k, v in answers.items()}.items():
            q = question.lower()
            if "plot" in q:
                m = re.search(r'(\d+)\s*[x×\*]\s*(\d+)', answer)
                if m:
                    d1, d2 = float(m.group(1)), float(m.group(2))
                    clues.plot_width, clues.plot_depth = max(d1,d2), min(d1,d2)
            elif "bedroom" in q or "bhk" in q:
                m = re.search(r'(\d+)', answer)
                if m: clues.bhk_count = int(m.group(1))
            elif "floor" in q:
                m = re.search(r'(\d+)', answer)
                if m: clues.floors = int(m.group(1))
            elif "parking" in q:
                clues.has_parking = "yes" in answer or "need" in answer
                m = re.search(r'(\d+)', answer)
                if m: clues.parking_vehicles = int(m.group(1))
        return clues