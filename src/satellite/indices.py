"""Spectral vegetation indices for Sentinel-2 reflectance (0-1 scale).

Each function works on scalars or NumPy arrays, so it can be used for a
single pixel or a whole raster band.
"""

from __future__ import annotations

import numpy as np


def _safe_div(num, den):
    num, den = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(den == 0, np.nan, num / den)
    return out.item() if out.ndim == 0 else out


def ndvi(nir, red):
    """Normalized Difference Vegetation Index (B8, B4)."""
    return _safe_div(np.subtract(nir, red), np.add(nir, red))


def savi(nir, red, L: float = 0.5):
    """Soil-Adjusted Vegetation Index, better than NDVI on sparse semi-arid cover."""
    return _safe_div((np.subtract(nir, red)) * (1 + L), np.add(np.add(nir, red), L))


def evi(nir, red, blue):
    """Enhanced Vegetation Index, does not saturate over dense canopies."""
    return _safe_div(2.5 * np.subtract(nir, red), np.asarray(nir) + 6 * np.asarray(red) - 7.5 * np.asarray(blue) + 1)


def ndwi(green, nir):
    """McFeeters Normalized Difference Water Index (B3, B8): open water > 0."""
    return _safe_div(np.subtract(green, nir), np.add(green, nir))


def ndmi(nir, swir1):
    """Normalized Difference Moisture Index (B8, B11): canopy water content."""
    return _safe_div(np.subtract(nir, swir1), np.add(nir, swir1))


def describe_ndvi(value: float | None) -> str:
    if value is None or np.isnan(value):
        return "Unavailable"
    if value < 0:
        return "Water / non-vegetated"
    if value < 0.15:
        return "Bare soil / built-up"
    if value < 0.3:
        return "Sparse vegetation"
    if value < 0.5:
        return "Moderate vegetation"
    return "Dense, vigorous vegetation"
