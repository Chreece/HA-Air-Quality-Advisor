"""Do not confuse provider-specific indices or unverified measurements."""
from custom_components.environment_manager.logic import (
    evaluate, Reading, Weather, Room, Window, Reason,
)
from custom_components.environment_manager.dashboard import dashboard_snapshot


OUTDOOR = (Reading("sensor.out_pm","Outdoor particles","pm25",7),)
WEATHER = (Weather("weather.home","sunny",20,45,6),)
ROOM = Room("bedroom","Bedroom",(Window("binary_sensor.window","Window",False),),
            (Reading("sensor.co2","CO₂","co2",640),))


def plan(outside=OUTDOOR, environment=None, extras=(), room=ROOM):
    return evaluate(outside, WEATHER, (), (room,), environment=environment,
                    extra_outside=extras)


def test_unknown_aqi_scale_is_not_silently_classified_as_usa():
    aqi = (Reading("sensor.out_aqi","Provider AQI","aqi",3,
                   {"aqi":{"status":"configuration_required"}}),)
    result=plan(outside=aqi)
    assert result.status=="blocked"
    assert "aqi_scale_unconfigured" in [r.code for r in result.outside_reasons]
    assert "sensor.out_aqi" in result.unavailable_outdoor
    assert dashboard_snapshot(result,{})["outdoor"]["status"]=="unknown"


def test_european_aqi_category_and_us_indices_have_independent_policies():
    for scale,value in (("eea_category",4),("us_epa",125)):
        aqi=(Reading("sensor.out_aqi","AQI","aqi",value,
                     {"aqi":{"status":"ready","scale":scale,"operational_unsafe":True}}),)
        result=plan(outside=aqi)
        assert result.status=="blocked"
        assert "outside_aqi" in [r.code for r in result.outside_reasons]


def test_opt_in_pollen_hazard_closes_open_window_but_otherwise_is_advisory():
    open_room=Room("bedroom","Bedroom",
        (Window("binary_sensor.window","Window",True),),ROOM.readings)
    pollen=(Reason("outside_pollen","Pollen","4 / 5"),)
    assert plan(extras=pollen,room=open_room).status=="close"
    assert plan(room=open_room).status=="idle"


def test_verified_formaldehyde_30min_can_create_window_advice_no_phantom_sources():
    environment={"bedroom":{"international":{"formaldehyde_30min":{
        "status":"ready","mean":123,"above_who_100ug_m3":True
    }}}}
    result=plan(environment=environment)
    assert result.status=="open"
    assert [r.code for r in result.recommendations[0].reasons] == ["inside_formaldehyde"]
    unverified={"bedroom":{"international":{"formaldehyde_30min":{
        "status":"sensor_verification_required"
    }}}}
    assert plan(environment=unverified).status=="idle"


def test_cooling_opportunity_is_conditional_on_model_and_outdoor_safety():
    env={"bedroom":{"passive_cooling":{"status":"cooling_opportunity",
        "cooling_delta_c":4.5}}}
    result=plan(environment=env)
    assert result.status=="open"
    assert result.recommendations[0].reasons[0].code=="inside_passive_cooling"
    blocked=plan(
        outside=(Reading("sensor.out","Outdoor PM2.5","pm25",70),),
        environment=env,
    )
    assert blocked.status=="blocked"


def test_risk_indicators_do_not_directly_operate_climate_devices():
    env={"bedroom":{"international":{"radon":{"status":"annual_screening",
        "mean_bq_m3":200,"above_reference":True}}}}
    p=plan(environment=env)
    assert p.status=="idle"
    board=dashboard_snapshot(p,{})
    assert board["rooms"][0]["status"]=="attention"
    assert board["rooms"][0]["action"] is None
