"""Procesamiento de resultados peatonales de SUMO."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import fmean

from walksim.domain.models import DirectionResult, SimulationResult


def _float_attr(element: ET.Element, name: str, default: float = 0.0) -> float:
    raw = element.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _aggregate(records: list[tuple[float, float, float]]) -> DirectionResult:
    if not records:
        return DirectionResult()

    durations = [duration for duration, _, _ in records]
    lengths = [length for _, length, _ in records]
    losses = [loss for _, _, loss in records]
    speeds = [
        length / duration for duration, length, _ in records if duration > 0.0 and length >= 0.0
    ]

    return DirectionResult(
        completed_walks=len(records),
        mean_duration_s=fmean(durations),
        mean_speed_mps=fmean(speeds) if speeds else 0.0,
        mean_time_loss_s=fmean(losses),
        mean_route_length_m=fmean(lengths),
    )


def parse_personinfo(path: str | Path) -> SimulationResult:
    root = ET.parse(Path(path)).getroot()

    ab_records: list[tuple[float, float, float]] = []
    ba_records: list[tuple[float, float, float]] = []

    for person in root.findall(".//personinfo"):
        walk = person.find("walk")
        if walk is None:
            continue

        if _float_attr(walk, "arrival", 0) < 0:
            continue

        duration = _float_attr(walk, "duration")
        if duration <= 0.0:
            depart = _float_attr(walk, "depart")
            arrival = _float_attr(walk, "arrival")
            duration = max(0.0, arrival - depart)

        route_length = _float_attr(walk, "routeLength")
        time_loss = _float_attr(walk, "timeLoss")
        record = (duration, route_length, time_loss)

        person_id = person.get("id", "")
        if person_id.startswith("BA"):
            ba_records.append(record)
        else:
            ab_records.append(record)

    all_records = ab_records + ba_records
    return SimulationResult(
        total=_aggregate(all_records),
        ab=_aggregate(ab_records),
        ba=_aggregate(ba_records),
    )


def corridor_measurements(
    path: str | Path, length_m: float, width_m: float, analysis_time_s: float
) -> dict:
    """Integra presencia durante la demanda, incluyendo recorridos inconclusos."""
    from walksim.domain.analysis import criterion_thresholds, space_los

    person_seconds = 0.0
    started = unfinished = completed_in_period = 0
    events = []
    for person in ET.parse(Path(path)).getroot().findall(".//personinfo"):
        walk = person.find("walk")
        if walk is None:
            continue
        depart = _float_attr(walk, "depart", -1)
        arrival = _float_attr(walk, "arrival", -1)
        if depart < 0:
            continue
        started += 1
        if arrival < 0:
            unfinished += 1
        elif arrival <= analysis_time_s:
            completed_in_period += 1
        start = max(0.0, depart)
        end = min(analysis_time_s, arrival if arrival >= 0 else analysis_time_s)
        if end > start:
            person_seconds += end - start
            events += [(start, 1), (end, -1)]
    present = maximum = 0
    for _time, delta in sorted(events):
        present += delta
        maximum = max(maximum, present)
    mean_count = person_seconds / analysis_time_s
    density = mean_count / (length_m * width_m)
    space = 1 / density if density else None
    return {
        "Peatones con recorrido iniciado": started,
        "Recorridos inconclusos al final del despeje": unfinished,
        "Recorridos completados durante la demanda": completed_in_period,
        "Presencia acumulada durante la demanda (peat·s)": person_seconds,
        "Ocupación media temporal del corredor (peat)": mean_count,
        "Ocupación máxima simultánea global (peat)": maximum,
        "Densidad media temporal global (peat/m²)": density,
        "Espacio equivalente global (m²/peatón)": space,
        "LOS indicativo por espacio global": space_los(space, criterion_thresholds("walkway")),
    }
