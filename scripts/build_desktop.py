"""Build the desktop app with PyInstaller.

Use a clean virtual environment for smaller builds:
    uv venv --python 3.12 .venv-clean
    uv pip install --python .venv-clean/Scripts/python.exe -r requirements.txt

Usage:
    python scripts/build_desktop.py            # onedir + onefile
    python scripts/build_desktop.py --onedir
    python scripts/build_desktop.py --onefile
    python scripts/build_desktop.py --onedir --dist dist-clean --work build-clean
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(onefile: bool, dist_dir: Path | None, work_dir: Path | None) -> None:
    if "anaconda" in sys.prefix.lower():
        print(
            "warning: building inside Anaconda bundles MKL and a large PySide6 "
            "install; use a clean Python 3.12 venv for a ~55 MB onefile build"
        )
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "EarCurve",
        "--icon",
        str(ROOT / "assets" / "icon.ico"),
        "--add-data",
        f"{ROOT / 'assets'}{os.pathsep}assets",
        "--add-data",
        f"{ROOT / 'THIRD_PARTY_NOTICES.md'}{os.pathsep}.",
        "--add-data",
        f"{ROOT / 'licenses'}{os.pathsep}licenses",
        "--collect-data",
        "sounddevice",
        "--collect-binaries",
        "sounddevice",
        "--collect-data",
        "soundfile",
        "--collect-binaries",
        "soundfile",
        "--paths",
        str(ROOT / "src"),
        str(ROOT / "run_earcurve.py"),
    ]
    command.insert(3, "--onefile" if onefile else "--onedir")
    if dist_dir is not None:
        command[3:3] = ["--distpath", str(dist_dir)]
    if work_dir is not None:
        command[3:3] = ["--workpath", str(work_dir), "--specpath", str(work_dir)]
    print("running:", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--onedir", action="store_true")
    parser.add_argument("--onefile", action="store_true")
    parser.add_argument("--dist", type=Path, default=None)
    parser.add_argument("--work", type=Path, default=None)
    args = parser.parse_args()
    do_onedir = not args.onefile or args.onedir
    do_onefile = not args.onedir or args.onefile
    if do_onedir:
        build(onefile=False, dist_dir=args.dist, work_dir=args.work)
    if do_onefile:
        build(onefile=True, dist_dir=args.dist, work_dir=args.work)


if __name__ == "__main__":
    main()
