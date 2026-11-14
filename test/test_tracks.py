"""Checks for the bundled CC0 sample library."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACKS = ROOT / "assets" / "tracks"


def test_manifest_matches_bundled_files() -> None:
    manifest = json.loads((TRACKS / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 8
    names = {entry["file"] for entry in manifest}
    assert len(names) == 8
    for entry in manifest:
        path = TRACKS / entry["file"]
        assert path.is_file(), entry["file"]
        assert path.stat().st_size > 100_000
        assert entry["license"] == "CC0-1.0"
        assert entry["source_url"].startswith("https://")
        assert 20 <= entry["duration_seconds"] <= 30
        assert entry["bitrate_kbps"] == 128


def test_credits_and_license_present() -> None:
    credits = (TRACKS / "CREDITS.md").read_text(encoding="utf-8")
    license_text = (TRACKS / "CC0-1.0.txt").read_text(encoding="utf-8")
    assert "CC0 1.0 Universal" in credits
    assert "Kevin MacLeod" in credits
    assert "Creative Commons" in license_text
