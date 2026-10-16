from custom_components.air_quality_advisor.logic import (
    Reading, Room, Warning, Weather, Window, evaluate,
)
from custom_components.air_quality_advisor.messages import announcement, explain


GOOD = (Reading("sensor.outside_pm25", "Outside PM2.5", "pm25", 8),)
FAIR = (Weather("weather.home", "sunny", 20, 45, 8),)
ROOM = Room("living_room", "Living room", (
    Window("binary_sensor.living_window", "Living window", False),
), (
    Reading("sensor.co2", "CO₂", "co2", 1250),
))


def plan(*, outside=GOOD, conditions=FAIR, alerts=(), areas=(ROOM,)):
    return evaluate(outside, conditions, alerts, areas)


def test_high_co2_suggests_open_windows():
    result = plan()
    assert result.status == "open"
    assert result.outdoor_safe
    assert result.recommendations[0].windows[0].entity_id == "binary_sensor.living_window"
    assert result.recommendations[0].reasons[0].code == "inside_co2"


def test_good_inside_does_not_suggest_opening():
    room = Room("bedroom", "Bedroom", ROOM.windows, (
        Reading("sensor.co2", "CO₂", "co2", 600),
    ))
    assert plan(areas=(room,)).status == "idle"


def test_outdoor_pollution_prevents_ventilation():
    result = plan(outside=(Reading("sensor.bad", "Outdoor PM2.5", "pm25", 31),))
    assert result.status == "blocked"
    assert result.outside_reasons[0].code == "outside_pm25"


def test_unavailable_outdoor_is_neutral_and_exposed():
    result = plan(outside=(Reading("sensor.unknown", "Outside", "aqi", None),))
    assert result.status == "open"
    assert result.outdoor_safe
    assert result.outside_reasons == ()
    assert result.unavailable_outdoor == ("sensor.unknown",)


def test_missing_outdoor_does_not_hide_known_pollution():
    result = plan(outside=(
        Reading("sensor.unknown", "Outside AQI", "aqi", None),
        Reading("sensor.bad", "Outside PM2.5", "pm25", 30),
    ))
    assert result.status == "blocked"
    assert [r.code for r in result.outside_reasons] == ["outside_pm25"]
    assert result.unavailable_outdoor == ("sensor.unknown",)


def test_unavailable_outdoor_does_not_trigger_close():
    opened = Room("living_room", "Living room", (
        Window("binary_sensor.window", "Window", True),
    ), ROOM.readings)
    result = plan(outside=(Reading("sensor.unknown", "Outside", "pm25", None),), areas=(opened,))
    assert result.status == "idle"


def test_no_outdoor_sensor_is_not_safe():
    assert plan(outside=()).outside_reasons[0].code == "no_outdoor_data"


def test_missing_weather_is_not_safe():
    assert plan(conditions=()).status == "blocked"


def test_rain_and_open_window_require_closure_even_if_indoor_co2_high():
    room = Room("living_room", "Living room", (
        Window("binary_sensor.living_window", "Living window", True),
    ), ROOM.readings)
    result = plan(conditions=(Weather("weather.home", "rainy", 20),), areas=(room,))
    assert result.status == "close"
    assert result.recommendations[0].action == "close"
    assert result.recommendations[0].reasons[0].code == "weather_condition"


def test_active_weather_warning_closes_open_windows():
    room = Room("living_room", "Living room", (
        Window("binary_sensor.living_window", "Living window", True),
    ), ROOM.readings)
    result = plan(alerts=(Warning("sensor.dwd_warn", "Storm alert", True),), areas=(room,))
    assert result.status == "close"
    assert "active_warning" in [r.code for r in result.outside_reasons]


def test_unavailable_warning_is_not_silent_clear():
    assert plan(alerts=(Warning("binary_sensor.alert", "Warning", None),)).status == "blocked"


def test_open_window_already_ventilating_does_not_trigger_open_again():
    room = Room("living_room", "Living room", (
        Window("binary_sensor.open_window", "Window", True),
        Window("binary_sensor.closed_window", "Other", False),
    ), ROOM.readings)
    assert plan(areas=(room,)).status == "idle"


def test_all_open_windows_receive_close_recommendations():
    room = Room("living_room", "Living room", (
        Window("binary_sensor.a", "A", True),
        Window("binary_sensor.b", "B", True),
    ), ROOM.readings)
    result = plan(conditions=(Weather("weather.home", "pouring"),), areas=(room,))
    assert {w.entity_id for w in result.recommendations[0].windows} == {
        "binary_sensor.a", "binary_sensor.b"
    }


def test_missing_room_window_has_diagnostic():
    room = Room("kitchen", "Kitchen", (), ROOM.readings)
    result = plan(areas=(room,))
    assert ("Kitchen", "no_windows") in result.diagnostics


def test_missing_room_air_data_does_not_trigger_opening():
    room = Room("kitchen", "Kitchen", ROOM.windows, ())
    result = plan(areas=(room,))
    assert result.status == "idle"
    assert ("Kitchen", "no_indoor_data") in result.diagnostics


def test_extreme_weather_is_blocked():
    assert plan(conditions=(Weather("weather.home", "sunny", -4),)).status == "blocked"
    assert plan(conditions=(Weather("weather.home", "sunny", 18, 95),)).status == "blocked"
    assert plan(conditions=(Weather("weather.home", "sunny", 18, 40, 50),)).status == "blocked"


def test_limit_can_be_adjusted_for_local_air_quality_index_scale():
    outside = (Reading("sensor.eu_aqi", "EU air index", "aqi", 3),)
    result = evaluate(outside, FAIR, (), (ROOM,), {"outdoor_aqi": 2})
    assert result.status == "blocked"


def test_announcement_signature_stable_for_same_window_actions():
    first = plan()
    modified = plan(areas=(Room("living_room", "Living room", ROOM.windows, (
        Reading("sensor.co2", "CO₂", "co2", 1600),
    )),))
    assert first.signature == modified.signature


def test_messages_translated_and_include_reasons():
    rec = plan().recommendations[0]
    assert "CO₂" in announcement(rec, "en")[1]
    assert "Öffne" in announcement(rec, "de")[1]
    assert "Άνοιξε" in announcement(rec, "el_GR")[1]
    assert "Abre" in announcement(rec, "es")[1]
    assert explain(rec.reasons[0], "fr").startswith("CO₂")
