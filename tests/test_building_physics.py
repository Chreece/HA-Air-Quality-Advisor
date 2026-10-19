"""Scientific calculation regression, invalid input and evidential-gating checks."""
from __future__ import annotations

import math

import pytest

from custom_components.air_quality_advisor.building_physics import (
    DAY_S, WEEK_S, absolute_humidity_g_m3, adaptive_comfort, co2_decay_ach,
    co2_trend, dew_point_c, heat_per_air_exchange_wh_m3,
    humidity_ratio_g_kg, moisture_potential, passive_cooling,
    surface_condensation, threshold_exposure_hours, weighted_window,
)
from custom_components.air_quality_advisor.environment_history import EnvironmentHistory


def test_winter_air_90_percent_outside_can_dry_warm_indoor_air():
    result = moisture_potential(22, 60, 4, 90)
    assert result["status"] == "drying"
    assert result["drying_potential_g_kg"] > 4
    assert 26 < result["outside_air_rh_when_warmed_percent"] < 32
    assert absolute_humidity_g_m3(22, 60) > absolute_humidity_g_m3(4, 90)
    assert 13 < result["indoor_dew_point_c"] < 15


def test_humid_hot_outside_not_recommended_for_drying():
    result = moisture_potential(20, 70, 29, 85)
    assert result["status"] == "humidifying"
    assert result["drying_potential_g_kg"] < -1


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -100, 200])
def test_invalid_measurement_returns_unavailable(bad):
    assert moisture_potential(22, 55, bad, 80)["status"] == "unavailable"
    assert dew_point_c(bad, 55) is None
    assert humidity_ratio_g_kg(22, bad) is None


def test_adaptive_80_percent_interval_and_domain_limit():
    result = adaptive_comfort(28, 20)
    assert result["comfort_center_c"] == 24.0
    assert result["lower_80_c"] == 20.5
    assert result["upper_80_c"] == 27.5
    assert result["status"] == "above_band"
    assert result["air_temperature_is_not_operative_temperature"]
    assert adaptive_comfort(22, 2)["status"] == "outside_applicability"
    assert adaptive_comfort(None, 20)["status"] == "unavailable"


def test_passive_cooling_requires_high_room_temp_clean_outdoors_and_delta():
    assert passive_cooling(29, 21, 27.5, True)["status"] == "cooling_opportunity"
    assert passive_cooling(29, 21, 27.5, False)["status"] == "outdoors_blocked"
    assert passive_cooling(23, 15, 27.5, True)["status"] == "not_needed"
    assert passive_cooling(29, 28, 27.5, True)["status"] == "insufficient_temperature_difference"
    assert passive_cooling(29, 21, None, True)["status"] == "comfort_model_unavailable"


def test_surface_rh_and_condensation_margin():
    result = surface_condensation(22, 60, 16)
    assert result["status"] == "high_surface_humidity"
    assert 80 <= result["surface_relative_humidity_percent"] < 95
    assert 1 < result["condensation_margin_c"] < 3
    assert surface_condensation(22, 60, 12)["status"] == "condensation_possible"
    assert surface_condensation(22, None, 12)["status"] == "unavailable"


def test_thermal_exchange_is_per_volume_not_fabricated_savings():
    assert heat_per_air_exchange_wh_m3(22, 2) == 6.7
    assert heat_per_air_exchange_wh_m3(None, 2) is None


def series(key, value, now=DAY_S, interval=300, span=DAY_S):
    return [{"t": t, key: value} for t in range(now - span, now + 1, interval)]


def test_24h_particle_mean_requires_80_percent_coverage():
    data = series("pm25", 12)
    result = weighted_window(data, "pm25", DAY_S, DAY_S)
    assert result == {"status": "ready", "coverage_percent": 100.0, "mean": 12.0}
    assert weighted_window(data[-5:], "pm25", DAY_S, DAY_S)["status"] == "insufficient_coverage"
    assert weighted_window([{"t": 0, "pm25": 12},
                            {"t": DAY_S, "pm25": 12}], "pm25", DAY_S, DAY_S)["status"] == "insufficient_coverage"


def test_history_threshold_exposure_hours_do_not_fill_gaps():
    data = series("surface_rh", 85)
    result = threshold_exposure_hours(data, "surface_rh", 80, DAY_S)
    assert result["above_threshold_hours"] == 24
    gap = [{"t": 0, "surface_rh": 85}, {"t": DAY_S, "surface_rh": 85}]
    result = threshold_exposure_hours(gap, "surface_rh", 80, DAY_S)
    assert result["status"] == "insufficient_coverage"
    assert result["above_threshold_hours"] == 0


def test_co2_trend_and_conditional_ach_require_real_evidence():
    points = [{"t": t, "co2": c, "occupied": False, "window_open": True}
              for t, c in [(0, 1200), (300, 1100), (600, 1000),
                           (900, 900), (1200, 800)]]
    assert co2_trend(points, 1200)["trend_ppm_per_hour"] == -1200
    assert co2_decay_ach(points, 1200, None)["status"] == "outdoor_co2_required"
    assert co2_decay_ach(points, 1200, 410)["status"] == "estimate"
    points[2]["occupied"] = None
    assert co2_decay_ach(points, 1200, 410)["status"] == "vacant_open_window_required"


def test_history_is_bounded_does_not_fabricate_warming_up_data():
    h = EnvironmentHistory()
    assert h.add("kitchen", {"temperature_c": 22, "pm25": 9}, now=1000000)
    assert not h.add("kitchen", {"temperature_c": 22}, now=1000001)
    assert h.add("kitchen", {"window_open": True}, now=1000002)
    restored = EnvironmentHistory.restore(h.snapshot(), now=1000100)
    assert len(restored.samples("kitchen")) == 2
    assert EnvironmentHistory.restore({"version": 0, "areas": {}}, now=1000100).samples("kitchen") == []
    assert EnvironmentHistory.restore({"version": 1, "areas": {"bad": [{"t": 0}]}},
                                      now=1000000).samples("bad") == []
    assert not h.add("kitchen", {}, now=999999)  # Out-of-order samples rejected.
