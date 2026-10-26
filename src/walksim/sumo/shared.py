"""Sendero mixto: bicicletas-vehículo y peatones comparten dos mitades direccionales."""

from __future__ import annotations

import math
import random
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from walksim.analysis.shared import summarize
from walksim.domain.shared import SharedInput, evaluate_shared, flows
from walksim.sumo.generator import _write_xml
from walksim.sumo.runner import SumoExecutionError, _run_command, detect_sumo
from walksim.sumo.walkway import generate_arrivals


def generate_entries(x):
    duration = x.warmup_s + x.duration_s
    q = flows(x)
    expected = sum(q.values()) * duration / 3600
    if expected > 5000 or expected * (duration + x.clearance_s) > 2_000_000:
        raise ValueError(
            "Reduzca demanda o periodos: máximo 5000 usuarios "
            "y 2 millones de usuario·s potenciales."
        )
    entries = []
    for i, (g, rate) in enumerate(q.items()):
        if not rate:
            continue
        rng = random.Random(x.seed + 100 + i)
        times = (
            generate_arrivals(rate, duration, x.seed + i)
            if x.arrival == "random"
            else [
                (j + 0.5) * 3600 / rate
                for j in range(math.ceil(duration * rate / 3600))
                if (j + 0.5) * 3600 / rate < duration
            ]
        )
        mu = x.ped_speed if g.startswith("P") else x.bike_speed
        sd = (x.ped_sd if g.startswith("P") else x.bike_sd) if x.task != "ped" else 0
        for j, t in enumerate(times):
            speed = min(15.0, max(0.2, rng.gauss(mu, sd))) if sd else mu
            entries.append((t, g + "." + str(j), speed))
    if len(entries) > 5000:
        raise ValueError("La realización supera 5000 usuarios.")
    return sorted(entries)


def run_shared_simulation(raw, output_dir=None):
    a = evaluate_shared(raw)
    x = SharedInput.parse(raw)
    entries = generate_entries(x)
    installation = detect_sumo()
    if not installation.available:
        raise SumoExecutionError("Faltan sumo o netconvert en PATH.")
    folder = Path(output_dir or mkdtemp(prefix="walksim-shared-"))
    folder.mkdir(parents=True, exist_ok=True)
    nodes = ET.Element("nodes")
    ET.SubElement(nodes, "node", id="A", x="0", y="0")
    ET.SubElement(nodes, "node", id="B", x=str(x.length_m), y="0")
    edges = ET.Element("edges")
    for d, fr, to, opp in [("AB", "A", "B", "BA"), ("BA", "B", "A", "AB")]:
        e = ET.SubElement(
            edges,
            "edge",
            id=d,
            attrib={
                "from": fr,
                "to": to,
                "numLanes": "1",
                "width": str(x.width_m / 2),
                "allow": "pedestrian bicycle",
                "speed": "15",
            },
        )
        ET.SubElement(e, "neigh", lane=opp + "_0")
    _write_xml(nodes, folder / "nodes.xml")
    _write_xml(edges, folder / "edges.xml")
    _run_command(
        [installation.netconvert, "-n", "nodes.xml", "-e", "edges.xml", "-o", "network.xml"],
        folder,
        "netconvert",
    )
    routes = ET.Element("routes")
    for i, (_t, ident, speed) in enumerate(entries):
        mode = ident[0]
        attrs = dict(
            id="u" + str(i),
            vClass="pedestrian" if mode == "P" else "bicycle",
            maxSpeed=str(speed),
            speedFactor="1",
            speedDev="0",
        )
        if mode == "B":
            attrs.update(
                desiredMaxSpeed=str(speed),
                carFollowModel="IDM",
                latAlignment="right",
                minGapLat="0.3",
                length="1.6",
                width=".65",
            )
        ET.SubElement(routes, "vType", **attrs)
    for d in ["AB", "BA"]:
        ET.SubElement(routes, "route", id=d, edges=d)
    for i, (t, ident, _speed) in enumerate(entries):
        direction = ident.split(".")[1]
        if ident.startswith("B"):
            ET.SubElement(
                routes,
                "vehicle",
                id=ident,
                type="u" + str(i),
                route=direction,
                depart=f"{t:.6f}",
                departSpeed="max",
            )
        else:
            p = ET.SubElement(
                routes, "person", id=ident, type="u" + str(i), depart=f"{t:.6f}", departPos=".1"
            )
            ET.SubElement(p, "walk", edges=direction, arrivalPos=str(x.length_m - 0.1))
    _write_xml(routes, folder / "routes.xml")
    final = x.warmup_s + x.duration_s + x.clearance_s
    _run_command(
        [
            installation.sumo,
            "-n",
            "network.xml",
            "-r",
            "routes.xml",
            "--end",
            str(math.ceil(final * 2) / 2),
            "--step-length",
            ".5",
            "--lateral-resolution",
            ".3",
            "--collision.action",
            "warn",
            "--collision-output",
            "collisions.xml",
            "--time-to-teleport",
            "-1",
            "--pedestrian.striping.jamtime",
            "1000000",
            "--pedestrian.striping.mingap-to-vehicle",
            "0.5",
            "--pedestrian.model",
            "striping",
            "--personinfo-output",
            "persons.xml",
            "--tripinfo-output",
            "trips.xml",
            "--tripinfo-output.write-unfinished",
            "true",
            "--fcd-output",
            "positions.xml",
            "--seed",
            str(x.seed),
            "--no-step-log",
            "true",
        ],
        folder,
        "SUMO",
    )
    if not any(p.startswith("P") for _t, p, _s in entries):
        _write_xml(ET.Element("tripinfos"), folder / "persons.xml")
    if not any(p.startswith("B") for _t, p, _s in entries):
        _write_xml(ET.Element("tripinfos"), folder / "trips.xml")
    if any(not (folder / p).exists() for p in ["persons.xml", "trips.xml", "positions.xml"]):
        raise SumoExecutionError("Faltan salidas del escenario mixto.")
    data = summarize(
        folder / "trips.xml", folder / "persons.xml", folder / "positions.xml", x, entries
    )
    warnings = []
    collision_file = folder / "collisions.xml"
    collisions = (
        len(ET.parse(collision_file).findall("collision")) if collision_file.exists() else 0
    )
    if collisions:
        warnings.append(
            f"SUMO registró {collisions} colisiones o solapamientos numéricos. "
            "Revise parámetros y alcance del modelo antes de interpretar los eventos."
        )
    if data["summary"]["pending"]:
        warnings.append(
            "Quedan usuarios pendientes: la cohorte completada puede subestimar los tiempos."
        )
    if not entries:
        warnings.append("Demanda nula: no hay muestra de tiempos ni tasas de eventos.")
    warnings.append(
        "Los eventos simulados no sustituyen la probabilidad documentada usada en BLOS."
    )
    version = subprocess.run(
        [installation.sumo, "--version"], capture_output=True, text=True, timeout=10, check=False
    ).stdout.splitlines()
    return dict(
        **data,
        inputs=x.to_dict(),
        signature=a["signature"],
        analytical=a,
        engine_version=version[0] if version else "?",
        created_at=datetime.now(UTC).isoformat(),
        sample_s=0.5,
        collisions=collisions,
        model="striping + sublane / IDM",
        warnings=warnings,
    )
