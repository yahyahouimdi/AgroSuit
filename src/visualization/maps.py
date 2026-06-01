"""Folium web maps: site locator and suitability grids."""

from __future__ import annotations

import branca.colormap as cm
import folium
import pandas as pd
from folium.plugins import Fullscreen, MeasureControl, MiniMap

from src.config import SUITABILITY_CLASSES
from src.models.crop_profiles import CROPS

ESRI_IMAGERY = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
ESRI_LABELS = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"

# Distinct colours for "best crop" maps
CROP_COLOURS = {
    "durum_wheat": "#fbc02d", "barley": "#ef6c00", "olive": "#556b2f", "date_palm": "#8d6e63",
    "citrus": "#ff9800", "grapevine": "#6a1b9a", "almond": "#f8bbd0", "pistachio": "#9ccc65",
    "fig": "#ec407a", "tomato": "#e53935", "potato": "#795548", "chickpea": "#ffe082", "faba_bean": "#2e7d32",
}


def base_map(lat: float, lon: float, zoom: int = 8) -> folium.Map:
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer(ESRI_IMAGERY, attr="Esri World Imagery", name="Satellite").add_to(m)
    folium.TileLayer(ESRI_LABELS, attr="Esri", name="Labels", overlay=True, control=True).add_to(m)
    folium.TileLayer("CartoDB positron", name="Light", show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Streets", show=False).add_to(m)
    m.get_root().header.add_child(folium.Element(
        "<style>.leaflet-control-attribution{font-size:10px!important;line-height:1.3}</style>"
    ))
    Fullscreen().add_to(m)
    MeasureControl(primary_length_unit="kilometers", primary_area_unit="hectares").add_to(m)
    MiniMap(toggle_display=True, position="bottomleft").add_to(m)
    return m


def site_map(lat: float, lon: float, report=None, zoom: int = 9) -> folium.Map:
    m = base_map(lat, lon, zoom)
    if report is not None:
        best = report.best
        top = "".join(
            f"<tr><td>{r.crop.icon} {r.crop.name}</td><td style='text-align:right'><b>{r.score:.2f}</b></td>"
            f"<td><span style='background:{r.colour};padding:1px 6px;border-radius:6px'>{r.code}</span></td></tr>"
            for r in report.results[:5]
        )
        html = (
            f"<div style='font-family:sans-serif;min-width:220px'><h4 style='margin:0 0 4px'>{best.crop.icon} {best.crop.name}</h4>"
            f"<div style='color:#666;margin-bottom:6px'>{lat:.4f}, {lon:.4f}</div><table>{top}</table></div>"
        )
        folium.Marker([lat, lon], popup=folium.Popup(html, max_width=300), tooltip=f"Best: {best.crop.name}",
                      icon=folium.Icon(color="green", icon="leaf", prefix="fa")).add_to(m)
        folium.Circle([lat, lon], radius=5000, color="#43a047", fill=True, fill_opacity=0.08, weight=1).add_to(m)
    else:
        folium.Marker([lat, lon], icon=folium.Icon(color="blue", icon="crosshairs", prefix="fa")).add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


def _cell(lat: float, lon: float, step: float) -> list[list[float]]:
    h = step / 2
    return [[lat - h, lon - h], [lat + h, lon + h]]


def scan_map(df: pd.DataFrame, step: float, layer: str = "best_crop") -> folium.Map:
    """Grid map coloured by one crop's score, or by the best crop per cell."""
    m = base_map(df["lat"].mean(), df["lon"].mean(), zoom=7)
    if layer == "best_crop":
        for _, r in df.iterrows():
            crop = CROPS[r.best_crop]
            folium.Rectangle(
                _cell(r.lat, r.lon, step), color=None, weight=0, fill=True,
                fill_color=CROP_COLOURS.get(r.best_crop, "#999"), fill_opacity=0.65 * (0.4 + 0.6 * r.best_score),
                tooltip=f"{crop.icon} {crop.name} ({r.best_score:.2f}) · {r.rain:.0f} mm · {r.elev:.0f} m",
            ).add_to(m)
        present = df["best_crop"].value_counts()
        items = "".join(
            f"<div><span style='display:inline-block;width:12px;height:12px;background:{CROP_COLOURS[k]};margin-right:6px'></span>"
            f"{CROPS[k].name} ({n})</div>" for k, n in present.items()
        )
        _legend(m, "Best crop per cell", items)
    else:
        cmap = cm.LinearColormap(
            [c for *_, c in reversed(SUITABILITY_CLASSES)], index=[0.2, 0.4, 0.6, 0.8], vmin=0, vmax=1,
            caption=f"{CROPS[layer].name} suitability",
        )
        for _, r in df.iterrows():
            score = r[layer]
            folium.Rectangle(
                _cell(r.lat, r.lon, step), color=None, weight=0, fill=True,
                fill_color=cmap(score), fill_opacity=0.7,
                tooltip=f"{CROPS[layer].name}: {score:.2f} · {r.rain:.0f} mm · {r.t_mean:.1f} °C · {r.elev:.0f} m",
            ).add_to(m)
        cmap.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m


def _legend(m: folium.Map, title: str, items_html: str) -> None:
    html = (
        "<div style='position:absolute;bottom:30px;right:10px;z-index:9999;background:rgba(255,255,255,0.92);"
        "padding:8px 12px;border-radius:8px;font:12px sans-serif;box-shadow:0 1px 4px rgba(0,0,0,0.3)'>"
        f"<b>{title}</b>{items_html}</div>"
    )
    m.get_root().html.add_child(folium.Element(html))
