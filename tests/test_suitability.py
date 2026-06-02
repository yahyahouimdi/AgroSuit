import math

import pytest

from src.models.crop_profiles import CROPS, FACTORS
from src.models.suitability import classify, rank_crops, score_crop, trapezoid

GOOD_OLIVE_SITE = {"rain": 450, "t_mean": 18, "t_cold": 9, "t_hot": 32, "ph": 7.5, "clay": 25, "elev": 200}


@pytest.mark.parametrize(
    "value, expected",
    [(0, 0.0), (10, 0.0), (15, 0.5), (20, 1.0), (25, 1.0), (30, 1.0), (35, 0.5), (40, 0.0), (99, 0.0)],
)
def test_trapezoid(value, expected):
    assert trapezoid(value, 10, 20, 30, 40) == pytest.approx(expected)


def test_trapezoid_open_lower_bound():
    # Date palm style range: no lower limit on rainfall
    assert trapezoid(0, 0, 0, 150, 450) == 1.0


def test_classify_thresholds():
    assert classify(0.95)[0] == "S1"
    assert classify(0.7)[0] == "S2"
    assert classify(0.5)[0] == "S3"
    assert classify(0.1)[0] == "N"


def test_all_profiles_are_valid_trapezoids():
    for crop in CROPS.values():
        assert set(crop.ranges) <= set(FACTORS), crop.key
        for factor, (a, b, c, d) in crop.ranges.items():
            assert a <= b <= c <= d, f"{crop.key}.{factor}"


def test_ideal_site_scores_s1():
    result = score_crop(GOOD_OLIVE_SITE, CROPS["olive"])
    assert result.code == "S1"
    assert 0.85 <= result.score <= 1.0


def test_failing_factor_forces_not_suitable():
    site = {**GOOD_OLIVE_SITE, "rain": 50}
    result = score_crop(site, CROPS["olive"])
    assert result.code == "N"
    assert result.limiting.factor == "rain"


def test_irrigation_removes_water_deficit():
    site = {**GOOD_OLIVE_SITE, "rain": 50}
    assert score_crop(site, CROPS["olive"], irrigated=True).code == "S1"


def test_irrigation_does_not_hide_excess_rain():
    site = {"rain": 900, "t_mean": 25, "t_cold": 12, "t_hot": 42, "ph": 8, "clay": 10, "elev": 50}
    rainfed = score_crop(site, CROPS["date_palm"])
    irrigated = score_crop(site, CROPS["date_palm"], irrigated=True)
    assert irrigated.score == pytest.approx(rainfed.score)


def test_missing_factor_is_skipped():
    site = {k: v for k, v in GOOD_OLIVE_SITE.items() if k != "ph"}
    result = score_crop(site, CROPS["olive"])
    assert "ph" not in {f.factor for f in result.factors}
    assert not math.isnan(result.score)


def test_ranking_is_sorted_and_complete():
    ranking = rank_crops(GOOD_OLIVE_SITE)
    scores = [r.score for r in ranking]
    assert scores == sorted(scores, reverse=True)
    assert len(ranking) == len(CROPS)


def test_desert_oasis_prefers_date_palm():
    oasis = {"rain": 85, "t_mean": 22.7, "t_cold": 11.4, "t_hot": 40.7, "ph": 8.3, "clay": 10, "elev": 46}
    assert rank_crops(oasis)[0].crop.key == "date_palm"


def test_advice_mentions_irrigation_when_dry():
    site = {**GOOD_OLIVE_SITE, "rain": 200}
    hints = score_crop(site, CROPS["durum_wheat"]).advice()
    assert any("irrigation" in h for h in hints)
