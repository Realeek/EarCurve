"""Application entry point."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .paths import asset


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    smoke = "--smoke" in args
    self_test = "--self-test" in args
    args = [arg for arg in args if arg not in ("--smoke", "--self-test")]

    if smoke or self_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(args)
    app.setApplicationName("EarCurve")
    app.setOrganizationName("EarCurve")
    app.setApplicationDisplayName("EarCurve")
    app.setWindowIcon(QIcon(asset("icon.ico")))
    app.setFont(QFont("Microsoft YaHei UI", 10))

    window = MainWindow(smoke=smoke or self_test)
    window.show()

    if self_test:
        from .audio.dsp import render_variant
        from .audio.tone import TonePlayer
        from .core.eq import flat_curve

        window.tuning._load_builtin()
        tracks = window.tuning.tracks
        if len(tracks) != 8:
            print(f"self-test failed: expected 8 built-in tracks, got {len(tracks)}")
            return 2
        rendered = render_variant(tracks[0], flat_curve(), 0.5, 1.0)
        outputs = len(TonePlayer().list_outputs())
        print(
            "self-test ok:"
            f" tracks={len(tracks)}"
            f" render={rendered.shape}"
            f" outputs={outputs}"
        )
        return 0

    if smoke:
        def finish() -> None:
            print("desktop smoke ok")
            app.quit()

        QTimer.singleShot(900, finish)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
