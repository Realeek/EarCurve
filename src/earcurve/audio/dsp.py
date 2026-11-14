"""Offline audio helpers for blind A/B tuning.

Excerpts are decoded and resampled to 48 kHz. Curve variants are rendered with
a zero-phase magnitude EQ via FFT; this is fast in pure NumPy and perceptually
equivalent for a static 10-band curve.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..core.eq import Curve

OUTPUT_RATE = 48000
EXCERPT_SECONDS = 12.0
CLIP_SECONDS = 10.0
TARGET_RMS = 0.1
PEAK_CAP = 0.9
FADE_SECONDS = 0.025
SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".aiff", ".aif"}


@dataclass
class Excerpt:
    name: str
    data: np.ndarray  # frames x 2, float32, OUTPUT_RATE

    @property
    def duration(self) -> float:
        return self.data.shape[0] / OUTPUT_RATE


def resample_linear(data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or data.shape[0] == 0:
        return np.ascontiguousarray(data, dtype=np.float32)
    frames = data.shape[0]
    target_frames = max(1, int(round(frames * target_rate / source_rate)))
    old = np.linspace(0.0, 1.0, frames, endpoint=False)
    new = np.linspace(0.0, 1.0, target_frames, endpoint=False)
    channels = [
        np.interp(new, old, data[:, index]).astype(np.float32)
        for index in range(data.shape[1])
    ]
    return np.ascontiguousarray(np.stack(channels, axis=1), dtype=np.float32)


def load_excerpt(
    path: Path,
    seconds: float = EXCERPT_SECONDS,
    rng: random.Random | None = None,
) -> Excerpt | None:
    import soundfile as sf

    source = rng or random
    try:
        with sf.SoundFile(str(path)) as handle:
            rate = int(handle.samplerate)
            frames = int(handle.frames)
            channels = int(handle.channels)
            if rate <= 0 or frames < 4 * rate:
                return None
            length = min(int(seconds * rate), frames)
            max_start = max(0, frames - length)
            middle = frames * 0.3 + source.random() * max(
                0.0, frames * 0.4 - length
            )
            start = int(max(0, min(max_start, middle)))
            handle.seek(start)
            data = handle.read(length, dtype="float32", always_2d=True)
    except (RuntimeError, OSError, ValueError):
        return None
    if channels == 1:
        data = np.repeat(data, 2, axis=1)
    elif channels > 2:
        data = data[:, :2]
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    data = resample_linear(data, rate, OUTPUT_RATE)
    if data.shape[0] < 4 * OUTPUT_RATE:
        return None
    return Excerpt(name=path.name, data=np.ascontiguousarray(data, dtype=np.float32))


def curve_magnitude_db(
    curve: Curve, freqs: np.ndarray, sample_rate: int = OUTPUT_RATE
) -> np.ndarray:
    """Cascade magnitude response (dB) of all peaking bands at the given bins."""
    frequency = np.asarray(freqs, dtype=np.float64)
    total = np.zeros_like(frequency)
    nyquist = sample_rate / 2.0 - 1.0
    safe = np.clip(frequency, 1e-6, nyquist)
    for band in curve.bands:
        a = 10.0 ** (band.gain / 40.0)
        w0 = 2.0 * math.pi * min(band.freq, nyquist) / sample_rate
        alpha = math.sin(w0) / (2.0 * max(band.q, 0.01))
        b0 = 1.0 + alpha * a
        b1 = -2.0 * math.cos(w0)
        b2 = 1.0 - alpha * a
        a0 = 1.0 + alpha / a
        a1 = -2.0 * math.cos(w0)
        a2 = 1.0 - alpha / a
        w = 2.0 * math.pi * safe / sample_rate
        z = np.exp(-1j * w)
        numerator = b0 + b1 * z + b2 * z * z
        denominator = a0 + a1 * z + a2 * z * z
        magnitude = np.abs(numerator) / np.maximum(1e-12, np.abs(denominator))
        total += 20.0 * np.log10(np.maximum(magnitude, 1e-6))
    total[frequency <= 0] = 0.0
    return total


def render_variant(
    excerpt: Excerpt,
    curve: Curve,
    start_sec: float,
    duration_sec: float = CLIP_SECONDS,
) -> np.ndarray:
    rate = OUTPUT_RATE
    data = excerpt.data
    start = int(max(0.0, min(start_sec * rate, max(0, len(data) - 1))))
    end = min(len(data), start + int(duration_sec * rate))
    segment = data[start:end]
    frames = segment.shape[0]
    if frames < 1:
        raise ValueError("empty excerpt")

    nfft = 1 << max(1, (frames - 1).bit_length())
    freqs = np.fft.rfftfreq(nfft, 1.0 / rate)
    gain_db = curve_magnitude_db(curve, freqs, rate) + float(curve.main_gain)
    amplitude = np.power(10.0, gain_db / 20.0)

    spectrum = np.fft.rfft(segment, n=nfft, axis=0)
    spectrum *= amplitude[:, None]
    rendered = np.fft.irfft(spectrum, n=nfft, axis=0)[:frames]
    rendered = np.ascontiguousarray(rendered, dtype=np.float32)

    fade = min(int(FADE_SECONDS * rate), frames // 2)
    if fade > 0:
        fade_in = np.linspace(0.0, 1.0, fade, endpoint=False, dtype=np.float32)
        fade_out = np.linspace(1.0, 0.0, fade, endpoint=True, dtype=np.float32)
        rendered[:fade] *= fade_in[:, None]
        rendered[-fade:] *= fade_out[:, None]
    return rendered


def rms(data: np.ndarray) -> float:
    if data.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(data, dtype=np.float64))))


def peak(data: np.ndarray) -> float:
    if data.size == 0:
        return 0.0
    return float(np.max(np.abs(data)))


def normalize_pair(first: np.ndarray, second: np.ndarray) -> tuple[float, float]:
    gain_first = TARGET_RMS / max(1e-6, rms(first))
    gain_second = TARGET_RMS / max(1e-6, rms(second))
    peak_value = max(peak(first) * gain_first, peak(second) * gain_second)
    if peak_value > PEAK_CAP:
        scale = PEAK_CAP / peak_value
        gain_first *= scale
        gain_second *= scale
    return gain_first, gain_second
