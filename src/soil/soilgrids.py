"""Topsoil properties from ISRIC SoilGrids 2.0 (250 m global soil maps).

SoilGrids stores values as integers with a scale factor (e.g. pH x10,
clay in g/kg). We query the 0-5, 5-15 and 15-30 cm layers and return a
thickness-weighted 0-30 cm mean in conventional units.

The public API has a fair-use limit (about 5 requests/minute), so callers
should cache results and fall back to defaults for bulk scans.
"""

from __future__ import annotations

from src.config import SOILGRIDS_URL
from src.http import DataSourceError, get_json

DEPTHS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
# property -> (output key, divisor to conventional units)
PROPERTIES = {
    "phh2o": ("ph", 10.0),     # pH x10      -> pH
    "clay": ("clay", 10.0),    # g/kg        -> %
    "sand": ("sand", 10.0),    # g/kg        -> %
    "soc": ("soc", 10.0),      # dg/kg       -> g/kg
}


def fetch_soil(lat: float, lon: float) -> dict[str, float]:
    """Query the point, then nudge ~1 km away if it falls on a masked pixel (town, road, water)."""
    last: DataSourceError | None = None
    for dlat, dlon in [(0, 0), (0.01, 0), (-0.01, 0.01)]:
        try:
            return _fetch_point(lat + dlat, lon + dlon)
        except DataSourceError as exc:
            last = exc
    raise last


def _fetch_point(lat: float, lon: float) -> dict[str, float]:
    params = {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "property": list(PROPERTIES),
        "depth": list(DEPTHS),
        "value": "mean",
    }
    data = get_json(SOILGRIDS_URL, params, retries=2, timeout=30)
    layers = data.get("properties", {}).get("layers", [])
    if not layers:
        raise DataSourceError("SoilGrids returned no layers")

    result: dict[str, float] = {}
    for layer in layers:
        key, divisor = PROPERTIES.get(layer["name"], (None, None))
        if key is None:
            continue
        total, weight = 0.0, 0
        for depth in layer["depths"]:
            thickness = DEPTHS.get(depth["label"])
            value = depth["values"].get("mean")
            if thickness and value is not None:
                total += value / divisor * thickness
                weight += thickness
        if weight:
            result[key] = round(total / weight, 2)

    # SoilGrids returns nulls over water, cities and bare rock.
    if "ph" not in result or "clay" not in result:
        raise DataSourceError("No soil data at this location (urban, water or rock?)")
    return result


def texture_class(clay: float, sand: float) -> str:
    """Simplified USDA texture triangle."""
    silt = max(0.0, 100 - clay - sand)
    if clay >= 40:
        return "Clay"
    if clay >= 27:
        return "Clay loam" if sand <= 45 else "Sandy clay loam"
    if sand >= 85:
        return "Sand"
    if sand >= 70:
        return "Loamy sand"
    if sand >= 52:
        return "Sandy loam"
    if silt >= 50:
        return "Silt loam"
    return "Loam"
