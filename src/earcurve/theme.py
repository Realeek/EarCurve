"""Dark/light Qt stylesheets for the desktop skeleton."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

_COMMON = """
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 14px;
}
QLabel#kicker {
    font-size: 11px;
    font-weight: 600;
}
QLabel#title {
    font-size: 46px;
}
QLabel#pageTitle {
    font-size: 28px;
    font-weight: 600;
}
QLabel#brand {
    font-size: 14px;
    font-weight: 600;
}
QLabel#tag {
    font-size: 11px;
    border-radius: 10px;
    padding: 3px 10px;
}
QLabel#line {
    font-size: 15px;
}
QLabel#muted {
    font-size: 14px;
}
QLabel#footer {
    font-size: 11px;
}
QFrame#card, QFrame#toolCard {
    border-radius: 16px;
}
QFrame#toolCard:hover {
    border-color: #7c5cf0;
}
QFrame#topbar {
    border: none;
    border-bottom-width: 1px;
    border-bottom-style: solid;
}
QPushButton {
    border-radius: 10px;
}
QPushButton#primary {
    border: none;
    border-radius: 12px;
    padding: 12px 36px;
    font-weight: 600;
}
QPushButton#introStart {
    border-radius: 25px;
    padding: 13px 44px;
    font-weight: 500;
}
QLabel#step {
    font-size: 10px;
    font-weight: 600;
}
QPushButton#ghost {
    padding: 8px 16px;
}
QPushButton#langBtn {
    padding: 4px 9px;
    font-size: 11px;
}
QPushButton#dotDark, QPushButton#dotLight {
    border-radius: 11px;
}
QPushButton#dotDark:checked, QPushButton#dotLight:checked {
    border: 2px solid #a78bfa;
}
QScrollArea {
    border: none;
    background: transparent;
}
QWidget#scrollBody {
    background: transparent;
}
QLabel#h2 {
    font-size: 17px;
    font-weight: 600;
}
QLabel#smallMuted {
    font-size: 12px;
}
QLabel#earBadge {
    border-radius: 11px;
    padding: 4px 12px;
    font-weight: 600;
}
QLabel#freqValue {
    font-size: 58px;
    font-weight: 600;
}
QLabel#freqUnit {
    font-size: 18px;
}
QLabel#levelValue, QLabel#kValue {
    font-weight: 600;
}
QFrame#innerCard {
    border-radius: 12px;
}
QLabel#dangerNotice, QLabel#warnNotice {
    border-radius: 10px;
    padding: 12px 14px;
}
QProgressBar#progressLine {
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
}
QProgressBar#progressLine::chunk {
    border-radius: 3px;
}
QSlider::groove:horizontal {
    height: 5px;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QPushButton#dangerGhost {
    padding: 8px 16px;
}
QPushButton#listenBtn {
    padding: 8px 18px;
}
QLabel#statusOk, QLabel#statusErr {
    font-size: 12px;
}
QComboBox {
    padding: 6px 10px;
    border-radius: 8px;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    outline: none;
    padding: 4px;
}
QTableWidget {
    border-radius: 8px;
}
QHeaderView::section {
    border: none;
    padding: 7px 8px;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px;
}
QCheckBox {
    spacing: 10px;
    font-weight: 600;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QMessageBox QPushButton {
    padding: 6px 16px;
    border-radius: 8px;
}
"""

_DARK = """
QWidget {
    color: #ececf2;
}
QWidget#windowRoot {
    background: #0b0b10;
}
QWidget#intro {
    background: qradialgradient(cx:0.5, cy:0.35, radius:0.95, fx:0.5, fy:0.35,
                                stop:0 #1b1430, stop:0.62 #0e0b17, stop:1 #07070b);
}
QLabel#kicker { color: #8b84a8; }
QLabel#title { color: #ffffff; }
QLabel#brand { color: #ececf2; }
QLabel#tag { color: #9a9aab; border: 1px solid #2a2a3a; }
QLabel#line { color: #8f8fa3; }
QLabel#muted { color: #9a9aab; }
QLabel#footer { color: #6f6f80; }
QFrame#card, QFrame#toolCard { background: #17171f; border: 1px solid #26263a; }
QFrame#topbar { background: #0c0c13; border-bottom: 1px solid #26263a; }
QPushButton#primary { background: #7c3aed; color: #ffffff; }
QPushButton#primary:hover { background: #8b5cf6; }
QPushButton#introStart { background: #171225; color: #ece7ff; border: 1px solid #5f4b9f; }
QPushButton#introStart:hover { background: #211a33; border-color: #9b86e6; color: #ffffff; }
QLabel#step { color: #8b7bd6; }
QPushButton#ghost { background: transparent; color: #cfcbe0; border: 1px solid #2e2e42; }
QPushButton#ghost:hover { border-color: #7c5cf0; color: #ffffff; }
QPushButton#langBtn { background: transparent; color: #9a9aab; border: 1px solid #3a3a4e; }
QPushButton#langBtn:hover { border-color: #7c5cf0; color: #ffffff; }
QPushButton#dotDark { background: #0d0d12; border: 1px solid #55556a; }
QPushButton#dotLight { background: #f4f2f9; border: 1px solid #55556a; }
QLabel#h2 { color: #ececf2; }
QLabel#smallMuted { color: #8b8b9e; }
QLabel#earBadge { background: #2a2143; color: #c4b5fd; }
QFrame#innerCard { background: #12121a; border: 1px solid #222236; }
QLabel#dangerNotice { background: #2a141b; border: 1px solid #5a2233; color: #f0a6b4; }
QLabel#warnNotice { background: #282214; border: 1px solid #51401e; color: #e5c07b; }
QProgressBar#progressLine { background: #1d1d2a; }
QProgressBar#progressLine::chunk { background: #7c3aed; }
QSlider::groove:horizontal { background: #26263a; }
QSlider::sub-page:horizontal { background: #7c3aed; }
QSlider::handle:horizontal { background: #f5f3ff; border: 2px solid #7c3aed; }
QPushButton#dangerGhost { background: transparent; color: #f08a9b; border: 1px solid #5a2b38; }
QPushButton#dangerGhost:hover { background: #2a151c; border-color: #f08a9b; color: #ffd0d8; }
QPushButton#listenBtn { background: transparent; color: #cfcbe0; border: 1px solid #2e2e42; }
QPushButton#listenBtn:hover { border-color: #7c5cf0; color: #ffffff; }
QPushButton#listenBtn:checked { background: #7c3aed; color: #ffffff; border-color: #7c3aed; font-weight: 600; }
QLabel#statusOk { color: #7ee2a8; }
QLabel#statusErr { color: #f0a6b4; }
QComboBox { background: #12121a; color: #ececf2; border: 1px solid #2e2e42; }
QComboBox:hover { border-color: #7c5cf0; }
QComboBox QAbstractItemView { background: #17171f; color: #ececf2; border: 1px solid #2e2e42; selection-background-color: #2a2143; selection-color: #ffffff; }
QTableWidget { background: transparent; color: #ececf2; border: 1px solid #26263a; gridline-color: #222232; selection-background-color: #2a2143; selection-color: #ffffff; }
QHeaderView::section { background: #12121a; color: #9a9aab; border-bottom: 1px solid #26263a; }
QCheckBox { color: #ececf2; }
QCheckBox::indicator { background: #12121a; border: 1px solid #3a3a4e; }
QCheckBox::indicator:checked { background: #7c3aed; border-color: #7c3aed; }
QScrollBar::handle:vertical { background: #2e2e42; }
QScrollBar::handle:vertical:hover { background: #454560; }
QMessageBox { background: #17171f; color: #ececf2; }
QMessageBox QPushButton { background: #17171f; color: #ececf2; border: 1px solid #2e2e42; }
QMessageBox QPushButton:hover { border-color: #7c5cf0; }
"""

_LIGHT = """
QWidget {
    color: #17151f;
}
QWidget#windowRoot {
    background: #f6f5fa;
}
QWidget#intro {
    background: qradialgradient(cx:0.5, cy:0.35, radius:0.95, fx:0.5, fy:0.35,
                                stop:0 #efeafc, stop:0.62 #f5f3fb, stop:1 #f6f5fa);
}
QLabel#kicker { color: #6b687c; }
QLabel#title { color: #1b1826; }
QLabel#brand { color: #17151f; }
QLabel#tag { color: #5f5c70; border: 1px solid #d8d2e8; }
QLabel#line { color: #5f5c70; }
QLabel#muted { color: #5f5c70; }
QLabel#footer { color: #8a8798; }
QFrame#card, QFrame#toolCard { background: #ffffff; border: 1px solid #e2dcef; }
QFrame#topbar { background: #fbfaff; border-bottom: 1px solid #e2dcef; }
QPushButton#primary { background: #6d3fd6; color: #ffffff; }
QPushButton#primary:hover { background: #7c4dea; }
QPushButton#introStart { background: #f0ebfb; color: #3f2a7a; border: 1px solid #c9bce9; }
QPushButton#introStart:hover { background: #e8e0fa; border-color: #8d72d9; color: #241a4d; }
QLabel#step { color: #6d3fd6; }
QPushButton#ghost { background: transparent; color: #3f2a7a; border: 1px solid #d8d2e8; }
QPushButton#ghost:hover { border-color: #6d3fd6; color: #241a4d; }
QPushButton#langBtn { background: transparent; color: #5f5c70; border: 1px solid #d8d2e8; }
QPushButton#langBtn:hover { border-color: #6d3fd6; color: #241a4d; }
QPushButton#dotDark { background: #0d0d12; border: 1px solid #b9b2cc; }
QPushButton#dotLight { background: #ffffff; border: 1px solid #b9b2cc; }
QLabel#h2 { color: #1b1826; }
QLabel#smallMuted { color: #7a7688; }
QLabel#earBadge { background: #efe8ff; color: #4c2a9e; }
QFrame#innerCard { background: #ffffff; border: 1px solid #e2dcef; }
QLabel#dangerNotice { background: #fdf0f2; border: 1px solid #f2c9d1; color: #9c2c3e; }
QLabel#warnNotice { background: #fff8e8; border: 1px solid #f0dbae; color: #7a5414; }
QProgressBar#progressLine { background: #e6e1f2; }
QProgressBar#progressLine::chunk { background: #6d3fd6; }
QSlider::groove:horizontal { background: #e2dcef; }
QSlider::sub-page:horizontal { background: #6d3fd6; }
QSlider::handle:horizontal { background: #ffffff; border: 2px solid #6d3fd6; }
QPushButton#dangerGhost { background: transparent; color: #a3283d; border: 1px solid #e7c1c9; }
QPushButton#dangerGhost:hover { background: #fdf0f2; border-color: #a3283d; color: #7d1428; }
QPushButton#listenBtn { background: transparent; color: #3f2a7a; border: 1px solid #d8d2e8; }
QPushButton#listenBtn:hover { border-color: #6d3fd6; color: #241a4d; }
QPushButton#listenBtn:checked { background: #6d3fd6; color: #ffffff; border-color: #6d3fd6; font-weight: 600; }
QLabel#statusOk { color: #1a7f4b; }
QLabel#statusErr { color: #a3283d; }
QComboBox { background: #ffffff; color: #17151f; border: 1px solid #d8d2e8; }
QComboBox:hover { border-color: #6d3fd6; }
QComboBox QAbstractItemView { background: #ffffff; color: #17151f; border: 1px solid #d8d2e8; selection-background-color: #efe8ff; selection-color: #241a4d; }
QTableWidget { background: transparent; color: #17151f; border: 1px solid #e2dcef; gridline-color: #ece7f5; selection-background-color: #efe8ff; selection-color: #241a4d; }
QHeaderView::section { background: #fbfaff; color: #5f5c70; border-bottom: 1px solid #e2dcef; }
QCheckBox { color: #17151f; }
QCheckBox::indicator { background: #ffffff; border: 1px solid #b9b2cc; }
QCheckBox::indicator:checked { background: #6d3fd6; border-color: #6d3fd6; }
QScrollBar::handle:vertical { background: #d8d2e8; }
QScrollBar::handle:vertical:hover { background: #b9b2cc; }
QMessageBox { background: #ffffff; color: #17151f; }
QMessageBox QPushButton { background: #ffffff; color: #17151f; border: 1px solid #d8d2e8; }
QMessageBox QPushButton:hover { border-color: #6d3fd6; }
"""


def apply_theme(app: QApplication, theme: str) -> None:
    app.setStyleSheet(_COMMON + (_LIGHT if theme == "light" else _DARK))
