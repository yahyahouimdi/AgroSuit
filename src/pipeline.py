"""End-to-end pipelines: single-site analysis and regional grid scan."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import numpy as np
import pandas as pd

from src.config import CLIMATE_END_YEAR, DEFAULT_SOIL, PRESET_SITES
from src.http import DataSourceError
from src.models.crop_profiles import CROPS
from src.models.suitability import CropSuitability, rank_crops
from src.preprocessing.features import aridity_class, build_features, synthetic_climatology
from src.satellite.sentinel2 import fetch_vegetation_indices
from src.soil.soilgrids import fetch_soil, texture_class
from src.weather.open_meteo import fetch_climatology, fetch_climatology_batch

log = logging.getLogger(__name__)


@dataclass
class SiteReport:
    lat: float
    lon: float
    name: str
    features: dict[str, float]
    climatology: pd.DataFrame
    results: list[CropSuitability]
    irrigated: bool
    sources: dict[str, str] = field(default_factory=dict)
    vegetation: dict | None = None
    warnings: list[str] = field(default_factory=list)
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    @property
    def best(self) -> CropSuitability:
        return self.results[0]

    @property
    def aridity(self) -> str:
        return aridity_class(self.features.get("aridity_index", float("nan")))

    @property
    def texture(self) -> str:
        f = self.features
        return texture_class(f.get("clay", 0), f.get("sand", 40))

    def ranking_frame(self) -> pd.DataFrame:
        return pd.DataFrame([r.as_dict() for r in self.results])


def analyze_site(
    lat: float,
    lon: float,
    *,
    name: str | None = None,
    years: int = 10,
    irrigated: bool = False,
    use_soilgrids: bool = True,
    use_satellite: bool = False,
    offline: bool = False,
) -> SiteReport:
    """Fetch data for one location and rank every crop by suitability."""
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"Invalid coordinates: {lat}, {lon}")

    warnings: list[str] = []
    sources: dict[str, str] = {}
    preset = _nearest_preset(lat, lon)

    # ── Climate ─────────────────────────────────────────────────────────
    clim, elevation = None, None
    if not offline:
        try:
            clim, elevation = fetch_climatology(lat, lon, years)
            sources["climate"] = f"ERA5 reanalysis via Open-Meteo ({CLIMATE_END_YEAR - years + 1}–{CLIMATE_END_YEAR})"
        except DataSourceError as exc:
            log.warning("Climate fetch failed: %s", exc)
            warnings.append(f"Live climate data unavailable ({exc}).")
    if clim is None:
        if preset is None:
            raise DataSourceError(
                "Climate data could not be downloaded and no reference site is close enough for offline mode."
            )
        p = PRESET_SITES[preset]
        clim = synthetic_climatology(lat, p["t_mean"], p["t_amp"], p["t_range"], p["rain"])
        elevation = p["elev"]
        sources["climate"] = f"Offline estimate from climate normals of {preset}"
        warnings.append("Using approximate offline climate normals: treat scores as indicative only.")

    # ── Soil ────────────────────────────────────────────────────────────
    soil = None
    if use_soilgrids and not offline:
        try:
            soil = fetch_soil(lat, lon)
            sources["soil"] = "ISRIC SoilGrids 2.0 (250 m, 0–30 cm)"
        except DataSourceError as exc:
            log.warning("Soil fetch failed: %s", exc)
            warnings.append(f"SoilGrids unavailable ({exc}); using regional default soil.")
    if soil is None:
        if preset is not None:
            p = PRESET_SITES[preset]
            soil = {**DEFAULT_SOIL, "ph": p["ph"], "clay": p["clay"]}
            sources["soil"] = f"Typical soil of {preset}"
        else:
            soil = dict(DEFAULT_SOIL)
            sources["soil"] = "Regional default (calcareous North African soil)"

    sources["terrain"] = "Copernicus GLO-90 DEM via Open-Meteo" if "ERA5" in sources["climate"] else "Reference site elevation"

    # ── Satellite (optional) ────────────────────────────────────────────
    vegetation = None
    if use_satellite and not offline:
        vegetation = fetch_vegetation_indices(lat, lon, CLIMATE_END_YEAR)
        if vegetation:
            sources["satellite"] = f"Sentinel-2 L2A via Google Earth Engine (Feb–May {CLIMATE_END_YEAR})"
        else:
            warnings.append("Sentinel-2 indices skipped (Earth Engine not authenticated).")

    features = build_features(clim, soil, elevation)
    results = rank_crops(features, irrigated=irrigated)

    return SiteReport(
        lat=lat, lon=lon, name=name or f"{lat:.4f}, {lon:.4f}",
        features=features, climatology=clim, results=results, irrigated=irrigated,
        sources=sources, vegetation=vegetation, warnings=warnings,
    )


def _nearest_preset(lat: float, lon: float, max_km: float = 60) -> str | None:
    best, best_d = None, math.inf
    for key, p in PRESET_SITES.items():
        d = _haversine(lat, lon, p["lat"], p["lon"])
        if d < best_d:
            best, best_d = key, d
    return best if best_d <= max_km else None


def _haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def make_grid(bbox: tuple[float, float, float, float], resolution: int) -> tuple[list[tuple[float, float]], float, float]:
    """Cell-centre points for an n x n-ish grid over (lat_min, lon_min, lat_max, lon_max)."""
    lat_min, lon_min, lat_max, lon_max = bbox
    step = max(lat_max - lat_min, lon_max - lon_min) / resolution
    lats = np.arange(lat_min + step / 2, lat_max, step)
    lons = np.arange(lon_min + step / 2, lon_max, step)
    return [(round(a, 4), round(o, 4)) for a in lats for o in lons], step, step


def scan_region(
    bbox: tuple[float, float, float, float],
    resolution: int = 10,
    *,
    years: int = 3,
    irrigated: bool = False,
    crops: list[str] | None = None,
    progress: Callable[[float], None] | None = None,
) -> tuple[pd.DataFrame, float]:
    """Score every crop on a regular grid. Returns (DataFrame, cell size in degrees).

    Soil comes from regional defaults here because SoilGrids' fair-use limit
    makes per-cell queries impractical; climate and terrain are live.
    """
    points, step, _ = make_grid(bbox, resolution)
    keys = crops or list(CROPS)
    rows = []
    failed = 0
    batch = 10
    for i in range(0, len(points), batch):
        try:
            fetched = fetch_climatology_batch(points[i:i + batch], years=years, batch_size=batch)
        except DataSourceError as exc:
            log.warning("Scan batch %d failed: %s", i // batch, exc)
            failed += len(points[i:i + batch])
            fetched = []
        for lat, lon, clim, elev in fetched:
            if clim is None or elev is None or elev <= 0:
                continue  # sea or no data
            features = build_features(clim, DEFAULT_SOIL, elev)
            ranking = rank_crops(features, irrigated=irrigated, crops=keys)
            row = {"lat": lat, "lon": lon, "elev": elev, "rain": features["rain"],
                   "t_mean": features["t_mean"], "aridity_index": features["aridity_index"],
                   "best_crop": ranking[0].crop.key, "best_score": round(ranking[0].score, 3)}
            row.update({r.crop.key: round(r.score, 3) for r in ranking})
            rows.append(row)
        if progress:
            progress(min(1.0, (i + batch) / len(points)))
    if failed == len(points):
        raise DataSourceError("Climate API unavailable for every grid cell (rate limit or no connection).")
    df = pd.DataFrame(rows)
    df.attrs["failed_points"] = failed
    return df, step
