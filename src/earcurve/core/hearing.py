"""Hearing-test session state and compensation-curve math.

Mirrors the browser tool so both front ends produce the same curve.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .eq import (
    BANDS,
    CURVE_MOVIE,
    CURVE_MUSIC,
    Curve,
    clamp,
    flat_curve,
    make_curve,
    round1,
)

DEFAULT_K = 0.7
MOVIE_ADD = {40: 2.0, 80: 2.0, 2000: 1.5, 4000: 1.0}


def _fresh_order(rng: random.Random | None = None) -> dict[str, list[int]]:
    source = rng or random
    order: dict[str, list[int]] = {}
    for ear in ("L", "R"):
        items = list(BANDS)
        source.shuffle(items)
        order[ear] = items
    return order


def _fresh_thresholds() -> dict[str, dict[int, float | None]]:
    return {"L": {}, "R": {}}


@dataclass
class HearingSession:
    ear: str = "L"
    index: int = 0
    order: dict[str, list[int]] = field(default_factory=_fresh_order)
    thresholds: dict[str, dict[int, float | None]] = field(default_factory=_fresh_thresholds)

    # -- traversal ------------------------------------------------------
    def current_freq(self) -> int:
        return self.order[self.ear][self.index]

    def progress_position(self) -> int:
        """0-based position across the 20-band run (used by the progress bar)."""
        return (0 if self.ear == "L" else 10) + self.index

    def record(self, value: float | None) -> bool:
        """Store the threshold for the current band; return True when finished."""
        self.thresholds[self.ear][self.current_freq()] = value
        self.index += 1
        if self.index < len(BANDS):
            return False
        if self.ear == "L":
            self.ear = "R"
            self.index = 0
            return False
        return True

    def previous(self) -> bool:
        if self.index > 0:
            self.index -= 1
            return True
        if self.ear == "R":
            self.ear = "L"
            self.index = len(BANDS) - 1
            return True
        return False

    # -- persistence ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "ear": self.ear,
            "index": self.index,
            "order": {ear: list(order) for ear, order in self.order.items()},
            "thresholds": {
                ear: {str(freq): value for freq, value in values.items()}
                for ear, values in self.thresholds.items()
            },
        }

    @classmethod
    def from_dict(cls, data: object) -> HearingSession | None:
        if not isinstance(data, dict):
            return None
        ear = data.get("ear")
        index = data.get("index")
        if ear not in ("L", "R") or not isinstance(index, int) or not 0 <= index < len(BANDS):
            return None
        raw_order = data.get("order")
        raw_thresholds = data.get("thresholds")
        if not isinstance(raw_order, dict) or not isinstance(raw_thresholds, dict):
            return None
        order: dict[str, list[int]] = {}
        for side in ("L", "R"):
            items = raw_order.get(side)
            if not isinstance(items, list) or len(items) != len(BANDS):
                return None
            try:
                freqs = [int(item) for item in items]
            except (TypeError, ValueError):
                return None
            if sorted(freqs) != sorted(BANDS):
                return None
            order[side] = freqs
        thresholds: dict[str, dict[int, float | None]] = {}
        for side in ("L", "R"):
            values = raw_thresholds.get(side, {})
            if not isinstance(values, dict):
                return None
            parsed: dict[int, float | None] = {}
            for key, value in values.items():
                try:
                    freq = int(key)
                except (TypeError, ValueError):
                    continue
                if freq not in BANDS:
                    continue
                if value is None:
                    parsed[freq] = None
                elif isinstance(value, (int, float)) and math.isfinite(value):
                    parsed[freq] = float(value)
            thresholds[side] = parsed
        return cls(ear=ear, index=index, order=order, thresholds=thresholds)


def reference_level(thresholds: dict[int, float | None]) -> float | None:
    direct = thresholds.get(1000)
    if isinstance(direct, (int, float)) and math.isfinite(direct):
        return float(direct)
    values = sorted(
        float(value)
        for value in thresholds.values()
        if isinstance(value, (int, float)) and math.isfinite(value)
    )
    if not values:
        return None
    return values[len(values) // 2]


@dataclass(frozen=True)
class BandResult:
    freq: int
    deviation: float
    missing: bool
    gain: float


@dataclass
class HearingResult:
    rows: list[BandResult]
    gains: list[float]
    main_gain: int
    refs: dict[str, float | None]
    curve: Curve


def compute_result(
    thresholds: dict[str, dict[int, float | None]], k: float = DEFAULT_K
) -> HearingResult:
    k = clamp(float(k), 0.0, 2.0)
    refs = {ear: reference_level(thresholds.get(ear, {})) for ear in ("L", "R")}
    deviations: list[float | None] = []
    missing_flags: list[bool] = []
    for freq in BANDS:
        deltas = []
        for ear in ("L", "R"):
            value = thresholds.get(ear, {}).get(freq)
            ref = refs[ear]
            if (
                isinstance(value, (int, float))
                and math.isfinite(value)
                and isinstance(ref, (int, float))
                and math.isfinite(ref)
            ):
                deltas.append(float(value) - float(ref))
        deviations.append(sum(deltas) / len(deltas) if deltas else None)
        missing_flags.append(not deltas)
    valid = [value for value in deviations if value is not None]
    fill = max(valid) + 6 if valid else 10.0
    filled = [value if value is not None else fill for value in deviations]
    gains = [round1(clamp(k * value, -12, 12)) for value in filled]
    gains[BANDS.index(1000)] = 0.0
    max_gain = max(gains)
    main_gain = max(-12, -math.ceil(max_gain) - 1) if max_gain > 0 else 0
    rows = [
        BandResult(
            freq=freq,
            deviation=filled[pos],
            missing=missing_flags[pos],
            gain=gains[pos],
        )
        for pos, freq in enumerate(BANDS)
    ]
    curve = make_curve(CURVE_MUSIC, gains, main_gain)
    return HearingResult(rows=rows, gains=gains, main_gain=main_gain, refs=refs, curve=curve)


def movie_curve(music: Curve) -> Curve:
    """Low-end/vocal lift for movies, with fixed headroom."""
    curve = flat_curve(CURVE_MOVIE)
    for index, band in enumerate(curve.bands):
        gain = clamp(music.bands[index].gain * 0.3, -4, 4) + MOVIE_ADD.get(band.freq, 0.0)
        band.gain = round1(clamp(gain, -12, 12))
    curve.main_gain = -6
    return curve
