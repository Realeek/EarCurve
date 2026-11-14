"""Tests for the desktop EQ core (mirrors test/eq.test.js)."""

import math

import pytest

from earcurve.core.eq import (
    BANDS,
    Band,
    flat_curve,
    from_driver_json,
    make_curve,
    peaking_response_db,
    to_driver_json,
    curve_response_db,
)


def test_flat_curve() -> None:
    curve = flat_curve()
    assert len(curve.bands) == 10
    assert all(band.gain == 0 and band.q == 1 for band in curve.bands)


def test_driver_json_shape() -> None:
    data = to_driver_json(flat_curve())
    assert set(data) == {"freq", "q", "sound", "type", "main_gain", "name"}
    assert len(data["freq"]) == 10
    assert all(isinstance(item, str) for item in data["q"])
    assert data["type"] == ["1"] * 10
    assert data["main_gain"] == 0


def test_sample_roundtrip() -> None:
    sample = {
        "freq": ["2900", "5328", "40", "100", "9000", "20", "200", "250", "140", "270"],
        "q": ["2.50", "1.50", "1.00", "2.00", "4.00", "0.80", "2.00", "1.00", "1.00", "3.50"],
        "sound": ["3", "-4", "-2", "-3.5", "-3", "-6", "3", "3.5", "1", "0"],
        "type": ["1"] * 10,
        "main_gain": 0,
        "name": "自定义1",
    }
    curve = from_driver_json(sample)
    assert len(curve.bands) == 10
    out = to_driver_json(curve)
    assert out["freq"] == ["20", "40", "100", "140", "200", "250", "270", "2900", "5328", "9000"]
    assert out["sound"][7] == "3"


def test_peaking_response() -> None:
    assert math.isclose(peaking_response_db(1000, Band(1000, 1, 0)), 0, abs_tol=1e-9)
    assert math.isclose(peaking_response_db(1000, Band(1000, 1, 6)), 6, abs_tol=0.01)
    assert math.isclose(peaking_response_db(1000, Band(1000, 1, -6)), -6, abs_tol=0.01)
    assert math.isclose(curve_response_db(flat_curve(), 500), 0, abs_tol=1e-9)


def test_make_curve_clamps() -> None:
    gains = [0] * 10
    gains[6] = 20
    curve = make_curve("x", gains)
    assert curve.bands[6].gain == 12


def test_invalid_json() -> None:
    with pytest.raises(ValueError):
        from_driver_json({})


def test_bands_match_web() -> None:
    assert BANDS == (40, 80, 160, 315, 630, 1000, 2000, 4000, 8000, 12000)
