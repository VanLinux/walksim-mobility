from walksim.domain.models import CorridorScenario


def test_default_corridor_is_valid() -> None:
    scenario = CorridorScenario()
    assert scenario.validate() == ()
    assert scenario.simulation_end_s > scenario.analysis_time_s


def test_corridor_requires_some_demand() -> None:
    scenario = CorridorScenario(flow_ab_pph=0, flow_ba_pph=0)
    assert scenario.validate()
