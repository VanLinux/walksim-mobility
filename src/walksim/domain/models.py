"""Modelos de datos independientes de la interfaz y de SUMO."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(slots=True)
class ProjectInfo:
    name: str = "Corredor peatonal"
    location: str = ""
    analyst: str = ""
    notes: str = ""


@dataclass(slots=True)
class CorridorScenario:
    length_m: float = 100.0
    width_m: float = 2.5
    flow_ab_pph: float = 600.0
    flow_ba_pph: float = 400.0
    walking_speed_mps: float = 1.34
    analysis_time_s: float = 3600.0
    seed: int = 42

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if not 5.0 <= self.length_m <= 2000.0:
            errors.append("La longitud debe estar entre 5 y 2000 m.")
        if not 0.5 <= self.width_m <= 20.0:
            errors.append("El ancho útil debe estar entre 0.5 y 20 m.")
        if not 0.0 <= self.flow_ab_pph <= 20000.0:
            errors.append("El flujo A → B debe estar entre 0 y 20 000 peat/h.")
        if not 0.0 <= self.flow_ba_pph <= 20000.0:
            errors.append("El flujo B → A debe estar entre 0 y 20 000 peat/h.")
        if self.flow_ab_pph + self.flow_ba_pph <= 0:
            errors.append("Debe existir demanda peatonal en al menos un sentido.")
        if not 0.2 <= self.walking_speed_mps <= 3.0:
            errors.append("La velocidad peatonal debe estar entre 0.2 y 3.0 m/s.")
        if not 60.0 <= self.analysis_time_s <= 28800.0:
            errors.append("El periodo de análisis debe estar entre 1 minuto y 8 horas.")
        if self.seed < 0:
            errors.append("La semilla no puede ser negativa.")
        return tuple(errors)

    @property
    def clearance_time_s(self) -> int:
        free_flow = self.length_m / max(self.walking_speed_mps, 0.2)
        return max(300, ceil(free_flow * 3.0))

    @property
    def simulation_end_s(self) -> int:
        return ceil(self.analysis_time_s) + self.clearance_time_s


@dataclass(frozen=True, slots=True)
class DirectionResult:
    completed_walks: int = 0
    mean_duration_s: float = 0.0
    mean_speed_mps: float = 0.0
    mean_time_loss_s: float = 0.0
    mean_route_length_m: float = 0.0


@dataclass(frozen=True, slots=True)
class SimulationResult:
    total: DirectionResult
    ab: DirectionResult
    ba: DirectionResult
