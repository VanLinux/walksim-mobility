"""Walkway 3: referencias independientes, diseño, CSV y migración de proyectos."""

import copy
import json

import pytest

from walksim.analysis.walkway import percentile
from walksim.domain.walkway import (
    WalkwayInput,
    evaluate_walkway,
    new_case,
    signature,
    validate_study,
)
from walksim.project import ProjectState, load_project, save_project
from walksim.sumo.walkway import generate_arrivals
from walksim.walkway_io import import_cases, template


def test_hourly_peak_counts_are_equivalent_without_double_phf():
    hourly = evaluate_walkway(dict(flow_ab_pph=900, flow_ba_pph=600, phf=0.5))
    counted = evaluate_walkway(dict(demand_basis="count", count_ab=450, count_ba=300, phf=0.1))
    assert hourly["metrics"]["Demanda de diseño (peat/h)"] == 3000
    assert hourly["metrics"]["Densidad estimada (peat/m²)"] == pytest.approx(
        3000 / (3600 * 2.5 * 1.2)
    )
    assert hourly["metrics"]["Espacio estimado (m²/peatón)"] == pytest.approx(3.6)
    assert counted["metrics"] == hourly["metrics"]


@pytest.mark.parametrize("los", list("ABCDE"))
def test_design_width_rounds_up_and_meets_strict_target(los):
    result = evaluate_walkway(
        dict(mode="design_width", target_los=los, flow_ab_pph=1800, flow_ba_pph=1800, phf=1)
    )
    width = result["metrics"]["Ancho total propuesto (m)"]
    effective = width - 0.5
    threshold = result["thresholds"]["ABCDE".index(los)]
    assert effective > 3600 * threshold / (3600 * 1.2)
    assert abs(width * 100 - round(width * 100)) < 1e-8
    assert result["metrics"]["Relación demanda/capacidad"] <= 1
    assert "ABCDEF".index(result["metrics"]["LOS operativo"]) <= "ABCDE".index(los)


@pytest.mark.parametrize(
    "flow_type,basis", [("random", "hourly"), ("random", "count"), ("platoon", "count")]
)
def test_maximum_demand_respects_space_margin_and_capacity(flow_type, basis):
    r = evaluate_walkway(dict(mode="design_demand", flow_type=flow_type, demand_basis=basis))
    m = r["metrics"]
    assert m["Relación demanda/capacidad"] <= 1
    assert m["Espacio estimado (m²/peatón)"] > r["thresholds"][2]
    assert r["resolved"]["flow_ab_pph"] + r["resolved"]["flow_ba_pph"] == pytest.approx(
        m["Demanda de diseño (peat/h)"]
    )


def test_saturation_zero_demand_and_invalid_parameters():
    r = evaluate_walkway(dict(flow_ab_pph=20000, flow_ba_pph=20000, width_m=1, phf=1))
    assert r["metrics"]["LOS operativo"] == "F"
    zero = evaluate_walkway(dict(flow_ab_pph=0, flow_ba_pph=0))
    assert zero["metrics"]["Espacio estimado (m²/peatón)"] is None
    for raw in [
        dict(phf=0),
        dict(phf="NaN"),
        dict(width_m=0.5),
        dict(slope_pct=6),
        dict(seed=0.5),
        dict(flow_type="platoon"),
        dict(flow_type="platoon", demand_basis="count", platoon_release_s=61),
    ]:
        with pytest.raises(ValueError):
            WalkwayInput.parse(raw)


def test_percentile_and_reproducible_limited_pulses():
    assert percentile([], 0.5) is None
    assert percentile([10, 20, 30, 40], 0.5) == 25
    assert percentile([10, 20, 30, 40], 0.95) == pytest.approx(38.5)
    a = generate_arrivals(3600, 300, 42)
    b = generate_arrivals(3600, 300, 43)
    assert a == generate_arrivals(3600, 300, 42) and a != b
    pulse = generate_arrivals(3600, 300, 42, 60, 15)
    assert len(pulse) == len(a)
    assert all(t % 60 < 15 for t in pulse)
    assert generate_arrivals(0, 300, 42) == []


@pytest.mark.parametrize("mode", ["operation", "design_width", "design_demand"])
def test_csv_template_for_each_task_and_provenance(tmp_path, mode):
    path = tmp_path / "template.csv"
    template(path, dict(mode=mode))
    cases = import_cases(path)
    assert len(cases) == 1
    assert cases[0]["inputs"]["mode"] == mode
    assert cases[0]["origins"]["speed_mps"] == "csv"
    assert evaluate_walkway(cases[0]["inputs"])["metrics"]


def test_v2_migration_preserves_original_and_writes_schema3(tmp_path):
    old = ProjectState().to_dict()
    old["schema_version"] = 1
    old["software_version"] = "2.1.0"
    old.pop("walkway")
    old["drafts"] = {"walkway": {"count": "incompleto"}}
    path = tmp_path / "old.wksim"
    path.write_text(json.dumps(old))
    previous = path.read_bytes()
    state = load_project(path)
    assert state.drafts["walkway"]["count"] == "incompleto"
    case = new_case()
    case["analytical"] = evaluate_walkway(case["inputs"])
    case["inputs"]["speed_mps"] = "borrador incompleto"
    state.walkway = dict(cases=[case], selected_id=case["id"], chart="speed")
    save_project(state, path)
    assert (tmp_path / "old.v2-backup.wksim").read_bytes() == previous
    assert json.loads(path.read_text())["schema_version"] == 3
    loaded = load_project(path)
    assert loaded.walkway["cases"][0]["inputs"]["speed_mps"] == "borrador incompleto"
    assert loaded.walkway["cases"][0]["analytical"]["metrics"]


def test_inconsistent_saved_results_and_unknown_modes_are_rejected():
    case = new_case()
    case["analytical"] = evaluate_walkway(case["inputs"])
    study = dict(cases=[case], selected_id=case["id"])
    validate_study(study)
    bad = copy.deepcopy(study)
    bad["cases"][0]["analytical"]["metrics"]["LOS operativo"] = "Z"
    with pytest.raises(ValueError):
        validate_study(bad)
    bad = copy.deepcopy(study)
    bad["cases"][0]["inputs"]["mode"] = "unknown"
    with pytest.raises(ValueError):
        validate_study(bad)
    assert len(signature(case["inputs"])) == 64


def test_walkway_only_report_has_design_provenance_and_excludes_stale_results():
    from walksim.report import build_report

    case = new_case("Alternativa & C", {**WalkwayInput().to_dict(), "mode": "operation"})
    case["analytical"] = evaluate_walkway(case["inputs"])
    state = ProjectState(walkway=dict(cases=[case], selected_id=case["id"]))
    state.project.analyst = "Ana_1"
    report = build_report(state)
    assert "Walkway 3" in report
    assert "Ana\\_1" in report
    assert "Predeterminado" in report
    assert "PHF" in report
    case["inputs"]["speed_mps"] = 1.4
    report = build_report(state)
    assert "se excluyen sus resultados anteriores" in report


def test_inactive_inputs_do_not_block_the_chosen_task():
    x = evaluate_walkway(dict(demand_basis="count", phf="", flow_ab_pph="incompleto"))
    assert x["metrics"]["Demanda de diseño (peat/h)"] == 1500
    x = evaluate_walkway(dict(mode="design_demand", flow_ab_pph="", flow_ba_pph=""))
    assert x["metrics"]["Demanda de diseño (peat/h)"] > 0
