"""International standard interpretation, validated inputs and math invariants."""
import math

import pytest

from custom_components.enviroment_manager.environment_science import (
    aqi_category, eea_hourly_category, ventilation_learning, particle_filtration,
    moisture_event, pollen_reading, radon_long_term, laeq_db_a,
    hcho_30min, daylight_exposure, overheating_degree_hours, pmv_iso7730,
)
from custom_components.enviroment_manager.building_physics import DAY_S


def test_aqi_unknown_not_misclassified_and_us_not_confused_with_europe():
    assert aqi_category(28, None)["status"] == "configuration_required"
    assert aqi_category(75, "us_epa")["category"] == "moderate"
    assert not aqi_category(75, "us_epa")["operational_unsafe"]
    assert aqi_category(140, "us_epa")["operational_unsafe"]
    assert aqi_category(4, "eea_category")["category"] == "poor"
    assert aqi_category(4, "eea_category")["operational_unsafe"]
    assert aqi_category(75, "eea_category")["status"] == "invalid"
    assert aqi_category(3, "custom", custom_limit=2)["operational_unsafe"]
    assert aqi_category(3, "custom")["status"] == "configuration_required"


def test_european_index_is_hourly_reference_not_worldwide_scale():
    assert eea_hourly_category("pm25", 20)["category"] == "moderate"
    assert eea_hourly_category("o3", 125)["category"] == "poor"
    assert eea_hourly_category("invalid", 20)["status"] == "unavailable"


def co2_points(now=1500, *, window=True):
    return [{"t": now - 1500 + i * 300, "co2": 1500 - i*110,
             "window_open": window, "occupied": False} for i in range(6)]


def test_ventilation_prediction_requires_continuous_real_window_evidence():
    points = co2_points()
    result = ventilation_learning(points, 1500, target_co2=1000)
    assert result["status"] in ("indicative", "target_reached")
    assert ventilation_learning(co2_points(window=None), 1500)["status"] == "window_not_continuously_open"
    assert ventilation_learning(points[:1], 1500)["status"] == "insufficient_data"
    constant = [{**p,"co2":1200} for p in points]
    assert ventilation_learning(constant, 1500)["status"] == "not_demonstrably_decreasing"


def test_particle_cadr_volume_requires_explicit_values_and_no_claim_on_gases():
    assert particle_filtration(None, 250, True, [], 100)["status"] == "configuration_required"
    e = particle_filtration(50, 250, True, [], 100)
    assert e["nominal_particle_clean_air_changes_h"] == 5
    assert e["particle_only"]
    assert e["pm25_observed_change_ug_m3"] is None


def test_relative_humidity_rise_does_not_infer_shower_or_cooking():
    series = [{"t":t,"humidity":40+i*5} for i,t in enumerate(range(0,1501,300))]
    e = moisture_event(series, 1500, extractor_on=False)
    assert e["status"] == "relative_humidity_rise"
    assert "undetermined" in e["source"]


def test_pollen_is_provider_scaled_opt_in_only():
    assert pollen_reading(4, max_scale=5)["high"]
    assert not pollen_reading(4, max_scale=5)["avoid_ventilation"]
    assert pollen_reading(4, max_scale=5, prevent_ventilation=True)["avoid_ventilation"]
    assert pollen_reading(7, max_scale=5)["status"] == "invalid_provider_scale"


def test_radon_requires_long_term_qualified_days():
    days = [{"day":d, "mean_bq_m3":170,"coverage_percent":100} for d in range(200,560)]
    now = 560 * DAY_S
    r = radon_long_term(days, now)
    assert r["status"] == "annual_screening"
    assert r["above_reference"] is True
    assert radon_long_term(days[-30:],now)["status"] == "insufficient_yearly_coverage"


def test_laeq_uses_linear_sound_energy_not_mean_decibels():
    s = [{"t":t, "noise_dba": 40 if t < 1000 else 60}
         for t in range(0, 1801, 300)]
    r = laeq_db_a(s,1800,1800)
    assert r["status"]=="indicative_laeq"
    assert r["db_a"] > 49
    assert laeq_db_a(s[:2],1800,1800)["status"] == "insufficient_coverage"


def test_hcho_30_min_guideline_only_for_verified_sensor_and_coverage():
    s = [{"t":t,"hcho":110} for t in range(0,1801,300)]
    assert hcho_30min(s,1800,verified=False)["status"] == "sensor_verification_required"
    assert hcho_30min(s,1800,verified=True)["above_who_100ug_m3"] is True
    assert hcho_30min(s[:2],1800,verified=True)["status"] == "insufficient_coverage"


def test_daylight_is_not_circadian_proxy_and_overheating_not_certification():
    s = [{"t":t,"lux":500,"temperature_c":28} for t in range(0, DAY_S+1, 300)]
    light = daylight_exposure(s,DAY_S)
    assert light["status"] == "descriptive"
    assert "not melanopic" in light["note"]
    overheating = overheating_degree_hours(s,DAY_S)
    assert overheating["degree_hours_over_reference"]==48
    assert "not_tm52_tm59" in overheating["method"]


def test_iso7730_requires_radiant_temperature_activity_and_clothing_explicitly():
    assert pmv_iso7730(22,None,50,0.1,1.2,0.7)["status"] == "missing_or_outside_iso7730_inputs"
    assert pmv_iso7730(22,22,50,0.0,1.2,0.7)["status"] == "missing_or_outside_iso7730_inputs"
