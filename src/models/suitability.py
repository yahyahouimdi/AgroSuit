"""Fuzzy multi-criteria land suitability engine (FAO framework).

1. Each site factor gets a 0-1 membership score from a trapezoid.
2. The scores are combined with a *weighted geometric mean*, so a factor at
   zero pulls the whole crop to zero (Liebig's law of the minimum) while
   still rewarding sites that are good on many factors.
3. A small centrality bonus (up to 15 %) separates crops that sit
   comfortably in the middle of their optimum from those at its edge, so
   ties at "1.0" are broken in an agronomically meaningful way.
4. The result maps to the FAO classes S1 / S2 / S3 / N, and the weakest
   factor is reported as the limiting factor, with a management hint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.config import SUITABILITY_CLASSES
from src.models.crop_profiles import CROPS, FACTORS, WATER_FACTORS, CropProfile

EPS = 1e-3
OPTIMAL = 0.98  # factor scores above this count as "within optimum"


def trapezoid(value: float, abs_min: float, opt_min: float, opt_max: float, abs_max: float) -> float:
    """Membership of ``value`` in a trapezoidal fuzzy set, between 0 and 1."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return float("nan")
    if opt_min <= value <= opt_max:
        return 1.0
    if value <= abs_min or value >= abs_max:
        return 0.0
    if value < opt_min:
        return (value - abs_min) / (opt_min - abs_min)
    return (abs_max - value) / (abs_max - opt_max)


def classify(score: float) -> tuple[str, str, str]:
    """Return (code, label, colour) for a 0-1 suitability score."""
    for lower, code, label, colour in SUITABILITY_CLASSES:
        if score >= lower:
            return code, label, colour
    return SUITABILITY_CLASSES[-1][1:]


@dataclass
class FactorScore:
    factor: str
    value: float
    score: float
    optimum: tuple[float, float]
    weight: float
    centrality: float = 0.0

    @property
    def label(self) -> str:
        return FACTORS[self.factor][0]

    @property
    def unit(self) -> str:
        return FACTORS[self.factor][1]


@dataclass
class CropSuitability:
    crop: CropProfile
    score: float
    factors: list[FactorScore] = field(default_factory=list)
    irrigated: bool = False

    @property
    def code(self) -> str:
        return classify(self.score)[0]

    @property
    def label(self) -> str:
        return classify(self.score)[1]

    @property
    def colour(self) -> str:
        return classify(self.score)[2]

    @property
    def limiting(self) -> FactorScore | None:
        scored = [f for f in self.factors if f.score < OPTIMAL]
        return min(scored, key=lambda f: f.score) if scored else None

    def advice(self) -> list[str]:
        """Human-readable management hints for every sub-optimal factor."""
        hints = []
        for f in sorted(self.factors, key=lambda f: f.score):
            if f.score >= OPTIMAL:
                continue
            lo, hi = f.optimum
            hints.append(_hint(f, lo, hi))
        return hints

    def as_dict(self) -> dict:
        lim = self.limiting
        return {
            "crop": self.crop.key,
            "name": self.crop.name,
            "score": round(self.score, 3),
            "class": self.code,
            "class_label": self.label,
            "limiting_factor": lim.label if lim else None,
            **{f"f_{f.factor}": round(f.score, 3) for f in self.factors},
        }


def _hint(f: FactorScore, lo: float, hi: float) -> str:
    unit = f" {f.unit}" if f.unit and f.unit != "%" else f.unit
    below = f.value < lo
    gap = (lo - f.value) if below else (f.value - hi)
    target = f"{lo:g}–{hi:g}{unit}"
    fixes = {
        ("rain", True): f"Water deficit of ~{gap:.0f} mm/yr: plan supplemental or drip irrigation, or use water-harvesting (tabias, jessour).",
        ("rain", False): f"Excess rainfall (+{gap:.0f} mm): ensure drainage and watch fungal disease pressure.",
        ("t_mean", True): "Climate is cooler than optimal: choose early-maturing varieties or sheltered, south-facing plots.",
        ("t_mean", False): "Climate is warmer than optimal: shift sowing dates, use heat-tolerant cultivars.",
        ("t_cold", True): "Frost risk in the coldest month: avoid frost pockets, use frost-tolerant rootstocks or late-flowering varieties.",
        ("t_cold", False): "Winters are too mild for full chilling/vernalisation: pick low-chill cultivars.",
        ("t_hot", True): "Summers are too cool for full ripening: favour early cultivars.",
        ("t_hot", False): "Heat stress at peak summer: shade nets, mulching, and timing flowering before the hottest weeks.",
        ("ph", True): "Soil is too acidic: apply agricultural lime.",
        ("ph", False): "Soil is too alkaline/calcareous: add organic matter, sulfur or acidifying fertilisers (ammonium sulfate); watch for iron chlorosis.",
        ("clay", True): "Soil is very light/sandy: build organic matter and irrigate more often in smaller doses.",
        ("clay", False): "Soil is heavy clay: improve drainage, avoid waterlogging, and work it only at the right moisture.",
        ("elev", True): "Below the preferred elevation range.",
        ("elev", False): "Above the preferred elevation: shorter season and colder nights are likely.",
    }
    action = fixes.get((f.factor, below), "")
    return f"**{f.label}** {f.value:g}{unit} vs optimum {target} (score {f.score:.2f}). {action}"


def _centrality(value: float, opt_min: float, opt_max: float, score: float) -> float:
    """1 at the centre of the optimum, 0 at its edges and beyond."""
    if score < 1.0:
        return 0.0
    half = (opt_max - opt_min) / 2
    if half <= 0:
        return 1.0
    return max(0.0, 1 - abs(value - (opt_min + half)) / half)


def score_crop(features: dict[str, float], crop: CropProfile, irrigated: bool = False) -> CropSuitability:
    factors: list[FactorScore] = []
    for name, (a, b, c, d) in crop.ranges.items():
        value = features.get(name)
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        s = trapezoid(value, a, b, c, d)
        # Under irrigation a water shortage no longer limits; excess rain still does.
        if irrigated and name in WATER_FACTORS and value < c:
            s = 1.0
        factors.append(FactorScore(name, float(value), s, (b, c), crop.weight(name), _centrality(value, b, c, s)))

    if not factors:
        return CropSuitability(crop, float("nan"), factors, irrigated)

    total_w = sum(f.weight for f in factors)
    log_sum = sum(f.weight * math.log(max(f.score, EPS)) for f in factors)
    membership = math.exp(log_sum / total_w)
    centre = sum(f.weight * f.centrality for f in factors) / total_w
    overall = membership * (0.85 + 0.15 * centre)
    if min(f.score for f in factors) <= 0.0:
        overall = min(overall, 0.39)  # a failed factor always means class N
    return CropSuitability(crop, overall, factors, irrigated)


def rank_crops(features: dict[str, float], irrigated: bool = False, crops: list[str] | None = None) -> list[CropSuitability]:
    keys = crops or list(CROPS)
    results = [score_crop(features, CROPS[k], irrigated) for k in keys]
    return sorted(results, key=lambda r: (-(r.score if not math.isnan(r.score) else -1)))
