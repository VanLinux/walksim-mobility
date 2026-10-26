"""Regresiones de apariencia y acceso en pantallas pequeñas, sin ejecutar el motor."""

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QLabel

from walksim.domain.models import DirectionResult, SimulationResult
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
    widget.setWindowModified(False)
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
    for index in range(6):
        widget.tabs.setCurrentIndex(index)
        app.processEvents()
    assert widget.width() == width
    assert widget.height() == height
    for index, card in enumerate(widget.metric_cards):
        position = widget.cards_layout.getItemPosition(widget.cards_layout.indexOf(card))
        assert position[:2] == (index // columns, index % columns)
    expected = Qt.Orientation.Vertical if width < 900 else Qt.Orientation.Horizontal
    assert widget.corridor_splitter.orientation() == expected
    widget.tabs.setCurrentIndex(4)
    app.processEvents()
    scroll = widget.tabs.widget(4)
    scroll.ensureWidgetVisible(widget.seed_spin)
    app.processEvents()
    center = widget.seed_spin.mapTo(scroll.viewport(), widget.seed_spin.rect().center())
    assert scroll.viewport().rect().contains(center)
    widget.tabs.setCurrentIndex(5)
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
            result=SimulationResult(ab=result, ba=result, total=result),
        ),
    )
    widget.simulate()
    import time

    deadline = time.monotonic() + 3
    while widget._busy and time.monotonic() < deadline:
        _app.processEvents()
    assert not widget._busy
    assert widget.tabs.currentIndex() == 5
    assert widget.last_output_dir == tmp_path
    assert widget.results_table.item(2, 0).text() == "Total"


def test_save_open_restores_partial_forms_and_results(window, tmp_path):
    widget, app = window
    widget.project_name.setText("Estudio de prueba")
    widget.project_analyst.setText("Héctor")
    panel = widget.analysis_widget
    panel.selector.setCurrentIndex(panel.selector.findData("queue"))
    panel.calculate_current()
    panel.selector.setCurrentIndex(panel.selector.findData("walkway"))
    panel.inputs["width_m"].clear()
    panel.inputs["count"].setText("incompleto")
    widget.width_spin.setValue(3.125)
    saved = widget.save_to_path(tmp_path / "estudio.wksim")
    assert not widget.isWindowModified()
    panel.inputs["count"].setText("otro")
    widget.load_from_path(saved)
    app.processEvents()
    assert widget.project_analyst.text() == "Héctor"
    assert widget.width_spin.value() == 3.125
    assert panel.method == "walkway"
    assert panel.inputs["width_m"].text() == ""
    assert panel.inputs["count"].text() == "incompleto"
    assert len(panel.results) == 1
    assert not widget.isWindowModified()


def test_open_bad_file_leaves_study_untouched(window, tmp_path):
    widget, _app = window
    widget.project_name.setText("No perder")
    bad = tmp_path / "corrupt.wksim"
    bad.write_text("{incorrecto}")
    with pytest.raises(ValueError):
        widget.load_from_path(bad)
    assert widget.project_name.text() == "No perder"
    assert widget.isWindowModified()


def test_invalid_csv_does_not_append_partial_cases(window, tmp_path, monkeypatch):
    widget, _app = window
    path = tmp_path / "batch.csv"
    path.write_text(
        "analysis,name,area_m2,excluded_area_m2,occupants\n"
        "queue,valid,30,0,20\nqueue,invalid,0,0,20\n"
    )
    monkeypatch.setattr("walksim.ui.analysis_widget.QMessageBox.warning", lambda *_: None)
    assert not widget.analysis_widget.import_path(str(path))
    assert widget.analysis_widget.results == []


def test_cancel_close_preserves_unsaved_work(window, monkeypatch):
    widget, _app = window
    widget.project_notes.setPlainText("Pendiente")
    monkeypatch.setattr(
        main_window.QMessageBox,
        "question",
        lambda *_args: main_window.QMessageBox.StandardButton.Cancel,
    )
    assert not widget.close()
    assert widget.isWindowModified()


def test_worker_failure_preserves_cases_and_releases_controls(window, monkeypatch):
    import time

    widget, app = window
    panel = widget.analysis_widget
    panel.calculate_current()

    def fail(_scenario):
        raise OSError("test failure")

    monkeypatch.setattr(main_window, "run_corridor_simulation", fail)
    monkeypatch.setattr(main_window.QMessageBox, "critical", lambda *_: None)
    widget.simulate()
    deadline = time.monotonic() + 3
    while widget._busy and time.monotonic() < deadline:
        app.processEvents()
    assert not widget._busy
    assert widget.save_action.isEnabled()
    assert len(panel.results) == 1
    assert not widget.simulation_records


def test_analysis_to_simulation_transfer_uses_effective_width_and_explicit_share(
    window, monkeypatch
):
    from walksim.domain.analysis import calculate

    widget, _app = window
    result = calculate(
        "walkway",
        dict(width_m=3, obstacles_m=0.2, edges_m=0.3, count=450, period_min=15, speed_mps=1.2),
    ).to_dict()
    answers = iter([(150, True), (60, True)])
    monkeypatch.setattr(main_window.QInputDialog, "getDouble", lambda *_args: next(answers))
    widget.prepare_analysis_simulation(result)
    assert widget.length_spin.value() == 150
    assert widget.width_spin.value() == 2.5
    assert widget.flow_ab_spin.value() == 1080
    assert widget.flow_ba_spin.value() == 720
    assert widget.tabs.currentIndex() == 4


def test_walkway_design_modes_invalidate_outputs_and_save_partial_drafts(window, tmp_path):
    from PySide6.QtTest import QTest

    widget, app = window
    panel = widget.walkway_widget
    panel.fields["mode"].setCurrentIndex(panel.fields["mode"].findData("design_width"))
    assert panel.calculate()
    assert panel.current["analytical"]["metrics"]["LOS operativo"] in "ABC"
    assert panel.fresh(panel.current, "analytical")
    entry = panel.fields["speed_mps"]
    entry.selectAll()
    QTest.keyClicks(entry, "1.3")
    app.processEvents()
    assert not panel.fresh(panel.current, "analytical")
    assert panel.current["origins"]["speed_mps"] == "entered"
    entry.selectAll()
    QTest.keyClick(entry, Qt.Key.Key_Backspace)
    app.processEvents()
    path = widget.save_to_path(tmp_path / "draft3.wksim")
    widget.load_from_path(path)
    assert panel.fields["speed_mps"].text() == ""
    assert panel.current["analytical"] is not None
    assert not panel.fresh(panel.current, "analytical")


def test_walkway_alternatives_are_independent_and_compared(window, monkeypatch):
    widget, _app = window
    panel = widget.walkway_widget
    panel.calculate()
    original = panel.current["id"]
    monkeypatch.setattr(
        "walksim.ui.walkway_widget.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Alternativa ancha", True),
    )
    panel.duplicate_case()
    assert len(panel.cases) == 2 and panel.selected_id != original
    panel.fields["width_m"].setText("4")
    panel._edited("width_m")
    assert panel.cases[0]["inputs"]["width_m"] != panel.current["inputs"]["width_m"]
    panel.compare_all()
    assert panel.compare_table.rowCount() == 2
    assert all(panel.fresh(case, "analytical") for case in panel.cases)
    panel.fields["flow_type"].setCurrentIndex(panel.fields["flow_type"].findData("platoon"))
    assert panel.fields["demand_basis"].currentData() == "count"


def test_walkway_controls_remain_accessible_at_small_size(window):
    widget, app = window
    widget.resize(480, 360)
    widget.tabs.setCurrentIndex(2)
    app.processEvents()
    panel = widget.walkway_widget
    assert widget.size().toTuple() == (480, 360)
    assert panel.more_button.isVisible()
    assert panel.splitter.orientation() == Qt.Orientation.Vertical
    outer = widget.tabs.widget(2)
    outer.ensureWidgetVisible(panel.splitter)
    app.processEvents()
    assert outer.verticalScrollBar().maximum() > 0


def test_access_dynamic_fields_drafts_theme_and_saved_results(window, tmp_path):
    from walksim.domain.access import fresh

    widget, app = window
    panel = widget.access_widget
    widget.tabs.setCurrentIndex(6)
    assert panel.calculate()
    assert panel.cards["capacity"].text() == "3,600 peat/h"
    panel.fields["layout"].setCurrentIndex(panel.fields["layout"].findData("metro_exit"))
    assert panel.fields["arrival"].currentData() == "batch"
    assert panel.metro_box.isVisible()
    assert not panel.fields["rate_pph"].isVisible()
    panel.fields["passengers"].setText("120")
    panel._edited("passengers")
    assert panel.calculate()
    panel.fields["service_s"].setText("")
    panel._edited("service_s")
    assert not fresh(panel.current, "analytical")
    path = widget.save_to_path(tmp_path / "access.wksim")
    widget.load_from_path(path)
    assert panel.fields["service_s"].text() == ""
    assert panel.current["analytical"] is not None
    widget.set_theme("dark")
    assert panel.dark
    widget.resize(480, 360)
    app.processEvents()
    assert panel.splitter.orientation() == Qt.Orientation.Vertical
    assert panel.more_button.isVisible()
    outer = widget.tabs.widget(6)
    assert panel.minimumSizeHint().width() <= outer.viewport().width()


def test_access_worker_runs_without_blocking_file_and_close_guards(window, monkeypatch):
    import time

    from walksim.domain.access import evaluate_access

    widget, app = window
    panel = widget.access_widget
    result = dict(signature=evaluate_access({})["signature"])
    monkeypatch.setattr("walksim.ui.access_widget.run_access_simulation", lambda _raw: result)
    # Keep this a thread/lifecycle check; rendering is covered by the actual result tests.
    original_render = panel.render
    panel.render = lambda: None
    panel.simulate()
    assert widget._busy and not widget.save_action.isEnabled()
    deadline = time.monotonic() + 5
    while widget._busy and time.monotonic() < deadline:
        app.processEvents()
    assert not widget._busy and panel.worker is None
    assert widget.save_action.isEnabled() and panel.current["simulation"] == result
    panel.current["simulation"] = None
    panel.render = original_render


def test_plaza_matrix_modes_partial_drafts_and_alternatives(window, tmp_path, monkeypatch):
    from walksim.domain.plaza import fresh

    widget, app = window
    p = widget.plaza_widget
    widget.tabs.setCurrentIndex(7)
    assert p.calculate()
    assert p.cards["area"].text() == "432.0 m²"
    p.matrix.item(0, 1).setText("850")
    assert p.current["inputs"]["od"][0][1] == "850"
    assert not fresh(p.current, "analytical")
    monkeypatch.setattr(
        "walksim.ui.plaza_widget.QInputDialog.getText", lambda *_a, **_k: ("Plaza amplia", True)
    )
    p.duplicate_case()
    p.matrix.item(0, 1).setText("")
    assert p.cases[0]["inputs"]["od"][0][1] == "850"
    p.fields["template"].setCurrentIndex(p.fields["template"].findData("tee"))
    assert not p.matrix.item(0, 1).flags() & Qt.ItemFlag.ItemIsEnabled
    p.fields["template"].setCurrentIndex(p.fields["template"].findData("rectangle"))
    assert p.matrix.item(0, 1).text() == ""
    path = widget.save_to_path(tmp_path / "plaza_draft.wksim")
    widget.load_from_path(path)
    assert p.matrix.item(0, 1).text() == "" and len(p.cases) == 2
    widget.set_theme("dark")
    widget.resize(480, 360)
    widget.tabs.setCurrentIndex(7)
    app.processEvents()
    assert p.dark and p.more_button.isVisible()
    assert p.splitter.orientation() == Qt.Orientation.Vertical
    outer = widget.tabs.widget(7)
    assert p.minimumSizeHint().width() <= outer.viewport().width()
