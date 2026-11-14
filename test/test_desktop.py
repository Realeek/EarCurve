"""Qt smoke test for the desktop app (offscreen)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from earcurve.main_window import MainWindow  # noqa: E402


def test_main_window_builds(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow(smoke=True)
    assert window.windowTitle() == "EarCurve"
    assert window.i18n.lang in {"zh", "en"}
    assert window.stack.count() == 5
    assert window.hearing.views.count() == 3
    assert window.tuning.views.count() == 3
    window.show_tool("hearing")
    assert window.stack.currentWidget() is window.hearing
    window.show_tool("tuning")
    assert window.stack.currentWidget() is window.tuning
    window.tuning._load_builtin()
    assert len(window.tuning.tracks) == 8
    assert window.tuning.start_btn.isEnabled()
    window.show_home()
    window.close()
    app.processEvents()
