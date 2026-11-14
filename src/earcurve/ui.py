"""Skeleton pages for the EarCurve desktop app."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QSize,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .i18n import I18n
from .paths import asset


def _fade_in(widget: QWidget, duration_ms: int = 650) -> QPropertyAnimation:
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    return anim


class GradientTitle(QWidget):
    """Large display title with a vertical gradient, like the web intro."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._theme = "dark"
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(text)
        font = QFont("Microsoft YaHei UI")
        font.setPixelSize(62)
        font.setWeight(QFont.Weight.Medium)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        self._font = font

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.setAccessibleName(text)
        self.update()

    def set_theme(self, theme: str) -> None:
        self._theme = "light" if theme == "light" else "dark"
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        metrics = QFontMetrics(self._font)
        return QSize(max(320, metrics.horizontalAdvance(self._text) + 80), 90)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(self._font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self._text)
        x = (self.width() - text_width) / 2.0
        baseline = (self.height() - metrics.height()) / 2.0 + metrics.ascent()
        path = QPainterPath()
        path.addText(QPointF(x, baseline), self._font, self._text)
        gradient = QLinearGradient(
            0,
            baseline - metrics.ascent(),
            0,
            baseline + metrics.descent(),
        )
        if self._theme == "light":
            gradient.setColorAt(0.0, QColor("#1b1826"))
            gradient.setColorAt(0.24, QColor("#1b1826"))
            gradient.setColorAt(1.0, QColor("#5b3bbd"))
        else:
            gradient.setColorAt(0.0, QColor("#ffffff"))
            gradient.setColorAt(0.28, QColor("#ffffff"))
            gradient.setColorAt(1.0, QColor("#b7a6ff"))
        painter.fillPath(path, QBrush(gradient))
        painter.end()


class PrefsBar(QWidget):
    theme_selected = Signal(str)
    language_toggled = Signal()

    def __init__(self, i18n: I18n, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        self.theme_label = QLabel(i18n.t("prefs.theme"))
        row.addWidget(self.theme_label)

        self.dark_btn = QPushButton()
        self.dark_btn.setObjectName("dotDark")
        self.dark_btn.setCheckable(True)
        self.dark_btn.setFixedSize(22, 22)
        self.dark_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        row.addWidget(self.dark_btn)

        self.light_btn = QPushButton()
        self.light_btn.setObjectName("dotLight")
        self.light_btn.setCheckable(True)
        self.light_btn.setFixedSize(22, 22)
        self.light_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        row.addWidget(self.light_btn)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.addButton(self.dark_btn)
        self.group.addButton(self.light_btn)

        self.lang_btn = QPushButton("简体中文/English")
        self.lang_btn.setObjectName("langBtn")
        self.lang_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        row.addWidget(self.lang_btn)

        self.dark_btn.clicked.connect(lambda: self.theme_selected.emit("dark"))
        self.light_btn.clicked.connect(lambda: self.theme_selected.emit("light"))
        self.lang_btn.clicked.connect(self.language_toggled.emit)

    def sync(self, theme: str) -> None:
        (self.dark_btn if theme == "dark" else self.light_btn).setChecked(True)

    def retranslate(self, i18n: I18n) -> None:
        self.theme_label.setText(i18n.t("prefs.theme"))


class ToolCard(QFrame):
    clicked = Signal()

    def __init__(
        self,
        title: str,
        body: str,
        step: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toolCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(172)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 22)
        layout.setSpacing(8)
        if step:
            step_label = QLabel(step)
            step_label.setObjectName("step")
            step_font = QFont("Microsoft YaHei UI")
            step_font.setPixelSize(10)
            step_font.setWeight(QFont.Weight.DemiBold)
            step_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
            step_label.setFont(step_font)
            layout.addWidget(step_label)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("", 12, QFont.Weight.DemiBold))
        self.body_label = QLabel(body)
        self.body_label.setObjectName("muted")
        self.body_label.setWordWrap(True)
        self.body_label.setMinimumHeight(44)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addStretch(1)

    def set_texts(self, title: str, body: str) -> None:
        self.title_label.setText(title)
        self.body_label.setText(body)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def topbar(i18n: I18n) -> tuple[QFrame, QLabel, QLabel]:
    bar = QFrame()
    bar.setObjectName("topbar")
    row = QHBoxLayout(bar)
    row.setContentsMargins(22, 10, 22, 10)
    row.setSpacing(10)

    icon = QLabel()
    icon.setPixmap(QPixmap(asset("icon-32.png")).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    row.addWidget(icon)
    brand = QLabel(i18n.t("app.name"))
    brand.setObjectName("brand")
    row.addWidget(brand)
    tag = QLabel(i18n.t("app.tag"))
    tag.setObjectName("tag")
    row.addWidget(tag)
    row.addStretch(1)
    return bar, brand, tag


class IntroPage(QWidget):
    started = Signal()
    theme_selected = Signal(str)
    language_toggled = Signal()

    def __init__(self, i18n: I18n, parent: QWidget | None = None, animate: bool = True) -> None:
        super().__init__(parent)
        self.setObjectName("intro")
        self._theme = "dark"
        self._animate = animate
        self._played = False
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 20, 26, 30)
        root.setSpacing(0)

        prefs_row = QHBoxLayout()
        prefs_row.addStretch(1)
        self.prefs = PrefsBar(i18n)
        prefs_row.addWidget(self.prefs)
        root.addLayout(prefs_row)

        root.addStretch(1)

        self.logo_wrap = QWidget()
        self.logo_wrap.setFixedHeight(112)
        self.logo_wrap.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        logo_layout = QVBoxLayout(self.logo_wrap)
        logo_layout.setContentsMargins(10, 6, 10, 6)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setFixedSize(86, 86)
        self.logo.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.logo.setPixmap(QPixmap(asset("icon-256.png")).scaled(86, 86, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo_layout.addStretch(1)
        logo_layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        logo_layout.addStretch(1)
        self._logo_shadow = QGraphicsDropShadowEffect(self.logo)
        self._logo_shadow.setBlurRadius(42)
        self._logo_shadow.setOffset(0, 0)
        self._logo_shadow.setColor(QColor(124, 58, 237, 70))
        self.logo.setGraphicsEffect(self._logo_shadow)
        root.addWidget(self.logo_wrap)
        root.addSpacing(18)

        self.kicker = QLabel(i18n.t("intro.kicker"))
        self.kicker.setObjectName("kicker")
        self.kicker.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        kicker_font = QFont("Microsoft YaHei UI")
        kicker_font.setPixelSize(11)
        kicker_font.setWeight(QFont.Weight.DemiBold)
        kicker_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.2)
        self.kicker.setFont(kicker_font)
        root.addWidget(self.kicker)
        root.addSpacing(6)

        self.title = GradientTitle(i18n.t("app.name"))
        root.addWidget(self.title)

        root.addSpacing(24)
        self.lines = []
        line_font = QFont("Microsoft YaHei UI")
        line_font.setPixelSize(15)
        line_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.1)
        for index, key in enumerate(("intro.line1", "intro.line2", "intro.line3")):
            label = QLabel(i18n.t(key))
            label.setObjectName("line")
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            label.setFont(line_font)
            self.lines.append(label)
            if index:
                root.addSpacing(4)
            root.addWidget(label)

        root.addStretch(1)

        self.start_btn = QPushButton(i18n.t("intro.start"))
        self.start_btn.setObjectName("introStart")
        self.start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_btn.setFixedWidth(200)
        self.start_btn.setFixedHeight(50)
        start_font = QFont("Microsoft YaHei UI")
        start_font.setPixelSize(14)
        start_font.setWeight(QFont.Weight.Medium)
        start_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4.0)
        self.start_btn.setFont(start_font)
        start_row = QHBoxLayout()
        start_row.addStretch(1)
        start_row.addWidget(self.start_btn)
        start_row.addStretch(1)
        root.addLayout(start_row)
        root.addSpacing(14)
        self.unofficial = QLabel(i18n.t("intro.unofficial"))
        self.unofficial.setObjectName("footer")
        self.unofficial.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.unofficial)
        root.addSpacing(14)

        self.start_btn.clicked.connect(self.started.emit)
        self.prefs.theme_selected.connect(self.theme_selected.emit)
        self.prefs.language_toggled.connect(self.language_toggled.emit)

        self._anims: list[QPropertyAnimation] = []
        if animate:
            widgets = [
                self.logo_wrap,
                self.kicker,
                self.title,
                *self.lines,
                self.start_btn,
            ]
            self._anims = [_fade_in(widget, 700) for widget in widgets]

    def play_intro(self) -> None:
        if not self._animate or self._played:
            return
        self._played = True
        delays = (100, 300, 550, 850, 1080, 1310, 1550)
        for anim, delay in zip(self._anims, delays):
            QTimer.singleShot(delay, anim.start)

    def set_theme(self, theme: str) -> None:
        self._theme = "light" if theme == "light" else "dark"
        self.title.set_theme(self._theme)
        if self._theme == "light":
            self._logo_shadow.setColor(QColor(109, 63, 214, 50))
        else:
            self._logo_shadow.setColor(QColor(124, 58, 237, 70))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self._theme == "light":
            grid = QColor(23, 21, 31, 9)
            edge = QColor("#f6f5fa")
            glow_color = QColor(109, 63, 214, 24)
            bottom_glow = QColor(59, 130, 246, 12)
        else:
            grid = QColor(255, 255, 255, 10)
            edge = QColor("#07070b")
            glow_color = QColor(139, 92, 246, 30)
            bottom_glow = QColor(59, 130, 246, 16)
        radius = max(self.width(), self.height())
        glow = QRadialGradient(
            self.width() / 2.0, self.height() * 0.42, radius * 0.52
        )
        glow.setColorAt(0.0, glow_color)
        glow.setColorAt(0.7, QColor(glow_color.red(), glow_color.green(), glow_color.blue(), 0))
        painter.fillRect(self.rect(), glow)
        lower = QRadialGradient(
            self.width() / 2.0, self.height() * 1.08, radius * 0.62
        )
        lower.setColorAt(0.0, bottom_glow)
        lower.setColorAt(0.75, QColor(bottom_glow.red(), bottom_glow.green(), bottom_glow.blue(), 0))
        painter.fillRect(self.rect(), lower)
        painter.setPen(QPen(grid, 1))
        step = 72
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)
        mask = QRadialGradient(
            self.width() / 2.0,
            self.height() * 0.45,
            max(self.width(), self.height()) * 0.72,
        )
        mask.setColorAt(0.0, QColor(edge.red(), edge.green(), edge.blue(), 0))
        mask.setColorAt(0.55, QColor(edge.red(), edge.green(), edge.blue(), 0))
        mask.setColorAt(1.0, QColor(edge.red(), edge.green(), edge.blue(), 235))
        painter.fillRect(self.rect(), mask)
        painter.end()

    def retranslate(self, i18n: I18n) -> None:
        self.title.setText(i18n.t("app.name"))
        self.kicker.setText(i18n.t("intro.kicker"))
        self.lines[0].setText(i18n.t("intro.line1"))
        self.lines[1].setText(i18n.t("intro.line2"))
        self.lines[2].setText(i18n.t("intro.line3"))
        self.start_btn.setText(i18n.t("intro.start"))
        self.unofficial.setText(i18n.t("intro.unofficial"))
        self.prefs.retranslate(i18n)


class HomePage(QWidget):
    tool_selected = Signal(str)

    def __init__(self, i18n: I18n, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar, self.brand, self.tag = topbar(i18n)
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setContentsMargins(46, 30, 46, 20)
        body.setSpacing(14)

        self.eyebrow = QLabel(i18n.t("home.eyebrow"))
        self.eyebrow.setObjectName("kicker")
        eyebrow_font = QFont("Microsoft YaHei UI")
        eyebrow_font.setPixelSize(10)
        eyebrow_font.setWeight(QFont.Weight.DemiBold)
        eyebrow_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.5)
        self.eyebrow.setFont(eyebrow_font)
        body.addWidget(self.eyebrow)

        self.title = QLabel(i18n.t("home.title"))
        self.title.setObjectName("pageTitle")
        body.addWidget(self.title)

        self.intro = QLabel(i18n.t("home.body"))
        self.intro.setObjectName("muted")
        self.intro.setWordWrap(True)
        body.addWidget(self.intro)

        self.notice = QLabel(i18n.t("home.notice"))
        self.notice.setObjectName("warnNotice")
        self.notice.setWordWrap(True)
        body.addWidget(self.notice)

        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card1 = ToolCard(
            i18n.t("card1.title"), i18n.t("card1.body"), step="STEP 01"
        )
        self.card2 = ToolCard(
            i18n.t("card2.title"), i18n.t("card2.body"), step="STEP 02"
        )
        cards.addWidget(self.card1)
        cards.addWidget(self.card2)
        body.addLayout(cards)

        self.flow = QLabel(i18n.t("home.flow"))
        self.flow.setObjectName("smallMuted")
        self.flow.setWordWrap(True)
        body.addWidget(self.flow)
        body.addStretch(1)

        self.footer = QLabel(i18n.t("footer"))
        self.footer.setObjectName("footer")
        self.footer.setWordWrap(True)
        body.addWidget(self.footer)
        root.addLayout(body, 1)

        self.card1.clicked.connect(lambda: self.tool_selected.emit("hearing"))
        self.card2.clicked.connect(lambda: self.tool_selected.emit("tuning"))

    def retranslate(self, i18n: I18n) -> None:
        self.brand.setText(i18n.t("app.name"))
        self.tag.setText(i18n.t("app.tag"))
        self.eyebrow.setText(i18n.t("home.eyebrow"))
        self.title.setText(i18n.t("home.title"))
        self.intro.setText(i18n.t("home.body"))
        self.notice.setText(i18n.t("home.notice"))
        self.flow.setText(i18n.t("home.flow"))
        self.card1.set_texts(i18n.t("card1.title"), i18n.t("card1.body"))
        self.card2.set_texts(i18n.t("card2.title"), i18n.t("card2.body"))
        self.footer.setText(i18n.t("footer"))


class PlaceholderPage(QWidget):
    back_requested = Signal()

    def __init__(self, i18n: I18n, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar, self.brand, self.tag = topbar(i18n)
        self.back_btn = QPushButton(i18n.t("back"))
        self.back_btn.setObjectName("ghost")
        self.back_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        bar.layout().addWidget(self.back_btn)
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setContentsMargins(46, 40, 46, 30)
        body.setSpacing(12)
        self.title = QLabel(i18n.t("placeholder.title"))
        self.title.setObjectName("pageTitle")
        self.body = QLabel(i18n.t("placeholder.body"))
        self.body.setObjectName("muted")
        self.body.setWordWrap(True)
        body.addWidget(self.title)
        body.addWidget(self.body)
        body.addStretch(1)
        root.addLayout(body, 1)

        self.back_btn.clicked.connect(self.back_requested.emit)

    def retranslate(self, i18n: I18n) -> None:
        self.brand.setText(i18n.t("app.name"))
        self.tag.setText(i18n.t("app.tag"))
        self.back_btn.setText(i18n.t("back"))
        self.title.setText(i18n.t("placeholder.title"))
        self.body.setText(i18n.t("placeholder.body"))
