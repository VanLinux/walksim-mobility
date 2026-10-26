"""Escenarios Walkway 3 con llegadas aleatorias o pulsos reproducibles."""

from __future__ import annotations

import random
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from walksim.analysis.walkway import summarize
from walksim.domain.models import CorridorScenario
from walksim.domain.walkway import evaluate_walkway
from walksim.sumo.generator import _write_xml, build_corridor_files
from walksim.sumo.runner import SumoExecutionError, _run_command, detect_sumo


def generate_arrivals(
    rate_pph: float, duration: float, seed: int, cycle: float = 0, release: float = 0
) -> list[float]:
    if not rate_pph:
        return []
    rng = random.Random(seed)
    time = 0.0
    arrivals = []
    while True:
        time += rng.expovariate(rate_pph / 3600)
        if time >= duration:
            return arrivals
        mapped = (int(time // cycle) * cycle + time % cycle * release / cycle) if cycle else time
        arrivals.append(mapped)
        if len(arrivals) > 100000:
            raise ValueError("Más de 100 000 peatones por sentido; reduzca la demanda o duración.")


def run_walkway_simulation(raw: dict, output_dir=None) -> dict:
    analytical = evaluate_walkway(raw)
    x = analytical["inputs"]
    scenario = CorridorScenario(**analytical["resolved"])
    errors = scenario.validate()
    if errors:
        raise ValueError("Escenario fuera del alcance de microsimulación: " + " ".join(errors))
    if scenario.analysis_time_s * (scenario.flow_ab_pph + scenario.flow_ba_pph) / 3600 > 100000:
        raise ValueError("Use menos de 100 000 peatones esperados por simulación.")
    installation = detect_sumo()
    if not installation.available:
        raise SumoExecutionError("Faltan sumo o netconvert en PATH. Revise la instalación.")
    files = build_corridor_files(scenario, output_dir)
    root = ET.Element("routes")
    ET.SubElement(
        root,
        "vType",
        id="pedestrian",
        vClass="pedestrian",
        maxSpeed=f"{x['speed_mps']:.6f}",
        speedFactor="1",
        speedDev="0",
    )
    entries = []
    generated = {}
    cycle = x["platoon_cycle_s"] if x["flow_type"] == "platoon" else 0
    release = x["platoon_release_s"]
    for direction, rate, offset in [
        ("AB", scenario.flow_ab_pph, 0),
        ("BA", scenario.flow_ba_pph, 1),
    ]:
        times = generate_arrivals(
            rate, scenario.analysis_time_s, x["seed"] + offset, cycle, release
        )
        generated[direction] = len(times)
        entries += [(time, direction, i) for i, time in enumerate(times)]
    for depart, direction, i in sorted(entries):
        begin, end = (
            (0.1, scenario.length_m - 0.1) if direction == "AB" else (scenario.length_m - 0.1, 0.1)
        )
        person = ET.SubElement(
            root,
            "person",
            id=f"{direction}.{i}",
            type="pedestrian",
            depart=f"{depart:.6f}",
            departPos=f"{begin:.6f}",
        )
        ET.SubElement(person, "walk", edges="corridor", arrivalPos=f"{end:.6f}")
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
            "--pedestrian.model",
            "striping",
            "--personinfo-output",
            files.personinfo.name,
            "--tripinfo-output.write-unfinished",
            "true",
            "--statistic-output",
            files.statistics.name,
            "--seed",
            str(x["seed"]),
            "--no-step-log",
            "true",
        ],
        files.workdir,
        "SUMO",
    )
    if not files.personinfo.exists():
        raise SumoExecutionError("La simulación no generó resultados peatonales.")
    version = subprocess.run(
        [installation.sumo, "--version"], capture_output=True, text=True, timeout=10, check=False
    ).stdout.splitlines()
    data = summarize(files.personinfo, analytical, generated)
    return dict(
        **data,
        inputs=x,
        signature=analytical["signature"],
        analytical=analytical,
        created_at=datetime.now(UTC).isoformat(),
        engine_version=version[0] if version else "?",
        model="striping",
        generated_by_direction=generated,
    )
