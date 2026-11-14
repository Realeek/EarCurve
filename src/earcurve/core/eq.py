"""10-band parametric EQ model, DARKRIM JSON I/O, and RBJ peaking response.

Mirrors web/js/eq.js so both front ends produce identical curves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

BANDS: tuple[int, ...] = (40, 80, 160, 315, 630, 1000, 2000, 4000, 8000, 12000)
MIN_GAIN = -12.0
MAX_GAIN = 12.0
SAMPLE_RATE = 48000.0

CURVE_MUSIC = "EarCurve-Music"
CURVE_MOVIE = "EarCurve-Movie"
CURVE_FINAL = "EarCurve-Final"


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def round1(value: float) -> float:
    # Match JavaScript Math.round (half towards +infinity), unlike Python's banker's rounding.
    return math.floor(value * 10 + 0.5) / 10 + 0.0


@dataclass
class Band:
    freq: float
    q: float = 1.0
    gain: float = 0.0


@dataclass
class Curve:
    bands: list[Band] = field(default_factory=list)
    main_gain: int = 0
    name: str = "自定义1"


def flat_curve(name: str = "自定义1") -> Curve:
    return Curve(bands=[Band(freq) for freq in BANDS], name=name)


def clone_curve(curve: Curve) -> Curve:
    return Curve(
        bands=[Band(band.freq, band.q, band.gain) for band in curve.bands],
        main_gain=curve.main_gain,
        name=curve.name,
    )


def make_curve(name: str, gains: list[float], main_gain: int = 0) -> Curve:
    bands = []
    for index, freq in enumerate(BANDS):
        gain = gains[index] if index < len(gains) else 0.0
        bands.append(Band(freq=freq, q=1.0, gain=round1(clamp(gain, MIN_GAIN, MAX_GAIN))))
    return Curve(bands=bands, main_gain=int(main_gain), name=name)


def _db_string(value: float) -> str:
    rounded = round1(value)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:g}"


def to_driver_json(curve: Curve) -> dict:
    bands = sorted(curve.bands, key=lambda band: band.freq)
    if len(bands) != 10:
        raise ValueError("驱动 EQ 需要正好 10 个频段")
    return {
        "freq": [str(int(round(band.freq))) for band in bands],
        "q": [f"{band.q:.2f}" for band in bands],
        "sound": [_db_string(band.gain) for band in bands],
        "type": ["1"] * len(bands),
        "main_gain": int(curve.main_gain),
        "name": curve.name or "自定义1",
    }


def from_driver_json(data: dict) -> Curve:
    if not isinstance(data, dict):
        raise ValueError("不是有效的 JSON 对象")
    for key in ("freq", "q", "sound"):
        if not isinstance(data.get(key), list):
            raise ValueError(f'缺少 "{key}" 数组')
    count = min(len(data["freq"]), len(data["q"]), len(data["sound"]))
    if count == 0:
        raise ValueError("EQ 文件里没有频段")
    bands = []
    for index in range(count):
        try:
            freq = float(data["freq"][index])
            q = float(data["q"][index])
            gain = float(data["sound"][index])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"第 {index + 1} 段参数非法") from exc
        if freq <= 0 or q <= 0 or not all(map(math.isfinite, (freq, q, gain))):
            raise ValueError(f"第 {index + 1} 段参数非法")
        bands.append(Band(freq=freq, q=q, gain=gain))
    try:
        main_gain = int(round(float(data.get("main_gain", 0))))
    except (TypeError, ValueError):
        main_gain = 0
    return Curve(
        bands=bands,
        main_gain=main_gain,
        name=data.get("name") if isinstance(data.get("name"), str) else "自定义1",
    )


def peaking_response_db(freq: float, band: Band, sample_rate: float = SAMPLE_RATE) -> float:
    nyquist = sample_rate / 2 - 1
    a = 10 ** (band.gain / 40)
    w0 = 2 * math.pi * min(band.freq, nyquist) / sample_rate
    alpha = math.sin(w0) / (2 * max(band.q, 0.01))
    b0 = 1 + alpha * a
    b1 = -2 * math.cos(w0)
    b2 = 1 - alpha * a
    a0 = 1 + alpha / a
    a1 = -2 * math.cos(w0)
    a2 = 1 - alpha / a
    w = 2 * math.pi * min(freq, nyquist) / sample_rate
    cw, sw = math.cos(w), math.sin(w)
    c2, s2 = math.cos(2 * w), math.sin(2 * w)
    num_re = b0 + b1 * cw + b2 * c2
    num_im = -(b1 * sw + b2 * s2)
    den_re = a0 + a1 * cw + a2 * c2
    den_im = -(a1 * sw + a2 * s2)
    magnitude = math.hypot(num_re, num_im) / max(1e-9, math.hypot(den_re, den_im))
    return 20 * math.log10(max(1e-6, magnitude))


def curve_response_db(curve: Curve, freq: float, include_main: bool = False) -> float:
    total = float(curve.main_gain) if include_main else 0.0
    for band in curve.bands:
        total += peaking_response_db(freq, band)
    return total
