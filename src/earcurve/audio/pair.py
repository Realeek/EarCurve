"""Synchronised two-buffer playback for blind A/B trials."""

from __future__ import annotations

import threading
import time

import numpy as np

from .dsp import OUTPUT_RATE
from .tone import AudioUnavailable

CROSSFADE_SECONDS = 0.03


class PairPlayer:
    """Both variants play from the same sample position; only gains switch."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream = None
        self._sample_rate = OUTPUT_RATE
        self._buf1: np.ndarray | None = None
        self._buf2: np.ndarray | None = None
        self._length = 0
        self._pos = 0
        self._playing = False
        self._active = 1
        self._mix1 = 1.0
        self._mix2 = 0.0
        self._target1 = 1.0
        self._target2 = 0.0
        self._stop_requested = False

    # -- public API -----------------------------------------------------
    def open_output(self) -> None:
        self._ensure_stream()

    def play(
        self,
        first: np.ndarray,
        gain_first: float,
        second: np.ndarray,
        gain_second: float,
        active: int = 1,
    ) -> None:
        self._ensure_stream()
        buf1 = np.ascontiguousarray(first * gain_first, dtype=np.float32)
        buf2 = np.ascontiguousarray(second * gain_second, dtype=np.float32)
        length = min(buf1.shape[0], buf2.shape[0])
        with self._lock:
            self._buf1 = buf1
            self._buf2 = buf2
            self._length = length
            self._pos = 0
            self._playing = length > 0
            self._active = 1 if active == 1 else 2
            self._mix1 = 1.0 if self._active == 1 else 0.0
            self._mix2 = 1.0 if self._active == 2 else 0.0
            self._target1 = self._mix1
            self._target2 = self._mix2
            self._stop_requested = False

    def switch_to(self, which: int) -> None:
        with self._lock:
            if not self._playing:
                return
            self._active = 1 if which == 1 else 2
            self._target1 = 1.0 if self._active == 1 else 0.0
            self._target2 = 1.0 if self._active == 2 else 0.0

    def stop(self) -> None:
        with self._lock:
            if self._playing:
                self._target1 = 0.0
                self._target2 = 0.0
                self._stop_requested = True
            else:
                self._playing = False

    def is_playing(self) -> bool:
        return self._playing

    def shutdown(self) -> None:
        with self._lock:
            self._playing = False
        if self._stream is not None:
            time.sleep(0.04)
        self._close_stream()

    # -- stream ---------------------------------------------------------
    def _ensure_stream(self) -> None:
        if self._stream is not None:
            return
        try:
            import sounddevice as sd
        except Exception as exc:  # pragma: no cover - environment dependent
            raise AudioUnavailable(f"sounddevice 不可用：{exc}") from exc
        try:
            stream = sd.OutputStream(
                channels=2,
                samplerate=OUTPUT_RATE,
                dtype="float32",
                blocksize=0,
                callback=self._callback,
            )
            stream.start()
        except Exception as exc:  # pragma: no cover - hardware dependent
            raise AudioUnavailable(str(exc)) from exc
        self._stream = stream

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
            if (
                not self._playing
                or self._buf1 is None
                or self._buf2 is None
                or self._length <= 0
            ):
                outdata.fill(0)
                return
            end = min(self._pos + frames, self._length)
            count = end - self._pos
            if count <= 0:
                outdata.fill(0)
                self._playing = False
                return

            ramp = np.linspace(0.0, 1.0, count, endpoint=False)
            mix1 = self._mix1 + (self._target1 - self._mix1) * ramp
            mix2 = self._mix2 + (self._target2 - self._mix2) * ramp
            left = (
                self._buf1[self._pos : end, 0] * mix1
                + self._buf2[self._pos : end, 0] * mix2
            )
            right = (
                self._buf1[self._pos : end, 1] * mix1
                + self._buf2[self._pos : end, 1] * mix2
            )
            outdata[:count, 0] = left
            outdata[:count, 1] = right
            if count < frames:
                outdata[count:].fill(0)

            self._pos = end
            self._mix1 = self._target1
            self._mix2 = self._target2
            if self._stop_requested and self._target1 == 0.0 and self._target2 == 0.0:
                self._playing = False
                self._stop_requested = False
            if self._pos >= self._length:
                self._playing = False
