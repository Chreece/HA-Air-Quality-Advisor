"""Regression coverage for capability-aware HVAC without unsafe actuation."""
from custom_components.environment_manager.climate_equipment import (
    classify_hvac, humidity_advice,
)
from custom_components.environment_manager.climate_strategy import capabilities


def test_radiator_only_heats():
    c = capabilities({"supported_features": 1, "hvac_modes": ["off", "heat"]}, "heat")
    assert c["heat"] and not c["cool"] and not c["dry"]
    assert c["equipment"]["heating"] and not c["equipment"]["cooling"]


def test_ac_dry_fan_and_humidity_are_separate_capabilities():
    c = capabilities({"supported_features": 1 | 4 | 8 | 32,
                      "hvac_modes": ["off", "cool", "dry", "fan_only"]}, "cool")
    assert c["cool"] and not c["heat"]
    assert c["dry"] and c["fan_only"] and c["humidity_setpoint"]
    assert c["equipment"]["fan_control"] and c["equipment"]["swing_control"]


def test_heat_pump_auto_does_not_imply_two_individual_modes():
    c = classify_hvac({"supported_features": 2,
                       "hvac_modes": ["off", "auto", "heat_cool"]}, "auto")
    assert c["native_heat_cool"] and c["auto_unspecified"]
    assert c["heating"] and c["cooling"]


def test_dry_is_advisory_and_requires_confirmed_device():
    a = humidity_advice(69, drying_available=False)
    assert a["action"] == "dry" and not a["available"] and not a["automatic_control"]
    assert humidity_advice(69, drying_available=True)["available"]
    assert humidity_advice(58, previous="dry")["action"] == "dry"
    assert humidity_advice(56, previous="dry")["action"] == "idle"


def test_low_humidity_and_invalid_values():
    assert humidity_advice(30, humidifying_available=True)["action"] == "humidify"
    assert humidity_advice("unknown")["status"] == "insufficient_data"
    assert humidity_advice(float("nan"))["status"] == "invalid_inputs"
    assert classify_hvac({"hvac_modes": "heat"}, "off")["status"] == "unknown_modes"
