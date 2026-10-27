"""Cruce aislado con fases excluyentes; red y control generados por SUMO/netconvert."""

from __future__ import annotations

import math
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from walksim.analysis.crossing import summarize
from walksim.domain.crossing import CrossingInput, evaluate_crossing, signature
from walksim.sumo.generator import _write_xml
from walksim.sumo.runner import SumoExecutionError, _run_command, detect_sumo
from walksim.sumo.walkway import generate_arrivals


def generate_entries(x):
    entries = []
    for i, (group, rate) in enumerate(
        [
            ("AB", x.ped_ab),
            ("BA", x.ped_ba),
            ("WE", x.vehicles_ph / 2),
            ("EW", x.vehicles_ph / 2),
        ]
    ):
        for j, t in enumerate(generate_arrivals(rate, x.duration_s, x.seed + i)):
            entries.append((t, group + "." + str(j)))
    if len(entries) > 5000:
        raise ValueError("La realización supera 5000 usuarios; reduzca la demanda.")
    return sorted(entries)


def build_network(x, folder, netconvert):
    nodes = ET.Element("nodes")
    for ident, px, py in [
        ("C", 0, 0),
        ("W", -150, 0),
        ("E", 150, 0),
        ("A", 0, x.length_m / 2 + 20),
        ("B", 0, -x.length_m / 2 - 20),
    ]:
        ET.SubElement(
            nodes,
            "node",
            id=ident,
            x=str(px),
            y=str(py),
            type="traffic_light" if ident == "C" else "priority",
        )
    edges = ET.Element("edges")
    for ident, fr, to in [
        ("WC", "W", "C"),
        ("CE", "C", "E"),
        ("EC", "E", "C"),
        ("CW", "C", "W"),
        ("AC", "A", "C"),
        ("CB", "C", "B"),
    ]:
        ped = ident in ("AC", "CB")
        ET.SubElement(
            edges,
            "edge",
            id=ident,
            attrib={
                "from": fr,
                "to": to,
                "numLanes": "1",
                "allow": "pedestrian" if ped else "passenger",
                "width": str(x.width_m if ped else x.length_m / 2),
                "speed": "3" if ped else str(30 / 3.6),
                "spreadType": "center" if ped else "right",
            },
        )
    con = ET.Element("connections")
    for fr, to in [("WC", "CE"), ("EC", "CW")]:
        ET.SubElement(con, "connection", attrib={"from": fr, "to": to})
    px = -x.width_m / 2 - 2
    ET.SubElement(
        con,
        "crossing",
        node="C",
        edges="WC CW",
        width=str(x.width_m),
        shape=f"{px},{x.length_m / 2} {px},{-x.length_m / 2}",
    )
    for element, name in [(nodes, "nodes.xml"), (edges, "edges.xml"), (con, "connections.xml")]:
        _write_xml(element, folder / name)
    _run_command(
        [
            netconvert,
            "-n",
            "nodes.xml",
            "-e",
            "edges.xml",
            "-x",
            "connections.xml",
            "-o",
            "network.xml",
            "--no-turnarounds",
            "true",
            "--offset.disable-normalization",
            "true",
        ],
        folder,
        "netconvert",
    )
    net = ET.parse(folder / "network.xml")
    crossings = {e.get("id") for e in net.findall("edge") if e.get("function") == "crossing"}
    if len(crossings) != 1:
        raise SumoExecutionError("La red no contiene un único paso peatonal.")
    lane = next(e.find("lane") for e in net.findall("edge") if e.get("id") in crossings)
    if not math.isclose(float(lane.get("length")), x.length_m, abs_tol=0.02):
        raise SumoExecutionError("La longitud generada no coincide con el cruce.")
    controlled = [c for c in net.findall("connection") if c.get("tl") == "C"]
    n = max(int(c.get("linkIndex")) for c in controlled) + 1
    ped_indices = {int(c.get("linkIndex")) for c in controlled if c.get("to") in crossings}
    if not ped_indices:
        raise SumoExecutionError("El semáforo no controla la entrada peatonal.")
    additional = ET.Element("additional")
    tls = ET.SubElement(
        additional, "tlLogic", id="C", type="static", programID="walksim", offset="0"
    )
    vg = x.cycle_s - x.walk_s - x.clearance_s - 3
    for duration, vehicle, pedestrian in [
        (vg, "G", "r"),
        (3, "y", "r"),
        (x.walk_s, "r", "G"),
        (x.clearance_s, "r", "r"),
    ]:
        state = "".join(pedestrian if i in ped_indices else vehicle for i in range(n))
        ET.SubElement(tls, "phase", duration=str(duration), state=state)
    _write_xml(additional, folder / "signals.xml")
    lengths = {
        e.get("id"): float(e.find("lane").get("length"))
        for e in net.findall("edge")
        if e.get("id") in {"AC", "CB"}
    }
    return crossings, lengths


def run_crossing_simulation(raw, output_dir=None):
    x = CrossingInput.parse(raw)
    a = evaluate_crossing(raw)
    installation = detect_sumo()
    if not installation.available:
        raise SumoExecutionError("Faltan sumo o netconvert en PATH.")
    entries = generate_entries(x)
    folder = Path(output_dir or mkdtemp(prefix="walksim-crossing-"))
    folder.mkdir(parents=True, exist_ok=True)
    crossings, lengths = build_network(x, folder, installation.netconvert)
    routes = ET.Element("routes")
    ET.SubElement(
        routes,
        "vType",
        id="ped",
        vClass="pedestrian",
        maxSpeed=str(x.speed_mps),
        speedFactor="1",
        speedDev="0",
        impatience="0",
        jmDriveAfterRedTime="-1",
    )
    ET.SubElement(
        routes,
        "vType",
        id="car",
        vClass="passenger",
        maxSpeed=str(30 / 3.6),
        speedFactor="1",
        speedDev="0",
        carFollowModel="Krauss",
        impatience="0",
    )
    for name, edges in [("WE", "WC CE"), ("EW", "EC CW")]:
        ET.SubElement(routes, "route", id=name, edges=edges)
    for t, ident in entries:
        group = ident.split(".")[0]
        if group in ("AB", "BA"):
            p = ET.SubElement(
                routes,
                "person",
                id=ident,
                type="ped",
                depart=str(t),
                departPos=str(lengths["AC"] - 10 if group == "AB" else 10),
            )
            ET.SubElement(
                p,
                "walk",
                edges="AC CB" if group == "AB" else "CB AC",
                arrivalPos=str(10 if group == "AB" else lengths["AC"] - 10),
            )
        else:
            ET.SubElement(routes, "vehicle", id=ident, type="car", route=group, depart=str(t))
    _write_xml(routes, folder / "routes.xml")
    end = x.duration_s + 2 * x.cycle_s
    _run_command(
        [
            installation.sumo,
            "-n",
            "network.xml",
            "-r",
            "routes.xml",
            "-a",
            "signals.xml",
            "--begin",
            "0",
            "--end",
            str(end),
            "--step-length",
            "0.5",
            "--seed",
            str(x.seed),
            "--pedestrian.model",
            "striping",
            "--pedestrian.striping.jamtime",
            "1000000",
            "--time-to-teleport",
            "-1",
            "--collision.action",
            "warn",
            "--collision-output",
            "collisions.xml",
            "--fcd-output",
            "fcd.xml",
            "--personinfo-output",
            "personinfo.xml",
            "--tripinfo-output.write-unfinished",
            "true",
            "--no-step-log",
            "true",
        ],
        folder,
        "SUMO",
    )
    result = summarize(x, entries, folder / "fcd.xml", crossings)
    collisions = len(ET.parse(folder / "collisions.xml").findall("collision"))
    warnings = list(a["warnings"])
    if result["summary"]["pending"]:
        warnings.append(
            "Quedan peatones pendientes tras dos ciclos de despeje adicional; "
            "la espera media excluye a quienes aún no iniciaron el cruce."
        )
    if result["summary"]["not_inserted"]:
        warnings.append(
            "Hay demanda que SUMO no logró insertar; no se incluye en las colas muestreadas."
        )
    if collisions:
        warnings.append(
            f"El motor registró {collisions} colisiones/solapamientos. "
            "Revise la representación antes de interpretar los resultados."
        )
    version = subprocess.run(
        [installation.sumo, "--version"], capture_output=True, text=True, timeout=10, check=False
    ).stdout.splitlines()
    return dict(
        **result,
        inputs=x.to_dict(),
        signature=signature(raw),
        sample_s=0.5,
        engine_version=version[0] if version else "No registrada",
        created_at=datetime.now(UTC).isoformat(),
        collisions=collisions,
        warnings=warnings,
    )
