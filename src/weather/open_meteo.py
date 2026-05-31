"""Multi-year climatology from the ERA5 reanalysis (served by Open-Meteo).

ERA5 is the ECMWF global reanalysis (~25 km, hourly since 1940). We pull
daily series for N full years and collapse them into a 12-month
climatology, plus FAO-56 reference evapotranspiration (ET0) for the
water balance.
"""

from __future__ import annotations

import pandas as pd

from src.config import CLIMATE_END_YEAR, OPEN_METEO_ARCHIVE_URL
from src.http import DataSourceError, get_json

DAILY_VARS = [
    "temperature_2m_mean",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "et0_fao_evapotranspiration",
]

MONTH_COLUMNS = ["t_mean", "t_max", "t_min", "precip", "et0"]


def _params(lats, lons, years: int) -> dict:
    start = CLIMATE_END_YEAR - years + 1
    return {
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lons),
        "start_date": f"{start}-01-01",
        "end_date": f"{CLIMATE_END_YEAR}-12-31",
        "daily": ",".join(DAILY_VARS),
        "timezone": "GMT",
    }


def _monthly_climatology(daily: dict) -> pd.DataFrame:
    df = pd.DataFrame(daily)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={
        "temperature_2m_mean": "t_mean", "temperature_2m_max": "t_max", "temperature_2m_min": "t_min",
        "precipitation_sum": "precip", "et0_fao_evapotranspiration": "et0",
    })
    if df[["t_mean", "precip"]].isna().all().any():
        raise DataSourceError("ERA5 returned no data for this location (ocean or outside coverage?)")
    df["year"], df["month"] = df["time"].dt.year, df["time"].dt.month

    # Monthly totals per year first, then average across years.
    per_year = df.groupby(["year", "month"]).agg(
        t_mean=("t_mean", "mean"), t_max=("t_max", "mean"), t_min=("t_min", "mean"),
        precip=("precip", "sum"), et0=("et0", "sum"),
    )
    clim = per_year.groupby("month").mean().reindex(range(1, 13))
    clim.index.name = "month"
    return clim.round(2)


def fetch_climatology(lat: float, lon: float, years: int = 10) -> tuple[pd.DataFrame, float | None]:
    """Return (12-row monthly climatology, ERA5 grid elevation in m)."""
    data = get_json(OPEN_METEO_ARCHIVE_URL, _params([lat], [lon], years))
    if "daily" not in data:
        raise DataSourceError(data.get("reason", "Unexpected response from Open-Meteo"))
    return _monthly_climatology(data["daily"]), data.get("elevation")


def fetch_climatology_batch(points: list[tuple[float, float]], years: int = 3, batch_size: int = 20):
    """Climatologies for many points, a few requests at a time (Open-Meteo multi-location)."""
    out = []
    for i in range(0, len(points), batch_size):
        chunk = points[i:i + batch_size]
        data = get_json(OPEN_METEO_ARCHIVE_URL, _params([p[0] for p in chunk], [p[1] for p in chunk], years))
        items = data if isinstance(data, list) else [data]
        for (lat, lon), item in zip(chunk, items):
            try:
                out.append((lat, lon, _monthly_climatology(item["daily"]), item.get("elevation")))
            except (KeyError, DataSourceError):
                out.append((lat, lon, None, item.get("elevation")))
    return out
