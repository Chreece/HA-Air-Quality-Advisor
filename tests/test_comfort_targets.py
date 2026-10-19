"""Evidence-qualified ISO 7730 inversion and local-time schedule contracts."""
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from custom_components.air_quality_advisor.comfort_targets import solve_pmv_air_temperature
from custom_components.air_quality_advisor.climate_schedule import (
    local_interval_active, scheduled_sleep,
)
from custom_components.air_quality_advisor.climate_strategy import policy


def standard_model(**kwargs):
    # Synthetic monotonic PMV to independently verify bisection math; the real
    # ISO 7730 implementation is the pinned pythermalcomfort dependency.
    return SimpleNamespace(pmv=(kwargs["tdb"]-23.0)*0.2)


def test_pmv_bisection_never_invents_missing_radiant_airflow_or_clothing():
    assert solve_pmv_air_temperature(None,50,.1,1.2,.7,evaluator=standard_model)["status"]=="insufficient_physical_inputs"
    assert solve_pmv_air_temperature(23,50,0,1.2,.7,evaluator=standard_model)["status"]=="insufficient_physical_inputs"
    result=solve_pmv_air_temperature(23,50,.1,1.2,.7,evaluator=standard_model)
    assert result["status"]=="estimate"
    assert result["air_temperature_target_c"]==23.0
    assert "iso7730" in result["method"]


def test_outside_root_bounds_returns_unavailable_not_extrapolated():
    model=lambda **kw: SimpleNamespace(pmv=5+kw["tdb"]*.01)
    assert solve_pmv_air_temperature(23,50,.1,1.2,.7,evaluator=model)["status"]=="target_not_bracketed"


def test_pmv_only_applies_bounded_adjustment_to_occupied_and_sleep():
    caps={"kind":"climate","heat":True,"cool":True,"setpoint":True}
    config={"enabled":True,"controller":"device","mode":"heat",
            "target_source":"pmv","comfort_adjustment_max_c":1.5}
    result=policy(config,temp_c=18,capability=caps,at_home="home",occupied="occupied",
                  comfort_target_c=24)
    assert result.temperature_c==21.5
    fixed=policy(config,temp_c=18,capability=caps,at_home="home",occupied="occupied")
    assert fixed.temperature_c==20.0
    away=policy(config,temp_c=14,capability=caps,at_home="away",occupied="unoccupied",
                comfort_target_c=24)
    assert away.temperature_c==16.0


def test_schedule_handles_midnight_crossing_and_local_time():
    berlin=ZoneInfo("Europe/Berlin")
    def at(year,month,day,hour,minute=0):
        return datetime(year,month,day,hour,minute,tzinfo=berlin).timestamp()
    assert local_interval_active(at(2026,11,1,23),"Europe/Berlin","22:00","07:00")[0] is True
    assert local_interval_active(at(2026,11,2,6),"Europe/Berlin","22:00","07:00")[0] is True
    assert local_interval_active(at(2026,11,2,8),"Europe/Berlin","22:00","07:00")[0] is False
    assert local_interval_active(at(2026,11,2,23),"Europe/Berlin","22:00","22:00")[0] is None
    assert local_interval_active(at(2026,11,2,23),"invalid/timezone","22:00","07:00")[0] is None


def test_manual_sleep_overrides_schedule_and_missing_schedule_stays_off():
    assert scheduled_sleep({"sleep_active":True},1,"UTC")[0]
    assert scheduled_sleep({"sleep_schedule_enabled":False},1,"UTC")[0] is False
    assert scheduled_sleep({"sleep_schedule_enabled":True,
                            "sleep_start":"bad","sleep_end":"07:00"},1,"UTC")[0] is False
