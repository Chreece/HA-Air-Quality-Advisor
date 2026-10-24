"""Recorder's 16 KiB attribute budget is not a dashboard size limit.

The full dashboard must stay available through its authenticated WebSocket
endpoint; even hundreds of recommendation items must never block Recorder.
"""
from __future__ import annotations

import json

from custom_components.environment_manager.recorder_attributes import (
    MAX_RECORDED_BYTES, bounded_attributes,
)


def size(attrs):
    return len(json.dumps(attrs,ensure_ascii=True,separators=(",",":")).encode())


def test_big_multiroom_recommendations_are_bounded_and_explicitly_truncated():
    required = {
        "dashboard_api":"environment_manager/dashboard",
        "dashboard_version":1,
        "dashboard_revision":1352,
        "recommendation_count":400,
        "open_window_count":400,
    }
    optional = {
        "open_windows":[f"binary_sensor.open_window_{i}" for i in range(400)],
        "recommendations":[{
            "area_id":f"room_{i}",
            "action":"open",
            "message": "Ανοίξτε το παράθυρο — " + "διαχείριση αέρα "*30,
            "reasons":[{"code":"inside_co2","value":"1800 ppm"}],
        } for i in range(400)],
        "outside_blockers":["Weather: high wind "*100 for i in range(200)],
        "home_settings":{"thresholds":{"pm25":25},"stored_options": "α" * 25000},
    }
    assert size({**required,**optional})>16384
    bounded=bounded_attributes(required,optional)
    assert size(bounded)<=MAX_RECORDED_BYTES<16384
    assert bounded["dashboard_api"]=="environment_manager/dashboard"
    assert bounded["recommendation_count"]==400
    assert bounded["dashboard_revision"]==1352
    assert bounded["truncated_fields"]
    assert len(bounded["open_windows"]) < len(optional["open_windows"])
    assert all("action" in item for item in bounded["recommendations"])


def test_normal_recommendation_metadata_keeps_legacy_attributes():
    required={"dashboard_api":"environment_manager/dashboard",
              "dashboard_revision":0}
    optional={"open_windows":["binary_sensor.kitchen"],
              "recommendations":[{"action":"open","area_id":"kitchen"}],
              "home_settings":{"automatic_notifications":True},
              "excluded_indoor_entities":{}}
    actual=bounded_attributes(required,optional)
    assert all(actual[key]==value for key,value in optional.items())
    assert "truncated_fields" not in actual


def test_pathological_single_huge_item_is_skipped_without_broken_json():
    base={"dashboard_api":"environment_manager/dashboard",
          "recommendation_count":1}
    items={"recommendations":[{"message":"💧"*50000}],
           "close_windows":["binary_sensor.kitchen"]}
    bounded=bounded_attributes(base,items)
    assert bounded["recommendations"]==[]
    assert bounded["close_windows"]==["binary_sensor.kitchen"]
    assert bounded["truncated_fields"]["recommendations"]==1
    assert size(bounded)<16384


def test_recorded_attributes_are_stable_with_many_fields_and_unicode():
    required={"dashboard_api":"environment_manager/dashboard",
              "dashboard_revision":123}
    optional={f"field_{i}":["Ελληνικά"*200 for _ in range(30)] for i in range(11)}
    actual=bounded_attributes(required,optional)
    assert size(actual)<16384
    assert actual["truncated_fields"]
