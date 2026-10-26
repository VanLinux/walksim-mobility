"""Presencia exacta en el periodo, cohortes completas y series de intervalos."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from statistics import fmean

from walksim.domain.analysis import space_los


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(values) - 1) * p
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def summarize(path, analytical: dict, generated: dict[str, int]) -> dict:
    x = analytical["inputs"]
    start = x["warmup_s"]
    duration = x["duration_s"]
    end = start + duration
    area = analytical["resolved"]["length_m"] * analytical["resolved"]["width_m"]
    bin_s = x["bin_s"]
    bins = math.ceil(duration / bin_s)
    occupied = [0.0] * bins
    entered = [0] * bins
    exited = [0] * bins
    exit_speeds: list[list[float]] = [[] for _ in range(bins)]
    by_direction = {"ab": [], "ba": []}
    events = []
    started = completed = pending = 0
    for _event, person in ET.iterparse(path, events=("end",)):
        if person.tag != "personinfo":
            continue
        walk = person.find("walk")
        if walk is None:
            person.clear()
            continue
        depart = float(walk.get("depart", "-1"))
        arrival = float(walk.get("arrival", "-1"))
        route = float(walk.get("routeLength", "0"))
        elapsed = float(walk.get("duration", "0"))
        loss = float(walk.get("timeLoss", "0"))
        direction = "ba" if person.get("id", "").startswith("BA") else "ab"
        if depart >= 0:
            started += 1
            if arrival < 0:
                pending += 1
            else:
                completed += 1
            if start <= depart < end:
                entered[min(bins - 1, int((depart - start) // bin_s))] += 1
                if arrival >= 0 and elapsed > 0:
                    by_direction[direction].append((elapsed, route, loss))
            if start <= arrival < end:
                i = min(bins - 1, int((arrival - start) // bin_s))
                exited[i] += 1
                if elapsed > 0:
                    exit_speeds[i].append(route / elapsed)
            left, right = max(start, depart), min(end, arrival if arrival >= 0 else end)
            if right > left:
                events.extend(((left, 1), (right, -1)))
                first = max(0, int((left - start) // bin_s))
                last = min(bins - 1, math.ceil((right - start) / bin_s) - 1)
                for i in range(first, last + 1):
                    occupied[i] += max(
                        0, min(right, start + (i + 1) * bin_s) - max(left, start + i * bin_s)
                    )
        person.clear()
    people = maximum = 0
    for _time, delta in sorted(events):
        people += delta
        maximum = max(maximum, people)
    series = []
    for i in range(bins):
        dt = min(bin_s, duration - i * bin_s)
        n = occupied[i] / dt
        series.append(
            dict(
                time_s=i * bin_s,
                interval_s=dt,
                occupancy=n,
                density=n / area,
                entered=entered[i],
                exited=exited[i],
                flow_pph=exited[i] * 3600 / dt,
                speed_mps=fmean(exit_speeds[i]) if exit_speeds[i] else None,
            )
        )
    summaries = {}
    for name, records in {**by_direction, "total": by_direction["ab"] + by_direction["ba"]}.items():
        times = [r[0] for r in records]
        summaries[name] = dict(
            count=len(records),
            mean_s=fmean(times) if times else None,
            min_s=min(times) if times else None,
            max_s=max(times) if times else None,
            p50_s=percentile(times, 0.5),
            p85_s=percentile(times, 0.85),
            p95_s=percentile(times, 0.95),
            spatial_speed_mps=(sum(r[1] for r in records) / sum(times)) if times else None,
            mean_speed_mps=fmean([r[1] / r[0] for r in records]) if records else None,
            mean_loss_s=fmean([r[2] for r in records]) if records else None,
        )
    density = sum(occupied) / (duration * area)
    space = 1 / density if density else None
    total = summaries["total"]
    warnings = list(analytical["warnings"])
    if pending or started < sum(generated.values()):
        warnings.append("Quedan recorridos pendientes o sin iniciar al terminar el despeje.")
    cohort_entries = sum(entered)
    if total["count"] < cohort_entries:
        warnings.append(
            "La cohorte está censurada: las estadísticas de tiempo excluyen "
            "recorridos que no terminaron durante el despeje."
        )
    los = space_los(space, analytical["thresholds"])
    metrics = dict(
        generated=sum(generated.values()),
        started=started,
        completed=completed,
        unfinished=pending,
        not_started=sum(generated.values()) - started,
        cohort_entered=cohort_entries,
        cohort_completed=total["count"],
        mean_occupancy=sum(occupied) / duration,
        max_occupancy=maximum,
        density=density,
        space=space,
        los_indicative=los,
        entered_pph=cohort_entries * 3600 / duration,
        exited_pph=sum(exited) * 3600 / duration,
    )
    a = analytical["metrics"]
    pairs = [
        (
            "Velocidad espacial de cohorte",
            "m/s",
            a["Velocidad de entrada (m/s)"],
            total["spatial_speed_mps"],
        ),
        ("Densidad media global", "peat/m²", a["Densidad estimada (peat/m²)"], density),
        ("Espacio equivalente global", "m²/peat", a["Espacio estimado (m²/peatón)"], space),
        ("LOS por espacio / indicativo", "", a["LOS por espacio"], los),
        (
            "Tiempo de recorrido comparable",
            "s",
            (analytical["resolved"]["length_m"] - 0.2) / x["speed_mps"],
            total["mean_s"],
        ),
        (
            "Tasa de entrada al periodo",
            "peat/h",
            a["Demanda de diseño (peat/h)"],
            metrics["entered_pph"],
        ),
    ]
    comparison = []
    for label, unit, estimated, observed in pairs:
        change = None
        if isinstance(estimated, (int, float)) and estimated and isinstance(observed, (int, float)):
            change = 100 * (observed - estimated) / estimated
        comparison.append(
            dict(label=label, unit=unit, analytical=estimated, simulated=observed, delta_pct=change)
        )
    return dict(
        summary=metrics,
        directions=summaries,
        series=series,
        travel_times_s=[r[0] for r in by_direction["ab"] + by_direction["ba"]],
        comparison=comparison,
        warnings=warnings,
        definitions=[
            "Ocupación y densidad: integrales exactas de presencia en el periodo posterior "
            "al calentamiento; superficie global L × ancho útil.",
            "Tiempos y velocidades: peatones que entran en el periodo observado y "
            "terminan antes del fin del despeje (cohorte).",
            "La velocidad temporal graficada corresponde a recorridos finalizados en "
            "cada intervalo; no es velocidad instantánea de todos los peatones.",
            "El LOS simulado es indicativo del espacio global; no mide el punto crítico local.",
            "El tiempo comparable usa L − 0.20 m, el recorrido efectivo entre posiciones "
            "de salida y llegada. El tiempo nominal analítico usa L.",
            "La velocidad de entrada es una hipótesis de referencia, no una predicción "
            "calibrada. Las diferencias no representan por sí solas error o validación.",
        ],
    )
