"""Sistema visual de WalkSim Mobility, alineado con HCNet Transport."""

from __future__ import annotations

COLORS = {
    "ink": "#202124",
    "muted": "#5F6368",
    "canvas": "#F5F5F5",
    "surface": "#FFFFFF",
    "line": "#DADCE0",
    "dark": "#30343B",
    "success": "#18794E",
    "warning": "#9A5B13",
    "error": "#B42318",
}

APP_STYLESHEET = """
QMainWindow, QDialog {
    background: #F5F5F5;
    color: #202124;
}
QWidget {
    color: #202124;
    font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 10pt;
}
QMenuBar {
    background: #FFFFFF;
    color: #202124;
    border-bottom: 1px solid #DADCE0;
}
QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #3F444B;
    color: #FFFFFF;
}
QMenu {
    background: #FFFFFF;
    border: 1px solid #C7C9CC;
    padding: 5px;
}
QMenu::item {
    padding: 7px 28px 7px 24px;
}
QTabWidget::pane {
    border: 0;
    background: #F5F5F5;
}
QTabBar::tab {
    background: transparent;
    color: #5F6368;
    border: 0;
    border-bottom: 3px solid transparent;
    padding: 11px 18px;
    font-weight: 600;
}
QTabBar::tab:selected {
    color: #202124;
    border-bottom-color: #3F444B;
}
QTabBar::tab:hover:!selected {
    color: #202124;
    background: #E8EAED;
}
QGroupBox {
    background: #FFFFFF;
    color: #30343B;
    border: 1px solid #DADCE0;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 13px;
    padding: 0 6px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {
    background: #FFFFFF;
    color: #202124;
    border: 1px solid #BFC2C5;
    border-radius: 5px;
    padding: 6px;
    selection-background-color: #4B5057;
    selection-color: #FFFFFF;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #5F6368;
    padding: 5px;
}
QPushButton {
    background: #FFFFFF;
    color: #202124;
    border: 1px solid #BFC2C5;
    border-radius: 6px;
    padding: 7px 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: #ECEDEF;
    border-color: #7A7F85;
}
QPushButton:pressed {
    background: #DADCE0;
}
QPushButton#primaryButton {
    background: #30343B;
    color: #FFFFFF;
    border-color: #30343B;
}
QPushButton#primaryButton:hover {
    background: #17191C;
}
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F7F7F7;
    border: 1px solid #DADCE0;
    border-radius: 7px;
    gridline-color: #E8EAED;
    selection-background-color: #5F6368;
    selection-color: #FFFFFF;
}
QHeaderView::section {
    background: #ECEDEF;
    color: #30343B;
    border: 0;
    border-right: 1px solid #DADCE0;
    border-bottom: 1px solid #C7C9CC;
    padding: 8px 6px;
    font-weight: 600;
}
QTextBrowser {
    background: #FFFFFF;
    color: #202124;
    border: 1px solid #DADCE0;
    border-radius: 7px;
}
QStatusBar {
    background: #FFFFFF;
    color: #5F6368;
    border-top: 1px solid #DADCE0;
}
QLabel#pageTitle {
    color: #202124;
    font-size: 19pt;
    font-weight: 700;
}
QLabel#pageSubtitle {
    color: #5F6368;
    font-size: 10pt;
}
QLabel#sectionTitle {
    color: #30343B;
    font-size: 13pt;
    font-weight: 700;
}
QLabel#infoBanner {
    background: #ECEDEF;
    color: #30343B;
    border-left: 4px solid #5F6368;
    border-radius: 4px;
    padding: 10px;
}
QFrame#metricCard {
    background: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 8px;
}
QLabel#metricLabel {
    color: #5F6368;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#metricValue {
    color: #202124;
    font-size: 20pt;
    font-weight: 700;
}
QFrame#sumoStatusOk {
    background: #EDF7F1;
    border: 1px solid #B7D9C6;
    border-radius: 7px;
}
QFrame#sumoStatusMissing {
    background: #F8F1E8;
    border: 1px solid #DDC5A5;
    border-radius: 7px;
}
"""
