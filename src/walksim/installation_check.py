"""Comprobación del ejecutable instalado, con su motor y bibliotecas reales."""

from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check_installation(folder: Path) -> dict:
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtGui import QFontDatabase
    from PySide6.QtWidgets import QApplication

    from walksim import __version__
    from walksim.domain import access, crossing, plaza, shared, walkway
    from walksim.domain.analysis import calculate
    from walksim.domain.models import CorridorScenario
    from walksim.project import ProjectState, load_project, save_project
    from walksim.report import write_report
    from walksim.sumo.access import run_access_simulation
    from walksim.sumo.crossing import run_crossing_simulation
    from walksim.sumo.plaza import run_plaza_simulation
    from walksim.sumo.runner import detect_sumo, run_corridor_simulation
    from walksim.sumo.runtime import bundled_bin_directory, engine_version
    from walksim.sumo.shared import run_shared_simulation
    from walksim.sumo.walkway import run_walkway_simulation
    from walksim.ui.main_window import MainWindow
    from walksim.ui.navigation import TAB_ORDER

    folder.mkdir(parents=True, exist_ok=True)
    checks = []
    installation = detect_sumo()
    require(installation.available, "Faltan los ejecutables SUMO incluidos.")
    bundled = bundled_bin_directory()
    if getattr(sys, "frozen", False):
        require(bundled is not None, "No se detectó la carpeta del motor privado.")
        for executable in (installation.sumo, installation.netconvert):
            require(Path(executable).parent == bundled, "Se está usando un SUMO externo.")
    version = engine_version(installation.sumo)
    require("1.28.0" in version, "La versión de SUMO no coincide con el paquete.")
    checks.append("bundled_sumo_and_netconvert")

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(folder / "settings")
    )
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setApplicationName("WalkSim Mobility")
    window = MainWindow()
    window.show()
    app.processEvents()
    require(window.tabs.count() == len(TAB_ORDER), "Faltan espacios de trabajo.")
    require("Latin Modern Roman" in QFontDatabase.families(), "Faltan las fuentes incluidas.")
    for key, _label in TAB_ORDER:
        window._show_tab(key)
        app.processEvents()
    window.set_theme("dark")
    app.processEvents()
    window.set_theme("light")
    checks.append("gui_tabs_fonts_and_themes")

    root = Path(sys.executable).parent if bundled else Path(__file__).resolve().parents[2]
    examples = list((root / "examples").glob("*.wksim"))
    require(len(examples) >= 6, "No se incluyeron los estudios de ejemplo.")
    for example in examples:
        load_project(example)
    checks.append("bundled_examples")

    scenario = CorridorScenario(
        length_m=20, width_m=3, analysis_time_s=60, flow_ab_pph=120, flow_ba_pph=120
    )
    corridor = run_corridor_simulation(scenario, folder / "Corredor México")
    require(corridor.result.ab.completed_walks > 0, "El sentido AB no completó recorridos.")
    require(corridor.result.ba.completed_walks > 0, "El sentido BA no completó recorridos.")
    state = ProjectState(corridor=scenario)
    state.project.name = "Práctica México"
    state.project.analyst = "Héctor & estudiantes"
    state.simulations = [
        dict(
            scenario=asdict(scenario),
            result=asdict(corridor.result),
            created_at="2026-11-01T12:00:00+00:00",
            engine_version=corridor.engine_version,
            measurements=corridor.measurements,
            assumptions=[],
        )
    ]
    state.analyses = [
        calculate(
            "queue", dict(area_m2=30, excluded_area_m2=3, occupants=35), "Área de espera"
        ).to_dict()
    ]
    checks.append("corridor_simulation")

    modules = {
        "walkway": (
            walkway,
            run_walkway_simulation,
            dict(
                length_m=20, duration_s=60, warmup_s=0, bin_s=30, flow_ab_pph=300, flow_ba_pph=300
            ),
        ),
        "access": (
            access,
            run_access_simulation,
            dict(duration_s=60, warmup_s=0, bin_s=30, clearance_s=120, rate_pph=240),
        ),
        "plaza": (
            plaza,
            run_plaza_simulation,
            dict(
                duration_s=60,
                warmup_s=0,
                bin_s=30,
                clearance_s=120,
                od=[[0 if i == j else 120 for j in range(4)] for i in range(4)],
            ),
        ),
        "shared": (
            shared,
            run_shared_simulation,
            dict(length_m=50, duration_s=60, warmup_s=0, bin_s=30, clearance_s=120),
        ),
        "crossing": (crossing, run_crossing_simulation, dict(duration_s=120)),
    }
    summaries = {}
    for name, (domain, run, inputs) in modules.items():
        result = run(inputs, folder / (name + " México"))
        summary = result["summary"]
        require(summary["generated"] > 0, f"{name}: no se generó demanda.")
        require(summary["completed"] > 0, f"{name}: no se completaron recorridos.")
        if name == "walkway":
            require(
                summary["generated"] == summary["started"] + summary["not_started"],
                "Walkway no conserva la demanda generada.",
            )
            require(
                summary["started"] == summary["completed"] + summary["unfinished"],
                "Walkway no conserva los recorridos iniciados.",
            )
        else:
            require(
                summary["generated"] == summary["completed"] + summary["pending"],
                f"{name}: no se conserva la demanda.",
            )
        case = domain.new_case("Prueba " + name, inputs=result["inputs"])
        case["analytical"], case["simulation"] = result["analytical"], result
        setattr(state, name, dict(cases=[case], selected_id=case["id"]))
        summaries[name] = summary
        checks.append(name + "_simulation")

    project = save_project(state, folder / "Práctica México.wksim")
    restored = load_project(project)
    require(restored.project.analyst == state.project.analyst, "No se recuperó el analista.")
    for name in modules:
        require(
            getattr(restored, name) == getattr(state, name),
            f"{name}: el archivo guardado perdió datos.",
        )
    checks.append("save_and_reopen_wksim")

    for scope in (*modules, "analyses", "corridor"):
        report = folder / (scope + ".tex")
        write_report(restored, str(report), scope=scope)
        require(
            "\\end{document}" in report.read_text(encoding="utf-8"), "Reporte incompleto: " + scope
        )
    figures = list(folder.glob("*_figuras/*.pdf"))
    require(len(figures) >= len(modules), "Faltan gráficas PDF en los informes.")
    require(
        all(p.read_bytes().startswith(b"%PDF-") for p in figures),
        "Alguna gráfica no es un PDF válido.",
    )
    checks.append("latex_reports_and_pdf_figures_without_tex")

    window._apply_project(restored)
    for key, _label in TAB_ORDER:
        window._show_tab(key)
        app.processEvents()
    window._show_tab("walkway")
    app.processEvents()
    require(
        window.grab().save(str(folder / "WalkSim-instalado.png")), "No se pudo capturar la GUI."
    )
    checks.append("gui_with_saved_results")
    window.setWindowModified(False)
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return dict(
        version=__version__,
        sumo_version=version,
        checks=checks,
        executables=asdict(installation),
        summaries=summaries,
        corridor_completed=corridor.result.total.completed_walks,
        report_figures=len(figures),
        examples=len(examples),
    )
