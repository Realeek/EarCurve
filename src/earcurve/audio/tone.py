"""Test-tone playback through sounddevice.

The stream stays open while a test page is active; the callback synthesises the
burst tone and applies smooth level/fade ramps so slider moves do not click.
"""

from __future__ import annotations

import math
import threading
import time

import numpy as np

SAMPLE_RATE = 48000
TONE_AMPLITUDE = 0.8
BURST_ON = 0.2
BURST_OFF = 0.2
BURST_PERIOD = BURST_ON + BURST_OFF
BURST_FADE = 0.015
RAMP_SECONDS = 0.02


class AudioUnavailable(RuntimeError):
    """Raised when no output stream can be opened."""


class TonePlayer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream = None
        self._sample_rate = SAMPLE_RATE
        self._device: int | None = None
        self._freq = 1000.0
        self._ear = "both"
        self._level_db = 0.0
        self._mode = "burst"
        self._playing = False
        self._phase = 0.0
        self._burst_pos = 0.0
        self._level_amp = 0.0
        self._fade_amp = 0.0

    # -- public API -----------------------------------------------------
    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def is_playing(self) -> bool:
        return self._playing

    def list_outputs(self) -> list[tuple[int, str]]:
        try:
            import sounddevice as sd
        except Exception:
            return []
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
        except Exception:
            return []
        result: list[tuple[int, str]] = []
        for index, info in enumerate(devices):
            if int(info.get("max_output_channels", 0)) <= 0:
                continue
            api_name = ""
            try:
                api_name = hostapis[int(info["hostapi"])]["name"]
            except (KeyError, IndexError, TypeError):
                pass
            label = str(info.get("name", f"Output {index + 1}"))
            if api_name:
                label = f"{label} · {api_name}"
            result.append((index, label))
        return result

    def set_output_device(self, index: int | None) -> None:
        if index == self._device:
            return
        self._close_stream()
        self._device = index

    def open_output(self) -> None:
        """Open (or reuse) the output stream; raises AudioUnavailable on failure."""
        self._ensure_stream()

    def start_tone(
        self, freq: float, ear: str = "both", level_db: float = 0.0, mode: str = "burst"
    ) -> None:
        self._ensure_stream()
        with self._lock:
            self._freq = float(freq)
            self._ear = ear if ear in ("L", "R", "both") else "both"
            self._level_db = float(min(0.0, max(-70.0, level_db)))
            self._mode = "steady" if mode == "steady" else "burst"
            self._playing = True
            self._phase = 0.0
            self._burst_pos = 0.0
            self._fade_amp = 0.0
            self._level_amp = self._amp_for_level(self._level_db)

    def set_level(self, level_db: float) -> None:
        with self._lock:
            self._level_db = float(min(0.0, max(-70.0, level_db)))

    def stop_tone(self) -> None:
        with self._lock:
            self._playing = False

    def shutdown(self) -> None:
        with self._lock:
            self._playing = False
        if self._stream is not None:
            time.sleep(0.05)
        self._close_stream()

    # -- stream ---------------------------------------------------------
    def _ensure_stream(self) -> None:
        if self._stream is not None:
            return
        try:
            import sounddevice as sd
        except Exception as exc:  # pragma: no cover - depends on environment
            raise AudioUnavailable(f"sounddevice 不可用：{exc}") from exc

        rates = [SAMPLE_RATE, 44100]
        try:
            default_rate = int(
                sd.query_devices(self._device, "output")["default_samplerate"]
            )
            if default_rate > 0 and default_rate not in rates:
                rates.append(default_rate)
        except Exception:
            pass

        errors: list[str] = []
        for rate in rates:
            try:
                stream = sd.OutputStream(
                    device=self._device,
                    channels=2,
                    samplerate=rate,
                    dtype="float32",
                    blocksize=0,
                    callback=self._callback,
                )
                stream.start()
            except Exception as exc:  # pragma: no cover - depends on hardware
                errors.append(str(exc))
                continue
            self._stream = stream
            self._sample_rate = rate
            return
        raise AudioUnavailable("；".join(errors) or "无法打开音频输出")

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    # -- synthesis ------------------------------------------------------
    def _callback(self, outdata, frames, _time, _status) -> None:
        with self._lock:
            rate = float(self._sample_rate)
            playing = self._playing
            fade_target = 1.0 if playing else 0.0
            if not playing and self._fade_amp <= 1e-6:
                outdata.fill(0)
                return

            level_target = self._amp_for_level(self._level_db)
            levels = np.linspace(self._level_amp, level_target, frames, endpoint=False)
            fades = np.linspace(self._fade_amp, fade_target, frames, endpoint=False)
            self._level_amp = level_target
            self._fade_amp = fade_target

            omega = 2.0 * math.pi * self._freq / rate
            phases = self._phase + omega * np.arange(frames, dtype=np.float64)
            samples = np.sin(phases)
            self._phase = (self._phase + omega * frames) % (2.0 * math.pi)

            envelope = np.ones(frames, dtype=np.float64)
            if self._mode == "burst":
                positions = (self._burst_pos + np.arange(frames) / rate) % BURST_PERIOD
                on = positions < BURST_ON
                attack = np.clip(positions / BURST_FADE, 0.0, 1.0)
                release = np.clip((BURST_ON - positions) / BURST_FADE, 0.0, 1.0)
                envelope = np.where(on, np.minimum(attack, release), 0.0)
                self._burst_pos = (self._burst_pos + frames / rate) % BURST_PERIOD

            signal = samples * levels * fades * envelope
            if self._ear == "L":
                left, right = signal, np.zeros_like(signal)
            elif self._ear == "R":
                left, right = np.zeros_like(signal), signal
            else:
                left = right = signal
            outdata[:, 0] = left
            outdata[:, 1] = right

    @staticmethod
    def _amp_for_level(level_db: float) -> float:
        return TONE_AMPLITUDE * (10.0 ** (level_db / 20.0))
