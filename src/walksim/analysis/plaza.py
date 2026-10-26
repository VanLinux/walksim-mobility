"""Estadísticos OD y mapas derivados de posiciones FCD, sin cargar trayectorias completas."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter
from statistics import fmean

from walksim.analysis.walkway import percentile
from walksim.domain.plaza import PORTS, area, grid, inside, polygon, ports


def summarize(person_path, position_path, x, entries):
    start, stop = x.warmup_s, x.warmup_s + x.duration_s
    final = stop + x.clearance_s
    generated = {ident: t for t, ident in entries}
    cohort = {ident for ident, t in generated.items() if start <= t < stop}
    by_od = {
        (p, q): []
        for p in ports(x)
        for q in ports(x)
        if p != q and x.od[PORTS.index(p)][PORTS.index(q)] > 0
    }
    counts = Counter(tuple(ident.split(".")[:2]) for ident in generated)
    finished = Counter()
    started = completed = 0
    cohort_values = []
    finish_times = []
    for _event, person in ET.iterparse(person_path, events=("end",)):
        if person.tag != "personinfo":
            continue
        ident = person.get("id")
        walk = person.find("walk")
        if ident in generated and walk is not None:
            depart = float(walk.get("depart", "-1"))
            arrival = float(walk.get("arrival", "-1"))
            if depart >= 0:
                started += 1
            if 0 <= arrival < final:
                completed += 1
                finish_times.append(arrival)
                pair = tuple(ident.split(".")[:2])
                finished[pair] += 1
                if ident in cohort:
                    # Includes any insertion delay after the requested generation time.
                    duration = arrival - generated[ident]
                    row = (
                        duration,
                        float(walk.get("routeLength", "0")),
                        max(0.0, float(walk.get("timeLoss", "0"))),
                    )
                    by_od[pair].append(row)
                    cohort_values.append(row)
        person.clear()
    cells = grid(x)
    n = len(cells)
    seconds = [0.0] * n
    maximum = [0] * n
    visitors = [set() for _ in range(n)]
    nx, ny = math.ceil(x.length_m / x.cell_m), math.ceil(x.height_m / x.cell_m)
    dx, dy = x.length_m / nx, x.height_m / ny
    bins = math.ceil(x.duration_s / x.bin_s)
    occupied = [0.0] * bins
    max_global = outside = 0
    context = ET.iterparse(position_path, events=("start", "end"))
    _event, root = next(context)
    for event, frame in context:
        if event != "end" or frame.tag != "timestep":
            continue
        t = float(frame.get("time"))
        left, right = max(t, start), min(t + 1, stop)
        if right > left:
            counts_cell = Counter()
            for person in frame.findall("person"):
                px, py = float(person.get("x")), float(person.get("y"))
                if not inside(x, px, py):
                    if person.get("edge", "").startswith(":J_"):
                        outside += 1
                    continue
                ix = min(nx - 1, max(0, int((px + x.length_m / 2) / dx)))
                iy = min(ny - 1, max(0, int((py + x.height_m / 2) / dy)))
                index = iy * nx + ix
                if cells[index]["area_m2"] <= 1e-9:
                    outside += 1
                    continue
                counts_cell[index] += 1
                visitors[index].add(person.get("id"))
            total = sum(counts_cell.values())
            max_global = max(max_global, total)
            for i, count in counts_cell.items():
                seconds[i] += count * (right - left)
                maximum[i] = max(maximum[i], count)
            lo = left
            while lo < right - 1e-10:
                k = min(bins - 1, int((lo - start + 1e-9) // x.bin_s))
                hi = min(right, start + (k + 1) * x.bin_s)
                occupied[k] += total * (hi - lo)
                lo = hi
        root.clear()
    for i, c in enumerate(cells):
        ar = c["area_m2"]
        c.update(
            person_seconds=seconds[i],
            mean_density=seconds[i] / (x.duration_s * ar) if ar > 1e-9 else 0.0,
            max_density=maximum[i] / ar if ar > 1e-9 else 0.0,
            visitors=len(visitors[i]),
            mean_stay_s=seconds[i] / len(visitors[i]) if visitors[i] else 0.0,
        )
    ar = area(polygon(x))
    series = []
    for k, value in enumerate(occupied):
        dt = min(x.bin_s, x.duration_s - k * x.bin_s)
        series.append(
            dict(time_s=k * x.bin_s, interval_s=dt, occupancy=value / dt, density=value / dt / ar)
        )

    def stats(rows):
        return dict(
            mean_trip_s=fmean(r[0] for r in rows) if rows else None,
            p95_trip_s=percentile([r[0] for r in rows], 0.95),
            spatial_speed_mps=sum(r[1] for r in rows) / sum(r[0] for r in rows) if rows else None,
            mean_loss_s=fmean(r[2] for r in rows) if rows else None,
        )

    od = []
    for (p, q), rows in by_od.items():
        od.append(
            dict(
                origin=p,
                destination=q,
                rate_pph=x.od[PORTS.index(p)][PORTS.index(q)],
                generated=counts[p, q],
                completed=finished[p, q],
                cohort_completed=len(rows),
                **stats(rows),
            )
        )
    summary = dict(
        generated=len(generated),
        started=started,
        completed=completed,
        pending=len(generated) - completed,
        cohort_generated=len(cohort),
        cohort_completed=len(cohort_values),
        completed_pct=100 * completed / len(generated) if generated else None,
        **stats(cohort_values),
        mean_occupancy=sum(seconds) / x.duration_s,
        max_occupancy=max_global,
        mean_density=sum(seconds) / x.duration_s / ar,
        max_cell_density=max((c["max_density"] for c in cells), default=0.0),
        outside_samples=outside,
        clearance_s=max(0.0, max(finish_times, default=stop) - stop)
        if completed == len(generated)
        else None,
    )
    critical = sorted(
        [i for i, c in enumerate(cells) if c["visitors"]],
        key=lambda i: cells[i]["mean_density"],
        reverse=True,
    )[:5]
    return dict(summary=summary, od=od, cells=cells, series=series, critical_cells=critical)
