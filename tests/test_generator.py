import xml.etree.ElementTree as ET

from walksim.domain.models import CorridorScenario
from walksim.sumo.generator import build_corridor_files


def test_generator_creates_bidirectional_person_flows(tmp_path) -> None:
    scenario = CorridorScenario(flow_ab_pph=600, flow_ba_pph=400)
    files = build_corridor_files(scenario, tmp_path)

    assert files.nodes.exists()
    assert files.edges.exists()
    assert files.routes.exists()
    assert files.config.exists()

    root = ET.parse(files.routes).getroot()
    flows = {element.get("id"): element for element in root.findall("personFlow")}

    assert set(flows) == {"AB", "BA"}
    assert flows["AB"].get("personsPerHour") == "600.000000"
    assert flows["BA"].get("personsPerHour") == "400.000000"
