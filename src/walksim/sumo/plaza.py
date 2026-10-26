"""Una red peatonal común con área de circulación y accesos bidireccionales."""

from __future__ import annotations

import math
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from walksim.analysis.plaza import summarize
from walksim.domain.plaza import PORTS, PlazaInput, evaluate_plaza, polygon, ports
from walksim.sumo.generator import _write_xml
from walksim.sumo.runner import SumoExecutionError, _run_command, detect_sumo
from walksim.sumo.walkway import generate_arrivals


def generate_entries(x):
    duration = x.warmup_s + x.duration_s
    expected = sum(map(sum, x.od)) * duration / 3600
    if expected > 10000 or expected * (duration + x.clearance_s) > 5_000_000:
        raise ValueError(
            "Escenario demasiado grande: reduzca demanda o periodos. "
            "Límites: 10 000 personas y 5 millones de persona·s potenciales."
        )
    entries = []
    for i, p in enumerate(PORTS):
        for j, q in enumerate(PORTS):
            rate = x.od[i][j]
            if not rate:
                continue
            if x.arrival == "random":
                times = generate_arrivals(rate, duration, x.seed + i * 4 + j)
            else:
                gap = 3600 / rate
                times = [
                    (k + 0.5) * gap
                    for k in range(math.ceil(duration / gap))
                    if (k + 0.5) * gap < duration
                ]
            entries.extend((t, f"{p}.{q}.{k}") for k, t in enumerate(times))
    if len(entries) > 10000:
        raise ValueError("La realización supera 10 000 personas; reduzca la demanda.")
    return sorted(entries)


def build_network(x, folder, installation):
    branched = x.template in {"cross", "tee"}
    w = x.arm_m / 2
    poly = [(-w, -w), (w, -w), (w, w), (-w, w)] if branched else polygon(x)
    shape = " ".join(f"{px:.6f},{py:.6f}" for px, py in poly)
    nodes = ET.Element("nodes")
    ET.SubElement(nodes, "node", id="J", x="0", y="0", type="priority", shape=shape)
    edges = ET.Element("edges")
    coords = dict(
        N=(0, x.height_m / 2 + x.approach_m),
        S=(0, -x.height_m / 2 - x.approach_m),
        E=(x.length_m / 2 + x.approach_m, 0),
        W=(-x.length_m / 2 - x.approach_m, 0),
    )
    selected = ports(x)
    for p in selected:
        px, py = coords[p]
        ET.SubElement(nodes, "node", id=p, x=str(px), y=str(py))
        if branched:
            bx, by = (
                (0, x.height_m / 2 if p == "N" else -x.height_m / 2)
                if p in {"N", "S"}
                else (x.length_m / 2 if p == "E" else -x.length_m / 2, 0)
            )
            ET.SubElement(nodes, "node", id="B_" + p, x=str(bx), y=str(by))
            ET.SubElement(
                edges,
                "edge",
                id=p + "_inner",
                attrib={
                    "from": "B_" + p,
                    "to": "J",
                    "allow": "pedestrian",
                    "width": str(x.arm_m),
                    "spreadType": "center",
                },
            )
        ET.SubElement(
            edges,
            "edge",
            id=p,
            attrib={
                "from": p,
                "to": "B_" + p if branched else "J",
                "allow": "pedestrian",
                "width": str(getattr(x, "width_" + p.lower() + "_m")),
                "spreadType": "center",
            },
        )
    connections = ET.Element("connections")
    ET.SubElement(
        connections,
        "walkingArea",
        node="J",
        edges=selected[0] + "_inner" if branched else selected[0],
        shape=shape,
        width=str(x.arm_m if x.template in {"cross", "tee"} else min(x.length_m, x.height_m)),
    )
    for name, root in [("nodes", nodes), ("edges", edges), ("connections", connections)]:
        _write_xml(root, folder / (name + ".xml"))
    _run_command(
        [
            installation.netconvert,
            "-n",
            "nodes.xml",
            "-e",
            "edges.xml",
            "-x",
            "connections.xml",
            "-o",
            "network.xml",
            "--walkingareas",
            "true",
            "--offset.disable-normalization",
            "true",
        ],
        folder,
        "netconvert",
    )
    net = ET.parse(folder / "network.xml")
    areas = [
        e for e in net.findall("edge[@function='walkingarea']") if e.get("id").startswith(":J_")
    ]
    if len(areas) != 1:
        raise SumoExecutionError("No se pudo construir el área peatonal común de la plantilla.")
    lane = areas[0].find("lane")
    actual = [tuple(map(float, p.split(",")[:2])) for p in lane.get("shape").split()]
    if len(actual) != len(poly) or any(
        abs(a - b) > 0.011
        for p, q in zip(actual, poly, strict=True)
        for a, b in zip(p, q, strict=True)
    ):
        raise SumoExecutionError("La geometría generada no coincide con la plantilla solicitada.")


def run_plaza_simulation(raw, output_dir=None):
    a = evaluate_plaza(raw)
    x = PlazaInput.parse(raw)
    entries = generate_entries(x)
    installation = detect_sumo()
    if not installation.available:
        raise SumoExecutionError("Faltan sumo o netconvert en PATH.")
    folder = Path(output_dir or mkdtemp(prefix="walksim-plaza-"))
    folder.mkdir(parents=True, exist_ok=True)
    build_network(x, folder, installation)
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
    for t, ident in entries:
        origin, destination, _i = ident.split(".")
        person = ET.SubElement(
            root, "person", id=ident, type="pedestrian", depart=f"{t:.6f}", departPos="0.1"
        )
        route = (
            [origin, origin + "_inner", destination + "_inner", destination]
            if x.template in {"cross", "tee"}
            else [origin, destination]
        )
        ET.SubElement(person, "walk", edges=" ".join(route), arrivalPos="0.1")
    _write_xml(root, folder / "routes.xml")
    final = x.warmup_s + x.duration_s + x.clearance_s
    _run_command(
        [
            installation.sumo,
            "-n",
            "network.xml",
            "-r",
            "routes.xml",
            "--end",
            str(math.ceil(final)),
            "--step-length",
            "1",
            "--pedestrian.model",
            "striping",
            "--personinfo-output",
            "persons.xml",
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
    # SUMO creates personinfo lazily; a zero-demand run produces no such file.
    if not entries:
        _write_xml(ET.Element("tripinfos"), folder / "persons.xml")
    if not (folder / "persons.xml").exists() or not (folder / "positions.xml").exists():
        raise SumoExecutionError("La ejecución no generó las salidas peatonales necesarias.")
    result = summarize(folder / "persons.xml", folder / "positions.xml", x, entries)
    version = subprocess.run(
        [installation.sumo, "--version"], capture_output=True, text=True, timeout=10, check=False
    ).stdout.splitlines()
    warnings = []
    if result["summary"]["pending"]:
        warnings.append(
            "Quedan recorridos pendientes al límite de despeje. La cohorte completada "
            "puede subestimar los tiempos del conjunto."
        )
    if result["summary"]["outside_samples"]:
        warnings.append(
            "Se detectaron posiciones del área común fuera del polígono. Se excluyen "
            "del mapa; revise la aproximación geométrica del motor "
            "antes de interpretar zonas críticas."
        )
    if not entries:
        warnings.append("Demanda realizada nula: no hay muestra de tiempos ni velocidades.")
    return dict(
        **result,
        inputs=x.to_dict(),
        signature=a["signature"],
        analytical=a,
        created_at=datetime.now(UTC).isoformat(),
        engine_version=version[0] if version else "?",
        model="striping",
        sample_s=1,
        warnings=warnings,
    )
