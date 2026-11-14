"""Main window and page wiring for the desktop skeleton."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSettings, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from .hearing_page import HearingPage
from .i18n import I18n
from .paths import asset, user_data_dir
from .theme import apply_theme
from .tuning_page import TuningPage
from .ui import HomePage, IntroPage, PlaceholderPage


class MainWindow(QMainWindow):
    def __init__(self, smoke: bool = False) -> None:
        super().__init__()
        self.settings = QSettings(
            str(user_data_dir() / "settings.ini"), QSettings.Format.IniFormat
        )
        self.i18n = I18n(self.settings.value("language", "zh", str))
        theme = self.settings.value("theme", "dark", str)
        self.theme = theme if theme in ("dark", "light") else "dark"
        self._dirty = False
        self._dirty_flags = {"hearing": False, "tuning": False}

        apply_theme(QApplication.instance(), self.theme)

        self.stack = QStackedWidget()
        self.stack.setObjectName("windowRoot")
        self.setCentralWidget(self.stack)

        self.intro = IntroPage(self.i18n, animate=not smoke)
        self.home = HomePage(self.i18n)
        self.hearing = HearingPage(self.i18n)
        self.tuning = TuningPage(self.i18n)
        self.placeholder = PlaceholderPage(self.i18n)
        for page in (self.intro, self.home, self.hearing, self.tuning, self.placeholder):
            self.stack.addWidget(page)

        self.intro.started.connect(self.show_home)
        self.intro.theme_selected.connect(self.set_theme)
        self.intro.language_toggled.connect(self.toggle_language)
        self.home.tool_selected.connect(self.show_tool)
        self.placeholder.back_requested.connect(self.show_home)
        self.hearing.back_requested.connect(self.show_home)
        self.hearing.tuning_requested.connect(lambda: self.show_tool("tuning"))
        self.tuning.back_requested.connect(self.show_home)
        self.hearing.dirty_changed.connect(
            lambda dirty: self._set_source_dirty("hearing", dirty)
        )
        self.tuning.dirty_changed.connect(
            lambda dirty: self._set_source_dirty("tuning", dirty)
        )

        self.intro.prefs.sync(self.theme)
        self.intro.set_theme(self.theme)
        self.hearing.set_theme(self.theme)
        self.tuning.set_theme(self.theme)
        self.setWindowIcon(QIcon(asset("icon.ico")))
        self.setWindowTitle("EarCurve")
        self.resize(1120, 780)
        self.setMinimumSize(940, 660)
        self.stack.setCurrentWidget(self.intro)
        self._intro_started = False
        self._page_anim: QPropertyAnimation | None = None

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._intro_started:
            self._intro_started = True
            QTimer.singleShot(120, self.intro.play_intro)

    # -- navigation -----------------------------------------------------
    def _fade_page(self, page) -> None:
        if not self.isVisible():
            return
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(260)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def finish() -> None:
            if page.graphicsEffect() is effect:
                page.setGraphicsEffect(None)

        anim.finished.connect(finish)
        self._page_anim = anim
        anim.start()

    def show_home(self) -> None:
        self.stack.setCurrentWidget(self.home)
        self.setWindowTitle("EarCurve")
        self._fade_page(self.home)

    def show_tool(self, tool: str) -> None:
        if tool == "hearing":
            self.stack.setCurrentWidget(self.hearing)
            self.hearing.on_shown()
            self.setWindowTitle(self.i18n.t("hearing.windowTitle"))
            self._fade_page(self.hearing)
        elif tool == "tuning":
            self.stack.setCurrentWidget(self.tuning)
            self.tuning.on_shown()
            self.setWindowTitle(self.i18n.t("ab.windowTitle"))
            self._fade_page(self.tuning)
        else:
            self.stack.setCurrentWidget(self.placeholder)
            self.setWindowTitle("EarCurve")
            self._fade_page(self.placeholder)

    # -- settings -------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.settings.setValue("theme", self.theme)
        apply_theme(QApplication.instance(), self.theme)
        self.intro.prefs.sync(self.theme)
        self.intro.set_theme(self.theme)
        self.hearing.set_theme(self.theme)
        self.tuning.set_theme(self.theme)

    def toggle_language(self) -> None:
        self.i18n.toggle()
        self.settings.setValue("language", self.i18n.lang)
        self.intro.retranslate(self.i18n)
        self.home.retranslate(self.i18n)
        self.hearing.retranslate(self.i18n)
        self.tuning.retranslate(self.i18n)
        self.placeholder.retranslate(self.i18n)
        if self.stack.currentWidget() is self.hearing:
            self.setWindowTitle(self.i18n.t("hearing.windowTitle"))
        elif self.stack.currentWidget() is self.tuning:
            self.setWindowTitle(self.i18n.t("ab.windowTitle"))

    # -- progress state -------------------------------------------------
    def _set_source_dirty(self, source: str, dirty: bool) -> None:
        self._dirty_flags[source] = dirty
        self._dirty = any(self._dirty_flags.values())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._dirty:
            self.hearing.suspend_audio()
            self.tuning.suspend_audio()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(self.i18n.t("exit.title"))
            box.setText(self.i18n.t("exit.body"))
            cancel = box.addButton(self.i18n.t("exit.cancel"), QMessageBox.ButtonRole.RejectRole)
            confirm = box.addButton(self.i18n.t("exit.confirm"), QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not confirm:
                self.hearing.resume_audio()
                self.tuning.resume_audio()
                event.ignore()
                return
        self.hearing.shutdown()
        self.tuning.shutdown()
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()
