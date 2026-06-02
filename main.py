"""AgroSuit command-line interface.

Examples:
    python main.py analyze --lat 36.73 --lon 9.18
    python main.py analyze --site "Sfax" --irrigated --export outputs/
    python main.py scan --region "Northern Tunisia" --resolution 10
    python main.py crops
    python main.py app
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from src.config import OUTPUTS_DIR, PRESET_SITES, REGIONS
from src.http import DataSourceError
from src.models.crop_profiles import CROPS, FACTORS
from src.pipeline import analyze_site, scan_region
from src.reporting.export import scan_geojson, site_geojson, site_kml, site_markdown

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
console = Console()
CLASS_STYLE = {"S1": "bold green", "S2": "green", "S3": "yellow", "N": "red"}


def _resolve_site(args) -> tuple[float, float, str]:
    if args.site:
        matches = [k for k in PRESET_SITES if args.site.lower() in k.lower()]
        if not matches:
            raise SystemExit(f"No reference site matches '{args.site}'. Options: {', '.join(PRESET_SITES)}")
        p = PRESET_SITES[matches[0]]
        return p["lat"], p["lon"], matches[0]
    if args.lat is None or args.lon is None:
        raise SystemExit("Provide --lat and --lon, or --site.")
    return args.lat, args.lon, f"{args.lat:.4f}, {args.lon:.4f}"


def cmd_analyze(args) -> None:
    lat, lon, name = _resolve_site(args)
    with console.status(f"[green]Analysing {name}…"):
        report = analyze_site(lat, lon, name=name, years=args.years, irrigated=args.irrigated,
                              use_soilgrids=not args.no_soil, use_satellite=args.satellite, offline=args.offline)

    f = report.features
    best = report.best
    console.print(Panel.fit(
        f"[bold]{best.crop.icon}  {best.crop.name}[/]  [dim]{best.crop.scientific}[/]\n"
        f"Score [bold]{best.score:.2f}[/] · [{CLASS_STYLE[best.code]}]{best.code} {best.label}[/]\n"
        f"[dim]{name} · {'irrigated' if report.irrigated else 'rainfed'}[/]",
        title="🌾 Top recommendation", border_style="green",
    ))

    site = Table(box=box.SIMPLE_HEAVY, show_header=False, title="Site profile")
    site.add_column(style="dim")
    site.add_column(style="bold")
    for label, value in [
        ("Rainfall / ET₀", f"{f['rain']:.0f} mm / {f['et0']:.0f} mm"),
        ("Aridity index", f"{f['aridity_index']:.2f} ({report.aridity})"),
        ("Temperature", f"mean {f['t_mean']:.1f} °C · coldest month {f['t_cold']:.1f} · hottest max {f['t_hot']:.1f}"),
        ("Soil", f"pH {f.get('ph', float('nan')):.1f} · clay {f.get('clay', 0):.0f}% · {report.texture}"),
        ("Elevation", f"{f['elev']:.0f} m"),
    ]:
        site.add_row(label, value)
    console.print(site)

    table = Table(box=box.ROUNDED, title="Crop ranking", header_style="bold green")
    for col in ("#", "Crop", "Score", "Class", "Limiting factor"):
        table.add_column(col)
    for i, r in enumerate(report.results, 1):
        bar = "█" * round(r.score * 20)
        table.add_row(str(i), f"{r.crop.icon} {r.crop.name}", f"{r.score:.2f} [green]{bar}[/]",
                      f"[{CLASS_STYLE[r.code]}]{r.code}[/]", r.limiting.label if r.limiting else "–")
    console.print(table)

    for hint in best.advice()[:3]:
        console.print(f"  💡 {hint.replace('**', '')}")
    for w in report.warnings:
        console.print(f"[yellow]⚠ {w}[/]")
    console.print("[dim]Sources: " + " | ".join(report.sources.values()) + "[/]")

    if args.export:
        out = Path(args.export)
        out.mkdir(parents=True, exist_ok=True)
        slug = "".join(ch if ch.isalnum() else "_" for ch in name)[:40]
        (out / f"{slug}_ranking.csv").write_text(report.ranking_frame().to_csv(index=False), encoding="utf-8")
        (out / f"{slug}.geojson").write_text(site_geojson(report), encoding="utf-8")
        (out / f"{slug}.kml").write_text(site_kml(report), encoding="utf-8")
        (out / f"{slug}_report.md").write_text(site_markdown(report), encoding="utf-8")
        console.print(f"[green]✔ Exported CSV, GeoJSON, KML and Markdown report to {out.resolve()}[/]")


def cmd_scan(args) -> None:
    if args.region not in REGIONS:
        raise SystemExit(f"Unknown region. Options: {', '.join(REGIONS)}")
    with Progress(console=console) as progress:
        task = progress.add_task(f"Scanning {args.region}", total=1.0)
        df, step = scan_region(REGIONS[args.region], args.resolution, years=args.years, irrigated=args.irrigated,
                               progress=lambda p: progress.update(task, completed=p))
    if df.attrs.get("failed_points"):
        console.print(f"[yellow]⚠ {df.attrs['failed_points']} points failed to download (rate limit); results are partial.[/]")
    if df.empty:
        console.print("[red]No land cells with data.[/]")
        return
    counts = df["best_crop"].value_counts()
    table = Table(box=box.ROUNDED, title=f"{args.region}: best crop by area ({len(df)} cells, ~{step * 111:.0f} km)")
    for col in ("Crop", "Cells", "% area", "Mean score"):
        table.add_column(col)
    for key, n in counts.items():
        table.add_row(f"{CROPS[key].icon} {CROPS[key].name}", str(n), f"{n / len(df) * 100:.1f}", f"{df[key].mean():.2f}")
    console.print(table)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    slug = args.region.replace(" ", "_").replace("(", "").replace(")", "")
    df.to_csv(out / f"scan_{slug}.csv", index=False)
    (out / f"scan_{slug}.geojson").write_text(scan_geojson(df, step), encoding="utf-8")
    console.print(f"[green]✔ Saved grid to {out.resolve()} (CSV + GeoJSON, open the GeoJSON in QGIS)[/]")


def cmd_crops(_args) -> None:
    table = Table(box=box.ROUNDED, title="Crop knowledge base (optimal ranges)", header_style="bold green")
    table.add_column("Crop")
    for k in FACTORS:
        table.add_column(f"{FACTORS[k][0]}\n{FACTORS[k][1]}", justify="center")
    for c in CROPS.values():
        table.add_row(f"{c.icon} {c.name}", *[f"{c.ranges[k][1]:g}–{c.ranges[k][2]:g}" for k in FACTORS])
    console.print(table)


def cmd_app(_args) -> None:
    app = Path(__file__).parent / "app" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app)], check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agrosuit", description="Geospatial crop suitability for North Africa")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Rank crops for one location")
    a.add_argument("--lat", type=float)
    a.add_argument("--lon", type=float)
    a.add_argument("--site", help="Reference site name (partial match), e.g. 'Sfax'")
    a.add_argument("--years", type=int, default=10, help="Climate window in years (default 10)")
    a.add_argument("--irrigated", action="store_true", help="Irrigated scenario")
    a.add_argument("--no-soil", action="store_true", help="Skip SoilGrids, use default soil")
    a.add_argument("--satellite", action="store_true", help="Add Sentinel-2 indices (needs Earth Engine)")
    a.add_argument("--offline", action="store_true", help="Use built-in climate normals (reference sites only)")
    a.add_argument("--export", metavar="DIR", help="Write CSV/GeoJSON/KML/Markdown to DIR")
    a.set_defaults(func=cmd_analyze)

    s = sub.add_parser("scan", help="Grid suitability scan of a region")
    s.add_argument("--region", default="Northern Tunisia", help=f"One of: {', '.join(REGIONS)}")
    s.add_argument("--resolution", type=int, default=8)
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--irrigated", action="store_true")
    s.add_argument("--out", default=str(OUTPUTS_DIR))
    s.set_defaults(func=cmd_scan)

    sub.add_parser("crops", help="List crop requirement profiles").set_defaults(func=cmd_crops)
    sub.add_parser("app", help="Launch the Streamlit dashboard").set_defaults(func=cmd_app)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except DataSourceError as exc:
        console.print(f"[red]Data source error:[/] {exc}\n[dim]Tip: try --offline with --site for a reference site.[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
