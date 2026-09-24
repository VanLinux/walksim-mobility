"""Ejecución de netconvert y SUMO sin exponerlos al usuario."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from walksim.domain.models import CorridorScenario, SimulationResult
from walksim.sumo.generator import ScenarioFiles, build_corridor_files
from walksim.sumo.parser import parse_personinfo


@dataclass(frozen=True, slots=True)
class SumoInstallation:
    sumo: str | None
    netconvert: str | None

    @property
    def available(self) -> bool:
        return bool(self.sumo and self.netconvert)


@dataclass(frozen=True, slots=True)
class SimulationRun:
    result: SimulationResult
    files: ScenarioFiles


class SumoExecutionError(RuntimeError):
    """Error al generar o ejecutar un escenario SUMO."""


def detect_sumo() -> SumoInstallation:
    return SumoInstallation(
        sumo=shutil.which("sumo"),
        netconvert=shutil.which("netconvert"),
    )


def _run_command(command: list[str], cwd: Path, label: str) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "Sin detalle."
        raise SumoExecutionError(f"{label} terminó con error:\n{detail}")


def run_corridor_simulation(
    scenario: CorridorScenario,
    output_dir: str | Path | None = None,
) -> SimulationRun:
    installation = detect_sumo()
    if not installation.available:
        missing = []
        if not installation.sumo:
            missing.append("sumo")
        if not installation.netconvert:
            missing.append("netconvert")
        raise SumoExecutionError(
            "No se encontraron en PATH los ejecutables requeridos: " + ", ".join(missing)
        )

    files = build_corridor_files(scenario, output_dir)

    _run_command(
        [
            str(installation.netconvert),
            "--node-files",
            files.nodes.name,
            "--edge-files",
            files.edges.name,
            "--output-file",
            files.network.name,
        ],
        files.workdir,
        "netconvert",
    )

    _run_command(
        [
            str(installation.sumo),
            "-c",
            files.config.name,
            "--pedestrian.model",
            "striping",
            "--personinfo-output",
            files.personinfo.name,
            "--statistic-output",
            files.statistics.name,
            "--seed",
            str(scenario.seed),
            "--no-step-log",
            "true",
        ],
        files.workdir,
        "SUMO",
    )

    if not files.personinfo.exists():
        raise SumoExecutionError("SUMO finalizó sin generar personinfo.xml.")

    return SimulationRun(
        result=parse_personinfo(files.personinfo),
        files=files,
    )
