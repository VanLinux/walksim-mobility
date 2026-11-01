"""Navegación y presentación sin alterar los datos ni sus definiciones."""

import copy
import time
from dataclasses import asdict
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication, QLabel

from walksim.project import load_project
from walksim.ui import main_window
from walksim.ui.navigation import LINKED_TABS, SUMMARIES, TAB_ORDER


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    settings = QSettings(str(tmp_path / "appearance.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda *_a: settings)
    w = main_window.MainWindow()
    yield w, app
    w.setWindowModified(False)
    w.close()
    w.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def walkway_state():
    root = Path(__file__).resolve().parents[1]
    state = load_project(root / "examples/Walkway3_Comparacion.wksim")
    first = next(c for c in state.walkway["cases"] if c.get("simulation"))
    state.walkway["selected_id"] = first["id"]
    return state


def test_adjacent_groups_summaries_and_subtle_identifiers(window):
    w, app = window
    assert [w.tabs.tabText(i) for i in range(w.tabs.count())] == [text for _, text in TAB_ORDER]
    keys = [key for key, _ in TAB_ORDER]
    assert keys.index("corridor_results") == keys.index("walkway") + 1
    assert keys.index("corridor") == keys.index("corridor_results") + 1
    assert keys.index("analyses") == keys.index("corridor") + 1
    for key in SUMMARIES:
        w._show_tab(key)
        app.processEvents()
        summaries = [
            label
            for label in w.pages[key].findChildren(QLabel)
            if label.property("workspaceSummary")
        ]
        assert len(summaries) == 1
        assert summaries[0].text() == SUMMARIES[key] and len(summaries[0].text()) < 180
        i = w.tabs.indexOf(w.pages[key])
        assert not w.tabs.tabIcon(i).isNull()
        tooltip = w.tabs.tabToolTip(i)
        assert ("Conectada:" in tooltip) == (key in LINKED_TABS)
        assert ("Independiente:" in tooltip) == (key not in LINKED_TABS)


def test_shared_view_reuses_widgets_and_keeps_inputs_and_results(window, walkway_state):
    w, app = window
    w._apply_project(walkway_state)
    w._show_tab("walkway")
    panel = w.walkway_widget
    results, figure = panel.results, panel.figure
    panel.output_tabs.setCurrentIndex(2)
    before = copy.deepcopy(w.collect_project().to_dict())
    for _ in range(3):
        w._show_tab("corridor_results")
        app.processEvents()
        assert results.parentWidget() is w.walkway_results_host
        assert w.results_stack.currentWidget() is w.walkway_results_host
        assert panel.results is results and panel.figure is figure
        assert w._active_scope() == "walkway"
        assert panel.current["name"] in w.results_source_label.text()
        assert panel.output_tabs.currentIndex() == 2
        assert w._active_report_state().walkway and not w._active_report_state().simulations
        w.results_return_button.click()
        assert w._current_workspace() == "walkway"
        assert results.parentWidget() is panel.splitter and panel.splitter.count() == 2
    # Ignore the generated software/version metadata; navigation must not touch study data.
    after = w.collect_project().to_dict()
    assert after == before
    w._show_tab("corridor_results")
    panel.current["name"] = "Escenario renombrado"
    panel.changed.emit()
    assert "Escenario renombrado" in w.results_source_label.text()
    w._show_tab("corridor")
    w._show_tab("corridor_results")
    assert w._active_scope() == "corridor"
    assert w.results_stack.currentWidget() is w.corridor_results_page
    assert "Corredor libre" in w.results_source_label.text()


def test_walkway_success_opens_its_results_even_after_tab_switch(
    window, walkway_state, monkeypatch
):
    import walksim.ui.walkway_widget as module

    w, app = window
    w._apply_project(walkway_state)
    panel = w.walkway_widget
    result = copy.deepcopy(panel.current["simulation"])
    original_corridor = asdict(w._scenario_from_ui())
    original_records = copy.deepcopy(w.simulation_records)
    monkeypatch.setattr(module, "run_walkway_simulation", lambda _raw: copy.deepcopy(result))
    w._show_tab("walkway")
    assert panel.calculate()
    assert w._current_workspace() == "walkway"
    panel.simulate()
    assert w._busy
    w._show_tab("corridor")
    deadline = time.monotonic() + 8
    while (w._busy or panel.worker) and time.monotonic() < deadline:
        app.processEvents()
    assert not w._busy and panel.worker is None
    assert w._current_workspace() == "corridor_results" and w._active_scope() == "walkway"
    assert w.results_stack.currentWidget() is w.walkway_results_host
    assert panel.current["simulation"] == result
    assert asdict(w._scenario_from_ui()) == original_corridor
    assert w.simulation_records == original_records
    assert w.report_action.isEnabled()


def test_failed_walkway_does_not_open_a_different_result(window, monkeypatch):
    import walksim.ui.walkway_widget as module

    w, app = window
    panel = w.walkway_widget
    notes = []

    def fail(_raw):
        raise RuntimeError("Fallo controlado")

    monkeypatch.setattr(module, "run_walkway_simulation", fail)
    monkeypatch.setattr(module.QMessageBox, "warning", lambda *a: notes.append(a))
    w._show_tab("walkway")
    panel.simulate()
    deadline = time.monotonic() + 8
    while (w._busy or panel.worker) and time.monotonic() < deadline:
        app.processEvents()
    assert not w._busy and notes
    assert w._current_workspace() == "walkway"
    assert not panel.current["simulation"]


def test_loading_and_new_study_release_shared_view(window, walkway_state, tmp_path):
    w, app = window
    w._apply_project(walkway_state)
    w._show_tab("walkway")
    w._show_tab("corridor_results")
    saved = w.save_to_path(tmp_path / "navigation.wksim")
    w.load_from_path(saved)
    w._show_tab("walkway")
    assert w.walkway_widget.splitter.count() == 2
    assert w.walkway_widget.current["simulation"]
    w._show_tab("corridor_results")
    w.setWindowModified(False)
    w.new_project()
    app.processEvents()
    assert w.walkway_widget.splitter.count() == 2
    assert w._pending_walkway_case is None
    assert not w.walkway_widget.current["simulation"] and not w.simulation_records


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_result_view_stays_accessible_on_small_screens(window, walkway_state, theme):
    w, app = window
    w._apply_project(walkway_state)
    w._show_tab("walkway")
    w._show_tab("corridor_results")
    w.set_theme(theme)
    w.resize(480, 360)
    w.show()
    for _ in range(4):
        app.processEvents()
    outer = w.pages["corridor_results"]
    assert w.width() == 480
    assert w.results_tab.minimumSizeHint().width() <= outer.viewport().width()
    assert w.results_source_label.isVisible() and w.results_return_button.isVisible()
    assert w.walkway_widget.dark == (theme == "dark")
    assert w.results_stack.currentWidget() is w.walkway_results_host
