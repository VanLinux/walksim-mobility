"""Generación automática del escenario SUMO para un corredor peatonal."""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from walksim.domain.models import CorridorScenario


@dataclass(frozen=True, slots=True)
class ScenarioFiles:
    workdir: Path
    nodes: Path
    edges: Path
    routes: Path
    config: Path
    network: Path
    personinfo: Path
    statistics: Path


def _write_xml(root: ET.Element, path: Path) -> None:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build_corridor_files(
    scenario: CorridorScenario,
    output_dir: str | Path | None = None,
) -> ScenarioFiles:
    errors = scenario.validate()
    if errors:
        raise ValueError(" ".join(errors))

    if output_dir is None:
        workdir = Path(tempfile.mkdtemp(prefix="walksim-"))
    else:
        workdir = Path(output_dir).expanduser().resolve()
        workdir.mkdir(parents=True, exist_ok=True)

    nodes_path = workdir / "corridor.nod.xml"
    edges_path = workdir / "corridor.edg.xml"
    routes_path = workdir / "persons.rou.xml"
    config_path = workdir / "walksim.sumocfg"
    network_path = workdir / "corridor.net.xml"
    personinfo_path = workdir / "personinfo.xml"
    statistics_path = workdir / "statistics.xml"

    nodes = ET.Element("nodes")
    ET.SubElement(nodes, "node", id="A", x="0.0", y="0.0", type="priority")
    ET.SubElement(
        nodes,
        "node",
        id="B",
        x=f"{scenario.length_m:.3f}",
        y="0.0",
        type="priority",
    )
    _write_xml(nodes, nodes_path)

    edges = ET.Element("edges")
    ET.SubElement(
        edges,
        "edge",
        id="corridor",
        attrib={
            "from": "A",
            "to": "B",
            "priority": "1",
            "numLanes": "1",
            "speed": f"{max(3.0, scenario.walking_speed_mps * 1.5):.3f}",
            "width": f"{scenario.width_m:.3f}",
            "allow": "pedestrian",
            "spreadType": "center",
        },
    )
    _write_xml(edges, edges_path)

    routes = ET.Element("routes")
    ET.SubElement(routes, "vType", id="pedestrian", vClass="pedestrian")

    start_pos = 0.10
    end_pos = max(start_pos + 0.10, scenario.length_m - 0.10)

    if scenario.flow_ab_pph > 0:
        flow_ab = ET.SubElement(
            routes,
            "personFlow",
            id="AB",
            type="pedestrian",
            begin="0",
            end=f"{scenario.analysis_time_s:.3f}",
            personsPerHour=f"{scenario.flow_ab_pph:.6f}",
            departPos=f"{start_pos:.2f}",
        )
        ET.SubElement(
            flow_ab,
            "walk",
            attrib={
                "from": "corridor",
                "to": "corridor",
                "arrivalPos": f"{end_pos:.3f}",
                "speed": f"{scenario.walking_speed_mps:.3f}",
            },
        )

    if scenario.flow_ba_pph > 0:
        flow_ba = ET.SubElement(
            routes,
            "personFlow",
            id="BA",
            type="pedestrian",
            begin="0",
            end=f"{scenario.analysis_time_s:.3f}",
            personsPerHour=f"{scenario.flow_ba_pph:.6f}",
            departPos=f"{end_pos:.3f}",
        )
        ET.SubElement(
            flow_ba,
            "walk",
            attrib={
                "from": "corridor",
                "to": "corridor",
                "arrivalPos": f"{start_pos:.2f}",
                "speed": f"{scenario.walking_speed_mps:.3f}",
            },
        )

    _write_xml(routes, routes_path)

    config = ET.Element("configuration")
    input_group = ET.SubElement(config, "input")
    ET.SubElement(input_group, "net-file", value=network_path.name)
    ET.SubElement(input_group, "route-files", value=routes_path.name)
    time_group = ET.SubElement(config, "time")
    ET.SubElement(time_group, "begin", value="0")
    ET.SubElement(time_group, "end", value=str(scenario.simulation_end_s))
    _write_xml(config, config_path)

    return ScenarioFiles(
        workdir=workdir,
        nodes=nodes_path,
        edges=edges_path,
        routes=routes_path,
        config=config_path,
        network=network_path,
        personinfo=personinfo_path,
        statistics=statistics_path,
    )
