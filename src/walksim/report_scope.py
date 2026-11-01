"""Selecciona únicamente resultados de la ventana activa, sin modificar el proyecto."""

import copy

from walksim.domain.access import fresh as access_fresh
from walksim.domain.crossing import fresh as crossing_fresh
from walksim.domain.plaza import fresh as plaza_fresh
from walksim.domain.shared import fresh as shared_fresh
from walksim.project import ProjectState
from walksim.walkway_report import current_result

SCOPE_TITLES = {
    "walkway": "Walkway",
    "analyses": "Complementarios",
    "corridor": "Corredor libre",
    "access": "Accesos y colas",
    "plaza": "Plaza y flujos cruzados",
    "shared": "Sendero compartido",
    "crossing": "Cruce semaforizado",
}

_CURRENT = {
    "walkway": current_result,
    "access": access_fresh,
    "plaza": plaza_fresh,
    "shared": shared_fresh,
    "crossing": crossing_fresh,
}


def select_report_state(state: ProjectState, scope: str) -> ProjectState:
    if scope not in SCOPE_TITLES:
        raise ValueError("Seleccione una ventana de trabajo para exportar su reporte.")
    selected = ProjectState(project=copy.deepcopy(state.project))
    if scope == "analyses":
        selected.analyses = copy.deepcopy(state.analyses)
        ready = bool(selected.analyses)
    elif scope == "corridor":
        # El corredor muestra una ejecución, no el historial de los demás módulos.
        selected.simulations = copy.deepcopy(state.simulations[-1:])
        ready = bool(selected.simulations)
    else:
        study = copy.deepcopy(getattr(state, scope))
        predicate = _CURRENT[scope]
        cases = []
        for case in study.get("cases", []):
            for kind in ("analytical", "simulation"):
                if not predicate(case, kind):
                    case[kind] = None
            if case.get("analytical") or case.get("simulation"):
                cases.append(case)
        ready = bool(cases)
        if cases:
            study["cases"] = cases
            if study.get("selected_id") not in {c["id"] for c in cases}:
                study["selected_id"] = cases[0]["id"]
            setattr(selected, scope, study)
    if not ready:
        raise ValueError(
            SCOPE_TITLES[scope] + ": no hay resultados actuales para exportar. "
            "Calcule o simule sus datos en esta ventana."
        )
    return selected
