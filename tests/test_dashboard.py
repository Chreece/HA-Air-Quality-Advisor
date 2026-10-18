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


def test_uncalibrated_mold_preserves_valid_pm25_and_aqi_as_partial_indoor_data():
    living = room("Living", (
        Reading("sensor.pm25","PM2.5","pm25",1.0),
        Reading("sensor.aqi","AQI","aqi",12.9),
        Reading("derived.mold_living","Mold indication","mold",None,{
            "status":"needs_calibration","humidity_sensor_count":2,
            "average_indoor_humidity":52.3,
        }),
    ))
    data = snapshot((living,))
    item = data["rooms"][0]
    assert item["status"] == "unknown"  # Never falsely green before calibration
    assert item["status_detail"] == "mold_not_calibrated"
    assert item["available_count"] == 2
    assert item["high_count"] == 0
    assert [(r["metric"],r["value"]) for r in item["readings"]] == [
        ("pm25",1.0),("aqi",12.9),("mold",None)
    ]
    assert item["readings"][2]["details"]["average_indoor_humidity"] == 52.3
    assert data["summary"]["unknown"] == 1 and data["summary"]["safe"] == 0


def test_calibrated_mold_with_missing_sensor_is_not_labeled_uncalibrated():
    item = snapshot((room("Bedroom", (
        Reading("sensor.co2","CO₂","co2",620),
        Reading("derived.mold_bedroom","Mold indication","mold",None,{
            "status":"inputs_unavailable","humidity_sensor_count":0,
        }),
    )),))["rooms"][0]
    assert item["status"] == "unknown"
    assert item["status_detail"] == "mold_inputs_unavailable"
    assert item["available_count"] == 1


def test_missing_unrelated_indoor_sensor_is_partial_and_all_missing_is_no_data():
    partial = snapshot((room("Kitchen", (
        Reading("sensor.co2","CO₂","co2",600),
        Reading("sensor.pm25","PM2.5","pm25",None),
    )),))["rooms"][0]
    assert partial["status_detail"] == "partial_indoor_data"
    unavailable = snapshot((room("Kitchen", ()),))["rooms"][0]
    assert unavailable["status_detail"] == "no_indoor_data"


def test_mold_missing_inputs_expose_room_warnings_without_hiding_valid_air_data():
    living = room("Living", (
        Reading("sensor.pm","PM2.5","pm25",1),
        Reading("sensor.aqi","AQI","aqi",12.9),
        Reading("derived.mold_living","Mold indication","mold",None,{
            "status":"needs_calibration",
            "missing_inputs":["calibration","indoor_temperature","outdoor_temperature","humidity"],
            "humidity_sensor_count":0,
        }),
    ))
    data = snapshot((living,))
    selected = data["rooms"][0]
    assert selected["status"] == "unknown"
    assert selected["mold_warnings"] == [
        "calibration","indoor_temperature","outdoor_temperature","humidity"]
    assert selected["available_count"] == 2
    assert data["summary"]["unknown"] == 1
    assert ("Living", "mold_calibration_unavailable") in (
        (p["area"],p["problem"]) for p in
        [{"area": name,"problem": issue} for name,issue in
            evaluate((Reading("sensor.out", "outside","pm25",8),),
                     (Weather("weather.home","rainy",20),),(),(living,)).diagnostics]
    )
    # Changing outside weather to unsafe never hides missing-input warnings.
    bad_weather = snapshot((living,), weather=(Weather("weather.home","rainy",20),))
    assert bad_weather["rooms"][0]["mold_warnings"] == selected["mold_warnings"]


def test_successful_mold_has_no_input_warnings():
    sample = room("Bedroom", (
        Reading("derived.mold_bedroom","Mold","mold",62,{
            "status":"ready","missing_inputs":[],
        }),
    ))
    item = snapshot((sample,))["rooms"][0]
    assert item["mold_warnings"] == []
    assert item["status"] == "safe"


def test_active_rh_fallback_is_visible_and_never_falsely_green_when_mold_missing():
    sample = room("Living", (
        Reading("derived.rh_fallback_living","RH fallback","humidity",71,{
            "fallback_for_mold": True, "humidity_sensor_count":2,
        }),
        Reading("sensor.pm25","PM2.5","pm25",1),
        Reading("sensor.aqi","AQI","aqi",12.9),
        Reading("derived.mold_living","Mold","mold",None,{
            "status":"needs_calibration", "missing_inputs":["calibration"],
            "average_indoor_humidity":71, "humidity_sensor_count":2,
        }),
    ))
    data = snapshot((sample,))
    item = data["rooms"][0]
    assert item["rh_fallback"] == {
        "active": True, "value": 71, "threshold":65,
        "humidity_sensor_count":2,
    }
    assert item["mold_warnings"] == ["calibration"]
    assert item["status"] == "attention"
    assert item["readings"][0]["metric"] == "humidity"
    assert item["readings"][0]["exceeded"]
    assert data["summary"]["attention"] == 1
    assert data["summary"]["safe"] == 0


def test_inactive_rh_fallback_does_not_hide_missing_mold_warning():
    sample = room("Living", (
        Reading("derived.rh_fallback_living","RH fallback","humidity",51,{
            "fallback_for_mold": True, "humidity_sensor_count":1,
        }),
        Reading("sensor.aqi","AQI","aqi",12.9),
        Reading("derived.mold_living","Mold","mold",None,{
            "status":"inputs_unavailable",
            "missing_inputs":["outdoor_temperature"],
            "average_indoor_humidity":51,
        }),
    ))
    item = snapshot((sample,))["rooms"][0]
    assert item["status"] == "unknown"
    assert item["rh_fallback"]["active"] is True
    assert item["mold_warnings"] == ["outdoor_temperature"]
    assert item["available_count"] == 2


def test_no_available_mold_and_no_rh_cannot_activate_fallback():
    sample = room("Living", (
        Reading("sensor.pm25","PM2.5","pm25",1),
        Reading("derived.mold_living","Mold","mold",None,{
            "status":"needs_calibration","missing_inputs":["calibration","humidity"],
        }),
    ))
    item = snapshot((sample,))["rooms"][0]
    assert item["rh_fallback"] == {"active":False}
    assert item["status"] == "unknown"
    assert item["mold_warnings"] == ["calibration","humidity"]
