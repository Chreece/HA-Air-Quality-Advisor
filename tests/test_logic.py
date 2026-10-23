from custom_components.enviroment_manager.logic import (
    Reading, Room, Warning, Weather, Window, evaluate,
)
from custom_components.enviroment_manager.messages import announcement, explain


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


def test_missing_mold_inputs_remain_diagnostic_even_if_rain_blocks_ventilation():
    room = Room("bedroom", "Bedroom", (
        Window("binary_sensor.window", "Window", False),
    ), (
        Reading("sensor.co2","CO₂","co2",600),
        Reading("derived.mold_bedroom","Mold indication","mold",None,{
            "status":"inputs_unavailable",
            "missing_inputs":["indoor_temperature","outdoor_temperature","humidity"],
        }),
    ))
    plan = evaluate((Reading("sensor.out", "Outside", "pm25", 7),),
                    (Weather("weather.home", "rainy", 10),), (), (room,))
    assert plan.status == "blocked"
    assert ("Bedroom", "mold_indicator_unavailable") in plan.diagnostics
    for key in ("indoor_temperature","outdoor_temperature","humidity"):
        assert ("Bedroom", f"mold_{key}_unavailable") in plan.diagnostics


def test_rh_fallback_uses_normal_65_percent_humidity_threshold_without_new_causes():
    room = Room("living", "Living", (
        Window("binary_sensor.win","Window",False),
    ), (
        Reading("derived.rh_fallback_living", "Average RH","humidity",68,{
            "fallback_for_mold": True,
            "humidity_sensor_count": 2,
        }),
        Reading("derived.mold_living","Mold","mold",None,{
            "status":"needs_calibration",
            "missing_inputs":["calibration"],
        }),
    ))
    result = plan(areas=(room,))
    assert result.status == "open"
    assert [r.code for r in result.recommendations[0].reasons] == [
        "inside_humidity"
    ]
    assert all(r.code != "inside_mold" for r in result.recommendations[0].reasons)

    # A missing mold reading never causes window openings by itself.
    only_mold = Room(room.area_id,room.name,room.windows,(room.readings[1],))
    assert plan(areas=(only_mold,)).status == "idle"

    # Rain still closes an open window even while an RH fallback is active.
    opened = Room(room.area_id,room.name,(
        Window("binary_sensor.win","Window",True),
    ),room.readings)
    closing = plan(areas=(opened,),conditions=(Weather("weather.home","rainy",8),))
    assert closing.status == "close"
    assert closing.recommendations[0].action == "close"
    assert all(r.code != "inside_humidity" for r in closing.recommendations[0].reasons)


def test_rh_fallback_custom_humidity_threshold_is_respected():
    room = Room("living","Living",ROOM.windows,(
        Reading("derived.rh_fallback_living","RH","humidity",68,{
            "fallback_for_mold": True,
        }),
        Reading("derived.mold_living","Mold","mold",None,{
            "status":"needs_calibration","missing_inputs":["calibration"],
        }),
    ))
    result = evaluate(GOOD,FAIR,(),(room,),{"indoor_humidity":72})
    assert result.status == "idle"
    result = evaluate(GOOD,FAIR,(),(room,),{"indoor_humidity":60})
    assert result.status == "open"
    assert result.recommendations[0].reasons[0].code == "inside_humidity"


def test_verified_running_cooling_can_add_one_room_window_reason():
    original=Room("living_room","Living room",ROOM.windows,(
        Reading("sensor.low_co2","CO₂","co2",600),
    ))
    substitution={
        "status":"opportunity","notify_enabled":True,
        "effect":"cool","active_device":"climate.room_ac",
        "evidence":{"temperature_difference_c":6},
    }
    report={"living_room":{"climate_plan":{"window_efficiency":substitution}}}
    result=evaluate(GOOD,FAIR,(),(original,),environment=report)
    assert result.status=="open"
    assert len(result.recommendations)==1
    rec=result.recommendations[0]
    assert rec.reasons[0].code=="climate_window_cool"
    assert "6 °C" in announcement(rec,"en")[1]
    assert "Fensterlüftung" in announcement(rec,"de")[0]
    assert "παραθύρου" in announcement(rec,"el")[0]

    substitution["notify_enabled"]=False
    result=evaluate(GOOD,FAIR,(),(original,),environment=report)
    assert result.recommendations==()


def test_existing_high_co2_preserves_priority_over_energy_hint():
    substitution={"status":"opportunity","notify_enabled":True,
                  "effect":"dry","active_device":"humidifier.dry",
                  "evidence":{"humidity_ratio_advantage_g_kg":3.7}}
    result=evaluate(GOOD,FAIR,(),(ROOM,),environment={
        "living_room":{"climate_plan":{"window_efficiency":substitution}}
    })
    assert [reason.code for reason in result.recommendations[0].reasons[:2]] == [
        "inside_co2","climate_window_dry",
    ]


def test_climate_only_recommendations_do_not_change_air_quality_counts():
    from dataclasses import replace
    rec=__import__("custom_components.enviroment_manager.logic",
                   fromlist=["Recommendation"]).Recommendation(
        "open","bedroom","Bedroom",
        (Window("binary_sensor.bedroom_window","Bedroom window",False),),
        (__import__("custom_components.enviroment_manager.logic",
                    fromlist=["Reason"]).Reason("climate_window_cool",
                    "climate.bedroom_ac","4 °C"),),
    )
    original=plan()
    patched=replace(original,climate_recommendations=(rec,))
    assert patched.status==original.status
    assert patched.rooms==original.rooms
    assert rec in patched.climate_recommendations
    assert "bedroom" in patched.signature
