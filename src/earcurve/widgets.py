"""Small reusable widgets (frequency-response chart)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from .core.eq import Curve, clamp, curve_response_db

_F_MIN = 20.0
_F_MAX = 20000.0


def scroll_area(body: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    body.setObjectName("scrollBody")
    area.setWidget(body)
    return area


class CenteredBody(QWidget):
    def __init__(self, inner: QWidget, max_width: int = 860) -> None:
        super().__init__()
        self._inner = inner
        self._max_width = max_width
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(inner)
        row.addStretch(1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        width = min(self.width(), self._max_width)
        self._inner.setMinimumWidth(width)
        self._inner.setMaximumWidth(width)
        super().resizeEvent(event)


def centered_scroll(body: QWidget, max_width: int = 860) -> QScrollArea:
    return scroll_area(CenteredBody(body, max_width))


class CurveChart(QWidget):
    """Log-frequency response chart for a 10-band curve."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._series: list[dict] = []
        self._theme = "dark"
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_curve(self, curve: Curve | None) -> None:
        self.set_series(
            [{"curve": curve, "role": "accent"}] if curve is not None else []
        )

    def set_series(self, series: list[dict]) -> None:
        self._series = [item for item in series if item.get("curve") is not None]
        self.update()

    def set_theme(self, theme: str) -> None:
        self._theme = "light" if theme == "light" else "dark"
        self.update()

    # -- painting -------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        height = self.height()
        pad_l, pad_r, pad_t, pad_b = 46, 16, 16, 30
        plot_w = max(10.0, width - pad_l - pad_r)
        plot_h = max(10.0, height - pad_t - pad_b)

        if self._theme == "light":
            grid = QColor(23, 21, 31, 20)
            text = QColor(23, 21, 31, 125)
            zero_line = QColor(23, 21, 31, 55)
            accent = QColor("#6d3fd6")
            baseline_color = QColor(23, 21, 31, 115)
        else:
            grid = QColor(255, 255, 255, 22)
            text = QColor(255, 255, 255, 112)
            zero_line = QColor(255, 255, 255, 55)
            accent = QColor("#a78bfa")
            baseline_color = QColor(255, 255, 255, 135)

        def x_of(freq: float) -> float:
            ratio = math.log(freq / _F_MIN) / math.log(_F_MAX / _F_MIN)
            return pad_l + ratio * plot_w

        def y_of(db: float) -> float:
            return pad_t + (1.0 - (db + 12.0) / 24.0) * plot_h

        font = QFont(self.font())
        font.setPointSizeF(8.5)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        painter.setPen(QPen(grid, 1))
        last_label_right = -100.0
        for freq in (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
            x = x_of(freq)
            painter.drawLine(QPointF(x, pad_t), QPointF(x, pad_t + plot_h))
            label = f"{freq // 1000}k" if freq >= 1000 else str(freq)
            label_w = metrics.horizontalAdvance(label)
            if x - label_w / 2 > last_label_right + 6 and x + label_w / 2 < width - 2:
                painter.setPen(text)
                painter.drawText(
                    QRectF(x - label_w / 2, height - 21, label_w, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
                last_label_right = x + label_w / 2
                painter.setPen(QPen(grid, 1))

        for db in (12, 6, 0, -6, -12):
            y = y_of(db)
            painter.drawLine(QPointF(pad_l, y), QPointF(pad_l + plot_w, y))
            label = f"+{db}" if db > 0 else str(db)
            painter.setPen(text)
            painter.drawText(
                QRectF(0, y - 8, pad_l - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            painter.setPen(QPen(grid, 1))

        painter.setPen(QPen(zero_line, 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(pad_l, y_of(0)), QPointF(pad_l + plot_w, y_of(0)))

        steps = 260
        for series in self._series:
            curve: Curve = series["curve"]
            role = series.get("role", "accent")
            color = QColor(series["color"]) if series.get("color") else QColor(
                baseline_color if role == "baseline" else accent
            )
            width = float(series.get("width", 1.6 if role == "baseline" else 2.4))
            dashed = bool(series.get("dash", role == "baseline"))
            draw_dots = bool(series.get("dots", role != "baseline"))
            fill_shape = bool(series.get("fill", role != "baseline"))

            points: list[QPointF] = []
            for index in range(steps + 1):
                freq = _F_MIN * ((_F_MAX / _F_MIN) ** (index / steps))
                db = clamp(curve_response_db(curve, freq), -12.0, 12.0)
                points.append(QPointF(x_of(freq), y_of(db)))

            path = QPainterPath(points[0])
            for point in points[1:]:
                path.lineTo(point)

            if fill_shape:
                fill = QPainterPath(path)
                fill.lineTo(points[-1].x(), y_of(0))
                fill.lineTo(points[0].x(), y_of(0))
                fill.closeSubpath()
                gradient = QLinearGradient(0, pad_t, 0, pad_t + plot_h)
                top = QColor(color)
                top.setAlpha(54)
                bottom = QColor(color)
                bottom.setAlpha(0)
                gradient.setColorAt(0.0, top)
                gradient.setColorAt(1.0, bottom)
                painter.fillPath(fill, gradient)

            pen = QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
                pen.setDashPattern([5, 5])
            painter.setPen(pen)
            painter.drawPath(path)

            if draw_dots:
                painter.setPen(QPen(color, 1.2))
                painter.setBrush(QColor(color))
                for band in curve.bands:
                    db = clamp(curve_response_db(curve, band.freq), -12.0, 12.0)
                    painter.drawEllipse(QPointF(x_of(band.freq), y_of(db)), 3.2, 3.2)
                painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.end()
