"""Guardado atómico, integridad de datos, importación por lotes y reporte escapado."""

import pytest

from walksim.csv_io import read_csv, write_template
from walksim.domain.analysis import METHODS, calculate
from walksim.project import ProjectState, load_project, save_project
from walksim.report import build_report, tex_escape


def populated_state():
    state = ProjectState()
    state.project.analyst = "Héctor & Ana_1 % {prueba}"
    state.project.notes = r"No ejecutar \input{externo}; área de estudio: 3 m²."
    state.drafts = {"walkway": {"width_m": "", "count": "texto parcial"}}
    for method, spec in METHODS.items():
        state.analyses.append(calculate(method, {f.key: f.default for f in spec.fields}).to_dict())
    return state


def test_roundtrip_keeps_partial_drafts_and_cases(tmp_path):
    state = populated_state()
    saved = save_project(state, tmp_path / "estudio")
    assert saved.suffix == ".wksim"
    restored = load_project(saved)
    assert restored.to_dict() == state.to_dict() | {
        "analyses": [row | {"data_source": "Captura manual"} for row in state.analyses]
    }
    assert restored.drafts["walkway"]["width_m"] == ""


def test_failed_write_preserves_previous_file(tmp_path, monkeypatch):
    path = save_project(ProjectState(), tmp_path / "valid.wksim")
    previous = path.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("walksim.project.os.replace", fail)
    with pytest.raises(OSError):
        save_project(populated_state(), path)
    assert path.read_bytes() == previous
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "content", ["not JSON", "{}", '{"format":"WalkSim Mobility Project","schema_version":99}']
)
def test_corrupt_or_future_project_rejected(tmp_path, content):
    path = tmp_path / "bad.wksim"
    path.write_text(content)
    with pytest.raises(ValueError):
        load_project(path)


@pytest.mark.parametrize("method", [*METHODS, "simulation"])
def test_csv_template_roundtrip(tmp_path, method):
    path = tmp_path / f"{method}.csv"
    write_template(path, method)
    imported_method, records = read_csv(path)
    assert imported_method == method
    assert len(records) == 1


def test_csv_semicolon_decimal_comma_and_atomic_batch_validation(tmp_path):
    path = tmp_path / "queue.csv"
    path.write_text(
        "analysis;name;area_m2;excluded_area_m2;occupants\nqueue;Espera;30,5;0,5;30\n",
        encoding="utf-8-sig",
    )
    assert read_csv(path)[1][0]["metrics"]["Área útil (m²)"] == 30
    with path.open("a") as stream:
        stream.write("queue;Error;0;0;4\n")
    with pytest.raises(ValueError, match="Fila 3"):
        read_csv(path)


def test_csv_unknown_headers_extra_columns_and_mixed_types(tmp_path):
    path = tmp_path / "bad.csv"
    for content in [
        "analysis,name,area_m2,occupants\nqueue,a,30,20\n",
        "analysis,name,area_m2,excluded_area_m2,occupants\nqueue,a,30,0,20,extra\n",
        "analysis,name,area_m2,excluded_area_m2,occupants\nqueue,a,30,0,20\nsignal,b,30,0,20\n",
    ]:
        path.write_text(content)
        with pytest.raises(ValueError):
            read_csv(path)


def test_report_contains_every_case_and_escapes_identification():
    state = populated_state()
    report = build_report(state)
    assert tex_escape(state.project.analyst) in report
    assert r"\input{externo}" not in report
    assert r"\textbackslash{}input\{externo\}" in report
    for spec in METHODS.values():
        assert tex_escape(spec.title) in report
    assert "schema" not in report
    assert "\\usepackage[T1]" not in report
    assert "letterpaper" in report
    state.project.analyst = ""
    with pytest.raises(ValueError, match="analista"):
        build_report(state)
