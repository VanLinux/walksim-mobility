"""Referencias numéricas independientes, límites LOS y validación de métodos."""

import math

import pytest

from walksim.domain.analysis import FT2, METHODS, calculate, criterion_thresholds, space_los


def sample(method):
    return {f.key: f.default for f in METHODS[method].fields}


@pytest.mark.parametrize("method", METHODS)
def test_every_method_computes_example(method):
    result = calculate(method, sample(method))
    assert result.source
    assert result.steps
    assert all(not isinstance(v, float) or math.isfinite(v) for v in result.metrics.values())


def test_width_flow_units_and_capacity():
    result = calculate(
        "walkway",
        dict(width_m=3, obstacles_m=0.2, edges_m=0.3, count=450, period_min=15, speed_mps=1.2),
    )
    assert result.metrics["Ancho efectivo (m)"] == 2.5
    assert result.metrics["Flujo específico (peat/min/m)"] == 12
    assert result.metrics["Densidad (peat/m²)"] == pytest.approx(1 / 6)
    assert result.metrics["Espacio medio (m²/peatón)"] == 6
    assert result.metrics["LOS por espacio"] == "A"
    assert result.metrics["Capacidad específica de referencia (peat/min/m)"] == pytest.approx(
        23 / 0.3048
    )


@pytest.mark.parametrize("method", ["walkway", "platoon", "stairs", "queue"])
def test_exact_imperial_boundaries_and_equality(method):
    limits = criterion_thresholds(method)
    assert len(limits) == 5
    for index, boundary in enumerate(limits):
        assert space_los(boundary, limits) == "BCDEF"[index]
        assert space_los(boundary + 1e-8, limits) == "ABCDE"[index]
    assert criterion_thresholds("stairs")[-1] == 5 * FT2
    assert space_los(None, limits) == "A"


def test_platoon_uses_five_minutes_and_own_thresholds():
    result = calculate("platoon", dict(width_m=2, obstacles_m=0, edges_m=0, count=100, speed_mps=1))
    assert result.metrics["Flujo específico (peat/min/m)"] == 10
    assert result.metrics["Espacio medio (m²/peatón)"] == 6
    assert result.metrics["LOS por espacio"] == "C"


def test_stair_reverse_flow_reserves_one_lane():
    x = sample("stairs")
    x["reverse_flow"] = "1"
    result = calculate("stairs", x)
    assert result.metrics["Ancho efectivo (m)"] == pytest.approx(3 - 0.2 - 0.3 - 0.762)
    assert result.metrics["Capacidad específica de referencia (peat/min/m)"] == pytest.approx(
        15 / 0.3048
    )


def test_signal_delay_and_independent_clearance():
    result = calculate(
        "signal", dict(cycle_s=90, green_s=30, crossing_m=12, speed_mps=1, clearance_s=10)
    )
    assert result.metrics["Demora media (s/peatón)"] == 20
    assert result.metrics["Categoría por demora (documento)"] == "C"
    assert result.metrics["Margen de despeje (s)"] == -2
    assert "no PLOS" in result.criterion


def test_unsignal_numeric_reference_and_zero_limit():
    x = dict(crossing_m=8, speed_mps=1, startup_s=2, vehicles_pph=360)
    r = calculate("unsignal", x)
    assert r.metrics["Demora media por brechas (s/peatón)"] == pytest.approx((math.e - 2) / 0.1)
    x["vehicles_pph"] = 0
    assert calculate("unsignal", x).metrics["Demora media por brechas (s/peatón)"] == 0
    x["vehicles_pph"] = 0.000001
    assert calculate("unsignal", x).metrics["Demora media por brechas (s/peatón)"] >= 0


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "texto"])
def test_bad_numeric_data_rejected(value):
    x = sample("queue")
    x["occupants"] = value
    with pytest.raises(ValueError):
        calculate("queue", x)


def test_invalid_geometry_partial_clearance_and_zero_occupation():
    x = sample("walkway")
    x["width_m"] = ".1"
    with pytest.raises(ValueError):
        calculate("walkway", x)
    with pytest.raises(ValueError):
        calculate("signal", dict(cycle_s=60, green_s=70))
    with pytest.raises(ValueError):
        calculate("signal", dict(cycle_s=60, green_s=20, crossing_m=10))
    result = calculate("queue", dict(area_m2=20, excluded_area_m2=0, occupants=0))
    assert result.metrics["Espacio medio (m²/peatón)"] is None
    assert result.metrics["Densidad (peat/m²)"] == 0
