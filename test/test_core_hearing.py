"""Tests for the hearing-test session and compensation math."""

import math

from earcurve.core.eq import BANDS, flat_curve, to_driver_json
from earcurve.core.hearing import (
    HearingSession,
    compute_result,
    movie_curve,
    reference_level,
)


def test_session_walks_both_ears() -> None:
    session = HearingSession()
    assert session.ear == "L"
    for _ in range(10):
        assert not session.record(-20)
    assert session.ear == "R" and session.index == 0
    for index in range(10):
        finished = session.record(-20)
        assert finished is (index == 9)
    assert len(session.thresholds["L"]) == 10
    assert len(session.thresholds["R"]) == 10


def test_previous_across_ears() -> None:
    session = HearingSession()
    for _ in range(10):
        session.record(-20)
    assert session.ear == "R" and session.index == 0
    assert session.previous()
    assert session.ear == "L" and session.index == 9
    for _ in range(9):
        assert session.previous()
    assert session.ear == "L" and session.index == 0
    assert not session.previous()


def test_reference_prefers_1khz() -> None:
    assert reference_level({1000: -30, 40: -10}) == -30
    assert reference_level({40: -10, 80: -30, 160: -20}) == -20
    assert reference_level({}) is None


def test_compute_curve_and_headroom() -> None:
    thresholds = {
        "L": {freq: -30 for freq in BANDS},
        "R": {freq: -30 for freq in BANDS},
    }
    thresholds["L"][40] = -10
    thresholds["R"][40] = -10
    thresholds["L"][8000] = -50
    thresholds["R"][8000] = -50
    result = compute_result(thresholds, 0.7)
    assert result.refs == {"L": -30, "R": -30}
    assert result.gains[BANDS.index(40)] == 12
    assert result.gains[BANDS.index(8000)] == -12
    assert result.gains[BANDS.index(1000)] == 0
    assert result.main_gain == -12
    assert result.curve.name == "EarCurve-Music"
    assert math.isclose(result.rows[0].deviation, 20, abs_tol=1e-9)


def test_missing_band_fills_upper_bound() -> None:
    result = compute_result({"L": {1000: -30}, "R": {1000: -30}}, 0.7)
    missing = result.rows[BANDS.index(40)]
    assert missing.missing
    assert math.isclose(missing.deviation, 6, abs_tol=1e-9)
    assert result.gains[BANDS.index(40)] == 4.2
    assert result.main_gain == -6


def test_session_roundtrip() -> None:
    session = HearingSession()
    session.record(-20)
    session.record(None)
    data = session.to_dict()
    restored = HearingSession.from_dict(data)
    assert restored is not None
    assert restored.ear == session.ear
    assert restored.index == session.index
    assert restored.thresholds == session.thresholds
    assert HearingSession.from_dict({"ear": "X"}) is None


def test_movie_curve() -> None:
    movie = movie_curve(flat_curve())
    assert movie.name == "EarCurve-Movie"
    assert movie.main_gain == -6
    gains = {band.freq: band.gain for band in movie.bands}
    assert gains[40] == 2
    assert gains[80] == 2
    assert gains[2000] == 1.5
    assert gains[4000] == 1
    assert to_driver_json(movie)["main_gain"] == -6
