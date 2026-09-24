"""Procesamiento de resultados peatonales de SUMO."""

from __future__ import annotations

from pathlib import Path
from statistics import fmean
import xml.etree.ElementTree as ET

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
        length / duration
        for duration, length, _ in records
        if duration > 0.0 and length >= 0.0
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
