"""Turn raw climate, soil and terrain data into suitability features."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.preprocessing.agroclimate import hargreaves_et0

# Mediterranean rainfall regime: share of annual rain per month (Jan..Dec).
_MED_RAIN_SHARE = np.array([13, 11, 10, 8, 5, 2, 0.5, 1.5, 6, 11, 14, 15], dtype=float)
_MED_RAIN_SHARE /= _MED_RAIN_SHARE.sum()

ARIDITY_CLASSES = [
    # UNEP (1997) aridity index P / ET0
    (0.05, "Hyper-arid"),
    (0.20, "Arid"),
    (0.50, "Semi-arid"),
    (0.65, "Dry sub-humid"),
    (math.inf, "Humid"),
]


def aridity_class(index: float) -> str:
    for upper, label in ARIDITY_CLASSES:
        if index < upper:
            return label
    return "Humid"


def climate_features(clim: pd.DataFrame) -> dict[str, float]:
    """Summarise a 12-month climatology into scalar features."""
    rain = float(clim["precip"].sum())
    et0 = float(clim["et0"].sum())
    ai = rain / et0 if et0 > 0 else float("nan")
    return {
        "rain": round(rain, 1),
        "t_mean": round(float(clim["t_mean"].mean()), 2),
        "t_cold": round(float(clim["t_mean"].min()), 2),
        "t_hot": round(float(clim["t_max"].max()), 2),
        "t_min_abs": round(float(clim["t_min"].min()), 2),
        "et0": round(et0, 1),
        "aridity_index": round(ai, 3),
        "dry_months": int((clim["precip"] < 0.5 * clim["et0"]).sum()),
        # Growing degree days above 5 °C, a proxy for season length / heat units.
        "gdd5": round(float(((clim["t_mean"] - 5).clip(lower=0) * _days_in_month()).sum()), 0),
    }


def _days_in_month() -> np.ndarray:
    return np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def synthetic_climatology(lat: float, t_mean: float, t_amp: float, t_range: float, rain: float) -> pd.DataFrame:
    """Build a plausible monthly climatology from a few climate normals.

    Used only for offline demo mode: a cosine annual temperature cycle
    peaking in late July, a Mediterranean winter-rain regime, and Hargreaves
    ET0 computed from latitude.
    """
    months = np.arange(1, 13)
    t = t_mean + t_amp * np.cos(2 * np.pi * (months - 7.5) / 12)
    half = t_range / 2
    df = pd.DataFrame({
        "t_mean": t,
        "t_max": t + half,
        "t_min": t - half,
        "precip": rain * _MED_RAIN_SHARE,
    }, index=pd.Index(months, name="month"))
    df["et0"] = [hargreaves_et0(lat, m, r.t_mean, r.t_max, r.t_min) for m, r in df.iterrows()]
    return df.round(2)


def build_features(clim: pd.DataFrame, soil: dict[str, float], elevation: float | None) -> dict[str, float]:
    features = climate_features(clim)
    features.update({k: v for k, v in soil.items() if v is not None})
    features["elev"] = float(elevation) if elevation is not None else float("nan")
    return features
