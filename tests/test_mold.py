"""Calibrated mold risk and multi-sensor humidity behavior."""
from __future__ import annotations

from test_discovery import adapter
from test_hub_manager import delivery_module

from custom_components.air_quality_advisor.mold import (
    calibration_factor, estimate_mold, estimate_mold_for_room,
    mean_valid_humidity, rh_fallback_for_room,
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
    assert missing.details["status"] == "needs_calibration"
    assert missing.details["missing_inputs"] == ["calibration"]
    assert absent.details["status"] == "inputs_unavailable"
    assert absent.details["missing_inputs"] == ["outdoor_temperature"]
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


def test_manager_mold_mode_follows_valid_room_humidity_and_ignores_zero(
    delivery_module,
):
    """Real manager capture preserves RH subscriptions and replaces RH with mold."""
    from types import SimpleNamespace
    from test_discovery import FakeHass, MockState
    source = [
        MockState("binary_sensor.bedroom_window", "off", device_class="window"),
        MockState("sensor.bedroom_temp", 21, device_class="temperature", unit="°C"),
        MockState("sensor.bedroom_humidity_a", 60, device_class="humidity", unit="%"),
        MockState("sensor.bedroom_humidity_b", 80, device_class="humidity", unit="%"),
        MockState("sensor.bedroom_humidity_broken", 0, device_class="humidity", unit="%"),
        MockState("sensor.outside_pm25", 8, device_class="pm25", unit="µg/m³"),
        MockState("weather.home", "sunny"),
    ]
    source[-1].attributes.update({"temperature": 6, "temperature_unit": "°C"})
    assignment = {
        state.entity_id: "bedroom" for state in source
        if state.entity_id.startswith("sensor.bedroom") or "window" in state.entity_id
    }
    home = FakeHass(source, assignment)
    entry = SimpleNamespace(entry_id="mold-test", options={}, data={
        "areas": ["bedroom"],
        "excluded_window_entities": [],
        "excluded_indoor_entities": {"bedroom": []},
        "outdoor_sensors": ["sensor.outside_pm25"],
        "weather_entities": ["weather.home"],
        "weather_warnings": [],
        "use_mold_indicator": True,
        "mold_rooms": {
            "bedroom": {
                "indoor_temperature_entity": "sensor.bedroom_temp",
                "outdoor_weather_entity": "weather.home",
                "critical_temperature_c": 13.5,
                "calibration_factor": 2.0,
            }
        },
    })
    manager = delivery_module.AirQualityManager(home, entry)
    state = manager._capture()
    values = state.rooms[0].readings
    assert len(values) == 1 and values[0].metric == "mold"
    assert values[0].details["humidity_sensor_count"] == 2
    assert values[0].details["average_indoor_humidity"] == 70
    assert "sensor.bedroom_humidity_a" in manager._tracked
    assert "sensor.bedroom_humidity_b" in manager._tracked
    assert "sensor.bedroom_temp" in manager._tracked
    assert state.status == "open"

    home._values["sensor.bedroom_humidity_a"].state = "unknown"
    home._values["sensor.bedroom_humidity_b"].state = "0"
    state = manager._capture()
    assert state.rooms[0].readings[0].value is None
    assert state.status == "idle"
    assert ("bedroom", "mold_indicator_unavailable") in state.diagnostics


def test_manager_original_rh_rule_remains_active_without_opt_in(delivery_module):
    from types import SimpleNamespace
    from test_discovery import FakeHass, MockState
    source = [
        MockState("binary_sensor.bedroom_window", "off", device_class="window"),
        MockState("sensor.bedroom_humidity", 70, device_class="humidity", unit="%"),
        MockState("sensor.outside_pm25", 8, device_class="pm25", unit="µg/m³"),
        MockState("weather.home", "sunny"),
    ]
    home = FakeHass(source, {
        "binary_sensor.bedroom_window": "bedroom",
        "sensor.bedroom_humidity": "bedroom",
    })
    manager = delivery_module.AirQualityManager(home, SimpleNamespace(
        entry_id="rh-test", options={}, data={
            "areas": ["bedroom"],
            "excluded_window_entities": [],
            "outdoor_sensors": ["sensor.outside_pm25"],
            "weather_entities": ["weather.home"],
            "weather_warnings": [],
        }
    ))
    state = manager._capture()
    assert state.status == "open"
    assert state.recommendations[0].reasons[0].code == "inside_humidity"
    assert state.rooms[0].readings[0].metric == "humidity"


def test_mold_explains_missing_inputs_even_when_rh_average_is_valid():
    room = Room("living", "Living room", (), (rh(52,"first"), rh(68,"second"),rh(0,"bad")))
    weather = (Weather("weather.home","sunny",8),)
    missing = estimate_mold_for_room(room, 22, weather, {})
    assert missing.value is None
    assert missing.details == {
        "humidity_sensor_count": 2,
        "status": "needs_calibration",
        "missing_inputs": ["calibration"],
        "average_indoor_humidity": 60,
    }
    calibrated_but_missing = estimate_mold_for_room(
        room, None, weather,
        {"calibration_factor":2.0,"outdoor_weather_entity":"weather.home"},
    )
    assert calibrated_but_missing.value is None
    assert calibrated_but_missing.details["status"] == "inputs_unavailable"
    assert calibrated_but_missing.details["missing_inputs"] == ["indoor_temperature"]

    healthy = estimate_mold_for_room(
        room, 22, weather,
        {"calibration_factor":2.0,"outdoor_weather_entity":"weather.home"},
    )
    assert healthy.value is not None
    assert healthy.details["status"] == "ready"
    assert healthy.details["missing_inputs"] == []


def test_all_unavailable_mold_inputs_are_reported_independently():
    room = Room("bedroom", "Bedroom", (), (rh(0), rh(None)))
    uncalibrated = estimate_mold_for_room(
        room, None, (Weather("weather.home", "rainy", None),), {},
    )
    assert uncalibrated.value is None
    assert uncalibrated.details["missing_inputs"] == [
        "calibration", "indoor_temperature", "outdoor_temperature", "humidity",
    ]
    assert uncalibrated.details["status"] == "needs_calibration"

    calibration = {"calibration_factor": 2.0,
                   "outdoor_weather_entity": "weather.home"}
    no_indoor = estimate_mold_for_room(room, None,
        (Weather("weather.home", "sunny", 10),), calibration)
    assert no_indoor.details["missing_inputs"] == ["indoor_temperature", "humidity"]
    missing_outdoor = estimate_mold_for_room(room, 22,
        (Weather("weather.home", "sunny", None),), calibration)
    assert missing_outdoor.details["missing_inputs"] == ["outdoor_temperature", "humidity"]
    no_humidity = estimate_mold_for_room(room, 22,
        (Weather("weather.home", "sunny", 10),), calibration)
    assert no_humidity.details["missing_inputs"] == ["humidity"]

    good_room = Room("bedroom", "Bedroom", (), (rh(65),))
    successful = estimate_mold_for_room(good_room, 22,
        (Weather("weather.home", "sunny", 10),), calibration)
    assert successful.value is not None
    assert successful.details["missing_inputs"] == []
    assert successful.details["outdoor_weather_entity"] == "weather.home"


def test_removed_calibration_weather_provider_requires_weather_warning():
    sample = Room("living", "Living", (), (rh(55),))
    reading = estimate_mold_for_room(sample, 22,
        (Weather("weather.new", "sunny", 10),),
        {"calibration_factor": 2, "outdoor_weather_entity": "weather.old"})
    assert reading.value is None
    assert reading.details["missing_inputs"] == ["outdoor_temperature"]
    assert reading.details["outdoor_weather_entity"] == "weather.old"


def test_weather_preview_before_calibration_reports_actual_missing_inputs():
    room = Room("living", "Living", (), (rh(60),))
    with_temperature = estimate_mold_for_room(room, 22,
        (Weather("weather.home", "cloudy", 12),), {})
    assert with_temperature.value is None
    assert with_temperature.details["missing_inputs"] == ["calibration"]
    without_temperature = estimate_mold_for_room(room, 22,
        (Weather("weather.home", "cloudy", None),), {})
    assert without_temperature.details["missing_inputs"] == [
        "calibration", "outdoor_temperature"
    ]


def test_out_of_range_temperatures_are_specific_missing_inputs():
    room = Room("living","Living",(),(rh(60),))
    calibration = {"calibration_factor":2.0,"outdoor_weather_entity":"weather.home"}
    invalid_room = estimate_mold_for_room(room, 999,
        (Weather("weather.home","sunny", 10),),calibration)
    assert invalid_room.value is None
    assert invalid_room.details["missing_inputs"] == ["indoor_temperature"]
    invalid_weather = estimate_mold_for_room(room, 22,
        (Weather("weather.home","sunny", -90),),calibration)
    assert invalid_weather.value is None
    assert invalid_weather.details["missing_inputs"] == ["outdoor_temperature"]


def test_mold_invalid_uses_single_valid_rh_mean_as_fallback():
    room = Room("living", "Living", (), (
        rh(50, "first"), rh(80, "second"), rh(0, "zero"),
        rh(None, "offline"), rh(150, "invalid"),
    ))
    mold = estimate_mold_for_room(room, 22,
        (Weather("weather.home", "sunny", 10),), {})
    assert mold.value is None
    fallback = rh_fallback_for_room(room, mold)
    assert fallback is not None
    assert fallback.metric == "humidity"
    assert fallback.entity_id == "derived.rh_fallback_living"
    assert fallback.value == 65
    assert fallback.details == {
        "fallback_for_mold": True,
        "humidity_sensor_count": 2,
    }


def test_fallback_is_immediately_disabled_when_calibrated_mold_recovers():
    room = Room("living", "Living", (), (rh(85),))
    usable = estimate_mold_for_room(room, 21,
        (Weather("weather.home", "sunny", 6),),
        {"calibration_factor": 2.0, "outdoor_weather_entity": "weather.home"})
    assert usable.value is not None
    assert rh_fallback_for_room(room, usable) is None

    missing = estimate_mold_for_room(room, 21,
        (Weather("weather.home", "sunny", None),),
        {"calibration_factor": 2.0, "outdoor_weather_entity": "weather.home"})
    assert missing.value is None
    assert rh_fallback_for_room(room, missing).value == 85


def test_no_valid_rh_leaves_fallback_unavailable():
    room = Room("kitchen", "Kitchen", (), (
        rh(0), rh(None), rh(float("nan")), rh(-4), rh(150),
    ))
    mold = estimate_mold_for_room(room, None, (Weather("weather.home","sunny", 9),), {})
    assert rh_fallback_for_room(room, mold) is None


def test_manager_fallback_triggers_only_one_rh_reason_then_prefers_recovered_mold(
    delivery_module,
):
    from types import SimpleNamespace
    from test_discovery import FakeHass, MockState
    states = [
        MockState("binary_sensor.living_window", "off", device_class="window"),
        MockState("sensor.living_temperature", 21, device_class="temperature", unit="°C"),
        MockState("sensor.living_humidity_a", 60, device_class="humidity", unit="%"),
        MockState("sensor.living_humidity_b", 80, device_class="humidity", unit="%"),
        MockState("sensor.living_humidity_zero", 0, device_class="humidity", unit="%"),
        MockState("sensor.outside_pm25", 8, device_class="pm25", unit="µg/m³"),
        MockState("weather.home", "sunny"),
    ]
    states[-1].attributes.update({"temperature": 6, "temperature_unit": "°C"})
    area_assignments = {
        value.entity_id: "living" for value in states
        if value.entity_id.startswith("sensor.living") or "window" in value.entity_id
    }
    hass = FakeHass(states, area_assignments)
    settings = {
        "areas": ["living"],
        "excluded_window_entities": [],
        "excluded_indoor_entities": {"living": []},
        "outdoor_sensors": ["sensor.outside_pm25"],
        "weather_entities": ["weather.home"],
        "weather_warnings": [],
        "use_mold_indicator": True,
        "mold_rooms": {},
    }
    entry = SimpleNamespace(entry_id="fallback-test", data=settings, options={})
    manager = delivery_module.AirQualityManager(hass, entry)
    no_calibration = manager._capture()
    readings = no_calibration.rooms[0].readings
    assert [r.metric for r in readings] == ["humidity", "mold"]
    assert readings[0].value == 70
    assert readings[0].details["humidity_sensor_count"] == 2
    assert readings[1].value is None
    assert readings[1].details["missing_inputs"] == [
        "calibration", "indoor_temperature",
    ]
    assert no_calibration.status == "open"
    assert [reason.code for reason in no_calibration.recommendations[0].reasons] == [
        "inside_humidity"
    ]
    assert "sensor.living_humidity_a" in manager._tracked
    assert "sensor.living_humidity_b" in manager._tracked

    # A newly valid calibration wins immediately, even though both raw
    # humidity sources still exceed the legacy 65% fallback threshold.
    settings["mold_rooms"] = {"living": {
        "calibration_factor": 1.0,
        "outdoor_weather_entity": "weather.home",
        "indoor_temperature_entity": "sensor.living_temperature",
    }}
    recovered = manager._capture()
    assert [r.metric for r in recovered.rooms[0].readings] == ["mold"]
    assert recovered.rooms[0].readings[0].value is not None
    assert recovered.recommendations[0].reasons[0].code == "inside_mold"

    # If the pinned weather input goes away, the valid RH average resumes.
    hass._values["weather.home"].attributes.pop("temperature")
    unavailable = manager._capture()
    assert [r.metric for r in unavailable.rooms[0].readings] == ["humidity", "mold"]
    assert unavailable.rooms[0].readings[1].details["missing_inputs"] == [
        "outdoor_temperature"
    ]
    assert unavailable.recommendations[0].reasons[0].code == "inside_humidity"


def test_excluded_humidity_sensor_not_averaged_into_rh_fallback(delivery_module):
    from types import SimpleNamespace
    from test_discovery import FakeHass, MockState
    states=[
        MockState("binary_sensor.kitchen_window","off",device_class="window"),
        MockState("sensor.kitchen_humidity_one",40,device_class="humidity",unit="%"),
        MockState("sensor.kitchen_humidity_two",95,device_class="humidity",unit="%"),
        MockState("sensor.outside_pm25",8,device_class="pm25",unit="µg/m³"),
        MockState("weather.home","sunny"),
    ]
    hass=FakeHass(states,{
        "binary_sensor.kitchen_window":"kitchen",
        "sensor.kitchen_humidity_one":"kitchen",
        "sensor.kitchen_humidity_two":"kitchen",
    })
    settings={
        "areas":["kitchen"],
        "excluded_window_entities":[],
        "excluded_indoor_entities":{"kitchen":["sensor.kitchen_humidity_two"]},
        "outdoor_sensors":["sensor.outside_pm25"],
        "weather_entities":["weather.home"],
        "weather_warnings":[],
        "use_mold_indicator":True,
        "mold_rooms":{},
    }
    manager=delivery_module.AirQualityManager(
        hass,SimpleNamespace(entry_id="exclusions",options={},data=settings),
    )
    state=manager._capture()
    assert [item.metric for item in state.rooms[0].readings]==["humidity","mold"]
    assert state.rooms[0].readings[0].value == 40
    assert state.rooms[0].readings[0].details["humidity_sensor_count"] == 1
    assert state.status == "idle"
    assert "sensor.kitchen_humidity_two" not in manager._tracked


def test_calibrated_mold_below_limit_does_not_fallback_to_high_raw_rh():
    room=Room("bedroom","Bedroom",(),(rh(85),))
    weather=(Weather("weather.home","sunny",6),)
    # An unusually warm surface can produce a low mold surface RH even when
    # room RH exceeds its 65% fallback threshold. In that case the valid
    # calibrated mold estimate takes priority, without an RH fallback.
    reading=estimate_mold_for_room(room,21,weather,{
        "outdoor_weather_entity":"weather.home", "calibration_factor":0.5,
    })
    assert reading.value is not None and reading.value < 70
    assert rh_fallback_for_room(room,reading) is None


def test_rh_fallback_comparison_keeps_full_sensor_precision():
    from custom_components.air_quality_advisor.logic import evaluate
    room=Room("living","Living",(
        Window("binary_sensor.window","Window",False),
    ),(rh(64.97,"one"),rh(65.01,"two")))
    fallback=rh_fallback_for_room(room,
        Reading("derived.mold_living","Mold","mold",None))
    assert fallback is not None
    assert fallback.value == (64.97+65.01)/2
    assert fallback.value < 65
    selected=Room(room.area_id,room.name,room.windows,(fallback,))
    no_open=evaluate(
        (Reading("sensor.outside","Outside","pm25",8),),
        (Weather("weather.home","sunny",20),),(),(selected,),
    )
    assert no_open.status == "idle"
