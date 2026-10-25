"""Regresiones de apariencia y acceso en pantallas pequeñas, sin ejecutar el motor."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel

from walksim.domain.models import DirectionResult
from walksim.ui import main_window


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    settings = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda *_args: settings)
    widget = main_window.MainWindow()
    widget.show()
    app.processEvents()
    yield widget, app
    widget.close()


def test_theme_persists_without_changing_scenario(window):
    widget, app = window
    widget.width_spin.setValue(4.75)
    for theme in ("dark", "light", "dark"):
        widget.set_theme(theme)
        app.processEvents()
        assert widget.width_spin.value() == 4.75
        lightness = widget.preview.palette().color(QPalette.ColorRole.Text).lightness()
        assert (lightness > 128) == (theme == "dark")
        assert widget.settings.value("appearance/theme") == theme
        assert "SUMO" not in widget.scope_browser.toPlainText()
    reopened = main_window.MainWindow()
    assert reopened.theme == "dark"
    reopened.close()


@pytest.mark.parametrize("width,height,columns", [(1280, 820, 4), (800, 480, 2), (480, 360, 1)])
def test_small_screen_navigation_and_controls(window, width, height, columns):
    widget, app = window
    widget.resize(width, height)
    for index in range(4):
        widget.tabs.setCurrentIndex(index)
        app.processEvents()
    assert widget.width() == width
    assert widget.height() == height
    for index, card in enumerate(widget.metric_cards):
        position = widget.cards_layout.getItemPosition(widget.cards_layout.indexOf(card))
        assert position[:2] == (index // columns, index % columns)
    expected = Qt.Orientation.Vertical if width < 900 else Qt.Orientation.Horizontal
    assert widget.corridor_splitter.orientation() == expected
    widget.tabs.setCurrentIndex(2)
    app.processEvents()
    scroll = widget.tabs.widget(2)
    scroll.ensureWidgetVisible(widget.seed_spin)
    app.processEvents()
    center = widget.seed_spin.mapTo(scroll.viewport(), widget.seed_spin.rect().center())
    assert scroll.viewport().rect().contains(center)
    widget.tabs.setCurrentIndex(3)
    app.processEvents()
    if width < 1000:
        assert widget.results_table.horizontalScrollBar().maximum() > 0
    assert all("SUMO" not in label.text() for label in widget.findChildren(QLabel))


def test_simulation_result_still_opens_results_tab(window, monkeypatch, tmp_path):
    widget, _app = window
    result = DirectionResult()
    monkeypatch.setattr(
        main_window,
        "run_corridor_simulation",
        lambda _scenario: SimpleNamespace(
            files=SimpleNamespace(workdir=tmp_path),
            result=SimpleNamespace(ab=result, ba=result, total=result),
        ),
    )
    widget.simulate()
    assert widget.tabs.currentIndex() == 3
    assert widget.last_output_dir == tmp_path
    assert widget.results_table.item(2, 0).text() == "Total"
