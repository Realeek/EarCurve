"""Build the bundled CC0 sample library from downloaded FreePD tracks.

Usage:
    python scripts/prepare_tracks.py --source <folder with source mp3s>

Requires: soundfile, numpy, lameenc, mutagen.

Each source is trimmed to a 25 s excerpt, RMS-normalised with a peak cap,
faded, and encoded as 128 kbps stereo MP3. Credits and a manifest are written
next to the output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote

import lameenc
import numpy as np
import soundfile as sf
from mutagen.id3 import COMM, TALB, TCON, TIT2, TPE1, ID3

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "assets" / "tracks"
MIRROR = "https://github.com/SoundSafari/CC0-1.0-Music/blob/main/freepd.com/"

CLIP_SECONDS = 25.0
TARGET_RMS_DB = -20.0
PEAK_CAP_DB = -1.0
FADE_SECONDS = 0.02
BITRATE = 128

TRACKS = [
    {
        "source": "Adventure.mp3",
        "file": "01-adventure.mp3",
        "title": "Adventure",
        "artist": "Rafael Krux / CinematicWaves",
        "genre": "Soundtrack",
        "start": 22.5,
    },
    {
        "source": "Brandenburg Concerto III, Allegro I.mp3",
        "file": "02-brandenburg-concerto-iii.mp3",
        "title": "Brandenburg Concerto No. 3",
        "artist": "J.S. Bach / dogsounds",
        "genre": "Classical",
        "start": 135.5,
    },
    {
        "source": "Blippy Trance.mp3",
        "file": "03-blippy-trance.mp3",
        "title": "Blippy Trance",
        "artist": "Kevin MacLeod",
        "genre": "Electronic",
        "start": 20.0,
    },
    {
        "source": "Hippety Hop.mp3",
        "file": "04-hippety-hop.mp3",
        "title": "Hippety Hop",
        "artist": "Alexander Nakarada",
        "genre": "Hip-Hop",
        "start": 44.0,
    },
    {
        "source": "Cumbish.mp3",
        "file": "05-cumbish.mp3",
        "title": "Cumbish",
        "artist": "Kevin MacLeod",
        "genre": "Latin",
        "start": 19.0,
    },
    {
        "source": "Take the Sting Out - Jazz Fi.mp3",
        "file": "06-take-the-sting-out.mp3",
        "title": "Take the Sting Out",
        "artist": "Kevin MacLeod",
        "genre": "Jazz",
        "start": 33.5,
    },
    {
        "source": "Happy Whistling Ukulele.mp3",
        "file": "07-happy-whistling-ukulele.mp3",
        "title": "Happy Whistling Ukulele",
        "artist": "Rafael Krux / CinematicWaves",
        "genre": "Folk / Acoustic",
        "start": 65.5,
    },
    {
        "source": "City Sunshine.mp3",
        "file": "08-city-sunshine.mp3",
        "title": "City Sunshine",
        "artist": "Kevin MacLeod",
        "genre": "Pop / Electronic",
        "start": 35.0,
    },
]


def encode_mp3(data: np.ndarray, sample_rate: int) -> bytes:
    pcm = np.clip(data, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(BITRATE)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(2)
    encoder.set_quality(2)
    return encoder.encode(pcm.tobytes()) + encoder.flush()


def tag(path: Path, track: dict) -> None:
    tags = ID3()
    tags.add(TIT2(encoding=3, text=track["title"]))
    tags.add(TPE1(encoding=3, text=track["artist"]))
    tags.add(TALB(encoding=3, text="EarCurve CC0 Sample Library"))
    tags.add(TCON(encoding=3, text=track["genre"]))
    tags.add(
        COMM(
            encoding=3,
            lang="eng",
            desc="License",
            text=(
                "CC0 1.0 Universal. Source: FreePD.com via "
                "SoundSafari/CC0-1.0-Music. Trimmed, level-normalised and "
                "re-encoded for the EarCurve sample library."
            ),
        )
    )
    tags.save(str(path))


def process(source_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for track in TRACKS:
        source = source_dir / track["source"]
        with sf.SoundFile(str(source)) as handle:
            rate = handle.samplerate
            start = int(track["start"] * rate)
            frames = int(CLIP_SECONDS * rate)
            handle.seek(start)
            data = handle.read(frames, dtype="float32", always_2d=True)
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]
        if data.shape[0] < frames:
            raise ValueError(f"{track['source']} is too short")

        rms = float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
        gain = 10 ** (TARGET_RMS_DB / 20) / max(1e-9, rms)
        peak = float(np.max(np.abs(data))) * gain
        peak_cap = 10 ** (PEAK_CAP_DB / 20)
        if peak > peak_cap:
            gain *= peak_cap / peak
        data = (data * gain).astype(np.float32)

        fade = int(FADE_SECONDS * rate)
        fade_in = np.linspace(0.0, 1.0, fade, endpoint=False, dtype=np.float32)
        fade_out = np.linspace(1.0, 0.0, fade, endpoint=True, dtype=np.float32)
        data[:fade] *= fade_in[:, None]
        data[-fade:] *= fade_out[:, None]

        encoded = encode_mp3(data, rate)
        destination = out_dir / track["file"]
        destination.write_bytes(encoded)
        tag(destination, track)

        source_url = MIRROR + quote(track["source"])
        manifest.append(
            {
                "file": track["file"],
                "title": track["title"],
                "artist": track["artist"],
                "genre": track["genre"],
                "duration_seconds": CLIP_SECONDS,
                "sample_rate": rate,
                "bitrate_kbps": BITRATE,
                "license": "CC0-1.0",
                "source_url": source_url,
                "source_file": track["source"],
                "start_seconds": track["start"],
                "modifications": "25 s excerpt, RMS level normalisation, 20 ms fades, MP3 128 kbps",
            }
        )
        print(f"wrote {destination.name} ({len(encoded) / 1024:.0f} KiB)")

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Bundled sample library",
        "",
        "The eight MP3 excerpts in this folder are dedicated to the public domain",
        "under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).",
        "Attribution is not required, but the sources are listed below.",
        "",
        "| File | Title | Artist | Genre | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for track in TRACKS:
        url = MIRROR + quote(track["source"])
        lines.append(
            f"| `{track['file']}` | {track['title']} | {track['artist']} | "
            f"{track['genre']} | [FreePD mirror]({url}) |"
        )
    lines += [
        "",
        "Each excerpt was trimmed, loudness-normalised, faded and re-encoded at",
        "128 kbps stereo for use inside EarCurve. The originals remain CC0.",
        "",
        "FreePD.com was a public-domain music catalog; its site has closed and the",
        "mirror above preserves the files. Track-level credits come from the",
        "original ID3 tags and the FreePD catalog.",
    ]
    (out_dir / "CREDITS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    process(args.source, args.out)


if __name__ == "__main__":
    main()
