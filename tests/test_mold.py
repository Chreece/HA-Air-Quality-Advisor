"""Calibrated mold risk and multi-sensor humidity behavior."""
from __future__ import annotations

from custom_components.air_quality_advisor.mold import (
    calibration_factor, estimate_mold, estimate_mold_for_room,
    mean_valid_humidity,
)
from custom_components.air_quality_advisor.logic import (
    Reading, Room, Weather, Window, evaluate,
)


def rh(value, name="RH"):
    return Reading("sensor." + name, name, "humidity", value)


def test_mold_calibration_matches_home_assistant_formula():
    factor = calibration_factor(21, 6, 13.5)
    assert factor == 2.0
    assert calibration_factor(21, 20, 13.5) is None
    assert calibration_factor(21, 6, 6) is None
    assert calibration_factor(21, 6, float("nan")) is None


def test_averages_only_physically_valid_included_humidity():
    assert mean_valid_humidity((rh(60,"a"),rh(80,"b"),rh(0),rh(None),
                                rh(float("nan")),rh(101),rh(-2))) == (70, 2)
    assert mean_valid_humidity((rh(0),rh(None),rh(200))) == (None, 0)


def test_estimated_surface_humidity_increases_as_wall_gets_colder():
    cold = estimate_mold(21, 6, 60, 2)
    warm = estimate_mold(21, 6, 60, 1)
    assert cold and warm
    assert cold.surface_humidity > warm.surface_humidity
    assert 70 <= cold.surface_humidity <= 100
    assert warm.surface_humidity == 60
    assert estimate_mold(21, 6, 0, 2) is None
    assert estimate_mold(21, 6, None, 2) is None


def test_derived_mold_reading_replaces_rh_as_action_trigger():
    room = Room("bedroom", "Bedroom", (Window("binary_sensor.window","Window",False),),
                (rh(60, "one"), rh(80,"two"), rh(0,"broken")))
    weather = (Weather("weather.home","sunny",6),)
    calibration = {"calibration_factor":2.0,"outdoor_weather_entity":"weather.home"}
    reading = estimate_mold_for_room(room, 21, weather, calibration)
    assert reading.value is not None and reading.value >= 70
    assert reading.details["humidity_sensor_count"] == 2
    assert reading.details["average_indoor_humidity"] == 70
    replacement = Room(room.area_id,room.name,room.windows,(reading,))
    plan = evaluate((Reading("sensor.outdoor_pm25","PM2.5","pm25",8),),
                    weather,(),(replacement,))
    assert plan.recommendations[0].reasons[0].code == "inside_mold"
    assert not any(r.code == "inside_humidity" for r in plan.recommendations[0].reasons)


def test_missing_calibration_or_weather_is_unknown_not_safe_or_open():
    room = Room("bedroom", "Bedroom", (Window("binary_sensor.window","Window",False),),
                (rh(90),))
    missing = estimate_mold_for_room(room,21,(Weather("weather.home","sunny",6),),{})
    absent = estimate_mold_for_room(
        room,21,(Weather("weather.home","sunny",None),),
        {"calibration_factor":2,"outdoor_weather_entity":"weather.home"})
    assert missing.value is None and absent.value is None
    for sample in (missing,absent):
        plan = evaluate((Reading("sensor.out","Outside","pm25",8),),
                        (Weather("weather.home","sunny",6),),(),
                        (Room(room.area_id,room.name,room.windows,(sample,)),))
        assert plan.status == "idle"
        assert ("Bedroom","mold_indicator_unavailable") in plan.diagnostics


def test_mold_does_not_overrule_bad_weather_closing():
    window = Window("binary_sensor.window","Window",True)
    room = Room("bedroom","Bedroom",(window,),(rh(90),))
    mold = estimate_mold_for_room(room,21,(Weather("weather.home","rainy",6),),
                    {"calibration_factor":2,"outdoor_weather_entity":"weather.home"})
    plan = evaluate((Reading("sensor.out","Outside","pm25",8),),
                    (Weather("weather.home","rainy",6),),(),
                    (Room(room.area_id,room.name,(window,),(mold,)),))
    assert plan.status == "close"
