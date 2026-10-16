"""Ensure presentation metadata never calls an uncertain room 'safe'."""
from custom_components.air_quality_advisor.const import DEFAULT_THRESHOLDS
from custom_components.air_quality_advisor.dashboard import dashboard_snapshot
from custom_components.air_quality_advisor.logic import (
    Reading, Room, Warning, Weather, Window, evaluate,
)


def room(name, measurements=(Reading("sensor.co2", "CO₂", "co2", 630),), opened=False):
    return Room(name.lower(), name, (Window(f"binary_sensor.{name.lower()}_window", "Window", opened),), measurements)


def snapshot(rooms, outside=None, warnings=(), weather=None):
    if outside is None:
        outside = (Reading("sensor.out_pm", "Outdoor PM2.5", "pm25", 9),)
    if weather is None:
        weather = (Weather("weather.home", "sunny", 22, 41, 8),)
    return dashboard_snapshot(evaluate(outside, weather, warnings, rooms), DEFAULT_THRESHOLDS)


def test_exposes_every_room_not_just_actionable_recommendations():
    data = snapshot((room("Kitchen"), room("Living", (
        Reading("sensor.co2", "CO₂", "co2", 1250),
    )), room("Bedroom", ())))
    assert data["summary"] == {"total": 3, "safe": 1, "attention": 1, "unknown": 1}
    assert [item["status"] for item in data["rooms"]] == ["safe", "attention", "unknown"]
    assert data["rooms"][1]["action"] == "open"
    assert data["rooms"][1]["readings"][0]["threshold"] == 1000
    assert data["rooms"][1]["readings"][0]["exceeded"]
    assert data["rooms"][0]["action"] is None


def test_stale_indoor_sensor_prevents_false_green_status():
    data = snapshot((room("Kitchen", (
        Reading("sensor.co2", "CO₂", "co2", 600),
        Reading("sensor.pm25", "PM2.5", "pm25", None),
    )),))
    assert data["rooms"][0]["status"] == "unknown"
    assert data["summary"]["safe"] == 0


def test_high_co2_with_open_window_is_attention_even_without_open_action():
    data = snapshot((room("Kitchen", (
        Reading("sensor.co2", "CO₂", "co2", 1350),
    ), opened=True),))
    assert data["rooms"][0]["status"] == "attention"
    assert data["rooms"][0]["action"] is None
    assert data["rooms"][0]["ventilating"]


def test_unsafe_outdoors_with_open_window_has_close_action_even_without_indoor_data():
    data = snapshot((room("Kitchen", (), opened=True),),
                    outside=(Reading("sensor.out_pm", "Outside", "pm25", 29),))
    assert data["outdoor"]["status"] == "unsafe"
    assert data["rooms"][0]["status"] == "attention"
    assert data["rooms"][0]["action"] == "close"


def test_missing_outdoor_reading_is_partial_not_unsafe():
    data = snapshot((room("Kitchen"),), outside=(
        Reading("sensor.unknown", "Missing", "aqi", None),
        Reading("sensor.out_pm", "Outdoor", "pm25", 8),
    ))
    assert data["outdoor"]["status"] == "partial"
    assert data["outdoor"]["safe_to_ventilate"] is True
    assert data["outdoor"]["data_complete"] is False
    assert data["outdoor"]["unavailable_sensors"] == ["sensor.unknown"]
    assert data["summary"]["safe"] == 1


def test_missing_weather_is_unknown_and_not_pollution():
    data = snapshot((room("Kitchen"),), weather=(Weather("weather.home", None),))
    assert data["outdoor"]["status"] == "unknown"
    assert data["outdoor"]["safe_to_ventilate"] is False
    assert data["outdoor"]["blockers"][0]["code"] == "unavailable_weather"


def test_warning_unknown_is_unknown_not_known_hazard():
    data = snapshot((room("Kitchen"),), warnings=(Warning("sensor.alert", "Alert", None),))
    assert data["outdoor"]["status"] == "unknown"
    assert data["outdoor"]["warnings"][0]["active"] is None


def test_open_window_with_unknown_contact_state_is_not_safely_classified():
    odd = Room("bedroom", "Bedroom", (Window("binary_sensor.window", "Window", None),),
               (Reading("sensor.co2", "CO₂", "co2", 600),))
    data = snapshot((odd,))
    assert data["summary"]["unknown"] == 1
    assert data["rooms"][0]["windows"][0]["opened"] is None


def test_metric_units_and_weather_are_serialized():
    data = snapshot((room("Kitchen"),))
    assert data["rooms"][0]["readings"][0]["unit"] == "ppm"
    assert data["outdoor"]["readings"][0]["unit"] == "µg/m³"
    assert data["outdoor"]["weather"][0]["temperature_c"] == 22
