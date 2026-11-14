"""Blind A/B preference-tuning page."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QEventLoop, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .audio import AudioUnavailable
from .audio.dsp import (
    CLIP_SECONDS,
    SUPPORTED_EXTENSIONS,
    Excerpt,
    load_excerpt,
    normalize_pair,
    render_variant,
)
from .audio.pair import PairPlayer
from .core.eq import (
    BANDS,
    CURVE_FINAL,
    Curve,
    clone_curve,
    flat_curve,
    from_driver_json,
    to_driver_json,
)
from .core.tuning import TuningSession, TrialPlan, nonzero_bands
from .formatting import freq_label, signed
from .i18n import I18n
from .paths import builtin_tracks_dir, user_data_dir
from .ui import topbar
from .widgets import CurveChart, centered_scroll


class TuningPage(QWidget):
    back_requested = Signal()
    dirty_changed = Signal(bool)

    def __init__(self, i18n: I18n, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.i18n = i18n
        self.player = PairPlayer()
        self.tracks: list[Excerpt] = []
        self.baseline: Curve = flat_curve()
        self.session: TuningSession | None = None
        self.pending: TrialPlan | None = None
        self.pending_buffers: tuple[object, object] | None = None
        self.pending_gains: tuple[float, float] = (1.0, 1.0)
        self.active = 1
        self._dirty = False
        self._theme = "dark"
        self._rng = random.Random()
        self._session_active = False
        self._accepting_votes = False
        self._rendering = False
        self._was_playing = False
        self._render_token = 0
        self._resume_after_dialog = False
        self._resume_render_after_dialog = False
        self._baseline_imported = False
        self._last_folder: str | None = None
        self._last_export_dir: str | None = None

        self._static_labels: list[tuple[QLabel, str]] = []
        self._static_buttons: list[tuple[QPushButton, str]] = []

        self._hearing_result_path = user_data_dir() / "hearing-result.json"
        self._tuning_result_path = user_data_dir() / "ab-result.json"

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar, self.brand, self.tag = topbar(i18n)
        self.tag.setText(i18n.t("ab.tag"))
        self.back_btn = QPushButton()
        self.back_btn.setObjectName("ghost")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.back_btn.clicked.connect(lambda: self._go_back(True))
        bar.layout().addWidget(self.back_btn)
        root.addWidget(bar)

        self.views = QStackedWidget()
        self.views.setObjectName("windowRoot")
        root.addWidget(self.views, 1)

        self.prepare_scroll = self._build_prepare()
        self.session_scroll = self._build_session()
        self.results_scroll = self._build_results()
        for area in (self.prepare_scroll, self.session_scroll, self.results_scroll):
            self.views.addWidget(area)

        self._end_timer = QTimer(self)
        self._end_timer.setInterval(120)
        self._end_timer.timeout.connect(self._poll_playback)

        self.views.setCurrentWidget(self.prepare_scroll)
        self.retranslate(i18n)
        self._refresh_baseline(reload=True)

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

    def _set_status(
        self,
        label: QLabel,
        key: str | None = None,
        kind: str | None = None,
        text: str | None = None,
        **vars: object,
    ) -> None:
        label.setText(self.i18n.t(key, **vars) if key else (text or ""))
        name = {"ok": "statusOk", "err": "statusErr"}.get(kind or "", "smallMuted")
        if label.objectName() != name:
            label.setObjectName(name)
            label.style().unpolish(label)
            label.style().polish(label)

    @staticmethod
    def _pump() -> None:
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    # ------------------------------------------------------------------
    # prepare view
    # ------------------------------------------------------------------
    def _build_prepare(self) -> QScrollArea:
        body = QWidget()
        box = QVBoxLayout(body)
        box.setContentsMargins(46, 22, 46, 20)
        box.setSpacing(9)

        box.addWidget(self._text("ab.h1", "pageTitle"))
        box.addWidget(self._text("ab.intro", "muted"))
        box.addWidget(self._text("ab.notice", "warnNotice"))

        box.addWidget(self._text("ab.section1", "h2"))
        folder_row = QHBoxLayout()
        folder_row.setSpacing(12)
        self.folder_btn = self._button("ab.chooseFolder")
        self.folder_btn.setMinimumWidth(140)
        self.folder_btn.clicked.connect(self._choose_folder)
        self.builtin_btn = self._button("ab.builtin")
        self.builtin_btn.setMinimumWidth(150)
        self.builtin_btn.clicked.connect(self._load_builtin)
        self.load_status = QLabel()
        self.load_status.setObjectName("smallMuted")
        self.load_status.setWordWrap(True)
        folder_row.addWidget(self.folder_btn)
        folder_row.addWidget(self.builtin_btn)
        folder_row.addWidget(self.load_status, 1)
        box.addLayout(folder_row)

        box.addWidget(self._text("ab.section2", "h2"))
        self.baseline_info = QLabel()
        self.baseline_info.setObjectName("muted")
        self.baseline_info.setWordWrap(True)
        box.addWidget(self.baseline_info)
        self.baseline_chart = CurveChart()
        self.baseline_chart.setMinimumHeight(160)
        self.baseline_chart.setMaximumHeight(190)
        box.addWidget(self.baseline_chart)
        import_row = QHBoxLayout()
        import_row.setSpacing(10)
        import_label = self._text("ab.baselineImport", "smallMuted")
        import_label.setWordWrap(False)
        self.import_btn = self._button("ab.chooseFile")
        self.import_btn.setMinimumWidth(110)
        self.import_btn.clicked.connect(self._import_baseline)
        import_row.addWidget(import_label)
        import_row.addWidget(self.import_btn)
        import_row.addStretch(1)
        box.addLayout(import_row)

        box.addWidget(self._text("ab.section3", "h2"))
        start_row = QHBoxLayout()
        start_row.setSpacing(12)
        trials_label = self._text("ab.trialsLabel", "smallMuted")
        trials_label.setWordWrap(False)
        self.trials_combo = QComboBox()
        self.trials_combo.setMinimumWidth(220)
        for value in (12, 24, 36):
            self.trials_combo.addItem(self.i18n.t(f"ab.trial{value}"), value)
        self.trials_combo.setCurrentIndex(1)
        self.start_btn = self._button("ab.startButton", "primary")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setMinimumWidth(160)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start_session)
        start_row.addWidget(trials_label)
        start_row.addWidget(self.trials_combo)
        start_row.addStretch(1)
        start_row.addWidget(self.start_btn)
        box.addLayout(start_row)

        self.start_status = QLabel()
        self.start_status.setObjectName("smallMuted")
        self.start_status.setWordWrap(True)
        box.addWidget(self.start_status)

        box.addStretch(1)
        box.addWidget(self._text("ab.footer", "footer"))
        return centered_scroll(body)

    # ------------------------------------------------------------------
    # session view
    # ------------------------------------------------------------------
    def _build_session(self) -> QScrollArea:
        body = QWidget()
        outer = QVBoxLayout(body)
        outer.setContentsMargins(46, 26, 46, 26)
        outer.setSpacing(0)
        outer.addStretch(1)

        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(800)
        card.setMaximumWidth(880)
        outer.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)

        box = QVBoxLayout(card)
        box.setContentsMargins(28, 24, 28, 26)
        box.setSpacing(14)

        top = QHBoxLayout()
        badge = self._text("ab.badge", "earBadge")
        self.trial_count = QLabel()
        self.trial_count.setObjectName("smallMuted")
        top.addWidget(badge)
        top.addStretch(1)
        top.addWidget(self.trial_count)
        box.addLayout(top)

        self.trial_progress = QProgressBar()
        self.trial_progress.setObjectName("progressLine")
        self.trial_progress.setRange(0, 24)
        self.trial_progress.setTextVisible(False)
        self.trial_progress.setFixedHeight(6)
        box.addWidget(self.trial_progress)

        self.session_status = QLabel()
        self.session_status.setObjectName("muted")
        self.session_status.setWordWrap(True)
        self.session_status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.session_status.setMinimumHeight(24)
        box.addWidget(self.session_status)

        play_row = QHBoxLayout()
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("ghost")
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.setMinimumWidth(120)
        self.play_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.play_btn.clicked.connect(self._toggle_play)
        play_row.addStretch(1)
        play_row.addWidget(self.play_btn)
        play_row.addStretch(1)
        box.addLayout(play_row)

        listen_row = QHBoxLayout()
        listen_row.setSpacing(12)
        self.listen1 = self._button("ab.listen1", "listenBtn")
        self.listen2 = self._button("ab.listen2", "listenBtn")
        for button in (self.listen1, self.listen2):
            button.setCheckable(True)
            button.setMinimumWidth(140)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.listen1.clicked.connect(lambda _checked=False: self._listen_to(1))
        self.listen2.clicked.connect(lambda _checked=False: self._listen_to(2))
        listen_row.addStretch(1)
        listen_row.addWidget(self.listen1)
        listen_row.addWidget(self.listen2)
        listen_row.addStretch(1)
        box.addLayout(listen_row)

        self.listen_status = QLabel()
        self.listen_status.setObjectName("smallMuted")
        self.listen_status.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.listen_status.setWordWrap(True)
        box.addWidget(self.listen_status)

        vote_row = QGridLayout()
        vote_row.setHorizontalSpacing(10)
        vote_row.setVerticalSpacing(10)
        self.vote1 = self._button("ab.vote1", "primary")
        self.vote2 = self._button("ab.vote2", "primary")
        self.same_btn = self._button("ab.same")
        for button, choice in ((self.vote1, 1), (self.vote2, 2), (self.same_btn, "skip")):
            button.setMinimumHeight(44)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            button.clicked.connect(lambda _checked=False, c=choice: self._vote(c))
        vote_row.addWidget(self.vote1, 0, 0)
        vote_row.addWidget(self.vote2, 0, 1)
        vote_row.addWidget(self.same_btn, 1, 0, 1, 2)
        vote_row.setColumnStretch(0, 1)
        vote_row.setColumnStretch(1, 1)
        box.addLayout(vote_row)

        help_label = self._text("ab.help", "smallMuted")
        help_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(help_label)
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

        box.addWidget(self._text("ab.resultsTitle", "pageTitle"))
        self.final_summary = QLabel()
        self.final_summary.setObjectName("muted")
        self.final_summary.setWordWrap(True)
        box.addWidget(self.final_summary)

        chart_card = QFrame()
        chart_card.setObjectName("card")
        chart_box = QVBoxLayout(chart_card)
        chart_box.setContentsMargins(20, 18, 20, 18)
        chart_box.setSpacing(10)
        self.final_chart = CurveChart()
        chart_box.addWidget(self.final_chart)
        chart_box.addWidget(self._text("ab.resultsNote", "smallMuted"))
        box.addWidget(chart_card)

        detail_card = QFrame()
        detail_card.setObjectName("card")
        detail_box = QVBoxLayout(detail_card)
        detail_box.setContentsMargins(20, 18, 20, 18)
        detail_box.setSpacing(10)
        detail_box.addWidget(self._text("ab.detailTitle", "h2"))
        self.table = QTableWidget(10, 4)
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
        box.addWidget(detail_card)

        apply_card = QFrame()
        apply_card.setObjectName("card")
        apply_box = QVBoxLayout(apply_card)
        apply_box.setContentsMargins(20, 18, 20, 18)
        apply_box.setSpacing(12)
        apply_box.addWidget(self._text("ab.applyTitle", "h2"))
        export_row = QHBoxLayout()
        export_row.setSpacing(10)
        self.export_btn = self._button("ab.export", "primary")
        self.again_btn = self._button("ab.again")
        self.export_btn.clicked.connect(self._export)
        self.again_btn.clicked.connect(self._again)
        export_row.addWidget(self.export_btn)
        export_row.addWidget(self.again_btn)
        export_row.addStretch(1)
        apply_box.addLayout(export_row)
        self.export_status = QLabel()
        self.export_status.setObjectName("smallMuted")
        self.export_status.setWordWrap(True)
        self.export_status.setVisible(False)
        apply_box.addWidget(self.export_status)
        apply_box.addWidget(self._text("ab.applyNote", "smallMuted"))
        apply_box.addWidget(self._text("ab.phoneNote", "warnNotice"))
        box.addWidget(apply_card)

        box.addStretch(1)
        box.addWidget(self._text("ab.footer", "footer"))
        return centered_scroll(body)

    # ------------------------------------------------------------------
    # baseline
    # ------------------------------------------------------------------
    def _read_json(self, path: Path) -> object | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _saved_at(data: dict) -> datetime:
        raw = data.get("savedAt")
        if isinstance(raw, str):
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError:
                parsed = None
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
        return datetime.min.replace(tzinfo=timezone.utc)

    def _load_baseline(self) -> Curve:
        candidates: list[tuple[datetime, Curve]] = []
        for path in (self._hearing_result_path, self._tuning_result_path):
            data = self._read_json(path)
            if not isinstance(data, dict) or not isinstance(data.get("curve"), dict):
                continue
            try:
                curve = from_driver_json(data["curve"])
            except ValueError:
                continue
            if len(curve.bands) != len(BANDS):
                continue
            candidates.append((self._saved_at(data), curve))
        if not candidates:
            return flat_curve()
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]

    def _refresh_baseline(self, reload: bool = False) -> None:
        if reload and not self._baseline_imported:
            self.baseline = self._load_baseline()
        count = nonzero_bands(self.baseline)
        if count:
            self.baseline_info.setText(
                self.i18n.t("ab.baselineLoaded", n=count, db=self.baseline.main_gain)
            )
        else:
            self.baseline_info.setText(self.i18n.t("ab.baselineFlat"))
        self.baseline_chart.set_curve(self.baseline)

    def _import_baseline(self) -> None:
        initial = self._last_folder or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.i18n.t("ab.selectJsonTitle"),
            initial,
            self.i18n.t("ab.importFilter"),
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            curve = from_driver_json(data)
            if len(curve.bands) != len(BANDS):
                raise ValueError(self.i18n.t("ab.importCount"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._set_status(
                self.start_status, "ab.importFail", "err", msg=str(exc)
            )
            return
        self.baseline = curve
        self._baseline_imported = True
        self._last_folder = str(Path(path).parent)
        self._refresh_baseline(reload=False)
        self._set_status(self.start_status, "ab.imported", "ok")

    # ------------------------------------------------------------------
    # tracks
    # ------------------------------------------------------------------
    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            self.i18n.t("ab.selectFolderTitle"),
            self._last_folder or str(Path.home()),
        )
        if not folder:
            return
        self._last_folder = folder
        self._load_tracks(Path(folder))

    def _load_builtin(self) -> None:
        folder = builtin_tracks_dir()
        try:
            files = sorted(
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() == ".mp3"
            )
        except OSError:
            files = []
        if not files:
            self._set_status(self.load_status, "ab.builtinMissing", "err")
            return
        self._load_files(files, "ab.builtinLoaded", shuffle=False)

    def _load_tracks(self, folder: Path) -> None:
        try:
            files = [
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
        except OSError as exc:
            self._set_status(self.load_status, text=str(exc), kind="err")
            return
        if not files:
            self._set_status(self.load_status, "ab.noAudio", "err")
            self.tracks = []
            self.start_btn.setEnabled(False)
            return
        self._set_status(
            self.load_status,
            text=self.i18n.t("ab.folderSelected", folder=folder.name),
        )
        self._load_files(files, "ab.loaded", shuffle=True)

    def _load_files(
        self, files: list[Path], done_key: str, shuffle: bool = True
    ) -> None:
        if shuffle:
            self._rng.shuffle(files)
        files = files[:8]
        self.folder_btn.setEnabled(False)
        self.builtin_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.tracks = []
        self._pump()
        for index, path in enumerate(files):
            self._set_status(
                self.load_status,
                "ab.decoding",
                i=index + 1,
                total=len(files),
                name=path.name,
            )
            self._pump()
            excerpt = load_excerpt(path, rng=self._rng)
            if excerpt is not None:
                self.tracks.append(excerpt)
        self.folder_btn.setEnabled(True)
        self.builtin_btn.setEnabled(True)
        if not self.tracks:
            self._set_status(self.load_status, "ab.decodeFail", "err")
            return
        self._set_status(self.load_status, done_key, "ok", n=len(self.tracks))
        self.start_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # session
    # ------------------------------------------------------------------
    def _start_session(self) -> None:
        if not self.tracks:
            self._set_status(self.start_status, "ab.needFolder", "err")
            return
        try:
            self.player.open_output()
        except AudioUnavailable as exc:
            self._set_status(self.start_status, "ab.audioError", "err", msg=str(exc))
            return
        trials = int(self.trials_combo.currentData() or 24)
        self.session = TuningSession(
            baseline=clone_curve(self.baseline),
            best=clone_curve(self.baseline),
            trials=trials,
        )
        self.pending = None
        self.pending_buffers = None
        self._baseline_imported = False
        self._session_active = True
        self._accepting_votes = False
        self._rendering = False
        self._render_token += 1
        self._set_dirty(True)
        self.start_status.clear()
        self.views.setCurrentWidget(self.session_scroll)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_hud()
        self.next_trial()

    def next_trial(self) -> None:
        if not self._session_active or self.session is None:
            return
        if self.session.done >= self.session.trials:
            self._show_results()
            return
        plan = self.session.next_plan(self._rng)
        if plan is None:
            self._show_results()
            return
        track = self._rng.choice(self.tracks)
        max_start = max(0.0, track.duration - CLIP_SECONDS - 0.05)
        start = self._rng.random() * max_start
        self.pending = plan
        self.pending_buffers = None
        self._rendering = True
        self._accepting_votes = False
        self._set_controls_enabled(False)
        self._set_status(self.session_status, "ab.preparing")
        self.listen_status.clear()
        self._update_play_button()
        self._update_listen_ui()
        self._render_token += 1
        token = self._render_token
        self._pump()
        QTimer.singleShot(
            20, lambda: self._render_trial(token, plan, track, start)
        )

    def _render_trial(
        self, token: int, plan: TrialPlan, track: Excerpt, start: float
    ) -> None:
        if token != self._render_token or not self._session_active or self.session is None:
            return
        try:
            best_buffer = render_variant(track, self.session.best, start)
            cand_buffer = render_variant(track, plan.candidate, start)
            gain_best, gain_cand = normalize_pair(best_buffer, cand_buffer)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            self._rendering = False
            self._set_status(
                self.session_status, "ab.processFail", "err", msg=str(exc)
            )
            QMessageBox.critical(
                self,
                self.i18n.t("ab.tag"),
                self.i18n.t("ab.processFail", msg=str(exc)),
            )
            self._go_back(False)
            return
        self.pending_buffers = (best_buffer, cand_buffer)
        self.pending_gains = (gain_best, gain_cand)
        self._rendering = False
        self._accepting_votes = True
        self._set_controls_enabled(True)
        if self._play_pending(1):
            self._set_status(self.session_status, "ab.listening", n=1)
        self._update_hud()

    def _play_pending(self, active: int = 1) -> bool:
        if self.pending is None or self.pending_buffers is None:
            return False
        best_buffer, cand_buffer = self.pending_buffers
        gain_best, gain_cand = self.pending_gains
        mapping = self.pending.mapping
        first_buffer = best_buffer if mapping[1] == "best" else cand_buffer
        first_gain = gain_best if mapping[1] == "best" else gain_cand
        second_buffer = best_buffer if mapping[2] == "best" else cand_buffer
        second_gain = gain_best if mapping[2] == "best" else gain_cand
        try:
            self.player.play(
                first_buffer,
                first_gain,
                second_buffer,
                second_gain,
                active=active,
            )
        except AudioUnavailable as exc:
            self._set_status(
                self.session_status, "ab.audioError", "err", msg=str(exc)
            )
            return False
        self.active = 1 if active == 1 else 2
        self._was_playing = True
        self._end_timer.start()
        self._update_play_button()
        self._update_listen_ui()
        return True

    def _toggle_play(self) -> None:
        if self.pending is None:
            return
        if self._was_playing and self.player.is_playing():
            self.player.stop()
            self._was_playing = False
            self._end_timer.stop()
            self._set_status(self.session_status, "ab.paused")
        elif self._play_pending(self.active):
            self._set_status(self.session_status, "ab.listening", n=self.active)
        self._update_play_button()
        self._update_listen_ui()

    def _listen_to(self, which: int) -> None:
        if self.pending is None or not self._accepting_votes:
            return
        if not (self._was_playing and self.player.is_playing()):
            if not self._play_pending(which):
                return
        else:
            self.player.switch_to(which)
        self.active = 1 if which == 1 else 2
        self._was_playing = True
        self._set_status(self.session_status, "ab.listening", n=self.active)
        self._update_listen_ui()

    def _poll_playback(self) -> None:
        if not self._was_playing:
            return
        if self.player.is_playing():
            return
        self._was_playing = False
        self._end_timer.stop()
        if self.pending is not None:
            self._set_status(self.session_status, "ab.pausedOrEnded")
        self._update_play_button()
        self._update_listen_ui()

    def _vote(self, choice: int | str) -> None:
        if not self._accepting_votes or self.pending is None or self.session is None:
            return
        plan = self.pending
        self.player.stop()
        self._end_timer.stop()
        self._was_playing = False
        self._accepting_votes = False
        self._set_controls_enabled(False)
        finished = self.session.record(choice, plan)
        self.pending = None
        self.pending_buffers = None
        self.listen_status.clear()
        self._update_hud()
        if finished:
            self._show_results()
        else:
            self.next_trial()

    def _update_hud(self) -> None:
        if self.session is None:
            return
        self.trial_count.setText(
            self.i18n.t(
                "ab.trialCount",
                n=min(self.session.done + 1, self.session.trials),
                total=self.session.trials,
            )
        )
        self.trial_progress.setRange(0, self.session.trials)
        self.trial_progress.setValue(self.session.done)

    def _update_play_button(self) -> None:
        self.play_btn.setText(
            self.i18n.t(
                "ab.pause"
                if self._was_playing and self.player.is_playing()
                else "ab.play"
            )
        )

    def _update_listen_ui(self) -> None:
        live = self._was_playing and self.player.is_playing()
        self.listen1.setChecked(live and self.active == 1)
        self.listen2.setChecked(live and self.active == 2)
        if live:
            self.listen_status.setText(
                self.i18n.t("ab.listenStatus", n=self.active)
            )
        elif self._rendering:
            self.listen_status.clear()
        elif self.pending is not None:
            self.listen_status.setText(self.i18n.t("ab.pausedOrEnded"))
        else:
            self.listen_status.clear()

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in (
            self.play_btn,
            self.listen1,
            self.listen2,
            self.vote1,
            self.vote2,
            self.same_btn,
        ):
            button.setEnabled(enabled)

    # ------------------------------------------------------------------
    # results
    # ------------------------------------------------------------------
    def _show_results(self) -> None:
        if self.session is None:
            return
        self.player.stop()
        self._end_timer.stop()
        self._was_playing = False
        self.pending = None
        self.pending_buffers = None
        self._accepting_votes = False
        self._session_active = False
        self._render_token += 1
        self.session.best.name = CURVE_FINAL
        self.views.setCurrentWidget(self.results_scroll)
        self.results_scroll.verticalScrollBar().setValue(0)
        self._render_results()
        self._save_result()

    def _render_results(self) -> None:
        if self.session is None:
            return
        self.final_chart.set_series(
            [
                {"curve": self.session.baseline, "role": "baseline"},
                {"curve": self.session.best, "role": "accent"},
            ]
        )
        self.final_summary.setText(
            self.i18n.t("ab.summary", n=self.session.trials)
        )
        self.table.setHorizontalHeaderLabels(
            [
                self.i18n.t("ab.thFreq"),
                self.i18n.t("ab.thInitial"),
                self.i18n.t("ab.thFinal"),
                self.i18n.t("ab.thChange"),
            ]
        )
        positive = QColor("#7ee2a8") if self._theme == "dark" else QColor("#1a7f4b")
        negative = QColor("#f0a6b4") if self._theme == "dark" else QColor("#a3283d")
        baseline_gains = {band.freq: band.gain for band in self.session.baseline.bands}
        for row, band in enumerate(self.session.best.bands):
            initial = baseline_gains.get(band.freq, 0.0)
            change = signed(band.gain - initial)
            cells = [
                f"{freq_label(band.freq)} Hz",
                signed(initial),
                signed(band.gain),
                change,
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 3:
                    if band.gain > initial:
                        item.setForeground(positive)
                    elif band.gain < initial:
                        item.setForeground(negative)
                self.table.setItem(row, column, item)

    def _save_result(self) -> None:
        if self.session is None:
            return
        payload = {
            "savedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "curve": to_driver_json(self.session.best),
        }
        try:
            self._tuning_result_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._tuning_result_path.with_name(
                self._tuning_result_path.name + ".tmp"
            )
            temp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temp.replace(self._tuning_result_path)
        except OSError:
            pass

    def _export(self) -> None:
        if self.session is None:
            return
        initial = (
            str(Path(self._last_export_dir) / "darkrim-eq-final.json")
            if self._last_export_dir
            else str(Path.home() / "darkrim-eq-final.json")
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.i18n.t("ab.exportTitle"),
            initial,
            self.i18n.t("ab.importFilter"),
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        self.session.best.name = CURVE_FINAL
        try:
            Path(path).write_text(
                json.dumps(
                    to_driver_json(self.session.best), ensure_ascii=False, indent=4
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            self.export_status.setText(
                self.i18n.t("ab.exportFail", msg=str(exc))
            )
            self.export_status.setVisible(True)
            return
        self._last_export_dir = str(Path(path).parent)
        self.export_status.setText(self.i18n.t("ab.exportDone", path=path))
        self.export_status.setVisible(True)

    def _again(self) -> None:
        if self.session is None:
            return
        self.session.again(self._rng)
        self.pending = None
        self.pending_buffers = None
        self._accepting_votes = False
        self._session_active = True
        self._render_token += 1
        self._set_dirty(True)
        self.views.setCurrentWidget(self.session_scroll)
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_hud()
        self.next_trial()

    # ------------------------------------------------------------------
    # navigation / lifecycle
    # ------------------------------------------------------------------
    def _go_back(self, confirm: bool = True) -> None:
        if (
            confirm
            and self._session_active
            and self.views.currentWidget() is self.session_scroll
        ):
            was_rendering = self._rendering
            if was_rendering:
                self._render_token += 1
                self._rendering = False
            was_playing = self.player.is_playing()
            if was_playing:
                self.player.stop()
                self._end_timer.stop()
                self._was_playing = False
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(self.i18n.t("exit.title"))
            box.setText(self.i18n.t("exit.body"))
            cancel = box.addButton(
                self.i18n.t("exit.cancel"), QMessageBox.ButtonRole.RejectRole
            )
            proceed = box.addButton(
                self.i18n.t("exit.confirm"), QMessageBox.ButtonRole.DestructiveRole
            )
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not proceed:
                if was_rendering:
                    self.next_trial()
                elif (
                    was_playing
                    and self.pending is not None
                    and self.pending_buffers is not None
                ):
                    if self._play_pending(self.active):
                        self._set_status(
                            self.session_status, "ab.listening", n=self.active
                        )
                return
        self._render_token += 1
        self._session_active = False
        self._accepting_votes = False
        self._rendering = False
        self.player.stop()
        self.player.shutdown()
        self._end_timer.stop()
        self._was_playing = False
        self.pending = None
        self.pending_buffers = None
        self._set_dirty(False)
        had_session = self.session is not None
        if had_session:
            self._baseline_imported = False
        self.views.setCurrentWidget(self.prepare_scroll)
        self.prepare_scroll.verticalScrollBar().setValue(0)
        self._refresh_baseline(reload=True)
        self.start_status.clear()
        self._update_load_status()
        self.session = None
        self.back_requested.emit()

    def _update_load_status(self) -> None:
        if self.tracks:
            self._set_status(self.load_status, "ab.loaded", "ok", n=len(self.tracks))
            self.start_btn.setEnabled(True)
        else:
            self._set_status(self.load_status, "ab.folderHint")
            self.start_btn.setEnabled(False)

    def on_shown(self) -> None:
        if self.views.currentWidget() is not self.prepare_scroll:
            return
        if not self._baseline_imported:
            self._refresh_baseline(reload=True)
        self._update_load_status()

    def suspend_audio(self) -> None:
        self._resume_render_after_dialog = self._rendering
        if self._rendering:
            self._render_token += 1
            self._rendering = False
        self._resume_after_dialog = self.player.is_playing()
        if self._resume_after_dialog:
            self.player.stop()
        self._end_timer.stop()
        self._was_playing = False

    def resume_audio(self) -> None:
        if self._resume_render_after_dialog:
            self._resume_render_after_dialog = False
            if self.views.currentWidget() is self.session_scroll:
                self.next_trial()
            return
        if (
            self._resume_after_dialog
            and self.pending is not None
            and self.pending_buffers is not None
            and self.views.currentWidget() is self.session_scroll
        ):
            if self._play_pending(self.active):
                self._set_status(self.session_status, "ab.listening", n=self.active)
        self._resume_after_dialog = False

    def shutdown(self) -> None:
        self.player.shutdown()

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

    def set_theme(self, theme: str) -> None:
        self._theme = "light" if theme == "light" else "dark"
        self.baseline_chart.set_theme(self._theme)
        self.final_chart.set_theme(self._theme)
        if self.views.currentWidget() is self.results_scroll and self.session is not None:
            self._render_results()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if (
            self._session_active
            and self.views.currentWidget() is self.session_scroll
            and self._accepting_votes
        ):
            if event.key() == Qt.Key.Key_Space:
                self._listen_to(2 if self.active == 1 else 1)
                event.accept()
                return
            if event.key() == Qt.Key.Key_1:
                self._vote(1)
                event.accept()
                return
            if event.key() == Qt.Key.Key_2:
                self._vote(2)
                event.accept()
                return
            if event.key() == Qt.Key.Key_0:
                self._vote("skip")
                event.accept()
                return
        super().keyPressEvent(event)

    def retranslate(self, i18n: I18n) -> None:
        self.i18n = i18n
        self.brand.setText(i18n.t("app.name"))
        self.tag.setText(i18n.t("ab.tag"))
        self.back_btn.setText(i18n.t("back"))
        for label, key in self._static_labels:
            label.setText(i18n.t(key))
        for button, key in self._static_buttons:
            button.setText(i18n.t(key))
        for index, value in enumerate((12, 24, 36)):
            self.trials_combo.setItemText(index, i18n.t(f"ab.trial{value}"))
        self._refresh_baseline(reload=False)
        self._update_load_status()
        self.start_status.clear()
        self.export_status.setVisible(False)
        if self.views.currentWidget() is self.session_scroll:
            self._update_hud()
            self._update_play_button()
            self._update_listen_ui()
            if self._rendering:
                self._set_status(self.session_status, "ab.preparing")
            elif self.pending is not None and self._was_playing:
                self._set_status(self.session_status, "ab.listening", n=self.active)
            elif self.pending is not None:
                self._set_status(self.session_status, "ab.pausedOrEnded")
        elif self.views.currentWidget() is self.results_scroll:
            self._render_results()
