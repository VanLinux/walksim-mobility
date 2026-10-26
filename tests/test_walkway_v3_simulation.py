"""Cohorte, conservación y serialización con el motor real cuando está disponible."""

import shutil

import pytest

from walksim.domain.walkway import new_case
from walksim.project import ProjectState, load_project, save_project
from walksim.sumo.walkway import run_walkway_simulation


@pytest.mark.skipif(
    not shutil.which("sumo") or not shutil.which("netconvert"), reason="Requiere SUMO"
)
@pytest.mark.parametrize("platoon", [False, True])
def test_real_simulation_conserves_people_and_saved_series(tmp_path, platoon):
    raw = dict(duration_s=120, warmup_s=60, bin_s=30)
    if platoon:
        raw.update(flow_type="platoon", demand_basis="count")
    r = run_walkway_simulation(raw, tmp_path / "engine")
    s = r["summary"]
    assert s["generated"] == s["started"] + s["not_started"]
    assert s["started"] == s["completed"] + s["unfinished"]
    assert s["cohort_entered"] >= s["cohort_completed"] > 0
    assert len(r["series"]) == 4
    assert sum(v["interval_s"] for v in r["series"]) == 120
    assert sum(v["occupancy"] * v["interval_s"] for v in r["series"]) == pytest.approx(
        s["mean_occupancy"] * 120
    )
    assert r["directions"]["total"]["p95_s"] >= r["directions"]["total"]["p50_s"]
    case = new_case(inputs=r["inputs"])
    case["analytical"] = r["analytical"]
    case["simulation"] = r
    state = ProjectState(walkway=dict(cases=[case], selected_id=case["id"]))
    path = save_project(state, tmp_path / "real.wksim")
    assert load_project(path).walkway == state.walkway
