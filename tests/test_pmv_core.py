"""Portable ISO 7730/PMV regression tests, independent of Numba/LLVM."""
import math
import json
from pathlib import Path

import pytest

from custom_components.environment_manager.pmv_core import pmv_ppd_iso
from custom_components.environment_manager.environment_science import pmv_iso7730


@pytest.mark.parametrize("inputs,expected_pmv,expected_ppd", [
    ((22,25,0.1,50,1.4,0.5),0.0,5.0),
    ((25,25,0.1,50,1.4,0.5),0.41,8.5),
    ((25,25,0.22,50,1.4,0.5),0.17,5.6),
    ((22,22,0.1,50,1.2,0.7),-0.37,7.8),
])
def test_matches_reference_library_vectors(inputs,expected_pmv,expected_ppd):
    # First three vectors come from pythermalcomfort 4.6.2 documentation;
    # fourth is an additional check against the reference equations.
    x=pmv_ppd_iso(*inputs, model="7730-2025")
    assert x.pmv == pytest.approx(expected_pmv,abs=0.01)
    assert x.ppd == pytest.approx(expected_ppd,abs=0.11)
    assert 5 <= x.ppd <= 100


def test_same_fanger_formula_under_both_iso_editions():
    inputs=(23,24,0.14,48,1.3,0.7)
    assert pmv_ppd_iso(*inputs,model="7730-2005") == pmv_ppd_iso(
        *inputs,model="7730-2025")
    with pytest.raises(ValueError):
        pmv_ppd_iso(*inputs,model="2020")


@pytest.mark.parametrize("args", [
    (30,25,0.1,50,1.4,0.5), # ISO air-temperature boundary
    (25,40,0.1,50,1.4,0.5), # ISO radiant-temperature boundary
    (25,25,0,50,1.4,0.5),   # missing air movement
    (25,25,0.1,50,4.5,0.5),
    (25,25,0.1,50,1.4,0),
    (25,25,0.1,float("nan"),1.4,0.5),
    (25,25,0.1,True,1.4,0.5),
])
def test_invalid_or_outside_inputs_fail_closed(args):
    result=pmv_ppd_iso(*args)
    assert math.isnan(result.pmv)
    assert math.isnan(result.ppd)


def test_standard_pmv_still_operates_without_third_party_packages():
    result=pmv_iso7730(25,25,50,0.1,1.4,0.5)
    assert result["status"] == "estimate"
    assert result["pmv"] == pytest.approx(0.41,abs=0.01)
    assert result["ppd_percent"] == pytest.approx(8.5,abs=0.11)


def test_no_mandatory_binary_dependencies_in_manifest():
    manifest=json.loads((Path(__file__).resolve().parents[1]/
        "custom_components/environment_manager/manifest.json").read_text(
            encoding="utf-8"))
    assert manifest["requirements"] == []
