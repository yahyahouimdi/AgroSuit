"""Export analyses as CSV, GeoJSON, KML (Google Earth) and Markdown reports."""

from __future__ import annotations

import json
from html import escape

import pandas as pd

from src.models.crop_profiles import FACTORS


def site_geojson(report) -> str:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [report.lon, report.lat]},
        "properties": {
            "name": report.name,
            "irrigated": report.irrigated,
            "best_crop": report.best.crop.name,
            "best_score": round(report.best.score, 3),
            "aridity": report.aridity,
            **{k: v for k, v in report.features.items() if isinstance(v, (int, float))},
            "ranking": [r.as_dict() for r in report.results],
            "sources": report.sources,
            "created": report.created,
        },
    }
    return json.dumps({"type": "FeatureCollection", "features": [feature]}, indent=2, default=float)


def scan_geojson(df: pd.DataFrame, step: float) -> str:
    h = step / 2
    features = []
    for rec in df.to_dict(orient="records"):
        lat, lon = rec["lat"], rec["lon"]
        ring = [[lon - h, lat - h], [lon + h, lat - h], [lon + h, lat + h], [lon - h, lat + h], [lon - h, lat - h]]
        features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": rec})
    return json.dumps({"type": "FeatureCollection", "features": features}, default=float)


def site_kml(report) -> str:
    rows = "".join(
        f"<tr><td>{escape(r.crop.name)}</td><td>{r.score:.2f}</td><td>{r.code}</td>"
        f"<td>{escape(r.limiting.label) if r.limiting else '–'}</td></tr>"
        for r in report.results
    )
    f = report.features
    desc = f"""
      <h2>{escape(report.best.crop.name)} — {report.best.label}</h2>
      <p><b>Mode:</b> {'Irrigated' if report.irrigated else 'Rainfed'} · <b>Aridity:</b> {report.aridity}</p>
      <p>Rain {f['rain']:.0f} mm · ET₀ {f['et0']:.0f} mm · T mean {f['t_mean']:.1f} °C · pH {f.get('ph', float('nan')):.1f} · Clay {f.get('clay', float('nan')):.0f}%</p>
      <table border="1" cellpadding="3"><tr><th>Crop</th><th>Score</th><th>Class</th><th>Limiting</th></tr>{rows}</table>
      <p style="font-size:10px">{escape('; '.join(report.sources.values()))}</p>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Crop suitability — {escape(report.name)}</name>
    <Style id="best"><IconStyle><scale>1.3</scale><Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon></IconStyle></Style>
    <Placemark>
      <name>{escape(report.best.crop.name)} ({report.best.score:.2f})</name>
      <styleUrl>#best</styleUrl>
      <description><![CDATA[{desc}]]></description>
      <Point><coordinates>{report.lon},{report.lat},0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def site_markdown(report) -> str:
    f = report.features
    lines = [
        f"# Crop Suitability Report — {report.name}",
        "",
        f"*Generated {report.created} · {'Irrigated' if report.irrigated else 'Rainfed'} scenario · "
        f"{report.lat:.4f}, {report.lon:.4f}*",
        "",
        f"## Recommendation: {report.best.crop.icon} {report.best.crop.name} ({report.best.score:.2f}, {report.best.label})",
        "",
        "## Site profile",
        "",
        "| Indicator | Value |",
        "|---|---|",
        f"| Annual rainfall | {f['rain']:.0f} mm |",
        f"| Reference ET₀ | {f['et0']:.0f} mm |",
        f"| Aridity index (P/ET₀) | {f['aridity_index']:.2f} ({report.aridity}) |",
        f"| Mean temperature | {f['t_mean']:.1f} °C |",
        f"| Coldest month mean | {f['t_cold']:.1f} °C |",
        f"| Hottest month max | {f['t_hot']:.1f} °C |",
        f"| Dry months (P < ½ET₀) | {f['dry_months']} |",
        f"| Growing degree days (>5 °C) | {f['gdd5']:.0f} |",
        f"| Soil pH | {f.get('ph', float('nan')):.1f} |",
        f"| Clay / Sand | {f.get('clay', float('nan')):.0f}% / {f.get('sand', float('nan')):.0f}% ({report.texture}) |",
        f"| Elevation | {f['elev']:.0f} m |",
        "",
        "## Crop ranking",
        "",
        "| # | Crop | Score | Class | Limiting factor |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(report.results, 1):
        lines.append(f"| {i} | {r.crop.icon} {r.crop.name} | {r.score:.2f} | {r.code} | {r.limiting.label if r.limiting else '–'} |")
    lines += ["", "## Management notes for the top 3 crops", ""]
    for r in report.results[:3]:
        lines.append(f"### {r.crop.icon} {r.crop.name}")
        lines += [f"- {h}" for h in r.advice()] or ["- All factors within the optimal range."]
        lines.append("")
    if report.warnings:
        lines += ["## Data warnings", ""] + [f"- {w}" for w in report.warnings] + [""]
    lines += ["## Data sources", ""] + [f"- **{k.title()}**: {v}" for k, v in report.sources.items()]
    lines += ["", "---", "", "Factor definitions: " + "; ".join(f"{v[0]} = {v[2]}" for v in FACTORS.values())]
    return "\n".join(lines)
