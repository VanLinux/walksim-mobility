"""Regresiones de alcance: reportar y simular desde la pestaña activa."""

import copy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from walksim import __version__
from walksim.domain import access, crossing, plaza, shared, walkway
from walksim.domain.analysis import calculate
from walksim.domain.models import CorridorScenario, DirectionResult, SimulationResult
from walksim.project import ProjectState, load_project
from walksim.report import build_report, tex_escape, write_report
from walksim.report_scope import SCOPE_TITLES, select_report_state
from walksim.ui import about_dialog, main_window

MODULES = {
    "walkway": (walkway.new_case, walkway.evaluate_walkway),
    "access": (access.new_case, access.evaluate_access),
    "plaza": (plaza.new_case, plaza.evaluate_plaza),
    "shared": (shared.new_case, shared.evaluate_shared),
    "crossing": (crossing.new_case, crossing.evaluate_crossing),
}


def record(length=100):
    return dict(
        scenario=asdict(CorridorScenario(length_m=length)),
        result=asdict(SimulationResult(*[DirectionResult()] * 3)),
        created_at="2026-10-31T20:00:00+00:00",
        assumptions=[],
    )


@pytest.fixture
def mixed():
    state = ProjectState()
    state.project.name = "Estudio con varias ventanas"
    state.project.analyst = "Héctor & equipo"
    for scope, (factory, evaluate) in MODULES.items():
        c = factory("SENTINEL_" + scope)
        c["analytical"] = evaluate(c["inputs"])
        setattr(state, scope, dict(cases=[c], selected_id=c["id"]))
    state.analyses = [
        calculate(
            "queue", dict(area_m2=30, excluded_area_m2=3, occupants=35), "SENTINEL_analyses"
        ).to_dict()
    ]
    state.simulations = [record(90), record(110)]
    return state


@pytest.mark.parametrize("scope", list(SCOPE_TITLES))
def test_scoped_report_includes_only_its_workspace(mixed, scope):
    before = mixed.to_dict()
    text = build_report(mixed, scope=scope)
    for name in (*MODULES, "analyses"):
        assert (tex_escape("SENTINEL_" + name) in text) == (name == scope)
    assert (r"\section{Microsimulación peatonal}" in text) == (scope == "corridor")
    assert r"Héctor \& equipo" in text
    assert mixed.to_dict() == before
    if scope == "corridor":
        assert len(select_report_state(mixed, scope).simulations) == 1
    if scope == "crossing":
        assert "Para cruces semaforizados se calcula demora uniforme" not in text


def test_stale_or_empty_workspace_does_not_export_other_workspaces(mixed, tmp_path):
    mixed.crossing["cases"][0]["inputs"]["cycle_s"] += 10
    with pytest.raises(ValueError, match="resultados actuales"):
        write_report(mixed, str(tmp_path / "cruce.tex"), scope="crossing")
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="ventana de trabajo"):
        select_report_state(mixed, "project")


def test_scoped_assets_do_not_include_another_module(tmp_path):
    root = Path(__file__).resolve().parents[1]
    state = load_project(root / "examples/Cruce_Semaforizado_Comparacion.wksim")
    state.shared = load_project(root / "examples/Sendero_Compartido_Comparacion.wksim").shared
    source = copy.deepcopy(state.shared)
    write_report(state, str(tmp_path / "cruce.tex"), scope="crossing")
    files = list((tmp_path / "cruce_figuras").iterdir())
    assert len(files) == 2 and all(p.name.startswith("crossing_") for p in files)
    assert state.shared == source
    assert "Sendero compartido" not in (tmp_path / "cruce.tex").read_text()


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda *_args: settings)
    w = main_window.MainWindow()
    yield w, app
    w.setWindowModified(False)
    w.close()
    w.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_menus_and_examples_follow_active_module_without_overwriting(window, monkeypatch):
    w, _app = window
    menus = {a.text(): a.menu() for a in w.menuBar().actions()}
    assert set(menus) == {"Archivo", "Simulación", "Apariencia", "Ayuda"}
    assert [a.text() for a in menus["Simulación"].actions()] == ["Simular ejemplo"]
    for index in (0, 1):
        w.tabs.setCurrentIndex(index)
        assert not w.simulate_action.isEnabled() and not w.report_action.isEnabled()
    w._show_tab("analyses")
    assert not w.simulate_action.isEnabled() and w.report_action.isEnabled()
    calls = []
    panels = {
        2: w.walkway_widget,
        6: w.access_widget,
        7: w.plaza_widget,
        8: w.shared_widget,
        9: w.crossing_widget,
    }
    for index, panel in panels.items():
        initial = copy.deepcopy(panel.cases)
        # User data must not be used as the example's input, nor be overwritten.
        panel.current["inputs"]["length_m" if index != 6 else "approach_m"] = 123
        initial = copy.deepcopy(panel.cases)
        monkeypatch.setattr(panel, "simulate", lambda p=panel: calls.append(p))
        w.tabs.setCurrentIndex(index)
        assert w.simulate_action.isEnabled()
        w.simulate_action.trigger()
        assert w.tabs.currentIndex() == index and calls[-1] is panel
        assert panel.cases[:-1] == initial
        assert panel.current["name"].startswith("Ejemplo · ")
        assert not panel.current["simulation"]
        getattr(
            {2: walkway, 6: access, 7: plaza, 8: shared, 9: crossing}[index],
            {
                2: "evaluate_walkway",
                6: "evaluate_access",
                7: "evaluate_plaza",
                8: "evaluate_shared",
                9: "evaluate_crossing",
            }[index],
        )(panel.current["inputs"])
    # The crossing limit is preserved, with no deletion of either case.
    saved = copy.deepcopy(w.crossing_widget.cases)
    notes = []
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *args: notes.append(args))
    w.simulate_example()
    assert w.crossing_widget.cases == saved and notes
    w._busy = True
    w._set_busy(True)
    assert not w.simulate_action.isEnabled() and not w.report_action.isEnabled()
    w.tabs.setCurrentIndex(2)
    assert not w.report_action.isEnabled()
    w._busy = False
    w._set_busy(False)
    assert w.report_action.isEnabled() and w.simulate_action.isEnabled()


def test_export_command_scopes_data_and_refuses_stale_corridor(
    window, mixed, monkeypatch, tmp_path
):
    w, _app = window
    w._apply_project(mixed)
    w.tabs.setCurrentIndex(9)
    path = tmp_path / "active.tex"
    monkeypatch.setattr(main_window.QFileDialog, "getSaveFileName", lambda *a: (str(path), ""))
    w.export_report()
    text = path.read_text()
    assert tex_escape("SENTINEL_crossing") in text
    assert tex_escape("SENTINEL_shared") not in text
    # Current corridor inputs do not match either saved run. Other modules must not leak in.
    notes = []
    monkeypatch.setattr(main_window.QMessageBox, "information", lambda *a: notes.append(a))
    w.tabs.setCurrentIndex(4)
    w.length_spin.setValue(135)
    path.unlink()
    w.export_report()
    assert not path.exists() and notes
    w._show_tab("corridor_results")
    assert w._active_report_state().simulations == mixed.simulations[-1:]
    w.export_report()
    assert "Microsimulación peatonal" in path.read_text()


def test_corridor_example_worker_preserves_form_and_results_are_labelled(
    window, monkeypatch, tmp_path
):
    import time

    w, app = window
    monkeypatch.setattr(
        main_window,
        "run_corridor_simulation",
        lambda scenario: SimpleNamespace(
            files=SimpleNamespace(workdir=tmp_path),
            result=SimulationResult(*[DirectionResult()] * 3),
        ),
    )
    w.length_spin.setValue(175)
    original = asdict(w._scenario_from_ui())
    w.tabs.setCurrentIndex(4)
    w.simulate_example()
    deadline = time.monotonic() + 5
    while w._busy and time.monotonic() < deadline:
        app.processEvents()
    assert not w._busy
    assert asdict(w._scenario_from_ui()) == original
    assert w._current_workspace() == "corridor_results"
    assert w.simulation_records[-1]["name"] == "Ejemplo · Corredor libre"
    assert "Ejemplo" in w.result_status.text()
    assert w.simulation_records[-1]["scenario"]["length_m"] != original["length_m"]


def test_about_contact_opens_mail_client_and_can_copy_without_sending(window, monkeypatch):
    w, app = window
    dialog = about_dialog.AboutDialog(w)
    assert any(__version__ in label.text() for label in dialog.findChildren(QLabel))
    contact = about_dialog.ContactDialog(dialog)
    opened = []
    monkeypatch.setattr(about_dialog.QDesktopServices, "openUrl", lambda url: opened.append(url))
    buttons = {b.text(): b for b in contact.findChildren(QPushButton)}
    buttons["Copiar correo"].click()
    assert app.clipboard().text() == about_dialog.CONTACT_EMAIL == "prof.benitezgh@gmail.com"
    buttons["Escribir sugerencia…"].click()
    assert len(opened) == 1
    assert opened[0].scheme() == "mailto"
    assert opened[0].path() == about_dialog.CONTACT_EMAIL
    assert "WalkSim" in opened[0].query()
    contact.close()
    dialog.close()
