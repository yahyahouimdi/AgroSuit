import numpy as np
import pandas as pd
import pytest

from src.preprocessing.agroclimate import extraterrestrial_radiation, hargreaves_et0
from src.preprocessing.features import aridity_class, climate_features, synthetic_climatology
from src.satellite.indices import describe_ndvi, ndvi, ndwi, savi
from src.soil.soilgrids import texture_class
from src.weather.open_meteo import _monthly_climatology


def test_ndvi_scalar_and_array():
    assert ndvi(0.5, 0.1) == pytest.approx(0.6667, abs=1e-3)
    arr = ndvi(np.array([0.5, 0.3]), np.array([0.1, 0.3]))
    np.testing.assert_allclose(arr, [0.6667, 0.0], atol=1e-3)


def test_ndvi_zero_denominator_is_nan():
    assert np.isnan(ndvi(0.0, 0.0))


def test_savi_lower_than_ndvi_on_sparse_cover():
    assert savi(0.25, 0.15) < ndvi(0.25, 0.15)


def test_ndwi_positive_on_water():
    assert ndwi(0.08, 0.02) > 0


def test_describe_ndvi():
    assert describe_ndvi(0.7).startswith("Dense")
    assert describe_ndvi(0.05) == "Bare soil / built-up"


def test_extraterrestrial_radiation_seasonality():
    # Tunis: summer Ra is much higher than winter Ra (FAO-56 table 2.6 ~ 41 vs 16 MJ/m2/day)
    assert extraterrestrial_radiation(36.8, 172) == pytest.approx(41.5, abs=1.5)
    assert extraterrestrial_radiation(36.8, 355) == pytest.approx(15.5, abs=1.5)


def test_hargreaves_reasonable_range():
    july = hargreaves_et0(36.8, 7, 27, 33, 21)
    jan = hargreaves_et0(36.8, 1, 11, 16, 6)
    assert 150 < july < 260
    assert 25 < jan < 70


def test_synthetic_climatology_matches_normals():
    clim = synthetic_climatology(36.8, t_mean=18.8, t_amp=7.8, t_range=9.5, rain=450)
    assert len(clim) == 12
    assert clim["precip"].sum() == pytest.approx(450, rel=0.01)
    assert clim["t_mean"].mean() == pytest.approx(18.8, abs=0.05)
    assert clim["t_mean"].idxmax() in (7, 8)


def test_climate_features_and_aridity():
    clim = synthetic_climatology(34.7, t_mean=19.5, t_amp=7.5, t_range=10, rain=210)
    feats = climate_features(clim)
    assert feats["rain"] == pytest.approx(210, rel=0.01)
    assert aridity_class(feats["aridity_index"]) in ("Arid", "Semi-arid")
    assert feats["dry_months"] >= 8


@pytest.mark.parametrize("ai, label", [(0.03, "Hyper-arid"), (0.1, "Arid"), (0.3, "Semi-arid"), (0.6, "Dry sub-humid"), (0.9, "Humid")])
def test_aridity_classes(ai, label):
    assert aridity_class(ai) == label


def test_monthly_climatology_aggregates_years():
    days = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    daily = {
        "time": days.strftime("%Y-%m-%d").tolist(),
        "temperature_2m_mean": [10.0] * len(days),
        "temperature_2m_max": [15.0] * len(days),
        "temperature_2m_min": [5.0] * len(days),
        "precipitation_sum": [1.0] * len(days),
        "et0_fao_evapotranspiration": [2.0] * len(days),
    }
    clim = _monthly_climatology(daily)
    assert clim.loc[1, "precip"] == pytest.approx(31)
    assert clim.loc[2, "precip"] == pytest.approx(28.5)  # 29 days in 2020, 28 in 2021
    assert clim["precip"].sum() == pytest.approx(365.5)


@pytest.mark.parametrize("clay, sand, expected", [(45, 20, "Clay"), (10, 88, "Sand"), (15, 60, "Sandy loam"), (20, 40, "Loam")])
def test_texture_class(clay, sand, expected):
    assert texture_class(clay, sand) == expected
