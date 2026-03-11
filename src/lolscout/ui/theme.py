from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


APP_STYLESHEET = """
QWidget {
    background: #0b1220;
    color: #e5edf7;
    font-family: "Segoe UI";
    font-size: 10.5pt;
}
QLabel {
    background: transparent;
}
QMainWindow {
    background: #09101d;
}
QFrame#Card {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111b2f, stop:1 #0f1730);
    border: 1px solid #22304d;
    border-radius: 18px;
}
QFrame#HeaderCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #13213b, stop:1 #0c1526);
    border: 1px solid #29436b;
    border-radius: 22px;
}
QLineEdit, QComboBox, QSpinBox {
    background: #0b1528;
    border: 1px solid #29436b;
    border-radius: 12px;
    padding: 10px 12px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #54d2a0;
}
QPushButton {
    background: #54d2a0;
    color: #04120f;
    border: none;
    border-radius: 14px;
    padding: 11px 18px;
    font-weight: 700;
}
QPushButton:hover {
    background: #68dfb0;
}
QPushButton:disabled {
    background: #29436b;
    color: #9db0cc;
}
QLabel#HeroTitle {
    font-size: 24pt;
    font-weight: 700;
}
QLabel#Muted {
    color: #93a8c6;
}
QLabel#StatValue {
    font-size: 18pt;
    font-weight: 700;
}
QLabel#StatLabel {
    color: #8aa0bf;
    font-size: 9pt;
    text-transform: uppercase;
}
QScrollArea {
    border: none;
}
QFrame#MatchWin {
    background: #0f2830;
    border: 1px solid #1f6d60;
    border-radius: 16px;
}
QFrame#MatchLoss {
    background: #2a131a;
    border: 1px solid #7a3046;
    border-radius: 16px;
}
"""


def build_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#09101d"))
    palette.setColor(QPalette.WindowText, QColor("#e5edf7"))
    palette.setColor(QPalette.Base, QColor("#0b1528"))
    palette.setColor(QPalette.AlternateBase, QColor("#111b2f"))
    palette.setColor(QPalette.ToolTipBase, QColor("#111b2f"))
    palette.setColor(QPalette.ToolTipText, QColor("#e5edf7"))
    palette.setColor(QPalette.Text, QColor("#e5edf7"))
    palette.setColor(QPalette.Button, QColor("#54d2a0"))
    palette.setColor(QPalette.ButtonText, QColor("#04120f"))
    palette.setColor(QPalette.Highlight, QColor("#54d2a0"))
    palette.setColor(QPalette.HighlightedText, QColor("#04120f"))
    return palette
