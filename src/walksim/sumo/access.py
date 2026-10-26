"""Microsimulación híbrida de recorridos SUMO y atención FCFS por eventos."""

from __future__ import annotations

import bisect
import heapq
import math
import random
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from walksim.analysis.walkway import percentile
from walksim.domain.access import AccessInput, evaluate_access, stages
from walksim.domain.models import CorridorScenario
from walksim.sumo.generator import _write_xml, build_corridor_files
from walksim.sumo.runner import SumoExecutionError, _run_command, detect_sumo
from walksim.sumo.walkway import generate_arrivals

MAX_PEOPLE = 10000


def arrivals(x):
    horizon = x.warmup_s + x.duration_s
    if x.arrival == "batch":
        if math.ceil(horizon / x.cycle_s) * x.passengers > MAX_PEOPLE:
            raise ValueError("Reduzca las descargas o el periodo a un máximo de 10 000 peatones.")
        times = [
            c * x.cycle_s + (i + 0.5) * x.release_s / x.passengers
            for c in range(math.ceil(horizon / x.cycle_s))
            for i in range(x.passengers)
        ]
        times = [t for t in times if t < horizon]
    elif not x.rate_pph:
        times = []
    elif x.arrival == "uniform":
        step = 3600 / x.rate_pph
        if horizon / step > MAX_PEOPLE:
            raise ValueError("Máximo 10 000 peatones por escenario.")
        times = [
            (i + 0.5) * step for i in range(math.ceil(horizon / step)) if (i + 0.5) * step < horizon
        ]
    else:
        if x.rate_pph * horizon / 3600 > MAX_PEOPLE:
            raise ValueError("Máximo 10 000 peatones esperados por escenario.")
        times = generate_arrivals(
            x.rate_pph,
            horizon,
            x.seed,
            x.cycle_s if x.arrival == "intermittent" else 0,
            x.release_s,
        )
    if len(times) > MAX_PEOPLE:
        raise ValueError("La realización excede 10 000 peatones; reduzca la demanda.")
    return {str(i): t for i, t in enumerate(times)}


def serve(entries, servers, mean_s, seed, exponential=False):
    """Una fila FCFS común; cada servidor atiende una persona a la vez."""
    free = [(0.0, i) for i in range(servers)]
    heapq.heapify(free)
    rng, rows = random.Random(seed), {}
    for person, arrival in sorted(entries.items(), key=lambda r: (r[1], int(r[0]))):
        available, server = heapq.heappop(free)
        start = max(arrival, available)
        duration = rng.expovariate(1 / mean_s) if exponential else mean_s
        end = start + duration
        rows[person] = (arrival, start, end)
        heapq.heappush(free, (end, server))
    return rows


class Integral:
    """Integral exacta de una ocupación escalonada, agrupando eventos simultáneos."""

    def __init__(self, intervals):
        events = defaultdict(int)
        for start, end in intervals:
            if end > start:
                events[start] += 1
                events[end] -= 1
        self.times, self.areas, self.values = [0.0], [0.0], [0]
        for t, delta in sorted(events.items()):
            area = self.areas[-1] + (t - self.times[-1]) * self.values[-1]
            self.times.append(t)
            self.areas.append(area)
            self.values.append(self.values[-1] + delta)

    def area(self, t):
        i = bisect.bisect_right(self.times, t) - 1
        return self.areas[i] + (t - self.times[i]) * self.values[i]

    def mean(self, start, end):
        return (self.area(end) - self.area(start)) / (end - start)

    def maximum(self, start, end):
        i = bisect.bisect_right(self.times, start) - 1
        j = bisect.bisect_left(self.times, end)
        return max(self.values[i:j], default=self.values[i])


def _walk(entries, length, x, folder, installation, final):
    if not entries:
        return {}
    scenario = CorridorScenario(
        length_m=length,
        width_m=x.width_m,
        flow_ab_pph=1,
        flow_ba_pph=0,
        walking_speed_mps=x.speed_mps,
        analysis_time_s=max(60, x.warmup_s + x.duration_s),
        seed=x.seed,
    )
    files = build_corridor_files(scenario, folder)
    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        id="pedestrian",
        vClass="pedestrian",
        maxSpeed=str(x.speed_mps),
        speedFactor="1",
        speedDev="0",
    )
    for person, depart in sorted(entries.items(), key=lambda r: (r[1], int(r[0]))):
        p = ET.SubElement(
            root, "person", id=person, type="pedestrian", depart=f"{depart:.6f}", departPos="0.1"
        )
        ET.SubElement(p, "walk", edges="corridor", arrivalPos=f"{length - 0.1:.6f}")
    _write_xml(root, files.routes)
    _run_command(
        [
            installation.netconvert,
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
            installation.sumo,
            "-c",
            files.config.name,
            "--end",
            str(final),
            "--pedestrian.model",
            "striping",
            "--personinfo-output",
            files.personinfo.name,
            "--tripinfo-output.write-unfinished",
            "true",
            "--seed",
            str(x.seed),
            "--no-step-log",
            "true",
        ],
        files.workdir,
        "SUMO",
    )
    output = {}
    for _event, elem in ET.iterparse(files.personinfo, events=("end",)):
        if elem.tag == "personinfo":
            walk = elem.find("walk")
            if walk is not None:
                finish = float(walk.get("arrival", "-1"))
                if 0 <= finish < final:
                    output[elem.get("id")] = finish
            elem.clear()
    return output


def _count(values, lo, hi):
    return bisect.bisect_left(values, hi) - bisect.bisect_left(values, lo)


def run_access_simulation(raw, output_dir=None):
    a = evaluate_access(raw)
    x = AccessInput.parse(raw)
    generated = arrivals(x)
    installation = detect_sumo()
    if not installation.available:
        raise SumoExecutionError("Faltan sumo o netconvert en PATH.")
    folder = Path(output_dir or mkdtemp(prefix="walksim-access-"))
    folder.mkdir(parents=True, exist_ok=True)
    start, stop = x.warmup_s, x.warmup_s + x.duration_s
    final = stop + x.clearance_s
    ready = _walk(generated, x.approach_m, x, folder / "aproximacion", installation, final)
    stage_results, stage_rows, integrals = [], [], []
    waiting_total = defaultdict(float)
    ss = stages(x)
    for index, stage in enumerate(ss):
        rows = serve(
            ready,
            stage["servers"],
            stage["mean_s"],
            x.seed + 100 + index,
            x.service == "exponential",
        )
        stage_rows.append(rows)
        queue = Integral([(arr, min(begin, final)) for arr, begin, _end in rows.values()])
        accumulation = Integral([(arr, min(end, final)) for arr, _begin, end in rows.values()])
        busy = Integral(
            [(begin, min(end, final)) for _arr, begin, end in rows.values() if begin < final]
        )
        integrals.append((queue, accumulation))
        waits = [
            begin - arr
            for arr, begin, _end in rows.values()
            if start <= arr < stop and begin < final
        ]
        completed = {p: end for p, (_arr, _begin, end) in rows.items() if end < final}
        for p, (arr, begin, _end) in rows.items():
            waiting_total[p] += begin - arr
        stage_results.append(
            dict(
                **stage,
                arrived=len(rows),
                processed=len(completed),
                pending=len(rows) - len(completed),
                mean_queue=queue.mean(start, stop),
                max_queue=queue.maximum(start, stop),
                mean_accumulation=accumulation.mean(start, stop),
                max_accumulation=accumulation.maximum(start, stop),
                density=accumulation.mean(start, stop) / stage["area_m2"],
                max_density=accumulation.maximum(start, stop) / stage["area_m2"],
                utilization=busy.mean(start, stop) / stage["servers"],
                mean_wait_s=sum(waits) / len(waits) if waits else None,
                max_wait_s=max(waits) if waits else None,
                p95_wait_s=percentile(waits, 0.95),
                wait_sample=len(waits),
                wait_censored=sum(
                    start <= arr < stop and begin >= final for arr, begin, _end in rows.values()
                ),
                pending_at_observation_end=sum(
                    arr < stop <= end for arr, _begin, end in rows.values()
                ),
            )
        )
        ready = completed
        if index < len(ss) - 1 or (x.layout != "access" and len(ss) == 1):
            ready = _walk(ready, x.transfer_m, x, folder / "vestibulo", installation, final)
    completed = _walk(ready, x.exit_m, x, folder / "salida", installation, final)
    cohort = [p for p, t in generated.items() if start <= t < stop]
    sample = [p for p in cohort if p in completed]
    waits = [waiting_total[p] for p in sample]
    trips = [completed[p] - generated[p] for p in sample]
    gen_times, end_times = sorted(generated.values()), sorted(completed.values())
    system = Integral([(t, completed.get(p, final)) for p, t in generated.items()])
    series = []
    for i in range(math.ceil(x.duration_s / x.bin_s)):
        lo, hi = start + i * x.bin_s, min(stop, start + (i + 1) * x.bin_s)
        row = dict(
            time_s=lo - start,
            interval_s=hi - lo,
            generated=_count(gen_times, lo, hi),
            completed=_count(end_times, lo, hi),
            mean_system=system.mean(lo, hi),
        )
        for stage, (q, occ) in zip(ss, integrals, strict=True):
            row.update(
                {
                    stage["key"] + "_queue": q.mean(lo, hi),
                    stage["key"] + "_density": occ.mean(lo, hi) / stage["area_m2"],
                }
            )
        series.append(row)
    hist = []
    if waits:
        width = max(max(waits) / 20, 1)
        for i in range(20):
            hist.append(
                dict(
                    start_s=i * width,
                    end_s=(i + 1) * width,
                    count=sum(
                        i * width <= w < (i + 1) * width or (i == 19 and w == (i + 1) * width)
                        for w in waits
                    ),
                )
            )
    residuals = []
    if x.arrival == "batch":
        for t in range(1, math.ceil(stop / x.cycle_s)):
            boundary = t * x.cycle_s
            residuals.append(
                dict(
                    time_s=boundary,
                    remaining=bisect.bisect_left(gen_times, boundary)
                    - bisect.bisect_left(end_times, boundary),
                )
            )
    summary = dict(
        generated=len(generated),
        completed=len(completed),
        pending=len(generated) - len(completed),
        cohort_generated=len(cohort),
        cohort_completed=len(sample),
        mean_wait_s=sum(waits) / len(waits) if waits else None,
        max_wait_s=max(waits) if waits else None,
        p95_wait_s=percentile(waits, 0.95),
        mean_trip_s=sum(trips) / len(trips) if trips else None,
        mean_system=system.mean(start, stop),
        max_system=system.maximum(start, stop),
        clearance_s=max(0.0, max(end_times, default=stop) - stop)
        if len(completed) == len(generated)
        else None,
        pending_at_observation_end=sum(
            t < stop <= completed.get(p, final) for p, t in generated.items()
        ),
    )
    warnings = list(a["warnings"])
    if summary["pending"]:
        warnings.append(
            "Quedan personas pendientes al límite de despeje. La espera y el tiempo "
            "de recorrido de la cohorte completada pueden estar sesgados a la baja."
        )
    version = subprocess.run(
        [installation.sumo, "--version"], capture_output=True, text=True, timeout=10, check=False
    ).stdout.splitlines()
    return dict(
        inputs=x.to_dict(),
        signature=a["signature"],
        analytical=a,
        created_at=datetime.now(UTC).isoformat(),
        engine_version=version[0] if version else "?",
        summary=summary,
        stages=stage_results,
        series=series,
        histogram=hist,
        train_residuals=residuals,
        warnings=warnings,
        definitions=a["assumptions"],
    )
