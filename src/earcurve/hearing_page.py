"""Per-ear hearing-threshold test page."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .audio import AudioUnavailable, TonePlayer
from .core.eq import BANDS, Curve, clamp, to_driver_json
from .core.hearing import (
    DEFAULT_K,
    HearingResult,
    HearingSession,
    compute_result,
    movie_curve,
)
from .formatting import freq_label as _freq_label
from .formatting import num as _num
from .formatting import signed as _signed
from .i18n import I18n
from .paths import user_data_dir
from .ui import topbar
from .widgets import CurveChart, centered_scroll


class HearingPage(QWidget):
    back_requested = Signal()
    tuning_requested = Signal()
    dirty_changed = Signal(bool)

    def __init__(self, i18n: I18n, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.tone = TonePlayer()
        self.session: HearingSession | None = None
        self.result: HearingResult | None = None
        self.level = -20
        self.ref_playing = False
        self.verifying = False
        self._dirty = False
        self._theme = "dark"
        self._device_index: int | None = None
        self._audio_warned = False
        self._resume_tone_after_dialog = False
        self._resume_ref_after_dialog = False
        self._last_export_dir: str | None = None

        self._static_labels: list[tuple[QLabel, str]] = []
        self._static_buttons: list[tuple[QPushButton, str]] = []
        self._static_checks: list[tuple[QCheckBox, str]] = []

        self._progress_path = user_data_dir() / "hearing-progress.json"
        self._result_path = user_data_dir() / "hearing-result.json"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar, self.brand, self.tag = topbar(i18n)
        self.tag.setText(i18n.t("hearing.tag"))
        self.back_btn = QPushButton()
        self.back_btn.setObjectName("ghost")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        bar.layout().addWidget(self.back_btn)
        root.addWidget(bar)

        self.views = QStackedWidget()
        self.views.setObjectName("windowRoot")
        root.addWidget(self.views, 1)

        self.prepare_scroll = self._build_prepare()
        self.test_scroll = self._build_test()
        self.results_scroll = self._build_results()
        for area in (self.prepare_scroll, self.test_scroll, self.results_scroll):
            self.views.addWidget(area)

        self.back_btn.clicked.connect(self._go_back)
        self._populate_outputs()
        self.views.setCurrentWidget(self.prepare_scroll)
        self.retranslate(i18n)

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    def _reg_label(self, label: QLabel, key: str) -> QLabel:
        self._static_labels.append((label, key))
        return label

    def _text(self, key: str, obj: str | None = None) -> QLabel:
        label = QLabel(self.i18n.t(key))
        if obj:
            label.setObjectName(obj)
        label.setWordWrap(True)
        self._reg_label(label, key)
        return label

    def _button(self, key: str, obj: str = "ghost") -> QPushButton:
        button = QPushButton(self.i18n.t(key))
        button.setObjectName(obj)
        button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._static_buttons.append((button, key))
        return button

    def _check(self, title_key: str, body_key: str) -> tuple[QCheckBox, QLabel]:
        check = QCheckBox(self.i18n.t(title_key))
        self._static_checks.append((check, title_key))
        body = self._text(body_key, "smallMuted")
        return check, body

    # ------------------------------------------------------------------
    # prepare view
    # ------------------------------------------------------------------
    def _build_prepare(self) -> QScrollArea:
        body = QWidget()
        box = QVBoxLayout(body)
        box.setContentsMargins(46, 24, 46, 20)
        box.setSpacing(10)

        box.addWidget(self._text("hearing.h1", "pageTitle"))
        intro = self._text("hearing.intro", "muted")
        box.addWidget(intro)
        box.addWidget(self._text("hearing.danger", "dangerNotice"))
        box.addWidget(self._text("hearing.warn", "warnNotice"))
        box.addWidget(self._text("hearing.checkTitle", "h2"))

        card = QFrame()
        card.setObjectName("card")
        card_box = QVBoxLayout(card)
        card_box.setContentsMargins(20, 14, 20, 14)
        card_box.setSpacing(10)
        for number in range(1, 6):
            check, detail = self._check(
                f"hearing.check{number}Title", f"hearing.check{number}Body"
            )
            row = QVBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(3)
            row.addWidget(check)
            detail_row = QHBoxLayout()
            detail_row.setContentsMargins(26, 0, 0, 0)
            detail_row.addWidget(detail, 1)
            row.addLayout(detail_row)
            card_box.addLayout(row)
        box.addWidget(card)

        ref_row = QHBoxLayout()
        ref_row.setSpacing(12)
        self.ref_btn = QPushButton()
        self.ref_btn.setObjectName("ghost")
        self.ref_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.ref_btn.clicked.connect(self._toggle_reference)
        self.ref_status = QLabel()
        self.ref_status.setObjectName("smallMuted")
        ref_row.addWidget(self.ref_btn)
        ref_row.addWidget(self.ref_status, 1)
        box.addLayout(ref_row)

        output_row = QHBoxLayout()
        output_row.setSpacing(10)
        output_label = self._text("hearing.outputLabel", "smallMuted")
        output_label.setWordWrap(False)
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(260)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        output_hint = self._text("hearing.outputHint", "smallMuted")
        output_row.addWidget(output_label)
        output_row.addWidget(self.device_combo)
        output_row.addWidget(output_hint, 1)
        box.addLayout(output_row)

        box.addSpacing(6)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.resume_btn = QPushButton()
        self.resume_btn.setObjectName("ghost")
        self.resume_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.resume_btn.clicked.connect(self._resume_test)
        self.last_btn = self._button("hearing.lastResult")
        self.last_btn.clicked.connect(self._show_last_result)
        self.start_btn = self._button("hearing.startLeft", "primary")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setMinimumWidth(200)
        self.start_btn.clicked.connect(self._start_new)
        action_row.addWidget(self.resume_btn)
        action_row.addWidget(self.last_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.start_btn)
        box.addLayout(action_row)

        box.addStretch(1)
        box.addWidget(self._text("footer", "footer"))
        return centered_scroll(body)

    # ------------------------------------------------------------------
    # test view
    # ------------------------------------------------------------------
    def _build_test(self) -> QScrollArea:
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(46, 30, 46, 30)
        outer.setSpacing(0)

        outer.addStretch(1)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)
        box = QVBoxLayout(card)
        box.setContentsMargins(28, 24, 28, 26)
        box.setSpacing(14)

        top = QHBoxLayout()
        self.ear_badge = QLabel()
        self.ear_badge.setObjectName("earBadge")
        self.progress_label = QLabel()
        self.progress_label.setObjectName("smallMuted")
        top.addWidget(self.ear_badge)
        top.addStretch(1)
        top.addWidget(self.progress_label)
        box.addLayout(top)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressLine")
        self.progress_bar.setRange(0, 20)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        box.addWidget(self.progress_bar)

        freq_row = QHBoxLayout()
        freq_row.setSpacing(8)
        self.freq_value = QLabel()
        self.freq_value.setObjectName("freqValue")
        freq_glow = QGraphicsDropShadowEffect(self.freq_value)
        freq_glow.setBlurRadius(30)
        freq_glow.setOffset(0, 0)
        freq_glow.setColor(QColor(139, 92, 246, 90))
        self.freq_value.setGraphicsEffect(freq_glow)
        self.freq_unit = QLabel("Hz")
        self.freq_unit.setObjectName("freqUnit")
        freq_row.addStretch(1)
        freq_row.addWidget(self.freq_value)
        freq_row.addWidget(self.freq_unit, 0, Qt.AlignmentFlag.AlignBottom)
        freq_row.addStretch(1)
        box.addLayout(freq_row)
        self.freq_unit.setContentsMargins(0, 0, 0, 12)

        tip = self._text("hearing.tip", "smallMuted")
        tip.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(tip)

        self.level_slider = QSlider(Qt.Orientation.Horizontal)
        self.level_slider.setRange(-70, 0)
        self.level_slider.setSingleStep(1)
        self.level_slider.setPageStep(2)
        self.level_slider.valueChanged.connect(self._on_level_changed)
        box.addWidget(self.level_slider)

        readout = QHBoxLayout()
        quiet = self._text("hearing.quiet", "smallMuted")
        quiet.setWordWrap(False)
        loud = self._text("hearing.loud", "smallMuted")
        loud.setWordWrap(False)
        level_label = self._text("hearing.levelLabel", "smallMuted")
        level_label.setWordWrap(False)
        self.level_value = QLabel()
        self.level_value.setObjectName("levelValue")
        readout.addWidget(quiet)
        readout.addStretch(1)
        readout.addWidget(level_label)
        readout.addWidget(self.level_value)
        readout.addStretch(1)
        readout.addWidget(loud)
        box.addLayout(readout)

        self.gate_warning = self._text("hearing.gateWarning", "warnNotice")
        self.gate_warning.setVisible(False)
        box.addWidget(self.gate_warning)

        box.addSpacing(4)
        confirm_row = QHBoxLayout()
        confirm_row.addStretch(1)
        self.confirm_btn = self._button("hearing.confirm", "primary")
        self.confirm_btn.setMinimumHeight(44)
        self.confirm_btn.clicked.connect(self._enter_verify)
        confirm_row.addWidget(self.confirm_btn)
        confirm_row.addStretch(1)
        box.addLayout(confirm_row)

        secondary = QHBoxLayout()
        secondary.setSpacing(12)
        self.cannot_btn = self._button("hearing.cannot", "dangerGhost")
        self.prev_btn = self._button("hearing.prev")
        self.cannot_btn.clicked.connect(lambda: self._record(None))
        self.prev_btn.clicked.connect(self._previous_band)
        secondary.addStretch(1)
        secondary.addWidget(self.cannot_btn)
        secondary.addWidget(self.prev_btn)
        secondary.addStretch(1)
        box.addLayout(secondary)

        self.verify_panel = QFrame()
        self.verify_panel.setObjectName("innerCard")
        verify_box = QVBoxLayout(self.verify_panel)
        verify_box.setContentsMargins(18, 16, 18, 16)
        verify_box.setSpacing(12)
        verify_box.addWidget(self._text("hearing.verifyText", "muted"))
        verify_row = QHBoxLayout()
        verify_row.setSpacing(10)
        self.verify_yes = self._button("hearing.verifyYes", "primary")
        self.verify_back = self._button("hearing.verifyBack")
        self.verify_yes.clicked.connect(lambda: self._record(self.level))
        self.verify_back.clicked.connect(self._verify_return)
        verify_row.addStretch(1)
        verify_row.addWidget(self.verify_yes)
        verify_row.addWidget(self.verify_back)
        verify_row.addStretch(1)
        verify_box.addLayout(verify_row)
        self.verify_panel.setVisible(False)
        box.addWidget(self.verify_panel)
        outer.addStretch(1)
        return centered_scroll(body)

    # ------------------------------------------------------------------
    # results view
    # ------------------------------------------------------------------
    def _build_results(self) -> QScrollArea:
        body = QWidget()
        box = QVBoxLayout(body)
        box.setContentsMargins(46, 30, 46, 28)
        box.setSpacing(14)

        box.addWidget(self._text("hearing.resultsTitle", "pageTitle"))
        self.summary_label = QLabel()
        self.summary_label.setObjectName("muted")
        self.summary_label.setWordWrap(True)
        box.addWidget(self.summary_label)

        result_card = QFrame()
        result_card.setObjectName("card")
        result_box = QVBoxLayout(result_card)
        result_box.setContentsMargins(20, 18, 20, 18)
        result_box.setSpacing(12)
        self.chart = CurveChart()
        result_box.addWidget(self.chart)

        k_row = QHBoxLayout()
        k_row.setSpacing(12)
        k_label = self._text("hearing.kLabel", "smallMuted")
        k_label.setWordWrap(False)
        self.k_slider = QSlider(Qt.Orientation.Horizontal)
        self.k_slider.setRange(50, 100)
        self.k_slider.setSingleStep(5)
        self.k_slider.setPageStep(5)
        self.k_slider.setFixedWidth(220)
        self.k_slider.valueChanged.connect(self._on_k_changed)
        self.k_value = QLabel()
        self.k_value.setObjectName("kValue")
        k_row.addWidget(k_label)
        k_row.addWidget(self.k_slider)
        k_row.addWidget(self.k_value)
        k_row.addStretch(1)
        result_box.addLayout(k_row)
        result_box.addWidget(self._text("hearing.kNote", "smallMuted"))
        box.addWidget(result_card)

        detail_card = QFrame()
        detail_card.setObjectName("card")
        detail_box = QVBoxLayout(detail_card)
        detail_box.setContentsMargins(20, 18, 20, 18)
        detail_box.setSpacing(10)
        detail_box.addWidget(self._text("hearing.detailTitle", "h2"))
        self.table = QTableWidget(10, 5)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(32 * 10 + 44)
        self.table.setMaximumHeight(32 * 10 + 48)
        detail_box.addWidget(self.table)
        self.main_gain_label = QLabel()
        self.main_gain_label.setObjectName("smallMuted")
        self.main_gain_label.setWordWrap(True)
        detail_box.addWidget(self.main_gain_label)
        box.addWidget(detail_card)

        import_card = QFrame()
        import_card.setObjectName("card")
        import_box = QVBoxLayout(import_card)
        import_box.setContentsMargins(20, 18, 20, 18)
        import_box.setSpacing(12)
        import_box.addWidget(self._text("hearing.importTitle", "h2"))

        export_row = QHBoxLayout()
        export_row.setSpacing(10)
        self.export_music_btn = self._button("hearing.exportMusic", "primary")
        self.export_movie_btn = self._button("hearing.exportMovie")
        self.export_music_btn.clicked.connect(lambda: self._export(False))
        self.export_movie_btn.clicked.connect(lambda: self._export(True))
        export_row.addWidget(self.export_music_btn)
        export_row.addWidget(self.export_movie_btn)
        export_row.addStretch(1)
        import_box.addLayout(export_row)

        steps = QGridLayout()
        steps.setHorizontalSpacing(8)
        steps.setVerticalSpacing(7)
        for index in range(1, 6):
            number = QLabel(f"{index}.")
            number.setObjectName("smallMuted")
            number.setAlignment(Qt.AlignmentFlag.AlignTop)
            steps.addWidget(number, index - 1, 0)
            steps.addWidget(self._text(f"hearing.import{index}", "smallMuted"), index - 1, 1)
        steps.setColumnStretch(1, 1)
        import_box.addLayout(steps)

        phone = self._text("hearing.phoneNotice", "muted")
        import_box.addWidget(phone)

        self.export_status = QLabel()
        self.export_status.setObjectName("smallMuted")
        self.export_status.setWordWrap(True)
        self.export_status.setVisible(False)
        import_box.addWidget(self.export_status)

        restart_row = QHBoxLayout()
        self.restart_btn = self._button("hearing.restart", "dangerGhost")
        self.restart_btn.clicked.connect(self._restart)
        self.next_btn = self._button("hearing.nextLink")
        self.next_btn.clicked.connect(self._go_tuning)
        restart_row.addWidget(self.restart_btn)
        restart_row.addStretch(1)
        restart_row.addWidget(self.next_btn)
        import_box.addLayout(restart_row)
        box.addWidget(import_card)

        box.addStretch(1)
        box.addWidget(self._text("footer", "footer"))
        return centered_scroll(body)

    # ------------------------------------------------------------------
    # audio
    # ------------------------------------------------------------------
    def _start_band_tone(self) -> None:
        if self.session is None:
            return
        try:
            self.tone.start_tone(
                self.session.current_freq(), self.session.ear, self.level, mode="burst"
            )
        except AudioUnavailable as exc:
            if not self._audio_warned:
                self._audio_warned = True
                QMessageBox.critical(
                    self,
                    self.i18n.t("hearing.tag"),
                    self.i18n.t("hearing.audioError", msg=str(exc)),
                )
        else:
            self._audio_warned = False

    def _ensure_band_tone(self) -> None:
        if not self.tone.is_playing():
            self._start_band_tone()
        else:
            self.tone.set_level(self.level)

    def _stop_reference(self) -> None:
        if self.ref_playing:
            self.tone.stop_tone()
            self.ref_playing = False
        self.ref_btn.setText(self.i18n.t("hearing.refButton"))
        self.ref_status.setText(self.i18n.t("hearing.refStatusIdle"))

    def _toggle_reference(self) -> None:
        if self.ref_playing:
            self._stop_reference()
            return
        try:
            self.tone.start_tone(1000, "both", 0, mode="steady")
        except AudioUnavailable as exc:
            QMessageBox.critical(
                self,
                self.i18n.t("hearing.tag"),
                self.i18n.t("hearing.audioError", msg=str(exc)),
            )
            return
        self.ref_playing = True
        self.ref_btn.setText(self.i18n.t("hearing.refStop"))
        self.ref_status.setText(self.i18n.t("hearing.refStatusPlaying"))

    def _on_device_changed(self, _index: int) -> None:
        value = self.device_combo.currentData()
        self._device_index = value if isinstance(value, int) else None
        try:
            self.tone.set_output_device(self._device_index)
        except Exception as exc:  # pragma: no cover - device dependent
            QMessageBox.warning(
                self,
                self.i18n.t("hearing.tag"),
                self.i18n.t("hearing.audioError", msg=str(exc)),
            )

    def _populate_outputs(self) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem(self.i18n.t("hearing.outputDefault"), None)
        for index, label in self.tone.list_outputs():
            self.device_combo.addItem(label, index)
        position = self.device_combo.findData(self._device_index)
        self.device_combo.setCurrentIndex(position if position >= 0 else 0)
        self.device_combo.blockSignals(False)

    def suspend_audio(self) -> None:
        self._resume_tone_after_dialog = self.tone.is_playing()
        self._resume_ref_after_dialog = self.ref_playing
        self._stop_reference()
        self.tone.stop_tone()

    def resume_audio(self) -> None:
        if self._resume_ref_after_dialog and self.views.currentWidget() is self.prepare_scroll:
            self._toggle_reference()
        elif self._resume_tone_after_dialog and self.views.currentWidget() is self.test_scroll:
            self._start_band_tone()
        self._resume_tone_after_dialog = False
        self._resume_ref_after_dialog = False

    def shutdown(self) -> None:
        self._stop_reference()
        self.tone.shutdown()

    # ------------------------------------------------------------------
    # flow
    # ------------------------------------------------------------------
    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

    def _start_new(self) -> None:
        self._stop_reference()
        self.tone.stop_tone()
        self.session = HearingSession()
        self.result = None
        self.k_slider.blockSignals(True)
        self.k_slider.setValue(int(round(DEFAULT_K * 100)))
        self.k_slider.blockSignals(False)
        self._enter_test()

    def _resume_test(self) -> None:
        saved = self._load_progress()
        if saved is None:
            QMessageBox.information(
                self, self.i18n.t("hearing.tag"), self.i18n.t("hearing.noProgress")
            )
            self._refresh_prepare()
            return
        self._stop_reference()
        self.tone.stop_tone()
        self.session = saved
        self._enter_test()

    def _enter_test(self) -> None:
        if self.session is None:
            return
        try:
            self.tone.open_output()
        except AudioUnavailable as exc:
            QMessageBox.critical(
                self,
                self.i18n.t("hearing.tag"),
                self.i18n.t("hearing.audioError", msg=str(exc)),
            )
            return
        self._set_dirty(True)
        self.views.setCurrentWidget(self.test_scroll)
        self._render_band()

    def _render_band(self) -> None:
        if self.session is None:
            return
        self.verifying = False
        self.verify_panel.setVisible(False)
        self.level_slider.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.cannot_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self._set_level(-20)
        self._update_test_texts()
        self.progress_bar.setValue(self.session.progress_position())
        self._save_progress()
        self.tone.stop_tone()
        self._start_band_tone()

    def _update_test_texts(self) -> None:
        if self.session is None:
            return
        ear = self.i18n.t("hearing.earLeft" if self.session.ear == "L" else "hearing.earRight")
        self.ear_badge.setText(ear)
        self.progress_label.setText(
            self.i18n.t("hearing.progress", n=self.session.index + 1)
        )
        self.freq_value.setText(_freq_label(self.session.current_freq()))
        self.level_value.setText(f"{self.level} dB")
        self.gate_warning.setVisible(self.level <= -60)
        self.progress_bar.setValue(self.session.progress_position())

    def _set_level(self, value: int) -> None:
        self.level = int(clamp(value, -70, 0))
        self.level_slider.blockSignals(True)
        self.level_slider.setValue(self.level)
        self.level_slider.blockSignals(False)
        self.level_value.setText(f"{self.level} dB")
        self.gate_warning.setVisible(self.level <= -60)
        if self.tone.is_playing():
            self.tone.set_level(self.level)

    def _on_level_changed(self, value: int) -> None:
        self.level = int(value)
        self.level_value.setText(f"{self.level} dB")
        self.gate_warning.setVisible(self.level <= -60)
        if self.tone.is_playing():
            self.tone.set_level(self.level)

    def _enter_verify(self) -> None:
        if self.session is None:
            return
        self.verifying = True
        self.verify_panel.setVisible(True)
        self.level_slider.setEnabled(False)
        self.confirm_btn.setEnabled(False)
        self.prev_btn.setEnabled(False)
        self._ensure_band_tone()

    def _verify_return(self) -> None:
        self.verifying = False
        self.verify_panel.setVisible(False)
        self.level_slider.setEnabled(True)
        self.confirm_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self._ensure_band_tone()

    def _record(self, value: float | None) -> None:
        if self.session is None:
            return
        self.tone.stop_tone()
        finished = self.session.record(value)
        if finished:
            self._finish()
        else:
            self._render_band()

    def _previous_band(self) -> None:
        if self.session is None or self.verifying:
            return
        self.tone.stop_tone()
        if self.session.previous():
            self._render_band()
        else:
            self._start_band_tone()

    def _finish(self) -> None:
        self.tone.stop_tone()
        self._delete_progress()
        self._save_result()
        self.views.setCurrentWidget(self.results_scroll)
        self.results_scroll.verticalScrollBar().setValue(0)
        self._render_results()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _read_json(self, path: Path) -> object | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def _load_progress(self) -> HearingSession | None:
        return HearingSession.from_dict(self._read_json(self._progress_path))

    def _save_progress(self) -> None:
        if self.session is None:
            return
        try:
            self._write_json(self._progress_path, self.session.to_dict())
        except OSError:
            pass

    def _delete_progress(self) -> None:
        try:
            self._progress_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _load_last_result(self) -> tuple[HearingSession, float] | None:
        data = self._read_json(self._result_path)
        if not isinstance(data, dict):
            return None
        raw_k = data.get("k", DEFAULT_K)
        k = float(raw_k) if isinstance(raw_k, (int, float)) else DEFAULT_K
        k = float(clamp(k, 0.5, 1.0))
        session = HearingSession.from_dict(
            {
                "ear": "L",
                "index": 0,
                "order": {"L": list(BANDS), "R": list(BANDS)},
                "thresholds": data.get("thresholds"),
            }
        )
        if session is None:
            return None
        return session, k

    def _save_result(self) -> None:
        if self.session is None or self.result is None:
            return
        payload = {
            "savedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "k": self.k_slider.value() / 100.0,
            "thresholds": self.session.to_dict()["thresholds"],
            "curve": to_driver_json(self.result.curve),
        }
        try:
            self._write_json(self._result_path, payload)
        except OSError:
            pass

    def _refresh_prepare(self) -> None:
        saved = self._load_progress()
        if saved is not None:
            self.resume_btn.setEnabled(True)
            ear = self.i18n.t(
                "hearing.earLeft" if saved.ear == "L" else "hearing.earRight"
            )
            self.resume_btn.setText(
                self.i18n.t("hearing.resumeAt", ear=ear, index=saved.index + 1)
            )
        else:
            self.resume_btn.setEnabled(False)
            self.resume_btn.setText(self.i18n.t("hearing.resume"))
        self.last_btn.setEnabled(self._load_last_result() is not None)

    def _show_last_result(self) -> None:
        loaded = self._load_last_result()
        if loaded is None:
            QMessageBox.information(
                self, self.i18n.t("hearing.tag"), self.i18n.t("hearing.noProgress")
            )
            self._refresh_prepare()
            return
        session, k = loaded
        self.session = session
        self.verifying = False
        self.k_slider.blockSignals(True)
        self.k_slider.setValue(int(round(k * 100)))
        self.k_slider.blockSignals(False)
        self._set_dirty(True)
        self.views.setCurrentWidget(self.results_scroll)
        self.results_scroll.verticalScrollBar().setValue(0)
        self._render_results()

    # ------------------------------------------------------------------
    # results
    # ------------------------------------------------------------------
    def _render_results(self) -> None:
        if self.session is None:
            return
        k = self.k_slider.value() / 100.0
        self.result = compute_result(self.session.thresholds, k)
        self.k_value.setText(f"{k:.2f}")
        self.chart.set_curve(self.result.curve)

        left_ref = self.result.refs.get("L")
        right_ref = self.result.refs.get("R")
        self.summary_label.setText(
            self.i18n.t(
                "hearing.summary",
                l=f"{_num(left_ref)} dB" if left_ref is not None else self.i18n.t("hearing.invalid"),
                r=f"{_num(right_ref)} dB" if right_ref is not None else self.i18n.t("hearing.invalid"),
            )
        )

        self.table.setHorizontalHeaderLabels(
            [
                self.i18n.t("hearing.thFreq"),
                self.i18n.t("hearing.thLeft"),
                self.i18n.t("hearing.thRight"),
                self.i18n.t("hearing.thDev"),
                self.i18n.t("hearing.thGain"),
            ]
        )
        positive = QColor("#7ee2a8") if self._theme == "dark" else QColor("#1a7f4b")
        negative = QColor("#f0a6b4") if self._theme == "dark" else QColor("#a3283d")
        for row_index, row in enumerate(self.result.rows):
            left = self.session.thresholds.get("L", {}).get(row.freq)
            right = self.session.thresholds.get("R", {}).get(row.freq)
            if row.missing:
                deviation = self.i18n.t("hearing.missingFill")
            else:
                deviation = _signed(row.deviation or 0.0, digits=1)
            cells = [
                f"{_freq_label(row.freq)} Hz",
                f"{_num(left)} dB" if left is not None else self.i18n.t("hearing.unheard"),
                f"{_num(right)} dB" if right is not None else self.i18n.t("hearing.unheard"),
                deviation,
                _signed(row.gain),
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 4:
                    if row.gain > 0:
                        item.setForeground(positive)
                    elif row.gain < 0:
                        item.setForeground(negative)
                self.table.setItem(row_index, column, item)

        self.main_gain_label.setText(
            self.i18n.t("hearing.tableNoteA")
            + str(self.result.main_gain)
            + self.i18n.t("hearing.tableNoteB")
        )
        self._save_result()

    def _on_k_changed(self, _value: int) -> None:
        if self.views.currentWidget() is self.results_scroll:
            self._render_results()
        else:
            self.k_value.setText(f"{self.k_slider.value() / 100.0:.2f}")

    def _export(self, movie: bool) -> None:
        if self.result is None:
            return
        curve: Curve = movie_curve(self.result.curve) if movie else self.result.curve
        filename = "darkrim-eq-movie.json" if movie else "darkrim-eq-music.json"
        initial = (
            str(Path(self._last_export_dir) / filename)
            if self._last_export_dir
            else str(Path.home() / filename)
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("hearing.exportTitle"),
            initial,
            self.i18n.t("hearing.exportFilter"),
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            Path(path).write_text(
                json.dumps(to_driver_json(curve), ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
        except OSError as exc:
            self.export_status.setText(self.i18n.t("hearing.exportFail", msg=str(exc)))
            self.export_status.setVisible(True)
            return
        self._last_export_dir = str(Path(path).parent)
        self.export_status.setText(self.i18n.t("hearing.exportDone", path=path))
        self.export_status.setVisible(True)

    def _restart(self) -> None:
        answer = QMessageBox.question(
            self,
            self.i18n.t("hearing.restart"),
            self.i18n.t("hearing.restartConfirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.tone.stop_tone()
        self._delete_progress()
        self.session = None
        self.result = None
        self.verifying = False
        self.export_status.setVisible(False)
        self.chart.set_curve(None)
        self._set_dirty(False)
        self.views.setCurrentWidget(self.prepare_scroll)
        self.prepare_scroll.verticalScrollBar().setValue(0)
        self._refresh_prepare()

    # ------------------------------------------------------------------
    # navigation / i18n
    # ------------------------------------------------------------------
    def _go_back(self) -> None:
        self._stop_reference()
        self.tone.stop_tone()
        self.tone.shutdown()
        self._set_dirty(False)
        self.views.setCurrentWidget(self.prepare_scroll)
        self._refresh_prepare()
        self.back_requested.emit()

    def _go_tuning(self) -> None:
        self._stop_reference()
        self.tone.stop_tone()
        self.tone.shutdown()
        self._set_dirty(False)
        self.views.setCurrentWidget(self.prepare_scroll)
        self._refresh_prepare()
        self.tuning_requested.emit()

    def on_shown(self) -> None:
        self._populate_outputs()
        self._refresh_prepare()

    def set_theme(self, theme: str) -> None:
        self._theme = "light" if theme == "light" else "dark"
        self.chart.set_theme(self._theme)
        if self.views.currentWidget() is self.results_scroll and self.session is not None:
            self._render_results()

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self.brand.setText(i18n.t("app.name"))
        self.tag.setText(i18n.t("hearing.tag"))
        self.back_btn.setText(i18n.t("back"))
        for label, key in self._static_labels:
            label.setText(i18n.t(key))
        for button, key in self._static_buttons:
            button.setText(i18n.t(key))
        for check, key in self._static_checks:
            check.setText(i18n.t(key))
        if self.device_combo.count():
            self.device_combo.setItemText(0, i18n.t("hearing.outputDefault"))
        self.ref_btn.setText(
            i18n.t("hearing.refStop" if self.ref_playing else "hearing.refButton")
        )
        self.ref_status.setText(
            i18n.t(
                "hearing.refStatusPlaying" if self.ref_playing else "hearing.refStatusIdle"
            )
        )
        self.export_status.setVisible(False)
        self._refresh_prepare()
        if self.views.currentWidget() is self.test_scroll:
            self._update_test_texts()
            self.level_value.setText(f"{self.level} dB")
        elif self.views.currentWidget() is self.results_scroll:
            self._render_results()
