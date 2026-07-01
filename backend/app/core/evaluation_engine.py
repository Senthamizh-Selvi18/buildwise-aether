# app/core/evaluation_engine.py
from typing import Dict, List
from dataclasses import dataclass, field

@dataclass
class EvaluationScore:
    category: str
    score: float
    explanation: str
    factors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

@dataclass
class LayoutEvaluation:
    space_efficiency: EvaluationScore
    vastu_compliance: EvaluationScore
    circulation_quality: EvaluationScore
    natural_lighting: EvaluationScore
    ventilation: EvaluationScore
    construction_efficiency: EvaluationScore
    privacy_zoning: EvaluationScore
    overall_score: float
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

class EvaluationEngine:
    @staticmethod
    def evaluate(rooms: List[Dict], walls: List[Dict],
                 plot_width: float, plot_depth: float,
                 floors: int = 1, mode: str = "adaptive") -> LayoutEvaluation:
        se  = EvaluationEngine._space_efficiency(rooms, plot_width, plot_depth)
        vc  = EvaluationEngine._vastu(rooms, plot_width, plot_depth, mode)
        cq  = EvaluationEngine._circulation(rooms)
        nl  = EvaluationEngine._lighting(rooms, plot_width, plot_depth)
        ven = EvaluationEngine._ventilation(rooms, plot_width, plot_depth)
        ce  = EvaluationEngine._construction(rooms, walls)
        pz  = EvaluationEngine._privacy(rooms)

        weights = {"se":0.20,"vc":0.10,"cq":0.15,"nl":0.15,"ven":0.15,"ce":0.10,"pz":0.15}
        overall = round(
            se.score*weights["se"] + vc.score*weights["vc"] +
            cq.score*weights["cq"] + nl.score*weights["nl"] +
            ven.score*weights["ven"] + ce.score*weights["ce"] +
            pz.score*weights["pz"], 1
        )

        issues = [f"{s.category}: {s.explanation}" for s in [se,vc,cq,nl,ven,ce,pz] if s.score < 60]
        suggestions = []
        for s in [se,vc,cq,nl,ven,ce,pz]:
            suggestions.extend(s.suggestions)

        return LayoutEvaluation(
            space_efficiency=se, vastu_compliance=vc, circulation_quality=cq,
            natural_lighting=nl, ventilation=ven, construction_efficiency=ce,
            privacy_zoning=pz, overall_score=overall,
            issues=issues, suggestions=suggestions,
        )

    @staticmethod
    def _space_efficiency(rooms, pw, pd):
        total = pw * pd
        used  = sum(r.get("area",0) for r in rooms)
        pct   = (used/total)*100 if total else 0
        score = 95 if 65<=pct<=80 else (85 if 60<=pct<65 or 80<pct<=90 else (70 if pct>90 else 50))
        factors = [f"Utilization {pct:.1f}%"]
        sug = [] if 60<=pct<=90 else ["Adjust room sizes for better space utilization."]
        return EvaluationScore("Space Efficiency", score, f"Space utilization {pct:.1f}%", factors, sug)

    @staticmethod
    def _vastu(rooms, pw, pd, mode):
        if mode != "vastu":
            return EvaluationScore("Vastu Compliance", 50,
                "Adaptive mode — Vastu not evaluated.", ["Adaptive mode selected"], [])
        score = 70.0
        factors = ["Vastu mode active"]
        kitchen = next((r for r in rooms if "kitchen" in r.get("name","")), None)
        if kitchen and kitchen.get("x2",0) > pw*0.6 and kitchen.get("y1",1)< pd*0.4:
            score += 15; factors.append("Kitchen in SE (auspicious)")
        master = next((r for r in rooms if "master" in r.get("name","")), None)
        if master and master.get("x2",0)>pw*0.6 and master.get("y2",0)>pd*0.6:
            score += 15; factors.append("Master bedroom in SW (auspicious)")
        return EvaluationScore("Vastu Compliance", min(100,score), " | ".join(factors), factors, [])

    @staticmethod
    def _circulation(rooms):
        accessible = sum(1 for r in rooms
                         if r.get("x1",0)<10 or r.get("x2",0)>90)
        score = 70 + (20 if accessible >= len(rooms)*0.5 else -15)
        factors = [f"{accessible}/{len(rooms)} rooms accessible from edges"]
        return EvaluationScore("Circulation Quality", max(0,min(100,score)),
                               factors[0], factors, [])

    @staticmethod
    def _lighting(rooms, pw, pd):
        exterior = sum(1 for r in rooms
                       if r.get("x1",0)<5 or r.get("x2",pw)>(pw-5)
                       or r.get("y1",0)<5 or r.get("y2",pd)>(pd-5))
        pct = exterior/len(rooms) if rooms else 0
        score = 60 + (30 if pct>=0.7 else 15 if pct>=0.5 else -10)
        factors = [f"{exterior}/{len(rooms)} rooms on exterior wall"]
        sug = [] if pct>=0.5 else ["Position more rooms on exterior walls for natural light."]
        return EvaluationScore("Natural Lighting", max(0,min(100,score)),
                               factors[0], factors, sug)

    @staticmethod
    def _ventilation(rooms, pw, pd):
        cross = sum(1 for r in rooms
                    if (r.get("x1",0)<5 and r.get("x2",0)>pw-5)
                    or (r.get("y1",0)<5 and r.get("y2",0)>pd-5))
        pct = cross/len(rooms) if rooms else 0
        score = 65 + (25 if pct>=0.5 else 10 if pct>=0.3 else 0)
        factors = [f"{cross}/{len(rooms)} rooms with cross-ventilation potential"]
        return EvaluationScore("Ventilation", max(0,min(100,score)),
                               factors[0], factors, [])

    @staticmethod
    def _construction(rooms, walls):
        score = 80.0
        factors = [f"All {len(rooms)} rooms rectangular — easy to construct"]
        return EvaluationScore("Construction Efficiency", score,
                               factors[0], factors, [])

    @staticmethod
    def _privacy(rooms):
        public  = [r for r in rooms if any(k in r.get("name","") for k in ["living","dining","entrance","kitchen"])]
        private = [r for r in rooms if any(k in r.get("name","") for k in ["bedroom","bathroom"])]
        score = 70.0
        factors, sug = [], []
        if public and private:
            px = sum((r.get("x1",0)+r.get("x2",0))/2 for r in public)/len(public)
            rx = sum((r.get("x1",0)+r.get("x2",0))/2 for r in private)/len(private)
            sep = abs(px-rx)
            score += 20 if sep>20 else 10 if sep>10 else -10
            factors.append(f"Public/private separation {sep:.0f}ft")
            if sep<=10: sug.append("Increase separation between living and bedroom zones.")
        return EvaluationScore("Privacy Zoning", max(0,min(100,score)),
                               factors[0] if factors else "Privacy evaluated",
                               factors, sug)