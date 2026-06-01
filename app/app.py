"""AgroSuit North Africa: interactive crop suitability dashboard.

Run from the project root:
    streamlit run app/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.config import PRESET_SITES, REGIONS, SUITABILITY_CLASSES
from src.http import DataSourceError
from src.models.crop_profiles import CROPS, FACTORS
from src.pipeline import analyze_site, scan_region
from src.reporting.export import scan_geojson, site_geojson, site_kml, site_markdown
from src.satellite.indices import describe_ndvi
from src.visualization import charts, maps

st.set_page_config(page_title="AgroSuit · Crop Suitability", page_icon="🌾", layout="wide", initial_sidebar_state="expanded")

# ════════════════════════════════════════════════════════════════════════════
# Styling
# ════════════════════════════════════════════════════════════════════════════
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stMarkdown, .stText { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1400px; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #0f2e1d 0%, #173f29 100%); }
[data-testid="stSidebar"] * { color: #e8f5e9 !important; }
[data-testid="stSidebar"] .stButton button { background: #66bb6a; color: #0f2e1d !important; border: none; font-weight: 700; }
[data-testid="stSidebar"] input, [data-testid="stSidebar"] [data-baseweb="select"] * { color: #0f2e1d !important; }

.hero { background: linear-gradient(120deg, #1b5e20 0%, #2e7d32 45%, #9e9d24 100%); border-radius: 18px;
        padding: 26px 32px; color: #fff; margin-bottom: 18px; box-shadow: 0 10px 30px rgba(27,94,32,.25); position: relative; overflow: hidden; }
.hero:after { content: "🌍"; position: absolute; right: 28px; top: 4px; font-size: 110px; opacity: .16; }
.hero h1 { margin: 0; font-size: 2.1rem; font-weight: 800; letter-spacing: -.5px; color: #fff; }
.hero p { margin: 6px 0 0; opacity: .92; font-size: 1.02rem; }
.hero .chips span { display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25);
        border-radius: 999px; padding: 3px 12px; margin: 10px 6px 0 0; font-size: .8rem; }

.kpi { background: var(--secondary-background-color, #f6f8f6); border-radius: 14px; padding: 14px 16px;
       border: 1px solid rgba(46,125,50,.15); height: 100%; }
.kpi .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .6px; opacity: .65; font-weight: 600; }
.kpi .value { font-size: 1.55rem; font-weight: 800; margin-top: 2px; }
.kpi .sub { font-size: .78rem; opacity: .7; }

.best { border-radius: 18px; padding: 22px 26px; color: #fff; display: flex; align-items: center; gap: 22px;
        box-shadow: 0 8px 24px rgba(0,0,0,.12); margin: 6px 0 18px; }
.best .icon { font-size: 64px; line-height: 1; }
.best h2 { margin: 0; font-size: 1.9rem; font-weight: 800; color: #fff; }
.best .meta { opacity: .95; font-size: .95rem; margin-top: 4px; }
.best .score { margin-left: auto; text-align: right; white-space: nowrap; }
.best .score b { font-size: 2.6rem; font-weight: 800; display: block; line-height: 1; }

.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; font-weight: 700; margin: 2px 4px 2px 0; }
.src { display: inline-block; padding: 4px 10px; border-radius: 8px; font-size: .76rem; margin: 3px 6px 3px 0;
       background: rgba(46,125,50,.08); border: 1px solid rgba(46,125,50,.2); }
.crop-card { border-radius: 14px; padding: 16px 18px; border: 1px solid rgba(128,128,128,.2); margin-bottom: 10px; }
.section-title { font-weight: 800; font-size: 1.15rem; margin: 18px 0 6px; }
div[data-testid="stTabs"] button p { font-size: 1rem; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)


def kpi(label: str, value: str, sub: str = "") -> str:
    return f"<div class='kpi'><div class='label'>{label}</div><div class='value'>{value}</div><div class='sub'>{sub}</div></div>"


def badge(code: str, label: str, colour: str) -> str:
    text = "#1b1b1b" if code in ("S2", "S3") else "#fff"
    return f"<span class='badge' style='background:{colour};color:{text}'>{code} · {label}</span>"


# ════════════════════════════════════════════════════════════════════════════
# Cached data access
# ════════════════════════════════════════════════════════════════════════════
@st.cache_data(show_spinner=False, ttl=24 * 3600)
def run_analysis(lat, lon, name, years, irrigated, soil, sat, offline):
    return analyze_site(lat, lon, name=name, years=years, irrigated=irrigated,
                        use_soilgrids=soil, use_satellite=sat, offline=offline)


@st.cache_data(show_spinner=False, ttl=24 * 3600)
def run_scan(region, resolution, years, irrigated):
    return scan_region(REGIONS[region], resolution, years=years, irrigated=irrigated)


ss = st.session_state
ss.setdefault("lat", PRESET_SITES["Béja, Tunisia (cereal belt)"]["lat"])
ss.setdefault("lon", PRESET_SITES["Béja, Tunisia (cereal belt)"]["lon"])
ss.setdefault("site_name", "Béja, Tunisia (cereal belt)")
ss.setdefault("report", None)
ss.setdefault("scan", None)

# ════════════════════════════════════════════════════════════════════════════
# Sidebar
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🌾 AgroSuit")
    st.caption("Geospatial crop suitability for North Africa")
    st.divider()

    st.markdown("### 📍 Location")
    mode = st.radio("Pick a site by", ["Reference site", "Coordinates", "Map click"], horizontal=False, label_visibility="collapsed")
    if mode == "Reference site":
        preset = st.selectbox("Reference site", list(PRESET_SITES), index=0)
        ss.lat, ss.lon, ss.site_name = PRESET_SITES[preset]["lat"], PRESET_SITES[preset]["lon"], preset
    elif mode == "Coordinates":
        c1, c2 = st.columns(2)
        ss.lat = c1.number_input("Latitude", -90.0, 90.0, float(ss.lat), 0.01, format="%.4f")
        ss.lon = c2.number_input("Longitude", -180.0, 180.0, float(ss.lon), 0.01, format="%.4f")
        ss.site_name = f"{ss.lat:.4f}, {ss.lon:.4f}"
    else:
        st.info("Click anywhere on the map in the **Site analysis** tab.")
    st.caption(f"Selected: **{ss.lat:.4f}, {ss.lon:.4f}**")

    st.markdown("### 💧 Scenario")
    irrigated = st.toggle("Irrigated agriculture", value=False, help="Removes rainfall shortage as a constraint (excess rain still counts).")

    st.markdown("### 🛰️ Data")
    years = st.slider("Climate window (years)", 3, 30, 10, help="Number of full ERA5 years averaged into the climatology.")
    use_soil = st.toggle("Live soil (ISRIC SoilGrids)", value=True)
    use_sat = st.toggle("Sentinel-2 NDVI (Earth Engine)", value=False, help="Requires `earthengine authenticate` and EE_PROJECT env var.")
    offline = st.toggle("Offline demo mode", value=False, help="Use built-in climate normals of the reference sites, no internet.")

    st.divider()
    analyse_clicked = st.button("🚀 Analyse site", width="stretch", type="primary")

# ════════════════════════════════════════════════════════════════════════════
# Header
# ════════════════════════════════════════════════════════════════════════════
st.markdown(
    f"""
<div class="hero">
  <h1>AgroSuit · Crop Suitability Intelligence</h1>
  <p>Which crop belongs where? FAO fuzzy land evaluation on ERA5 climate, SoilGrids soil and Copernicus terrain for
     {len(CROPS)} Mediterranean & Saharan crops.</p>
  <div class="chips"><span>🛰️ ERA5 reanalysis</span><span>🧱 SoilGrids 250 m</span><span>⛰️ Copernicus DEM</span>
  <span>🌿 Sentinel-2</span><span>📐 FAO S1/S2/S3/N</span></div>
</div>
""",
    unsafe_allow_html=True,
)

if analyse_clicked:
    with st.spinner("Fetching climate, soil and terrain data…"):
        try:
            ss.report = run_analysis(round(ss.lat, 4), round(ss.lon, 4), ss.site_name, years, irrigated, use_soil, use_sat, offline)
        except (DataSourceError, ValueError) as exc:
            st.error(f"Analysis failed: {exc}. Try **Offline demo mode** with a reference site.")

tab_site, tab_scan, tab_lib, tab_method = st.tabs(["🗺️ Site analysis", "🌍 Regional scan", "📚 Crop library", "🧪 Methodology"])

# ════════════════════════════════════════════════════════════════════════════
# Tab 1: site analysis
# ════════════════════════════════════════════════════════════════════════════
with tab_site:
    report = ss.report
    map_col, info_col = st.columns([1.35, 1])

    with map_col:
        m = maps.site_map(ss.lat, ss.lon, report if report and abs(report.lat - ss.lat) < 1e-3 and abs(report.lon - ss.lon) < 1e-3 else None)
        out = st_folium(m, height=470, use_container_width=True, returned_objects=["last_clicked"], key="site_map")
        clicked = (out or {}).get("last_clicked")
        if clicked and mode == "Map click":
            new = (round(clicked["lat"], 4), round(clicked["lng"], 4))
            if new != (round(ss.lat, 4), round(ss.lon, 4)):
                ss.lat, ss.lon = new
                ss.site_name = f"{new[0]:.4f}, {new[1]:.4f}"
                st.rerun()

    with info_col:
        if report is None:
            st.markdown("<div class='section-title'>How it works</div>", unsafe_allow_html=True)
            st.markdown(
                "1. **Pick a site** in the sidebar: a reference site, coordinates, or a map click.\n"
                "2. Choose **rainfed or irrigated**.\n"
                "3. Press **🚀 Analyse site**.\n\n"
                "AgroSuit downloads a multi-year ERA5 climatology and SoilGrids topsoil data, scores every crop "
                "against its agro-ecological requirements and explains **what limits each crop** and how to fix it."
            )
            st.markdown("<div class='section-title'>Suitability classes</div>", unsafe_allow_html=True)
            st.markdown("".join(badge(c, l, col) for _, c, l, col in SUITABILITY_CLASSES), unsafe_allow_html=True)
        else:
            best = report.best
            text = "#1b1b1b" if best.code in ("S2", "S3") else "#fff"
            st.markdown(
                f"""<div class="best" style="background:linear-gradient(120deg,{best.colour},{best.colour}cc);color:{text}">
                <div class="icon">{best.crop.icon}</div>
                <div><div style="font-size:.8rem;opacity:.85;text-transform:uppercase;letter-spacing:.8px">Top recommendation</div>
                <h2 style="color:{text}">{best.crop.name}</h2>
                <div class="meta"><i>{best.crop.scientific}</i> · {best.crop.season}</div></div>
                <div class="score"><b>{best.score:.2f}</b>{best.code} · {best.label}</div></div>""",
                unsafe_allow_html=True,
            )
            f = report.features
            c1, c2, c3 = st.columns(3)
            c1.markdown(kpi("Rainfall", f"{f['rain']:.0f} mm", f"ET₀ {f['et0']:.0f} mm/yr"), unsafe_allow_html=True)
            c2.markdown(kpi("Aridity", f"{f['aridity_index']:.2f}", report.aridity), unsafe_allow_html=True)
            c3.markdown(kpi("Mean temp", f"{f['t_mean']:.1f} °C", f"{f['t_cold']:.1f} → {f['t_hot']:.1f} °C"), unsafe_allow_html=True)
            st.write("")
            c4, c5, c6 = st.columns(3)
            c4.markdown(kpi("Soil pH", f"{f.get('ph', float('nan')):.1f}", "acidic" if f.get("ph", 7) < 6.5 else "neutral" if f.get("ph", 7) < 7.5 else "alkaline / calcareous"), unsafe_allow_html=True)
            c5.markdown(kpi("Texture", f"{f.get('clay', 0):.0f}% clay", report.texture), unsafe_allow_html=True)
            c6.markdown(kpi("Elevation", f"{f['elev']:.0f} m", f"{f['dry_months']} dry months"), unsafe_allow_html=True)

            st.markdown("<div style='margin-top:12px'></div>" + "".join(f"<span class='src'>{k}: {v}</span>" for k, v in report.sources.items()), unsafe_allow_html=True)
            for w in report.warnings:
                st.warning(w, icon="⚠️")

    if report is not None:
        st.divider()
        scenario = "💧 Irrigated" if report.irrigated else "🌦️ Rainfed"
        st.markdown(f"<div class='section-title'>Crop ranking · {report.name} · {scenario}</div>", unsafe_allow_html=True)
        left, right = st.columns([1.1, 1])
        with left:
            st.plotly_chart(charts.ranking_bar(report.results), width="stretch", config={"displayModeBar": False})
        with right:
            options = {f"{r.crop.icon} {r.crop.name}": r for r in report.results}
            names_ = list(options)
            default = list(dict.fromkeys([names_[0], names_[len(names_) // 2], names_[-1]]))  # best, middle, worst
            picked = st.multiselect("Compare factor profiles", names_, default=default, max_selections=4)
            if picked:
                st.plotly_chart(charts.factor_radar([options[p] for p in picked]), width="stretch", config={"displayModeBar": False})

        st.markdown("<div class='section-title'>Climate fingerprint</div>", unsafe_allow_html=True)
        cl, cr = st.columns([1.6, 1])
        cl.plotly_chart(charts.climograph(report.climatology), width="stretch", config={"displayModeBar": False})
        cr.plotly_chart(charts.water_balance(report.climatology), width="stretch", config={"displayModeBar": False})
        if report.vegetation:
            v = report.vegetation
            st.info(f"🌿 Sentinel-2 spring NDVI **{v.get('ndvi', float('nan')):.2f}** ({describe_ndvi(v.get('ndvi'))}) · "
                    f"SAVI {v.get('savi', float('nan')):.2f} · NDMI {v.get('ndmi', float('nan')):.2f}")

        st.markdown("<div class='section-title'>Why? Limiting factors & management advice</div>", unsafe_allow_html=True)
        for i, r in enumerate(report.results):
            with st.expander(f"{r.crop.icon} {r.crop.name} — {r.score:.2f} ({r.code} · {r.label})", expanded=i == 0):
                hints = r.advice()
                if hints:
                    for h in hints:
                        st.markdown(f"- {h}")
                else:
                    st.success("Every factor is inside the optimal range for this crop. 🎯")
                cols = st.columns(4)
                for j, fs in enumerate(r.factors):
                    with cols[j % 4]:
                        st.caption(f"{fs.label}: **{fs.score:.2f}**")
                        st.plotly_chart(charts.membership_curve(r.crop, fs.factor, fs.value), width="stretch",
                                        config={"displayModeBar": False}, key=f"mc_{r.crop.key}_{fs.factor}")

        st.markdown("<div class='section-title'>Export</div>", unsafe_allow_html=True)
        slug = "".join(ch if ch.isalnum() else "_" for ch in report.name)[:40]
        d1, d2, d3, d4 = st.columns(4)
        d1.download_button("📊 Ranking CSV", report.ranking_frame().to_csv(index=False), f"{slug}_ranking.csv", "text/csv", width="stretch")
        d2.download_button("🗺️ GeoJSON", site_geojson(report), f"{slug}.geojson", "application/geo+json", width="stretch")
        d3.download_button("🌐 Google Earth KML", site_kml(report), f"{slug}.kml", "application/vnd.google-earth.kml+xml", width="stretch")
        d4.download_button("📝 Markdown report", site_markdown(report), f"{slug}_report.md", "text/markdown", width="stretch")

# ════════════════════════════════════════════════════════════════════════════
# Tab 2: regional scan
# ════════════════════════════════════════════════════════════════════════════
with tab_scan:
    st.markdown("Score every crop on a regular grid of live ERA5 climate and terrain data, then map the best crop per cell.")
    c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
    region = c1.selectbox("Region", list(REGIONS), index=1)
    resolution = c2.slider("Grid resolution", 4, 16, 8, help="Cells along the longest side of the region.")
    scan_years = c3.slider("Years", 1, 5, 3)
    c4.write("")
    c4.write("")
    run = c4.button("🌍 Run scan", type="primary", width="stretch")
    st.caption("Soil is set to a regional calcareous default during scans (the SoilGrids API is rate-limited). "
               f"Scenario: **{'irrigated' if irrigated else 'rainfed'}** (change it in the sidebar).")

    if run:
        with st.spinner(f"Scanning {region}…"):
            try:
                df, step = run_scan(region, resolution, scan_years, irrigated)
                ss.scan = (region, df, step)
            except DataSourceError as exc:
                st.error(f"Scan failed: {exc}")

    if ss.scan is not None:
        region_name, df, step = ss.scan
        if df.attrs.get("failed_points"):
            st.warning(f"{df.attrs['failed_points']} grid points could not be downloaded (API rate limit); the map is partial. Re-run in a minute to fill the gaps.", icon="⚠️")
        if df.empty:
            st.warning("No land cells with data in this region.")
        else:
            names = {k: f"{c.icon} {c.name}" for k, c in CROPS.items()}
            layer_opts = {"🏆 Best crop per cell": "best_crop", **{names[k]: k for k in CROPS}}
            lcol, rcol = st.columns([1.6, 1])
            with lcol:
                layer = st.selectbox("Map layer", list(layer_opts))
                st_folium(maps.scan_map(df, step, layer_opts[layer]), height=560, use_container_width=True,
                          returned_objects=[], key=f"scan_{region_name}_{layer}")
            with rcol:
                order = df[list(CROPS)].mean().sort_values(ascending=False).index.tolist()
                st.markdown(f"**{len(df)} land cells** · {step * 111:.0f} km cells · mean rain {df['rain'].mean():.0f} mm")
                st.plotly_chart(charts.scan_distribution(df, order, names), width="stretch", config={"displayModeBar": False})
            top = df["best_crop"].value_counts().rename(index=lambda k: names[k]).rename("cells").rename_axis("Best crop")
            st.dataframe(pd.concat([top, (top / top.sum() * 100).round(1).rename("% of area")], axis=1), width="stretch")
            e1, e2 = st.columns(2)
            e1.download_button("📊 Grid CSV", df.to_csv(index=False), f"scan_{region_name}.csv", "text/csv", width="stretch")
            e2.download_button("🗺️ Grid GeoJSON (for QGIS)", scan_geojson(df, step), f"scan_{region_name}.geojson", "application/geo+json", width="stretch")

# ════════════════════════════════════════════════════════════════════════════
# Tab 3: crop library
# ════════════════════════════════════════════════════════════════════════════
with tab_lib:
    keys = list(CROPS)
    choice = st.selectbox("Crop", keys, format_func=lambda k: f"{CROPS[k].icon} {CROPS[k].name}")
    crop = CROPS[choice]
    st.markdown(
        f"""<div class="crop-card"><span style="font-size:42px">{crop.icon}</span>
        <h3 style="margin:4px 0 0">{crop.name} <span style="font-weight:400;font-size:1rem;opacity:.7"><i>{crop.scientific}</i></span></h3>
        <div>{crop.category} · Season: <b>{crop.season}</b> · Water need: <b>{crop.water_need}</b></div>
        <p style="margin:8px 0 0">{crop.notes}</p></div>""",
        unsafe_allow_html=True,
    )
    feats = ss.report.features if ss.report else {}
    if feats:
        st.caption(f"Orange dot = value at the last analysed site ({ss.report.name}).")
    cols = st.columns(4)
    for j, factor in enumerate(crop.ranges):
        with cols[j % 4]:
            a, b, c, d = crop.ranges[factor]
            st.markdown(f"**{FACTORS[factor][0]}** · optimum {b:g}–{c:g} {FACTORS[factor][1]}  \n<small>weight ×{crop.weight(factor):g}</small>", unsafe_allow_html=True)
            st.plotly_chart(charts.membership_curve(crop, factor, feats.get(factor)), width="stretch",
                            config={"displayModeBar": False}, key=f"lib_{choice}_{factor}")
    with st.expander("📋 Full requirement table (all crops)"):
        table = pd.DataFrame({
            f"{c.icon} {c.name}": {FACTORS[k][0]: f"{v[1]:g}–{v[2]:g} (limits {v[0]:g}–{v[3]:g})" for k, v in c.ranges.items()}
            for c in CROPS.values()
        }).T
        st.dataframe(table, width="stretch")

# ════════════════════════════════════════════════════════════════════════════
# Tab 4: methodology
# ════════════════════════════════════════════════════════════════════════════
with tab_method:
    st.markdown("### 1 · Data pipeline")
    st.markdown(
        "| Layer | Source | Resolution | Used for |\n|---|---|---|---|\n"
        "| Climate | ERA5 reanalysis (ECMWF) via Open-Meteo | ~25 km, daily | rainfall, temperatures, FAO-56 ET₀ |\n"
        "| Soil | ISRIC SoilGrids 2.0 | 250 m, 0–30 cm | pH, clay, sand, organic carbon |\n"
        "| Terrain | Copernicus GLO-90 DEM | 90 m | elevation |\n"
        "| Vegetation *(optional)* | Sentinel-2 L2A via Google Earth Engine | 10–20 m | NDVI / SAVI / NDMI context |"
    )
    st.markdown("### 2 · Fuzzy membership")
    st.markdown("Each factor value $x$ is scored against a crop-specific trapezoid $(a, b, c, d)$:")
    st.latex(r"\mu(x)=\begin{cases}0 & x\le a \text{ or } x\ge d\\ \frac{x-a}{b-a} & a<x<b\\ 1 & b\le x\le c\\ \frac{d-x}{d-c} & c<x<d\end{cases}")
    st.markdown("### 3 · Aggregation (law of the minimum)")
    st.latex(r"S=\Big(\prod_i \mu_i^{\,w_i}\Big)^{1/\sum w_i}\times\big(0.85+0.15\,\bar{C}\big)")
    st.markdown(
        "The weighted geometric mean makes one failing factor collapse the score (Liebig), unlike a simple average. "
        "$\\bar{C}$ is a *centrality* bonus that rewards sites sitting in the middle of the optimum rather than on its edge. "
        "Any factor at zero forces class **N**."
    )
    st.markdown("### 4 · FAO classes")
    st.markdown("".join(badge(c, f"{l} (≥ {lo:.1f})", col) for lo, c, l, col in SUITABILITY_CLASSES), unsafe_allow_html=True)
    st.markdown("### 5 · Derived agro-climatic indicators")
    st.markdown(
        "- **Aridity index** $AI = P / ET_0$ (UNEP 1997): hyper-arid < 0.05 < arid < 0.2 < semi-arid < 0.5 < dry sub-humid < 0.65 < humid\n"
        "- **Dry months**: months where $P < \\tfrac{1}{2} ET_0$ (FAO growing-period definition)\n"
        "- **GDD₅**: growing degree days above 5 °C\n"
        "- Offline mode rebuilds a monthly climatology from normals, with Hargreaves–Samani ET₀ computed from latitude."
    )
    st.markdown("### 6 · Limitations")
    st.markdown(
        "Crop requirements are generic and adapted from FAO ECOCROP; they should be calibrated against local yield data. "
        "ERA5 smooths rainfall over ~25 km and tends to under-estimate orographic rain. "
        "Soil salinity, slope, groundwater and market access are not modelled yet."
    )

st.markdown("<div style='text-align:center;opacity:.55;font-size:.8rem;margin-top:30px'>AgroSuit · Crop suitability project by Yahya Houimdi · ENIT</div>", unsafe_allow_html=True)
