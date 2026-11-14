"""Tests for offline EQ rendering and loudness normalisation."""

import math

import numpy as np

from earcurve.audio.dsp import (
    Excerpt,
    curve_magnitude_db,
    normalize_pair,
    peak,
    render_variant,
    resample_linear,
    rms,
)
from earcurve.core.eq import Band, flat_curve, peaking_response_db


def test_magnitude_matches_scalar_response() -> None:
    curve = flat_curve()
    curve.bands[5] = Band(1000, 1.0, 6.0)
    freqs = np.array([20.0, 100.0, 1000.0, 4000.0, 12000.0])
    magnitude = curve_magnitude_db(curve, freqs)
    for freq, value in zip(freqs, magnitude):
        expected = peaking_response_db(float(freq), curve.bands[5])
        assert math.isclose(value, expected, abs_tol=0.02)


def test_resample_changes_length() -> None:
    data = np.zeros((44100, 2), dtype=np.float32)
    resampled = resample_linear(data, 44100, 48000)
    assert resampled.shape[0] == 48000
    assert resampled.shape[1] == 2


def test_normalize_pair_matches_rms_and_caps_peak() -> None:
    rng = np.random.default_rng(3)
    first = rng.normal(0, 0.05, (24000, 2)).astype(np.float32)
    second = rng.normal(0, 0.2, (24000, 2)).astype(np.float32)
    gain_first, gain_second = normalize_pair(first, second)
    level_first = rms(first * gain_first)
    level_second = rms(second * gain_second)
    assert math.isclose(level_first, level_second, rel_tol=1e-6)
    assert max(peak(first * gain_first), peak(second * gain_second)) <= 0.9001


def test_render_variant_shape_and_fades() -> None:
    rng = np.random.default_rng(5)
    data = rng.normal(0, 0.1, (48000 * 2, 2)).astype(np.float32)
    excerpt = Excerpt(name="test.wav", data=data)
    curve = flat_curve()
    curve.bands[0].gain = 3
    rendered = render_variant(excerpt, curve, 0.1, 0.5)
    assert rendered.shape == (24000, 2)
    assert np.isfinite(rendered).all()
    assert abs(rendered[0, 0]) < 1e-6
    assert abs(rendered[-1, 0]) < 1e-6
