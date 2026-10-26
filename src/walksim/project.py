"""Archivos .wksim portables, validados y escritos de forma atómica."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from walksim import __version__
from walksim.domain.access import validate_study as validate_access_study
from walksim.domain.analysis import METHODS, calculate
from walksim.domain.models import CorridorScenario, DirectionResult, ProjectInfo
from walksim.domain.walkway import validate_study

MAX_FILE_BYTES = 8 * 1024 * 1024


@dataclass
class ProjectState:
    project: ProjectInfo = field(default_factory=ProjectInfo)
    corridor: CorridorScenario = field(default_factory=CorridorScenario)
    active_method: str = "walkway"
    drafts: dict[str, dict[str, str]] = field(default_factory=dict)
    draft_names: dict[str, str] = field(default_factory=dict)
    analyses: list[dict] = field(default_factory=list)
    simulations: list[dict] = field(default_factory=list)
    walkway: dict = field(default_factory=dict)
    access: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "WalkSim Mobility Project",
            "schema_version": 4,
            "software_version": __version__,
            **asdict(self),
        }


def atomic_write(path: str | Path, text: str) -> None:
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix="." + target.name,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _finite_tree(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("El proyecto contiene números no finitos.")
    if isinstance(value, dict):
        for item in value.values():
            _finite_tree(item)
    if isinstance(value, list):
        for item in value:
            _finite_tree(item)


def state_from_dict(data: Any) -> ProjectState:
    try:
        if not isinstance(data, dict) or data.get("format") != "WalkSim Mobility Project":
            raise ValueError("El archivo no es un proyecto WalkSim Mobility.")
        if data.get("schema_version") not in (1, 3, 4):
            raise ValueError("Versión de formato .wksim no compatible.")
        _finite_tree(data)
        project = ProjectInfo(**data["project"])
        if not all(isinstance(getattr(project, item.name), str) for item in fields(ProjectInfo)):
            raise ValueError("Los datos de identificación deben ser texto.")
        corridor = CorridorScenario(**data["corridor"])
        if (
            not all(
                isinstance(getattr(corridor, item.name), (int, float))
                and not isinstance(getattr(corridor, item.name), bool)
                for item in fields(CorridorScenario)
            )
            or not isinstance(corridor.seed, int)
            or corridor.seed > 2147483647
            or corridor.validate()
        ):
            raise ValueError("Parámetros del corredor no válidos.")
        active = data.get("active_method", "walkway")
        if active not in METHODS:
            raise ValueError("Análisis activo desconocido.")
        drafts, names = data.get("drafts", {}), data.get("draft_names", {})
        if not isinstance(drafts, dict) or not isinstance(names, dict):
            raise ValueError("Los borradores no tienen el formato esperado.")
        for method, raw in drafts.items():
            if method not in METHODS or not isinstance(raw, dict):
                raise ValueError("Borrador desconocido.")
            allowed = {item.key for item in METHODS[method].fields}
            if set(raw) - allowed or not all(isinstance(v, str) for v in raw.values()):
                raise ValueError("Campos del borrador no válidos.")
        if any(k not in METHODS or not isinstance(v, str) for k, v in names.items()):
            raise ValueError("Nombres de borradores no válidos.")
        analyses, simulations = data.get("analyses", []), data.get("simulations", [])
        if not isinstance(analyses, list) or not isinstance(simulations, list):
            raise ValueError("Resultados no válidos.")
        validated = []
        for row in analyses:
            # Recompute exact SI values with this version; never execute file content.
            result = calculate(row["method"], row["inputs"], row["name"]).to_dict()
            if not isinstance(row.get("created_at"), str):
                raise ValueError("Fecha de análisis no válida.")
            result["created_at"] = row["created_at"]
            result["data_source"] = str(row.get("data_source", "Captura manual"))
            validated.append(result)
        for row in simulations:
            saved_scenario = CorridorScenario(**row["scenario"])
            if (
                not all(
                    isinstance(getattr(saved_scenario, f.name), (int, float))
                    and not isinstance(getattr(saved_scenario, f.name), bool)
                    for f in fields(CorridorScenario)
                )
                or not isinstance(saved_scenario.seed, int)
                or saved_scenario.seed > 2147483647
                or saved_scenario.validate()
                or not isinstance(row["created_at"], str)
            ):
                raise ValueError("Resultado de simulación no válido.")
            if set(row["result"]) != {"total", "ab", "ba"}:
                raise ValueError("Los resultados por sentido no son válidos.")
            for direction in ("total", "ab", "ba"):
                summary = DirectionResult(**row["result"][direction])
                if (
                    not isinstance(summary.completed_walks, int)
                    or isinstance(summary.completed_walks, bool)
                    or summary.completed_walks < 0
                    or any(
                        not isinstance(getattr(summary, f.name), (int, float))
                        or isinstance(getattr(summary, f.name), bool)
                        or getattr(summary, f.name) < 0
                        for f in fields(DirectionResult)
                    )
                ):
                    raise ValueError("Indicadores simulados no válidos.")
            measurements = row.get("measurements", {})
            if not isinstance(measurements, dict) or any(
                not isinstance(k, str) or not isinstance(v, (str, int, float, type(None)))
                for k, v in measurements.items()
            ):
                raise ValueError("Mediciones simuladas no válidas.")
            if not isinstance(row.get("engine_version", ""), str):
                raise ValueError("Versión del motor no válida.")
            if not isinstance(row.get("assumptions", []), list) or not all(
                isinstance(v, str) for v in row.get("assumptions", [])
            ):
                raise ValueError("Supuestos de simulación no válidos.")
        walkway = validate_study(data.get("walkway", {}))
        return ProjectState(
            project,
            corridor,
            active,
            drafts,
            names,
            validated,
            simulations,
            walkway,
            validate_access_study(data.get("access", {})),
        )
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("Estructura del archivo .wksim incompleta o incorrecta.") from exc


def save_project(state: ProjectState, path: str | Path) -> Path:
    target = Path(path)
    if target.suffix.lower() != ".wksim":
        target = target.with_suffix(".wksim")
    data = state.to_dict()
    state_from_dict(data)
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    if len(text.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("El proyecto excede 8 MiB. Divida el estudio en varios archivos.")
    if target.exists():
        try:
            old = json.loads(target.read_text(encoding="utf-8-sig"))
            if isinstance(old, dict) and old.get("schema_version") in (1, 3):
                suffix = ".v2-backup.wksim" if old["schema_version"] == 1 else ".v3.0-backup.wksim"
                backup = target.with_name(target.stem + suffix)
                if not backup.exists():
                    atomic_write(backup, target.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeError):
            pass
    atomic_write(target, text + "\n")
    return target


def load_project(path: str | Path) -> ProjectState:
    target = Path(path)
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("El archivo excede el límite de 8 MiB.")
    try:
        return state_from_dict(json.loads(target.read_text(encoding="utf-8-sig")))
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise ValueError("El archivo .wksim está dañado o no contiene JSON UTF-8 válido.") from exc
