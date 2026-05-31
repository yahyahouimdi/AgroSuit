"""Project-wide constants: paths, API endpoints, regions and reference sites."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = RAW_DIR / "cache"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# ── External data sources ───────────────────────────────────────────────────
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SOILGRIDS_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
HTTP_TIMEOUT = 45
USER_AGENT = "crop-suitability-yahya/1.0 (academic geospatial project)"

# Last full year available in ERA5 at the time of writing; climatology windows
# are counted backwards from here so results are reproducible.
CLIMATE_END_YEAR = 2025

# Fallback soil values for calcareous North African soils, used when
# SoilGrids is unavailable or skipped (e.g. regional scans).
DEFAULT_SOIL = {"ph": 7.9, "clay": 28.0, "sand": 40.0, "soc": 8.0}

# ── FAO suitability classes ─────────────────────────────────────────────────
SUITABILITY_CLASSES = [
    # (lower bound, code, label, colour)
    (0.80, "S1", "Highly suitable", "#1a9850"),
    (0.60, "S2", "Moderately suitable", "#91cf60"),
    (0.40, "S3", "Marginally suitable", "#fee08b"),
    (0.00, "N", "Not suitable", "#d73027"),
]

# ── Regions for grid scans: (lat_min, lon_min, lat_max, lon_max) ───────────
REGIONS = {
    "Tunisia": (30.5, 7.5, 37.4, 11.6),
    "Northern Tunisia": (35.5, 8.3, 37.4, 11.1),
    "Cap Bon": (36.4, 10.3, 37.1, 11.1),
    "Sahel & Sfax": (34.3, 9.8, 36.0, 11.2),
    "Northern Morocco": (32.5, -9.5, 35.8, -2.0),
    "Saïss Plain (Morocco)": (33.6, -5.9, 34.3, -4.6),
    "Northern Algeria": (34.5, -1.5, 37.0, 8.5),
    "Nile Delta (Egypt)": (30.0, 29.8, 31.6, 32.4),
}

# ── Reference sites ─────────────────────────────────────────────────────────
# Approximate 1991-2020 climate normals, used for offline demo mode only.
# t_mean: annual mean (°C), t_amp: half the summer-winter spread (°C),
# t_range: mean daily max-min spread (°C), rain: annual rainfall (mm).
PRESET_SITES = {
    "Béja, Tunisia (cereal belt)": {"lat": 36.73, "lon": 9.18, "elev": 250, "t_mean": 17.8, "t_amp": 8.5, "t_range": 12.0, "rain": 600, "ph": 7.8, "clay": 38},
    "Tunis, Tunisia": {"lat": 36.81, "lon": 10.18, "elev": 10, "t_mean": 18.8, "t_amp": 7.8, "t_range": 9.5, "rain": 450, "ph": 7.9, "clay": 30},
    "Nabeul, Cap Bon": {"lat": 36.45, "lon": 10.73, "elev": 20, "t_mean": 18.6, "t_amp": 7.2, "t_range": 9.0, "rain": 470, "ph": 7.6, "clay": 22},
    "Kairouan, Tunisia": {"lat": 35.68, "lon": 10.10, "elev": 60, "t_mean": 19.8, "t_amp": 9.0, "t_range": 13.0, "rain": 300, "ph": 8.1, "clay": 26},
    "Sfax, Tunisia (olive groves)": {"lat": 34.74, "lon": 10.76, "elev": 20, "t_mean": 19.5, "t_amp": 7.5, "t_range": 10.0, "rain": 210, "ph": 8.2, "clay": 14},
    "Kasserine, Tunisia (pistachio)": {"lat": 35.17, "lon": 8.83, "elev": 680, "t_mean": 16.5, "t_amp": 9.5, "t_range": 14.0, "rain": 330, "ph": 8.2, "clay": 24},
    "Tozeur, Tunisia (oasis)": {"lat": 33.92, "lon": 8.13, "elev": 50, "t_mean": 21.6, "t_amp": 10.5, "t_range": 14.0, "rain": 90, "ph": 8.3, "clay": 10},
    "Meknès, Morocco (Saïss)": {"lat": 33.89, "lon": -5.55, "elev": 550, "t_mean": 17.2, "t_amp": 8.5, "t_range": 13.0, "rain": 560, "ph": 7.7, "clay": 35},
    "Sétif, Algeria (high plains)": {"lat": 36.19, "lon": 5.41, "elev": 1080, "t_mean": 14.6, "t_amp": 10.0, "t_range": 13.0, "rain": 400, "ph": 8.0, "clay": 36},
}
