"""Room integration tests with Home Assistant stand-ins and no cloud inputs."""
from __future__ import annotations

from custom_components.air_quality_advisor.building_physics import DAY_S, WEEK_S
from custom_components.air_quality_advisor.environment_history import EnvironmentHistory
from custom_components.air_quality_advisor.logic import Reading, Room, Weather, Window, evaluate
from test_discovery import FakeHass, MockState, adapter


def room():
    return Room("kitchen", "Küche",
                (Window("binary_sensor.kitchen_window", "Kitchen", False),),
                (Reading("sensor.kitchen_humidity", "RH", "humidity", 60),
                 Reading("sensor.kitchen_co2", "CO₂", "co2", 1250),
                 Reading("sensor.kitchen_pm25", "PM2.5", "pm25", 12)))


def fixture_home(*, other_temp=False):
    values = [
        MockState("sensor.kitchen_temperature", 22, device_class="temperature", unit="°C"),
        MockState("binary_sensor.kitchen_presence", "off", device_class="presence"),
    ]
    areas = {s.entity_id: "kitchen" for s in values}
    if other_temp:
        other = MockState("sensor.second_temperature", 25, device_class="temperature", unit="°C")
        values.append(other)
        areas[other.entity_id] = "kitchen"
    return FakeHass(values, areas)


def test_room_moisture_drying_diagnostics_use_measured_paired_weather(adapter):
    from custom_components.air_quality_advisor.environment import build_environment
    h = EnvironmentHistory()
    input_room = room()
    data, changed = build_environment(
        fixture_home(), (input_room,), (input_room,),
        (Weather("weather.home", "sunny", 4, 90, 5),),
        (Reading("sensor.out", "PM", "pm25", 8),),
        history=h, max_age_minutes=90, outside_safe=False, now=1000000,
    )
    e = data["kitchen"]
    assert changed
    assert e["moisture"]["status"] == "drying"
    assert e["moisture"]["outside_air_rh_when_warmed_percent"] < 33
    assert e["thermal_comfort"]["status"] == "unavailable"  # no 7-day history
    assert e["passive_cooling"]["status"] == "comfort_model_unavailable"
    assert e["sources"]["indoor_temperature_entity"] == "sensor.kitchen_temperature"
    assert e["sources"]["co2_sensor_technology_verified"] is False
    assert e["co2_decay_ach"]["status"] == "outdoor_co2_required"
    assert h.samples("kitchen")[-1]["occupied"] is False


def test_multiple_temperature_sources_without_calibration_fail_closed(adapter):
    from custom_components.air_quality_advisor.environment import build_environment
    rec = room()
    report, _ = build_environment(
        fixture_home(other_temp=True), (rec,), (rec,),
        (Weather("weather.home", "sunny", 4, 90),), (),
        history=EnvironmentHistory(), max_age_minutes=90, now=1000000,
    )
    e = report["kitchen"]
    assert e["sources"]["indoor_temperature_status"] == "ambiguous_sensors"
    assert e["moisture"]["status"] == "unavailable"
    assert e["thermal_comfort"]["status"] == "unavailable"


def test_configured_temperature_wins_when_multiple_sources(adapter):
    from custom_components.air_quality_advisor.environment import build_environment
    rec = room()
    report, _ = build_environment(
        fixture_home(other_temp=True), (rec,), (rec,),
        (Weather("weather.home", "sunny", 4, 90),), (),
        history=EnvironmentHistory(), max_age_minutes=90, now=1000000,
        mold_calibrations={"kitchen": {"indoor_temperature_entity": "sensor.kitchen_temperature"}},
    )
    assert report["kitchen"]["moisture"]["status"] == "drying"


def test_ambiguous_outdoor_weather_sources_withheld(adapter):
    from custom_components.air_quality_advisor.environment import build_environment
    rec = room()
    report, _ = build_environment(
        fixture_home(), (rec,), (rec,),
        (Weather("weather.one", "sunny", 4, 90), Weather("weather.two", "sunny", 21, 40)), (),
        history=EnvironmentHistory(), max_age_minutes=90, now=1000000,
    )
    e = report["kitchen"]
    assert e["sources"]["outdoor_weather_status"] == "multiple_sources"
    assert e["moisture"]["status"] == "unavailable"


def test_humidity_only_open_action_withheld_when_outside_more_humid():
    outside = (Reading("sensor.out", "Outside", "pm25", 5),)
    wx = (Weather("weather.home", "sunny", 20, 40),)
    rec = Room("kitchen", "Küche", (Window("binary_sensor.win", "Window", False),),
               (Reading("sensor.rh", "RH", "humidity", 70),))
    legacy = evaluate(outside, wx, (), (rec,))
    assert legacy.status == "open"
    physics = evaluate(outside, wx, (), (rec,), environment={
        "kitchen": {"moisture": {"status": "humidifying"}},
    })
    assert physics.status == "idle"
    assert ("Küche", "outdoor_more_humid_than_indoor") in physics.diagnostics
    # Even when drying is unfavorable, elevated CO2 is an independent reason.
    co2_room = Room(rec.area_id, rec.name, rec.windows,
                    rec.readings + (Reading("sensor.co2", "CO2", "co2", 1400),))
    physics = evaluate(outside, wx, (), (co2_room,), environment={
        "kitchen": {"moisture": {"status": "humidifying"}},
    })
    assert physics.status == "open"
    assert [reason.code for reason in physics.recommendations[0].reasons] == ["inside_co2"]


def test_7_day_adaptive_mean_requires_continuous_observations(adapter):
    from custom_components.air_quality_advisor.environment import build_environment
    h = EnvironmentHistory()
    current = WEEK_S + 1000000
    for elapsed in range(0, WEEK_S + 1, 300):
        h.add("__outside__", {"outdoor_temperature_c": 20}, now=1000000 + elapsed)
    rec = room()
    report, _ = build_environment(
        fixture_home(), (rec,), (rec,),
        (Weather("weather.home", "sunny", 20, 40),), (),
        history=h, max_age_minutes=90, now=current,
    )
    comfort = report["kitchen"]["thermal_comfort"]
    assert comfort["status"] == "within_band"
    assert comfort["comfort_center_c"] == 24.0
