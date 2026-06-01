"""Agro-ecological requirement profiles for North African crops.

Each factor range is a trapezoid ``(abs_min, opt_min, opt_max, abs_max)``:
outside the absolute limits the crop fails, between the optimal limits it
thrives, and in between suitability falls off linearly. The ranges are
adapted from FAO ECOCROP and regional agronomic literature and tuned for
Mediterranean / semi-arid conditions. Treat them as a transparent starting
point that can be refined with local field data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Factor metadata: label, unit, short description
FACTORS = {
    "rain": ("Annual rainfall", "mm", "Mean annual precipitation"),
    "t_mean": ("Mean temperature", "°C", "Mean annual air temperature"),
    "t_cold": ("Coldest month", "°C", "Mean temperature of the coldest month (frost risk / chilling)"),
    "t_hot": ("Hottest month max", "°C", "Mean daily maximum of the hottest month (heat stress)"),
    "ph": ("Soil pH", "", "Topsoil pH in water (0-30 cm)"),
    "clay": ("Clay content", "%", "Topsoil clay fraction (0-30 cm)"),
    "elev": ("Elevation", "m", "Height above sea level"),
}

WATER_FACTORS = {"rain"}


@dataclass(frozen=True)
class CropProfile:
    key: str
    name: str
    scientific: str
    icon: str
    category: str
    season: str
    water_need: str
    ranges: dict[str, tuple[float, float, float, float]]
    weights: dict[str, float] = field(default_factory=dict)
    notes: str = ""

    def weight(self, factor: str) -> float:
        return self.weights.get(factor, 1.0)


CROPS: dict[str, CropProfile] = {
    p.key: p
    for p in [
        CropProfile(
            "durum_wheat", "Durum wheat", "Triticum durum", "🌾", "Cereal", "Nov–Jun (winter)", "Medium",
            ranges={
                "rain": (250, 400, 700, 1100), "t_mean": (8, 13, 20, 25), "t_cold": (-8, 2, 12, 17),
                "t_hot": (20, 25, 40, 47), "ph": (5.5, 6.5, 8.2, 8.8), "clay": (5, 20, 45, 60), "elev": (-50, 0, 1300, 2300),
            },
            weights={"rain": 1.5, "t_hot": 0.4, "elev": 0.5},
            notes="Backbone of the Tunisian and Algerian cereal belts; prefers deep clay-loam soils.",
        ),
        CropProfile(
            "barley", "Barley", "Hordeum vulgare", "🌾", "Cereal", "Nov–May (winter)", "Low",
            ranges={
                "rain": (150, 280, 600, 1000), "t_mean": (6, 12, 21, 27), "t_cold": (-10, 0, 12, 18),
                "t_hot": (20, 25, 41, 48), "ph": (5.5, 6.5, 8.4, 9.0), "clay": (3, 12, 40, 60), "elev": (-50, 0, 1600, 2800),
            },
            weights={"rain": 1.5, "t_hot": 0.4, "elev": 0.5},
            notes="The most drought- and salt-tolerant cereal; standard choice on marginal semi-arid land.",
        ),
        CropProfile(
            "olive", "Olive", "Olea europaea", "🫒", "Tree crop", "Perennial", "Low",
            ranges={
                "rain": (150, 300, 700, 1200), "t_mean": (12, 15, 21, 25), "t_cold": (2, 6, 12, 16),
                "t_hot": (22, 28, 37, 43), "ph": (5.5, 6.5, 8.5, 9.0), "clay": (3, 10, 40, 55), "elev": (-50, 0, 800, 1400),
            },
            weights={"rain": 1.2},
            notes="Needs mild winter chilling for flowering. Sfax-style rainfed groves survive on ~200 mm with wide spacing.",
        ),
        CropProfile(
            "date_palm", "Date palm", "Phoenix dactylifera", "🌴", "Tree crop", "Perennial", "High (groundwater)",
            ranges={
                "rain": (0, 0, 150, 450), "t_mean": (18, 21, 30, 35), "t_cold": (5, 10, 18, 25),
                "t_hot": (32, 38, 46, 50), "ph": (6.0, 7.0, 8.6, 9.5), "clay": (0, 3, 30, 50), "elev": (-50, 0, 500, 1000),
            },
            weights={"t_hot": 1.5},
            notes="Oasis crop: dry air ripens the fruit, roots tap groundwater. Rain at harvest causes rot.",
        ),
        CropProfile(
            "citrus", "Citrus", "Citrus sinensis", "🍊", "Tree crop", "Perennial", "High",
            ranges={
                "rain": (300, 900, 1500, 2500), "t_mean": (13, 17, 25, 30), "t_cold": (3, 8, 15, 22),
                "t_hot": (24, 28, 36, 42), "ph": (5.0, 6.0, 7.6, 8.5), "clay": (5, 10, 35, 50), "elev": (-50, 0, 600, 1200),
            },
            weights={"t_cold": 1.4},
            notes="Frost-sensitive. Cap Bon is the reference area; almost always irrigated.",
        ),
        CropProfile(
            "grapevine", "Grapevine", "Vitis vinifera", "🍇", "Tree crop", "Perennial", "Medium",
            ranges={
                "rain": (250, 400, 800, 1300), "t_mean": (10, 14, 20, 24), "t_cold": (-5, 2, 10, 14),
                "t_hot": (22, 26, 35, 41), "ph": (5.5, 6.0, 8.2, 8.7), "clay": (3, 10, 35, 50), "elev": (-50, 0, 1000, 1600),
            },
            notes="Wine and table grapes; winter dormancy needs cool months.",
        ),
        CropProfile(
            "almond", "Almond", "Prunus dulcis", "🌰", "Tree crop", "Perennial", "Low–medium",
            ranges={
                "rain": (200, 350, 700, 1000), "t_mean": (10, 14, 20, 24), "t_cold": (-2, 3, 10, 14),
                "t_hot": (24, 28, 37, 42), "ph": (6.0, 7.0, 8.4, 8.8), "clay": (3, 8, 30, 45), "elev": (-50, 0, 1100, 1700),
            },
            notes="Early flowering makes late frosts the main risk; dislikes heavy wet soils.",
        ),
        CropProfile(
            "pistachio", "Pistachio", "Pistacia vera", "🥜", "Tree crop", "Perennial", "Low",
            ranges={
                "rain": (120, 220, 500, 800), "t_mean": (12, 15, 22, 26), "t_cold": (-5, 2, 10, 14),
                "t_hot": (30, 33, 40, 45), "ph": (6.5, 7.2, 8.6, 9.2), "clay": (3, 8, 30, 45), "elev": (-50, 100, 1200, 2000),
            },
            weights={"t_cold": 1.3, "t_hot": 1.2},
            notes="Needs hot dry summers and cold winters; well adapted to central Tunisia (Kasserine, Sidi Bouzid).",
        ),
        CropProfile(
            "fig", "Fig", "Ficus carica", "🌳", "Tree crop", "Perennial", "Low",
            ranges={
                "rain": (200, 350, 800, 1200), "t_mean": (12, 15, 22, 27), "t_cold": (-2, 4, 12, 18),
                "t_hot": (26, 30, 38, 44), "ph": (5.5, 6.5, 8.2, 8.8), "clay": (3, 10, 35, 50), "elev": (-50, 0, 900, 1500),
            },
            notes="Hardy smallholder tree, tolerant of poor stony soils.",
        ),
        CropProfile(
            "tomato", "Tomato", "Solanum lycopersicum", "🍅", "Vegetable", "Mar–Sep (open field)", "High",
            ranges={
                "rain": (300, 500, 900, 1500), "t_mean": (12, 17, 25, 30), "t_cold": (0, 6, 16, 24),
                "t_hot": (22, 27, 33, 40), "ph": (5.5, 6.0, 7.6, 8.4), "clay": (5, 12, 35, 50), "elev": (-50, 0, 800, 1500),
            },
            weights={"rain": 0.8, "t_cold": 0.5, "t_hot": 1.4},
            notes="Major processing crop in Tunisia (Cap Bon, Kairouan) under irrigation; fruit set drops above ~35 °C.",
        ),
        CropProfile(
            "potato", "Potato", "Solanum tuberosum", "🥔", "Vegetable", "Two seasons (spring / autumn)", "High",
            ranges={
                "rain": (300, 500, 800, 1200), "t_mean": (8, 13, 20, 25), "t_cold": (-2, 5, 14, 20),
                "t_hot": (18, 22, 31, 44), "ph": (4.8, 5.5, 7.2, 8.2), "clay": (3, 8, 28, 50), "elev": (-50, 0, 1500, 2500),
            },
            weights={"t_hot": 0.5, "clay": 1.2},
            notes="Light, well-drained soils give clean tubers. Grown in two cycles to avoid summer heat.",
        ),
        CropProfile(
            "chickpea", "Chickpea", "Cicer arietinum", "🫘", "Legume", "Dec–Jun (winter / spring)", "Low",
            ranges={
                "rain": (250, 350, 650, 1000), "t_mean": (8, 13, 22, 28), "t_cold": (-5, 3, 12, 18),
                "t_hot": (22, 26, 38, 44), "ph": (5.5, 6.5, 8.2, 8.8), "clay": (5, 15, 40, 55), "elev": (-50, 0, 1200, 2200),
            },
            weights={"t_hot": 0.6},
            notes="Fixes nitrogen and breaks cereal disease cycles in wheat rotations.",
        ),
        CropProfile(
            "faba_bean", "Faba bean", "Vicia faba", "🫛", "Legume", "Nov–May (winter)", "Medium",
            ranges={
                "rain": (300, 400, 700, 1100), "t_mean": (6, 12, 19, 25), "t_cold": (-5, 3, 12, 16),
                "t_hot": (20, 24, 38, 44), "ph": (5.5, 6.5, 8.2, 8.7), "clay": (10, 20, 45, 60), "elev": (-50, 0, 1500, 2500),
            },
            weights={"t_hot": 0.5},
            notes="Traditional legume of the sub-humid north; good rotation partner for durum wheat.",
        ),
    ]
}


def get_crop(key: str) -> CropProfile:
    try:
        return CROPS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown crop '{key}'. Options: {', '.join(CROPS)}") from exc
