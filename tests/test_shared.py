"""Referencias independientes, extremos, eventos y conservación del sendero mixto."""

import copy
import json
import math
import shutil

import pytest

from walksim.analysis.shared import crossings
from walksim.domain.shared import (
    SharedInput,
    blos_grade,
    evaluate_shared,
    event_rates,
    fresh,
    new_case,
    plos,
    validate_study,
)
from walksim.project import ProjectState, load_project, save_project
from walksim.report import build_report
from walksim.shared_io import import_cases, template
from walksim.sumo.shared import run_shared_simulation


def test_plos_directional_reference_and_strict_thresholds():
    a = evaluate_shared(
        dict(task="ped", phf=1, ped_speed=1.25, bike_speed=5, bike_ab=60, bike_ba=40)
    )
    ab, ba = [r["pedestrian"] for r in a["directions"]]
    assert ab == dict(passing_h=45, meeting_h=50, weighted_h=70, los="C")
    assert ba == dict(passing_h=30, meeting_h=75, weighted_h=67.5, los="C")
    for v, expected in [(38, "A"), (60, "B"), (103, "C"), (144, "D"), (180, "E"), (180.01, "F")]:
        assert plos(v) == expected
    for v, expected in [(4.01, "A"), (4, "B"), (3.5, "C"), (3, "D"), (2.5, "E"), (2, "F")]:
        assert blos_grade(v) == expected


def test_direct_counts_do_not_apply_phf_twice():
    a = evaluate_shared(dict(phf=0.5, ped_ab=100, ped_ba=100, bike_ab=100, bike_ba=100))
    b = evaluate_shared(
        dict(
            basis="count",
            phf=0.5,
            count_ped_ab=50,
            count_ped_ba=50,
            count_bike_ab=50,
            count_bike_ba=50,
        )
    )
    assert a["flows"] == b["flows"] and a["directions"] == b["directions"]
    p = evaluate_shared(dict(task="ped", basis="count", phf="", ped_sd="", bike_sd=""))
    assert p["flows"]["P.AB"] == 100


def test_blos_with_documented_probability_and_delay_counts():
    raw = dict(
        ped_speed=1.25,
        bike_speed=5,
        ped_sd=0,
        bike_sd=0,
        phf=1,
        ped_ab=60,
        ped_ba=120,
        bike_ab=60,
        bike_ba=60,
        attempts_ab=100,
        delayed_ab=25,
        attempts_ba=100,
        delayed_ba=25,
    )
    a = evaluate_shared(raw)
    b = a["directions"][0]["bicycle"]
    assert b["active_min"] == pytest.approx(3)
    assert b["meetings_min"] == pytest.approx(12)
    assert b["probability_delay"] == 0.25 and b["delayed_min"] == 0.75
    assert b["score"] == pytest.approx(5.446 - 0.00809 * 42 - 1.586 - 0.375)
    stripe = evaluate_shared({**raw, "centerline": "yes"})["directions"][0]["bicycle"]
    assert b["score"] - stripe["score"] == pytest.approx(0.287)
    probability = evaluate_shared(
        {**raw, "delay_source": "probability", "probability_ab": 0.25, "probability_ba": 0.25}
    )
    assert probability["directions"] == a["directions"]


def test_missing_probability_width_domain_no_sample_and_low_volume():
    assert evaluate_shared({})["directions"][0]["bicycle"]["los"] is None
    assert (
        evaluate_shared(dict(attempts_ab=0, delayed_ab=0))["directions"][0]["bicycle"][
            "probability_delay"
        ]
        is None
    )
    r = evaluate_shared(dict(width_m=2, delay_source="probability", probability_ab=0))
    assert r["directions"][0]["bicycle"]["score"] is None
    r = evaluate_shared(
        dict(
            ped_ab=0,
            ped_ba=0,
            bike_ab=1,
            bike_ba=1,
            delay_source="probability",
            probability_ab=0,
            probability_ba=0,
        )
    )
    assert r["directions"][0]["bicycle"]["los"] == "A"
    assert r["directions"][0]["pedestrian"]["los"] is None
    with pytest.raises(ValueError):
        SharedInput.parse(dict(attempts_ab=10, delayed_ab=11))
    with pytest.raises(ValueError):
        SharedInput.parse(dict(probability_ab=2, delay_source="probability"))
    with pytest.raises(ValueError):
        SharedInput.parse(dict(bike_speed=1, ped_speed=2))


def test_normal_integration_matches_closed_form():
    u, mu, sd, rate = 5.7, 1.5, 0.3, 100

    def phi(z):
        return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)

    def Phi(z):
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def primitive(v):
        return (v - mu) * Phi((v - mu) / sd) + sd * phi((v - mu) / sd)

    fraction = (primitive(u) - primitive(0)) / u
    expected = rate * u / (60 * mu) * fraction
    assert event_rates(2000, u, mu, sd, rate) == pytest.approx(expected, rel=1e-4)
    assert event_rates(2000, u, mu, sd, rate) + event_rates(
        2000, u, mu, sd, rate, True
    ) == pytest.approx(rate * u / (60 * mu))


def test_event_detection_types_direction_and_unique_pairs():
    seen = set()
    old = {"P.AB.0": 10, "B.AB.0": 5}
    new = {"P.AB.0": 11, "B.AB.0": 12}
    events = crossings(old, new, seen)
    assert len(events) == 1 and events[0][:3] == ("passes_bp", "B.AB.0", "P.AB.0")
    assert crossings(new, old, seen) == []
    events = crossings({"B.AB.0": 0, "B.BA.0": 10}, {"B.AB.0": 6, "B.BA.0": 4}, set())
    assert len(events) == 1 and events[0][0] == "meetings_bb"
    assert crossings({"P.AB.0": 0, "P.AB.1": 1}, {"P.AB.0": 2, "P.AB.1": 1.5}, set()) == []


@pytest.mark.parametrize(
    "task,basis,source",
    [("both", "hourly", "counts"), ("ped", "count", "counts"), ("bike", "count", "probability")],
)
def test_csv_templates_by_task(tmp_path, task, basis, source):
    p = tmp_path / "guide.csv"
    template(p, dict(task=task, basis=basis, delay_source=source))
    c = import_cases(p)[0]
    assert c["inputs"]["task"] == task and c["origins"]["ped_speed"] == "csv"
    assert evaluate_shared(c["inputs"])["flows"]


def test_drafts_migration_and_report_variants(tmp_path):
    c = new_case("Sendero & prueba")
    c["analytical"] = evaluate_shared(c["inputs"])
    state = ProjectState(shared=dict(cases=[c], selected_id=c["id"]))
    state.project.analyst = "Ana_1"
    tex = build_report(state)
    assert "Ana\\_1" in tex and "Sendero \\& prueba" in tex
    assert "BLOS condicionado" in tex and "24-5" in tex
    c["inputs"]["ped_speed"] = ""
    assert not fresh(c, "analytical")
    p = save_project(state, tmp_path / "draft.wksim")
    assert load_project(p).shared == state.shared
    assert "se excluyen sus resultados anteriores" in build_report(state)
    old = ProjectState().to_dict()
    old.pop("shared")
    old["schema_version"] = 5
    old["software_version"] = "3.2.0"
    p.write_text(json.dumps(old))
    before = p.read_bytes()
    save_project(load_project(p), p)
    assert (tmp_path / "draft.v3.2-backup.wksim").read_bytes() == before
    bad = copy.deepcopy(state.shared)
    bad["cases"][0]["analytical"]["directions"][0]["pedestrian"]["los"] = "Z"
    with pytest.raises(ValueError):
        validate_study(bad)


@pytest.mark.skipif(not shutil.which("sumo") or not shutil.which("netconvert"), reason="SUMO")
@pytest.mark.parametrize(
    "mode,clearance", [("both", 240), ("ped", 240), ("bike", 240), ("empty", 0), ("both", 0)]
)
def test_real_mixed_engine_conserves_each_group_and_saved_events(tmp_path, mode, clearance):
    raw = dict(length_m=80, duration_s=60, warmup_s=0, clearance_s=clearance, arrival="uniform")
    if mode in {"ped", "empty"}:
        raw.update(bike_ab=0, bike_ba=0)
    if mode in {"bike", "empty"}:
        raw.update(ped_ab=0, ped_ba=0)
    r = run_shared_simulation(raw, tmp_path / "engine")
    m = r["summary"]
    assert m["generated"] == m["completed"] + m["pending"]
    if clearance:
        assert m["pending"] == 0
    if mode == "empty":
        assert m["generated"] == 0
    if mode == "both" and not clearance:
        assert m["pending"] > 0
    for e in ["meetings_pb", "passes_bp", "meetings_bb", "passes_bb"]:
        assert sum(v[e] for v in r["series"]) == m[e]
    c = new_case(inputs=r["inputs"])
    c["simulation"] = r
    c["analytical"] = r["analytical"]
    state = ProjectState(shared=dict(cases=[c], selected_id=c["id"]))
    p = save_project(state, tmp_path / "shared.wksim")
    assert load_project(p).shared == state.shared
