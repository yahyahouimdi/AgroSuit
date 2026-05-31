"""Optional Sentinel-2 vegetation snapshot through Google Earth Engine.

Earth Engine needs a one-time ``earthengine authenticate`` and a Cloud
project. When the ``ee`` package or credentials are missing, every function
returns ``None`` and the rest of the pipeline keeps working.
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def earth_engine_ready() -> bool:
    try:
        import ee  # noqa: F401
    except ImportError:
        return False
    try:
        project = os.getenv("EE_PROJECT")
        ee.Initialize(project=project) if project else ee.Initialize()
        return True
    except Exception:
        return False


def fetch_vegetation_indices(lat: float, lon: float, year: int, buffer_m: int = 500) -> dict | None:
    """Median growing-season (Feb-May) NDVI/SAVI/NDMI around a point."""
    if not earth_engine_ready():
        return None
    import ee

    point = ee.Geometry.Point([lon, lat]).buffer(buffer_m)

    def mask_clouds(img):
        scl = img.select("SCL")
        clear = scl.neq(3).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
        return img.updateMask(clear).divide(10000)

    image = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(point)
        .filterDate(f"{year}-02-01", f"{year}-05-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
        .map(mask_clouds)
        .median()
    )
    stack = ee.Image.cat([
        image.normalizedDifference(["B8", "B4"]).rename("ndvi"),
        image.expression("((NIR - RED) * 1.5) / (NIR + RED + 0.5)", {"NIR": image.select("B8"), "RED": image.select("B4")}).rename("savi"),
        image.normalizedDifference(["B8", "B11"]).rename("ndmi"),
    ])
    try:
        stats = stack.reduceRegion(ee.Reducer.mean(), point, scale=20, maxPixels=1e8).getInfo()
    except Exception:
        return None
    if not stats or stats.get("ndvi") is None:
        return None
    return {k: round(v, 3) for k, v in stats.items() if v is not None}
