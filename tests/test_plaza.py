"""Geometría independiente, integración espacial, formatos y motor real."""

import copy
import json
import shutil

import pytest

from walksim.analysis.plaza import summarize
from walksim.domain.plaza import (
    PlazaInput,
    area,
    evaluate_plaza,
    fresh,
    grid,
    new_case,
    polygon,
    validate_study,
)
from walksim.plaza_io import export_matrix, import_cases, import_matrix, template
from walksim.project import ProjectState, load_project, save_project
from walksim.report import build_report
from walksim.sumo.plaza import generate_entries, run_plaza_simulation


@pytest.mark.parametrize(
    "kind,expected", [("rectangle", 432), ("hall", 432), ("cross", 216), ("tee", 180)]
)
def test_geometry_area_and_clipped_grid_conserve_area(kind, expected):
    x = PlazaInput.parse(dict(template=kind, cell_m=2.7))
    assert area(polygon(x)) == expected
    cells = grid(x)
    assert sum(c["area_m2"] for c in cells) == pytest.approx(expected)
    assert all(c["area_m2"] >= 0 for c in cells)
    if kind in {"cross", "tee"}:
        assert any(0 < c["area_m2"] < c["width_m"] * c["height_m"] for c in cells)


def test_local_matrix_sums_inactive_inputs_and_diagonal():
    a = evaluate_plaza({})
    assert a["total_pph"] == 2400
    assert all(r["origin_pph"] == 600 and r["destination_pph"] == 600 for r in a["accesses"])
    two = evaluate_plaza(dict(accesses="2", arm_m="", width_n_m="incompleto"))
    assert two["total_pph"] == 400 and len(two["accesses"]) == 2
    bad = PlazaInput().od
    bad[0][0] = 1
    with pytest.raises(ValueError):
        PlazaInput.parse(dict(od=bad))
    for raw in [
        dict(seed=0.5),
        dict(width_n_m=25),
        dict(template="cross", arm_m=20),
        dict(cell_m=0.5, length_m=100, height_m=100),
        dict(speed_mps="nan"),
    ]:
        with pytest.raises(ValueError):
            PlazaInput.parse(raw)


def test_spatial_integration_has_independent_known_person_seconds(tmp_path):
    # One observed person in cell for one second, second frame empty.
    x = PlazaInput.parse(
        dict(length_m=8, height_m=8, cell_m=4, duration_s=60, warmup_s=0.5, bin_s=17)
    )
    person = tmp_path / "persons.xml"
    positions = tmp_path / "fcd.xml"
    person.write_text(
        '<tripinfos><personinfo id="N.S.0"><walk depart="0" arrival="3" '
        'routeLength="3" duration="3" timeLoss="0"/></personinfo></tripinfos>'
    )
    positions.write_text(
        '<fcd-export><timestep time="0"><person id="N.S.0" x="-1" y="-1" edge=":J_w0"/>'
        '</timestep><timestep time="1"><person id="N.S.0" x="-1" y="-1" edge=":J_w0"/>'
        '</timestep><timestep time="2"/></fcd-export>'
    )
    r = summarize(person, positions, x, [(0.0, "N.S.0")])
    # t0 contributes .5s and t1 1s.
    c = next(c for c in r["cells"] if c["visitors"])
    assert c["person_seconds"] == 1.5 and c["visitors"] == 1 and c["mean_stay_s"] == 1.5
    assert c["mean_density"] == pytest.approx(1.5 / (16 * 60))
    assert c["max_density"] == pytest.approx(1 / 16)
    assert r["summary"]["mean_occupancy"] == pytest.approx(1.5 / 60)
    assert sum(row["occupancy"] * row["interval_s"] for row in r["series"]) == 1.5
    assert r["summary"]["cohort_completed"] == 0  # generated before warmup


@pytest.mark.parametrize("kind", ["rectangle", "cross", "tee"])
def test_templates_matrix_csv_and_decimal_comma(tmp_path, kind):
    p = tmp_path / "matrix.csv"
    export_matrix(p, PlazaInput().od)
    assert import_matrix(p) == PlazaInput().od
    p = tmp_path / "cases.csv"
    template(p, dict(template=kind))
    cases = import_cases(p)
    assert cases[0]["inputs"]["template"] == kind
    assert cases[0]["origins"]["od"] == "csv"
    content = p.read_text(encoding="utf-8-sig").splitlines()
    p.write_text("\n".join(content + content[-1:]))
    with pytest.raises(ValueError, match="repetido"):
        import_cases(p)
    p = tmp_path / "decimal.csv"
    p.write_text("origin;N;S;E;W\nN;0;10,5;0;0\nS;0;0;0;0\nE;0;0;0;0\nW;0;0;0;0\n")
    assert import_matrix(p)[0][1] == 10.5


def test_arrivals_repeat_and_guard_large_models():
    x = PlazaInput.parse(dict(arrival="random", duration_s=60))
    assert generate_entries(x) == generate_entries(x)
    assert all(t < x.duration_s + x.warmup_s for t, _p in generate_entries(x))
    with pytest.raises(ValueError):
        generate_entries(
            PlazaInput.parse(
                dict(
                    duration_s=3600,
                    od=[[0 if i == j else 20000 for j in range(4)] for i in range(4)],
                )
            )
        )


def test_partial_draft_schema31_migration_and_access_preservation(tmp_path):
    c = new_case()
    c["analytical"] = evaluate_plaza(c["inputs"])
    c["inputs"]["od"][0][1] = ""
    study = dict(cases=[c], selected_id=c["id"], view="max_density")
    assert not fresh(c, "analytical")
    validate_study(study)
    state = ProjectState(plaza=study)
    path = save_project(state, tmp_path / "draft.wksim")
    assert load_project(path).plaza == study
    old = ProjectState().to_dict()
    old.pop("plaza")
    old["schema_version"] = 4
    old["software_version"] = "3.1.0"
    path.write_text(json.dumps(old))
    before = path.read_bytes()
    save_project(load_project(path), path)
    assert (tmp_path / "draft.v3.1-backup.wksim").read_bytes() == before


def test_plaza_only_report_and_stale_snapshot():
    c = new_case("Plaza & vestíbulo")
    c["analytical"] = evaluate_plaza(c["inputs"])
    state = ProjectState(plaza=dict(cases=[c], selected_id=c["id"]))
    state.project.analyst = "Ana_1"
    tex = build_report(state)
    assert "Ana\\_1" in tex and "Plaza \\& vestíbulo" in tex
    assert "Matriz OD local" in tex and "FCD" in tex
    c["inputs"]["length_m"] = 30
    assert "se excluyen sus resultados anteriores" in build_report(state)


@pytest.mark.skipif(not shutil.which("sumo") or not shutil.which("netconvert"), reason="SUMO")
@pytest.mark.parametrize(
    "kind,arrival,clearance",
    [
        ("rectangle", "uniform", 180),
        ("cross", "random", 180),
        ("tee", "uniform", 180),
        ("rectangle", "uniform", 0),
    ],
)
def test_real_plaza_geometry_conservation_cohorts_and_maps(tmp_path, kind, arrival, clearance):
    r = run_plaza_simulation(
        dict(
            template=kind,
            arrival=arrival,
            duration_s=60.5,
            warmup_s=0.3,
            clearance_s=clearance,
            cell_m=2.7,
            bin_s=17,
        ),
        tmp_path / "engine",
    )
    m = r["summary"]
    assert m["generated"] == m["completed"] + m["pending"]
    assert m["cohort_completed"] <= m["cohort_generated"]
    assert m["outside_samples"] == 0
    assert sum(c["person_seconds"] for c in r["cells"]) == pytest.approx(m["mean_occupancy"] * 60.5)
    assert sum(v["occupancy"] * v["interval_s"] for v in r["series"]) == pytest.approx(
        m["mean_occupancy"] * 60.5
    )
    assert sum(v["generated"] for v in r["od"]) == m["generated"]
    if not clearance:
        assert m["pending"] > 0 and m["clearance_s"] is None
    c = new_case(inputs=r["inputs"])
    c["simulation"] = r
    c["analytical"] = r["analytical"]
    state = ProjectState(plaza=dict(cases=[c], selected_id=c["id"]))
    path = save_project(state, tmp_path / "complete.wksim")
    assert load_project(path).plaza == state.plaza
    bad = copy.deepcopy(state.plaza)
    bad["cases"][0]["simulation"]["cells"][0]["person_seconds"] += 1
    with pytest.raises(ValueError):
        validate_study(bad)


@pytest.mark.skipif(not shutil.which("sumo") or not shutil.which("netconvert"), reason="SUMO")
def test_zero_demand_has_empty_maps_and_no_statistics(tmp_path):
    from walksim.domain.plaza import validate_simulation

    r = run_plaza_simulation(
        dict(od=[[0] * 4 for _ in range(4)], duration_s=60, warmup_s=0, clearance_s=0),
        tmp_path / "empty",
    )
    validate_simulation(r)
    assert r["summary"]["generated"] == 0 and r["summary"]["mean_trip_s"] is None
    assert r["summary"]["completed_pct"] is None
    assert all(c["person_seconds"] == 0 for c in r["cells"])
