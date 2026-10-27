"""Semáforo real, censura de espera, conservación de peatones y portabilidad."""

import copy
import json
import shutil
import xml.etree.ElementTree as ET

import pytest

from walksim.analysis.crossing import summarize
from walksim.crossing_io import import_cases, template
from walksim.domain.crossing import (
    CrossingInput,
    evaluate_crossing,
    fresh,
    new_case,
    validate_simulation,
    validate_study,
)
from walksim.project import ProjectState, load_project, save_project
from walksim.report import build_report, write_report
from walksim.sumo.crossing import run_crossing_simulation


def test_reference_cycle_and_clearance_warning():
    a = evaluate_crossing(dict(length_m=12, speed_mps=1.2, cycle_s=90, walk_s=20, clearance_s=15))
    assert a["reference_s"] == 10
    assert a["vehicle_green_s"] == 52
    assert not a["warnings"]
    assert evaluate_crossing(dict(clearance_s=2))["warnings"]


@pytest.mark.parametrize(
    "raw",
    [
        {"length_m": 0},
        {"width_m": float("nan")},
        {"seed": True},
        {"seed": 1.5},
        {"cycle_s": 30, "walk_s": 20, "clearance_s": 15},
        {"ped_ab": 0, "ped_ba": 0},
        {"vehicles_ph": -1},
        {"duration_s": 60.5},
        {"invented": 1},
        {"duration_s": 1800, "ped_ab": 3000, "ped_ba": 3000},
    ],
)
def test_validation(raw):
    with pytest.raises(ValueError):
        CrossingInput.parse(raw)


def test_measurements_exclude_unserved_from_mean_and_detect_crossing_exit(tmp_path):
    path = tmp_path / "fcd.xml"
    root = ET.Element("fcd-export")
    # AB.0 waits 1 s, crosses, exits; BA.0 is stopped throughout, hence censored.
    for i in range(8):
        step = ET.SubElement(root, "timestep", time=str(i * 0.5))
        ET.SubElement(
            step,
            "person",
            id="AB.0",
            edge="AC" if i < 2 else ":C_c0" if i < 5 else "CB",
            speed="0" if i < 2 else "1.2",
        )
        ET.SubElement(step, "person", id="BA.0", edge="CB", speed="0")
    ET.ElementTree(root).write(path)
    x = CrossingInput.parse(dict(duration_s=60))
    s = summarize(x, [(0, "AB.0"), (0, "BA.0"), (0, "BA.1")], path, {":C_c0"})
    m = s["summary"]
    assert m["mean_wait_s"] == 1
    assert (m["generated"], m["entered"], m["completed"], m["pending"]) == (3, 1, 1, 2)
    assert m["waiting"] == 1 and m["not_inserted"] == 1
    assert m["max_queue_ab"] == m["max_queue_ba"] == 1
    assert s["directions"]["BA"]["mean_wait_s"] is None


def test_csv_roundtrip_bom_semicolon_and_atomic_errors(tmp_path):
    path = tmp_path / "guide.csv"
    template(path)
    cases = import_cases(path)
    assert CrossingInput.parse(cases[0]["inputs"]) == CrossingInput()
    assert set(cases[0]["origins"].values()) == {"csv"}
    text = path.read_text(encoding="utf-8-sig").replace(",", ";").replace("1.2", "1,2")
    path.write_text("\ufeff" + text, encoding="utf-8")
    assert import_cases(path)[0]["inputs"]["speed_mps"] == 1.2
    path.write_text(
        text + text.splitlines()[1] + "\n" + text.splitlines()[1] + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="alternativa"):
        import_cases(path)


def test_drafts_freshness_legacy_backup_report_without_simulation(tmp_path):
    c = new_case()
    c["analytical"] = evaluate_crossing(c["inputs"])
    assert fresh(c, "analytical")
    c["inputs"]["cycle_s"] = ""
    assert not fresh(c, "analytical")
    study = dict(cases=[c], selected_id=c["id"])
    state = ProjectState(crossing=study)
    p = tmp_path / "study.wksim"
    save_project(state, p)
    assert load_project(p).crossing == study
    old = state.to_dict()
    old["schema_version"] = 6
    old.pop("crossing")
    p.write_text(json.dumps(old))
    save_project(state, p)
    assert p.with_name("study.v3.3-backup.wksim").exists()
    assert not load_project(p.with_name("study.v3.3-backup.wksim")).crossing
    c["inputs"]["cycle_s"] = 80
    state.project.analyst = "Héctor & equipo"
    report = build_report(state)
    assert "Cruce peatonal semaforizado" in report and r"Héctor \& equipo" in report
    with pytest.raises(ValueError):
        validate_study(dict(cases=[c, new_case(), new_case()], selected_id=c["id"]))


@pytest.fixture(scope="module")
def simulated(tmp_path_factory):
    if not (shutil.which("sumo") and shutil.which("netconvert")):
        pytest.skip("SUMO no está instalado")
    folder = tmp_path_factory.mktemp("crossing")
    raw = dict(duration_s=180, cycle_s=80, seed=50, vehicles_ph=500)
    a = run_crossing_simulation(raw, folder / "base")
    b = run_crossing_simulation({**raw, "walk_s": 30}, folder / "alt")
    return a, b, folder


def test_real_sumo_conserves_demand_and_signal_controls_start(simulated):
    a, b, folder = simulated
    for s in (a, b):
        validate_simulation(s)
        m = s["summary"]
        assert m["generated"] > 0 and m["completed"] > 0
        assert m["generated"] == m["completed"] + m["pending"]
        assert s["collisions"] == 0
    assert a["summary"]["generated"] == b["summary"]["generated"]
    assert a["summary"]["mean_wait_s"] > b["summary"]["mean_wait_s"]
    seen = set()
    enters = []
    for step in ET.parse(folder / "base" / "fcd.xml").findall("timestep"):
        t = float(step.get("time"))
        for person in step.findall("person"):
            ident = person.get("id")
            if person.get("edge") == ":C_c0" and ident not in seen:
                seen.add(ident)
                enters.append(t)
    assert enters
    # Sampling can detect entry at most one time step after a transition.
    for t in enters:
        phase = t % 80
        assert 50 <= phase <= 68.5


def test_simulation_save_report_assets_and_reject_inconsistent_counts(simulated, tmp_path):
    a, b, _folder = simulated
    cases = []
    for name, sim in [("Base", a), ("Alternativa", b)]:
        c = new_case(name, sim["inputs"])
        c["analytical"] = evaluate_crossing(c["inputs"])
        c["simulation"] = sim
        cases.append(c)
    state = ProjectState(crossing=dict(cases=cases, selected_id=cases[0]["id"]))
    state.project.analyst = "Héctor Benítez"
    p = save_project(state, tmp_path / "cruce.wksim")
    assert load_project(p).crossing == state.crossing
    write_report(state, str(tmp_path / "report.tex"))
    assert len(list((tmp_path / "report_figuras").glob("crossing_*.pdf"))) == 2
    assert "Espera media" in (tmp_path / "report.tex").read_text()
    bad = copy.deepcopy(a)
    bad["summary"]["completed"] += 1
    with pytest.raises(ValueError):
        validate_simulation(bad)


def test_crossing_ui_worker_guard_and_small_screen(simulated, tmp_path, monkeypatch):
    import time

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from walksim.ui import crossing_widget, main_window

    a, _b, _folder = simulated
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(main_window, "QSettings", lambda *_args: settings)
    monkeypatch.setattr(crossing_widget, "run_crossing_simulation", lambda raw: a)
    w = main_window.MainWindow()
    try:
        panel = w.crossing_widget
        panel.current["inputs"].update(a["inputs"])
        panel._load_current()
        w.tabs.setCurrentIndex(9)
        w.resize(480, 360)
        w.show()
        app.processEvents()
        assert not panel.advanced_body.isVisible()
        assert panel.minimumSizeHint().width() <= w.tabs.widget(9).viewport().width()
        panel.simulate()
        assert w._busy and not w.save_action.isEnabled() and not w.open_action.isEnabled()
        deadline = time.monotonic() + 5
        while panel.worker and time.monotonic() < deadline:
            app.processEvents()
        assert panel.worker is None and not w._busy and w.save_action.isEnabled()
        assert panel.current["simulation"]["summary"] == a["summary"]
        w.set_theme("dark")
        assert panel.dark
        panel.duplicate_case()
        assert len(panel.cases) == 2
        p = w.save_to_path(tmp_path / "ui.wksim")
        restored = load_project(p)
        assert len(restored.crossing["cases"]) == 2
    finally:
        w.setWindowModified(False)
        w.close()


def test_real_saturation_preserves_unserved_and_partial_crossings(tmp_path):
    if not (shutil.which("sumo") and shutil.which("netconvert")):
        pytest.skip("SUMO no está instalado")
    s = run_crossing_simulation(
        dict(
            length_m=20,
            width_m=2,
            ped_ab=3000,
            ped_ba=3000,
            speed_mps=0.3,
            cycle_s=120,
            walk_s=3,
            clearance_s=1,
            vehicles_ph=0,
            duration_s=60,
        ),
        tmp_path,
    )
    validate_simulation(s)
    m = s["summary"]
    assert m["pending"] > 0 and m["waiting"] > 0 and m["crossing"] > 0
    assert m["completed"] + m["crossing"] + m["waiting"] + m["not_inserted"] == m["generated"]
    assert any("excluye" in note for note in s["warnings"])
