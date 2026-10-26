"""Referencias independientes para servicio, conservación, formatos y microsimulación."""

import copy
import json
import shutil

import pytest

from walksim.access_io import import_cases, template
from walksim.domain.access import (
    AccessInput,
    erlang_c,
    evaluate_access,
    fresh,
    new_case,
    validate_study,
)
from walksim.project import ProjectState, load_project, save_project
from walksim.report import build_report
from walksim.sumo.access import Integral, arrivals, run_access_simulation, serve


def test_capacity_time_rate_tandem_and_inactive_drafts():
    time = evaluate_access(dict(devices=4, service_s=3))
    rate = evaluate_access(dict(devices=4, service_basis="rate", service_pph=1200, service_s=""))
    assert time["metrics"] == rate["metrics"]
    assert time["metrics"]["Capacidad de servicio (peat/h)"] == 4800
    tandem = evaluate_access(dict(layout="metro_exit", devices=4, service_s=3, stair_pph=2400))
    assert tandem["metrics"]["Capacidad de servicio (peat/h)"] == 2400
    assert [s["key"] for s in tandem["stages"]] == ["stairs", "gate"]
    free = evaluate_access(dict(device="free", service_s="", devices="", rate_pph=0))
    assert free["metrics"]["Capacidad de servicio (peat/h)"] is None
    with pytest.raises(ValueError):
        AccessInput.parse(dict(devices=1.2))
    with pytest.raises(ValueError):
        AccessInput.parse(dict(arrival="batch", release_s=200, cycle_s=100))


def test_erlang_matches_closed_form_mm1_and_mm2():
    # lambda=8/h, mu=10/h: rho=.8, Wq=.4h, Lq=3.2.
    r = erlang_c(8, 360, 1)
    assert r["probability_wait"] == pytest.approx(0.8)
    assert r["mean_wait_s"] == pytest.approx(1440)
    assert r["mean_queue"] == pytest.approx(3.2)
    # lambda=3/h, mu=2/h, c=2: P0=1/7, Pwait=9/14.
    r = erlang_c(3, 1800, 2)
    assert r["probability_wait"] == pytest.approx(9 / 14)
    assert r["mean_wait_s"] == pytest.approx(9 / 14 * 3600)
    assert erlang_c(10, 360, 1) is None
    assert erlang_c(0, 360, 1)["mean_wait_s"] == 0
    a = evaluate_access(dict(arrival="random", service="exponential", rate_pph=1000))
    assert a["reference"] is not None
    assert evaluate_access(dict(arrival="batch"))["reference"] is None


def test_fcfs_multiple_servers_exact_schedule_and_reproducibility():
    entries = {"0": 0, "1": 0, "2": 1, "3": 1}
    r = serve(entries, 2, 3, 42)
    assert r == {"0": (0, 0, 3), "1": (0, 0, 3), "2": (1, 3, 6), "3": (1, 3, 6)}
    four = serve(entries, 4, 3, 42)
    assert all(start == arr for arr, start, _end in four.values())
    exp = serve(entries, 2, 3, 42, True)
    assert exp == serve(entries, 2, 3, 42, True)
    assert exp != serve(entries, 2, 3, 43, True)


def test_exact_integrals_exclude_simultaneous_departures_from_queue_peaks():
    v = Integral([(0, 5), (5, 10), (3, 7)])
    assert v.mean(0, 10) == pytest.approx(1.4)
    assert v.maximum(0, 10) == 2
    assert v.mean(5, 7) == 2
    assert v.maximum(7, 10) == 1
    assert v.mean(10, 20) == 0


@pytest.mark.parametrize("pattern", ["uniform", "random", "intermittent", "batch"])
def test_arrival_patterns_are_reproducible_and_within_generation_window(pattern):
    x = AccessInput.parse(
        dict(arrival=pattern, duration_s=360, warmup_s=0, passengers=60, cycle_s=180, release_s=30)
    )
    values = list(arrivals(x).values())
    assert values == list(arrivals(x).values())
    assert all(0 <= t < 360 for t in values)
    if pattern in {"intermittent", "batch"}:
        assert all(t % 180 < 30 for t in values)
    if pattern == "batch":
        assert len(values) == 120
    with pytest.raises(ValueError):
        arrivals(AccessInput.parse(dict(arrival="batch", passengers=10000, duration_s=600)))


@pytest.mark.parametrize(
    "layout,device,arrival",
    [
        ("access", "turnstile", "uniform"),
        ("metro_exit", "turnstile", "batch"),
        ("metro_entry", "free", "random"),
    ],
)
def test_csv_task_template_and_missing_required_columns(tmp_path, layout, device, arrival):
    path = tmp_path / "template.csv"
    template(path, dict(layout=layout, device=device, arrival=arrival))
    cases = import_cases(path)
    assert cases[0]["inputs"]["layout"] == layout
    assert cases[0]["origins"]["speed_mps"] == "csv"
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    column = lines[0].split(",").index("speed_mps")
    path.write_text(
        "\n".join(
            ",".join(v for i, v in enumerate(line.split(",")) if i != column) for line in lines
        )
    )
    with pytest.raises(ValueError, match="Faltan columnas"):
        import_cases(path)


def test_projects_preserve_partial_drafts_and_backup_v30(tmp_path):
    c = new_case()
    c["analytical"] = evaluate_access(c["inputs"])
    c["inputs"]["service_s"] = ""
    study = dict(cases=[c], selected_id=c["id"])
    assert not fresh(c, "analytical")
    validate_study(study)
    state = ProjectState(access=study)
    path = save_project(state, tmp_path / "current.wksim")
    assert load_project(path).access == study
    old = state.to_dict()
    old["schema_version"] = 3
    old.pop("access")
    path.write_text(json.dumps(old))
    previous = path.read_bytes()
    migrated = load_project(path)
    assert not migrated.access
    save_project(migrated, path)
    assert (tmp_path / "current.v3.0-backup.wksim").read_bytes() == previous
    bad = copy.deepcopy(study)
    bad["cases"][0]["analytical"]["metrics"]["Capacidad de servicio (peat/h)"] = 1
    with pytest.raises(ValueError):
        validate_study(bad)


def test_access_only_report_escapes_names_and_excludes_stale_results():
    c = new_case("Puerta & acceso")
    c["analytical"] = evaluate_access(c["inputs"])
    state = ProjectState(access=dict(cases=[c], selected_id=c["id"]))
    state.project.analyst = "Ana_1"
    tex = build_report(state)
    assert "Ana\\_1" in tex and "Puerta \\& acceso" in tex
    assert "Erlang" in tex and "FCFS" in tex and "Predeterminado" in tex
    assert "\\begin{itemize}\n\\end{itemize}" not in tex
    c["inputs"]["service_s"] = 3
    assert "se excluyen sus resultados anteriores" in build_report(state)


@pytest.mark.skipif(not shutil.which("sumo") or not shutil.which("netconvert"), reason="SUMO")
@pytest.mark.parametrize(
    "layout,device,rate,clearance",
    [
        ("access", "turnstile", 1200, 120),
        ("metro_exit", "turnstile", 1200, 180),
        ("metro_entry", "free", 600, 120),
        ("access", "turnstile", 0, 0),
        ("access", "turnstile", 8000, 0),
    ],
)
def test_real_hybrid_conservation_series_and_saved_results(
    tmp_path, layout, device, rate, clearance
):
    raw = dict(
        layout=layout,
        device=device,
        rate_pph=rate,
        duration_s=60,
        warmup_s=0,
        clearance_s=clearance,
        passengers=40,
        cycle_s=180,
        release_s=15,
        arrival="batch" if layout == "metro_exit" else "uniform",
    )
    r = run_access_simulation(raw, tmp_path / "engine")
    s = r["summary"]
    assert s["generated"] == s["completed"] + s["pending"]
    assert s["cohort_generated"] == s["generated"]
    assert sum(row["generated"] for row in r["series"]) == s["generated"]
    assert sum(row["interval_s"] for row in r["series"]) == 60
    assert sum(row["count"] for row in r["histogram"]) == s["cohort_completed"]
    if not clearance and rate:
        assert s["pending"] > 0 and s["clearance_s"] is None
    if not rate:
        assert s["generated"] == 0 and s["mean_wait_s"] is None
    c = new_case(inputs=r["inputs"])
    c["analytical"], c["simulation"] = r["analytical"], r
    state = ProjectState(access=dict(cases=[c], selected_id=c["id"]))
    path = save_project(state, tmp_path / "saved.wksim")
    assert load_project(path).access == state.access
    tampered = copy.deepcopy(state.access)
    tampered["cases"][0]["simulation"]["summary"]["pending"] += 1
    with pytest.raises(ValueError):
        validate_study(tampered)
