import json

import pytest

from src import pipeline
from src.http import DataSourceError
from src.preprocessing.features import synthetic_climatology
from src.reporting.export import scan_geojson, site_geojson, site_kml, site_markdown


@pytest.fixture
def no_network(monkeypatch):
    """Make every remote fetch fail, as if offline."""
    def fail(*_a, **_k):
        raise DataSourceError("offline")
    monkeypatch.setattr(pipeline, "fetch_climatology", fail)
    monkeypatch.setattr(pipeline, "fetch_soil", fail)


@pytest.fixture
def fake_network(monkeypatch):
    clim = synthetic_climatology(36.7, 17.8, 8.5, 12, 600)
    monkeypatch.setattr(pipeline, "fetch_climatology", lambda lat, lon, years: (clim, 250.0))
    monkeypatch.setattr(pipeline, "fetch_soil", lambda lat, lon: {"ph": 7.6, "clay": 35.0, "sand": 30.0, "soc": 12.0})


def test_offline_mode_near_reference_site():
    report = pipeline.analyze_site(34.74, 10.76, offline=True)
    assert "Offline" in report.sources["climate"]
    assert report.best.crop.key in {"olive", "barley"}
    assert report.warnings


def test_falls_back_to_offline_when_network_fails(no_network):
    report = pipeline.analyze_site(36.73, 9.18)
    assert "Offline" in report.sources["climate"]
    assert "Typical soil" in report.sources["soil"]


def test_far_from_reference_and_offline_raises(no_network):
    with pytest.raises(DataSourceError):
        pipeline.analyze_site(48.85, 2.35)


def test_live_path_uses_fetched_data(fake_network):
    report = pipeline.analyze_site(36.73, 9.18, name="Béja")
    assert report.sources["soil"].startswith("ISRIC")
    assert report.features["ph"] == 7.6
    assert report.features["elev"] == 250.0
    assert report.best.code == "S1"


def test_invalid_coordinates():
    with pytest.raises(ValueError):
        pipeline.analyze_site(120, 10)


def test_make_grid_covers_bbox():
    points, step, _ = pipeline.make_grid((30, 8, 32, 10), 4)
    assert len(points) == 16
    assert step == pytest.approx(0.5)
    assert all(30 < lat < 32 and 8 < lon < 10 for lat, lon in points)


def test_exports_are_valid(fake_network):
    report = pipeline.analyze_site(36.73, 9.18, name="Béja")
    gj = json.loads(site_geojson(report))
    assert gj["features"][0]["geometry"]["coordinates"] == [9.18, 36.73]
    assert "<kml" in site_kml(report) and "Béja" in site_kml(report)
    md = site_markdown(report)
    assert md.startswith("# Crop Suitability Report") and "Crop ranking" in md


def test_scan_geojson_polygons():
    import pandas as pd
    df = pd.DataFrame([{"lat": 36.0, "lon": 10.0, "best_crop": "olive", "best_score": 0.9}])
    gj = json.loads(scan_geojson(df, 0.5))
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1] and len(ring) == 5
