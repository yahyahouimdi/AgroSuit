"""Plotly figures for the dashboard and notebooks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.config import SUITABILITY_CLASSES
from src.models.crop_profiles import FACTORS, CropProfile
from src.models.suitability import CropSuitability, trapezoid

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FONT = "Inter, Segoe UI, sans-serif"


def _layout(fig: go.Figure, height: int = 420, **kw) -> go.Figure:
    base = dict(
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13),
        hoverlabel=dict(font_family=FONT),
    )
    fig.update_layout(**{**base, **kw})
    return fig


def ranking_bar(results: list[CropSuitability]) -> go.Figure:
    rows = list(reversed(results))
    fig = go.Figure(go.Bar(
        x=[r.score for r in rows],
        y=[f"{r.crop.icon} {r.crop.name}" for r in rows],
        orientation="h",
        marker=dict(color=[r.colour for r in rows], line=dict(width=0)),
        text=[f"{r.score:.2f} · {r.code}" for r in rows],
        textposition="outside",
        customdata=[(r.label, r.limiting.label if r.limiting else "none") for r in rows],
        hovertemplate="<b>%{y}</b><br>Score %{x:.2f}<br>%{customdata[0]}<br>Limiting: %{customdata[1]}<extra></extra>",
    ))
    for lower, code, _, colour in SUITABILITY_CLASSES[:-1]:
        fig.add_vline(x=lower, line=dict(color=colour, dash="dot", width=1))
    fig.update_xaxes(range=[0, 1.12], title="Suitability score", gridcolor="rgba(128,128,128,0.15)")
    return _layout(fig, height=max(320, 34 * len(rows)), showlegend=False)


def factor_radar(results: list[CropSuitability]) -> go.Figure:
    fig = go.Figure()
    palette = ["#2e7d32", "#f9a825", "#1565c0", "#ad1457"]
    for i, r in enumerate(results):
        labels = [FACTORS[f.factor][0] for f in r.factors]
        values = [f.score for f in r.factors]
        fig.add_trace(go.Scatterpolar(
            r=values + values[:1], theta=labels + labels[:1], name=f"{r.crop.icon} {r.crop.name}",
            fill="toself", opacity=0.55, line=dict(color=palette[i % len(palette)], width=2),
        ))
    fig.update_layout(polar=dict(
        bgcolor="rgba(0,0,0,0)",
        radialaxis=dict(range=[0, 1], tickvals=[0.4, 0.6, 0.8, 1.0], gridcolor="rgba(128,128,128,0.25)"),
        angularaxis=dict(gridcolor="rgba(128,128,128,0.25)"),
    ))
    return _layout(fig, height=430, legend=dict(orientation="h", y=-0.08))


def climograph(clim: pd.DataFrame) -> go.Figure:
    """Rainfall vs reference evapotranspiration bars with the temperature envelope."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=MONTHS, y=clim["precip"], name="Rainfall (mm)", marker_color="#1e88e5")
    fig.add_bar(x=MONTHS, y=clim["et0"], name="ET₀ demand (mm)", marker_color="#ffb74d", opacity=0.75)
    fig.add_scatter(x=MONTHS, y=clim["t_max"], name="T max", line=dict(color="#e53935", width=1, dash="dot"), secondary_y=True)
    fig.add_scatter(x=MONTHS, y=clim["t_mean"], name="T mean", line=dict(color="#c62828", width=3), mode="lines+markers", secondary_y=True)
    fig.add_scatter(x=MONTHS, y=clim["t_min"], name="T min", line=dict(color="#5e35b1", width=1, dash="dot"), secondary_y=True)
    fig.update_yaxes(title_text="mm / month", secondary_y=False, gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(title_text="°C", secondary_y=True, showgrid=False, tickformat=".0f")
    return _layout(fig, height=400, barmode="group", bargap=0.25, legend=dict(orientation="h", y=1.12))


def water_balance(clim: pd.DataFrame) -> go.Figure:
    balance = clim["precip"] - clim["et0"]
    fig = go.Figure(go.Bar(
        x=MONTHS, y=balance,
        marker_color=np.where(balance >= 0, "#43a047", "#e53935"),
        hovertemplate="%{x}: %{y:.0f} mm<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color="gray", width=1))
    fig.update_yaxes(title="P − ET₀ (mm)", gridcolor="rgba(128,128,128,0.15)")
    return _layout(fig, height=300, showlegend=False, title=dict(text="Monthly climatic water balance", font=dict(size=14)))


def membership_curve(crop: CropProfile, factor: str, value: float | None = None) -> go.Figure:
    a, b, c, d = crop.ranges[factor]
    pad = (d - a) * 0.15 or 1
    xs = np.linspace(a - pad, d + pad, 300)
    ys = [trapezoid(x, a, b, c, d) for x in xs]
    label, unit, _ = FACTORS[factor]
    fig = go.Figure(go.Scatter(x=xs, y=ys, fill="tozeroy", line=dict(color="#2e7d32", width=2),
                               fillcolor="rgba(46,125,50,0.18)", hoverinfo="skip"))
    if value is not None and not np.isnan(value):
        s = trapezoid(value, a, b, c, d)
        fig.add_scatter(x=[value], y=[s], mode="markers+text", marker=dict(size=13, color="#d84315", line=dict(color="white", width=2)),
                        text=[f"site: {value:.4g}"], textposition="top center", hoverinfo="skip")
    fig.update_xaxes(title=f"{label} ({unit})" if unit else label, gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(range=[0, 1.32], tickvals=[0, 0.5, 1], title="Membership", gridcolor="rgba(128,128,128,0.15)")
    return _layout(fig, height=230, showlegend=False, margin=dict(l=10, r=10, t=20, b=10))


def scan_distribution(df: pd.DataFrame, crop_keys: list[str], names: dict[str, str]) -> go.Figure:
    """Share of land cells per suitability class for each crop."""
    fig = go.Figure()
    bins = [(code, label, colour, lo) for lo, code, label, colour in SUITABILITY_CLASSES]
    for idx, (code, label, colour, lo) in enumerate(bins):
        hi = 10 if idx == 0 else bins[idx - 1][3]
        shares = [((df[k] >= lo) & (df[k] < hi)).mean() * 100 for k in crop_keys]
        fig.add_bar(y=[names[k] for k in crop_keys], x=shares, name=f"{code} – {label}", orientation="h", marker_color=colour)
    fig.update_xaxes(title="% of land cells", range=[0, 100])
    return _layout(fig, height=max(360, 30 * len(crop_keys) + 90), barmode="stack",
                   legend=dict(orientation="h", y=-0.18, x=0, font=dict(size=11)))
