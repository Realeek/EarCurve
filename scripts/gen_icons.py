"""Generate Windows/web icon sizes from the master renders.

Inputs:
  assets/icon-1024.png       full-detail icon (transparent rounded square)
  assets/icon-small-512.png  simplified icon for 16-32 px

Outputs:
  assets/icon-{512,256,180,128,64,48,32,24,16}.png
  assets/icon.ico            multi-resolution (16-256)
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def resized(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    full = Image.open(ASSETS / "icon-1024.png").convert("RGBA")
    small = Image.open(ASSETS / "icon-small-512.png").convert("RGBA")

    for size in (512, 256, 180, 128, 64, 48):
        resized(full, size).save(ASSETS / f"icon-{size}.png")
    for size in (32, 24, 16):
        resized(small, size).save(ASSETS / f"icon-{size}.png")

    entries: list[tuple[int, bytes]] = []
    for size, source in (
        (16, small),
        (24, small),
        (32, small),
        (48, full),
        (64, full),
        (128, full),
        (256, full),
    ):
        buf = io.BytesIO()
        resized(source, size).save(buf, format="PNG")
        entries.append((size, buf.getvalue()))

    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory = bytearray()
    for size, data in entries:
        edge = 0 if size == 256 else size
        directory += struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(data), offset)
        offset += len(data)

    (ASSETS / "icon.ico").write_bytes(header + bytes(directory) + b"".join(d for _, d in entries))
    print("generated", len(entries), "sizes + icon.ico")


if __name__ == "__main__":
    main()
