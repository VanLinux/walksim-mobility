"""Ejecución de netconvert y SUMO sin exponerlos al usuario."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from walksim.domain.models import CorridorScenario, SimulationResult
from walksim.sumo.generator import ScenarioFiles, build_corridor_files
from walksim.sumo.parser import corridor_measurements, parse_personinfo
from walksim.sumo.runtime import engine_version, find_sumo_tool, run_native


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
    engine_version: str = "No registrada"
    measurements: dict = field(default_factory=dict)


class SumoExecutionError(RuntimeError):
    """Error al generar o ejecutar un escenario SUMO."""


def detect_sumo() -> SumoInstallation:
    return SumoInstallation(
        sumo=find_sumo_tool("sumo"),
        netconvert=find_sumo_tool("netconvert"),
    )


def _run_command(command: list[str], cwd: Path, label: str) -> None:
    completed = run_native(command, cwd=cwd, timeout=180)
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
            "--tripinfo-output.write-unfinished",
            "true",
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

    version = engine_version(str(installation.sumo))
    return SimulationRun(
        engine_version=version,
        measurements=corridor_measurements(
            files.personinfo, scenario.length_m, scenario.width_m, scenario.analysis_time_s
        ),
        result=parse_personinfo(files.personinfo),
        files=files,
    )
