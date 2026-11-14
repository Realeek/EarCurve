"""Resource and user-data paths, compatible with PyInstaller."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[2]


def asset(*parts: str) -> str:
    return str(repo_root() / "assets" / Path(*parts))


def builtin_tracks_dir() -> Path:
    return repo_root() / "assets" / "tracks"


def user_data_dir() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    path = root / "EarCurve"
    path.mkdir(parents=True, exist_ok=True)
    return path
