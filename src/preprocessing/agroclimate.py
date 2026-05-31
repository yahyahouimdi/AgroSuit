"""FAO-56 agro-climatic helpers."""

from __future__ import annotations

import math

_MID_MONTH_DOY = [15, 46, 74, 105, 135, 162, 198, 228, 258, 288, 319, 344]
_DAYS = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def extraterrestrial_radiation(lat: float, doy: int) -> float:
    """Daily extraterrestrial radiation Ra in MJ m-2 day-1 (FAO-56 eq. 21)."""
    gsc = 0.0820
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )


def hargreaves_et0(lat: float, month: int, t_mean: float, t_max: float, t_min: float) -> float:
    """Monthly reference evapotranspiration (mm) using Hargreaves-Samani."""
    ra_mm = 0.408 * extraterrestrial_radiation(lat, _MID_MONTH_DOY[month - 1])
    daily = 0.0023 * ra_mm * (t_mean + 17.8) * math.sqrt(max(t_max - t_min, 0.0))
    return round(daily * _DAYS[month - 1], 1)
