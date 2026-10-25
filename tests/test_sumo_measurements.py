"""Ocupación espacio-tiempo, censura de recorridos y ejecución real opcional."""

import shutil

import pytest

from walksim.domain.models import CorridorScenario
from walksim.sumo.parser import corridor_measurements, parse_personinfo
from walksim.sumo.runner import run_corridor_simulation


def test_unfinished_walk_is_excluded_from_means_but_included_in_occupation(tmp_path):
    path = tmp_path / "persons.xml"
    path.write_text("""<personinfos>
      <personinfo id="AB.0"><walk depart="0" arrival="10" duration="10"
        routeLength="10" timeLoss="0"/></personinfo>
      <personinfo id="BA.0"><walk depart="5" arrival="-1" duration="15"
        routeLength="8" timeLoss="1"/></personinfo>
      <personinfo id="AB.pending"><walk depart="-1" arrival="-1"/></personinfo>
    </personinfos>""")
    summary = parse_personinfo(path)
    assert summary.total.completed_walks == 1
    assert summary.ba.completed_walks == 0
    result = corridor_measurements(path, 10, 2, 20)
    assert result["Presencia acumulada durante la demanda (peat·s)"] == 25
    assert result["Ocupación media temporal del corredor (peat)"] == 1.25
    assert result["Ocupación máxima simultánea global (peat)"] == 2
    assert result["Peatones con recorrido iniciado"] == 2
    assert result["Recorridos inconclusos al final del despeje"] == 1
    assert result["Espacio equivalente global (m²/peatón)"] == 16


@pytest.mark.skipif(
    not shutil.which("sumo") or not shutil.which("netconvert"),
    reason="SUMO y netconvert no disponibles",
)
def test_real_sumo_corridor_has_both_directions_and_conserves_started_walks(tmp_path):
    run = run_corridor_simulation(CorridorScenario(analysis_time_s=60), tmp_path)
    assert run.result.ab.completed_walks > 0
    assert run.result.ba.completed_walks > 0
    assert (
        run.result.total.completed_walks
        == run.result.ab.completed_walks + run.result.ba.completed_walks
    )
    assert (
        run.result.total.completed_walks
        + run.measurements["Recorridos inconclusos al final del despeje"]
        == run.measurements["Peatones con recorrido iniciado"]
    )
    assert run.measurements["Densidad media temporal global (peat/m²)"] > 0
    assert run.engine_version != "No registrada"
