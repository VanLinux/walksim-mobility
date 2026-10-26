"""Walkway 3: demanda, diseño inverso y evaluación operacional en SI."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from uuid import uuid4

from walksim.domain.analysis import FT, HCM24, criterion_thresholds, space_los


@dataclass
class WalkwayInput:
    mode: str = "operation"
    flow_type: str = "random"
    demand_basis: str = "hourly"
    length_m: float = 100
    width_m: float = 3
    obstacles_m: float = 0.2
    edges_m: float = 0.3
    flow_ab_pph: float = 900
    flow_ba_pph: float = 600
    count_ab: int = 225
    count_ba: int = 150
    phf: float = 0.9
    speed_mps: float = 1.2
    slope_pct: float = 0
    target_los: str = "C"
    margin_pct: float = 1
    share_ab_pct: float = 60
    duration_s: float = 900
    warmup_s: float = 120
    bin_s: float = 30
    seed: int = 42
    platoon_cycle_s: float = 60
    platoon_release_s: float = 15

    @classmethod
    def parse(cls, raw: dict) -> WalkwayInput:
        default = asdict(cls())
        if not isinstance(raw, dict) or set(raw) - set(default):
            raise ValueError("Campos de Walkway desconocidos.")
        value = default | raw
        choices = {
            "mode": ("operation", "design_width", "design_demand"),
            "flow_type": ("random", "platoon"),
            "demand_basis": ("hourly", "count"),
            "target_los": tuple("ABCDE"),
        }
        for key, allowed in choices.items():
            if value[key] not in allowed:
                raise ValueError(f"Opción no válida: {key}.")
        active = {
            "length_m",
            "obstacles_m",
            "edges_m",
            "speed_mps",
            "slope_pct",
            "duration_s",
            "warmup_s",
            "bin_s",
            "seed",
            *choices,
        }
        if value["mode"] != "design_width":
            active.add("width_m")
        if value["mode"] != "design_demand":
            active.update(
                ("flow_ab_pph", "flow_ba_pph", "phf")
                if value["demand_basis"] == "hourly"
                else ("count_ab", "count_ba")
            )
        else:
            active.add("share_ab_pct")
            if value["demand_basis"] == "hourly":
                active.add("phf")
        if value["mode"] != "operation":
            active.update(("target_los", "margin_pct"))
        if value["flow_type"] == "platoon":
            active.update(("platoon_cycle_s", "platoon_release_s"))
        for key in set(default) - active:
            value[key] = default[key]
        for key in set(default) - set(choices):
            try:
                if isinstance(value[key], bool):
                    raise ValueError()
                value[key] = float(str(value[key]).replace(",", "."))
                if not math.isfinite(value[key]):
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{key}: introduzca un número finito.") from exc
        bounds = {
            "length_m": (5, 2000),
            "width_m": (0.5, 50),
            "obstacles_m": (0, 49),
            "edges_m": (0, 49),
            "flow_ab_pph": (0, 20000),
            "flow_ba_pph": (0, 20000),
            "count_ab": (0, 100000),
            "count_ba": (0, 100000),
            "phf": (0.01, 1),
            "speed_mps": (0.2, 3),
            "slope_pct": (-5, 5),
            "margin_pct": (0.01, 25),
            "share_ab_pct": (0, 100),
            "duration_s": (60, 14400),
            "warmup_s": (0, 7200),
            "bin_s": (5, 300),
            "seed": (0, 2147483647),
            "platoon_cycle_s": (10, 600),
            "platoon_release_s": (1, 600),
        }
        for key, (low, high) in bounds.items():
            if not low <= value[key] <= high:
                raise ValueError(f"{key}: rango permitido {low:g}–{high:g}.")
        for key in ("count_ab", "count_ba", "seed"):
            if not value[key].is_integer():
                raise ValueError(f"{key} debe ser entero.")
            value[key] = int(value[key])
        result = cls(**value)
        if result.flow_type == "platoon" and result.demand_basis == "hourly":
            raise ValueError(
                "Para pelotones use el conteo de 5 min; el PHF de 15 min no lo sustituye."
            )
        if result.platoon_release_s > result.platoon_cycle_s:
            raise ValueError("La descarga del pelotón no puede superar su intervalo.")
        if result.mode != "design_width" and result.effective_width <= 0:
            raise ValueError("Los descuentos consumen todo el ancho: revise el ancho efectivo.")
        return result

    @property
    def effective_width(self) -> float:
        return self.width_m - self.obstacles_m - self.edges_m

    def to_dict(self) -> dict:
        return asdict(self)


def signature(raw: dict) -> str:
    data = WalkwayInput.parse(raw).to_dict()
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def evaluate_walkway(raw: dict) -> dict:
    x = WalkwayInput.parse(raw)
    table = "platoon" if x.flow_type == "platoon" else "walkway"
    thresholds = criterion_thresholds(table)
    target_space = thresholds["ABCDE".index(x.target_los)]
    c = (18 if x.flow_type == "platoon" else 23) / FT
    if x.demand_basis == "hourly":
        ab, ba = x.flow_ab_pph / x.phf, x.flow_ba_pph / x.phf
    else:
        interval = 5 if x.flow_type == "platoon" else 15
        ab, ba = x.count_ab * 60 / interval, x.count_ba * 60 / interval
    demand = ab + ba
    warnings = []
    width = x.effective_width
    width_limit = demand * target_space / (3600 * x.speed_mps)
    width_required = max(width_limit * (1 + x.margin_pct / 100), demand / (60 * c), 0.5)
    total_required = math.ceil((width_required + x.obstacles_m + x.edges_m) * 100 - 1e-10) / 100
    if x.mode == "design_width":
        width = total_required - x.obstacles_m - x.edges_m
    max_peak = min(
        3600 * x.speed_mps * width / target_space / (1 + x.margin_pct / 100), 60 * c * width
    )
    if x.mode == "design_demand":
        demand = max_peak
        ab, ba = demand * x.share_ab_pct / 100, demand * (1 - x.share_ab_pct / 100)
    q = demand / (60 * width)
    density = q / (60 * x.speed_mps)
    space = 1 / density if density else None
    los_space = space_los(space, thresholds)
    los = "F" if q > c else los_space
    if q > c:
        warnings.append(
            "La demanda supera la capacidad: la relación flujo–velocidad estacionaria "
            "no representa una operación sostenible."
        )
    if x.warmup_s < x.length_m / x.speed_mps:
        warnings.append(
            "El calentamiento es menor que un tiempo libre de recorrido; "
            "la ocupación simulada puede estar influida por el arranque vacío."
        )
    if x.obstacles_m + x.edges_m:
        warnings.append(
            "La microsimulación utiliza el ancho útil uniforme; "
            "los descuentos no crean obstáculos puntuales en la geometría."
        )
    if x.slope_pct:
        warnings.append(
            "La pendiente de hasta 5 % se documenta; se simula un corredor plano "
            "con la velocidad introducida, sin corrección biomecánica de pendiente."
        )
    if x.flow_type == "platoon":
        warnings.append(
            "El conteo de 5 min define la demanda media. La forma temporal del pelotón "
            "se configura mediante intervalo y duración de descarga."
        )
    peak_label = (
        "Tasa equivalente de los 5 min" if x.flow_type == "platoon" else "Tasa de diseño de 15 min"
    )
    metrics = {
        "Ancho efectivo evaluado (m)": width,
        "Demanda de diseño (peat/h)": demand,
        "Flujo específico (peat/min/m)": q,
        "Velocidad de entrada (m/s)": x.speed_mps,
        "Densidad estimada (peat/m²)": density,
        "Espacio estimado (m²/peatón)": space,
        "Capacidad de referencia (peat/h)": c * width * 60,
        "Relación demanda/capacidad": q / c,
        "LOS por espacio": los_space,
        "LOS operativo": los,
        "Tiempo libre nominal (s)": x.length_m / x.speed_mps,
    }
    if x.mode == "design_width":
        metrics["Ancho total propuesto (m)"] = total_required
        metrics["Límite teórico de ancho por espacio (m)"] = width_limit
    if x.mode == "design_demand":
        metrics["Demanda máxima de diseño con margen (peat/h)"] = max_peak
        if x.demand_basis == "hourly":
            metrics["Demanda horaria admisible (peat/h)"] = max_peak * x.phf
        else:
            minutes = 5 if x.flow_type == "platoon" else 15
            metrics[f"Conteo total admisible en {minutes} min (peat)"] = math.floor(
                max_peak * minutes / 60
            )
    equations = [
        r"W_E = W_T-W_O-W_B",
        r"Q_d=Q_h/PHF\quad\mathrm{o}\quad Q_d=60N/T",
        r"q=Q_d/(60W_E)",
        r"D=q/(60S)",
        r"M=1/D",
        r"X=Q_d/(60cW_E)",
    ]
    if x.mode != "operation":
        equations += [
            r"W_{E,lim}=Q_d M_{obj}/(3600 S)",
            r"Q_{d,max}=\min(3600 S W_E/(M_{obj}(1+m)),60cW_E)",
        ]
    return dict(
        inputs=x.to_dict(),
        signature=signature(raw),
        metrics=metrics,
        resolved=dict(
            length_m=x.length_m,
            width_m=width,
            flow_ab_pph=ab,
            flow_ba_pph=ba,
            walking_speed_mps=x.speed_mps,
            analysis_time_s=x.duration_s + x.warmup_s,
            seed=x.seed,
        ),
        warnings=warnings,
        source=HCM24,
        thresholds=thresholds,
        equations=equations,
        assumptions=[
            peak_label + "; no se vuelve a aplicar PHF a conteos directos.",
            "Relación estacionaria con velocidad representativa; el diseño es condicional "
            "a esa velocidad y a la tabla de espacio del HCM 7.",
            "El objetivo es LOS " + x.target_los + " o mejor. El margen positivo evita "
            "clasificar exactamente en un límite inferior estricto.",
            "La capacidad es una referencia. El ancho propuesto se redondea hacia arriba "
            "a centímetros; no sustituye criterios de accesibilidad o ancho normativo mínimo.",
        ],
        created_at=datetime.now(UTC).isoformat(),
    )


def new_case(name: str = "Base", inputs: dict | None = None) -> dict:
    return dict(
        id=uuid4().hex,
        name=name,
        inputs=inputs or WalkwayInput().to_dict(),
        origins={f.name: "default" for f in fields(WalkwayInput)},
        analytical=None,
        simulation=None,
    )


def validate_study(study: dict) -> dict:
    """Acepta borradores incompletos, pero valida todos los resultados y sus identidades."""
    if not study:
        return {}
    if not isinstance(study, dict) or not isinstance(study.get("cases"), list):
        raise ValueError("Estudio Walkway no válido.")
    cases = study["cases"]
    if not 1 <= len(cases) <= 30:
        raise ValueError("El estudio admite entre 1 y 30 escenarios Walkway.")
    if study.get("chart", "overview") not in ("overview", "speed"):
        raise ValueError("Gráfica seleccionada no válida.")
    seen = set()
    keys = set(WalkwayInput().to_dict())
    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("id"), str)
            or not case["id"]
            or len(case["id"]) > 200
            or case["id"] in seen
            or not isinstance(case.get("name"), str)
            or not isinstance(case.get("inputs"), dict)
            or set(case["inputs"]) != keys
            or any(
                not isinstance(v, (str, int, float)) or isinstance(v, bool)
                for v in case["inputs"].values()
            )
        ):
            raise ValueError("Escenario Walkway no válido o duplicado.")
        for key, allowed in {
            "mode": ("operation", "design_width", "design_demand"),
            "flow_type": ("random", "platoon"),
            "demand_basis": ("hourly", "count"),
            "target_los": tuple("ABCDE"),
        }.items():
            if case["inputs"][key] not in allowed:
                raise ValueError("Tipo de borrador no válido.")
        seen.add(case["id"])
        if (
            not isinstance(case.get("origins"), dict)
            or set(case["origins"]) - keys
            or any(
                v not in ("default", "entered", "observed", "csv") for v in case["origins"].values()
            )
        ):
            raise ValueError("Origen de datos no válido.")
        for kind in ("analytical", "simulation"):
            saved = case.get(kind)
            if saved is None:
                continue
            if not isinstance(saved, dict) or saved.get("signature") != signature(saved["inputs"]):
                raise ValueError("Resultado Walkway sin correspondencia con sus entradas.")
            if kind == "analytical":
                computed = evaluate_walkway(saved["inputs"])
                if any(saved.get(k) != v for k, v in computed.items() if k != "created_at"):
                    raise ValueError("Resultado analítico inconsistente.")
            else:
                _validate_simulation(saved)
    if study.get("selected_id") not in seen:
        raise ValueError("El escenario seleccionado no existe.")
    return study


def _validate_simulation(saved: dict) -> None:
    numeric = (int, float)
    summary_keys = {
        "generated",
        "started",
        "completed",
        "unfinished",
        "not_started",
        "cohort_entered",
        "cohort_completed",
        "mean_occupancy",
        "max_occupancy",
        "density",
        "space",
        "los_indicative",
        "entered_pph",
        "exited_pph",
    }
    summary = saved.get("summary")
    if not isinstance(summary, dict) or set(summary) != summary_keys:
        raise ValueError("Resumen simulado no válido.")
    for key, value in summary.items():
        if key == "los_indicative":
            if value not in tuple("ABCDEF"):
                raise ValueError("LOS simulado no válido.")
        elif value is not None and (
            not isinstance(value, numeric)
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("Medición simulada no válida.")
    if (
        summary["started"] + summary["not_started"] != summary["generated"]
        or summary["completed"] + summary["unfinished"] != summary["started"]
        or summary["cohort_completed"] > summary["cohort_entered"]
    ):
        raise ValueError("No se conserva la población simulada.")
    directions = saved.get("directions")
    if not isinstance(directions, dict) or set(directions) != {"total", "ab", "ba"}:
        raise ValueError("Resultados direccionales no válidos.")
    direction_keys = {
        "count",
        "mean_s",
        "min_s",
        "max_s",
        "p50_s",
        "p85_s",
        "p95_s",
        "spatial_speed_mps",
        "mean_speed_mps",
        "mean_loss_s",
    }
    for values in directions.values():
        if not isinstance(values, dict) or set(values) != direction_keys:
            raise ValueError("Estadísticos direccionales no válidos.")
        if any(
            v is not None and (not isinstance(v, numeric) or not math.isfinite(v) or v < 0)
            for v in values.values()
        ):
            raise ValueError("Estadístico simulado no válido.")
    series = saved.get("series")
    if not isinstance(series, list) or not 1 <= len(series) <= 5000:
        raise ValueError("Serie temporal no válida.")
    series_keys = {
        "time_s",
        "interval_s",
        "occupancy",
        "density",
        "entered",
        "exited",
        "flow_pph",
        "speed_mps",
    }
    previous = 0
    for row in series:
        if not isinstance(row, dict) or set(row) != series_keys:
            raise ValueError("Fila de serie temporal no válida.")
        if any(
            (v is None and k != "speed_mps")
            or (v is not None and (not isinstance(v, numeric) or not math.isfinite(v) or v < 0))
            for k, v in row.items()
        ):
            raise ValueError("Valor de serie temporal no válido.")
        if abs(row["time_s"] - previous) > 1e-6 or row["interval_s"] <= 0:
            raise ValueError("Intervalos temporales no válidos.")
        previous += row["interval_s"]
    if abs(previous - saved["inputs"]["duration_s"]) > 1e-6:
        raise ValueError("La serie temporal no coincide con el periodo observado.")
    if not isinstance(saved.get("comparison"), list):
        raise ValueError("Comparación simulada no válida.")
    for row in saved["comparison"]:
        if not isinstance(row, dict) or set(row) != {
            "label",
            "unit",
            "analytical",
            "simulated",
            "delta_pct",
        }:
            raise ValueError("Indicadores comparados no válidos.")
        if not all(isinstance(row[k], str) for k in ("label", "unit")):
            raise ValueError("Etiquetas de comparación no válidas.")
        if any(
            not isinstance(row[k], (str, int, float, type(None)))
            for k in ("analytical", "simulated", "delta_pct")
        ):
            raise ValueError("Valores comparados no válidos.")
    for key in ("warnings", "definitions"):
        if not isinstance(saved.get(key), list) or not all(isinstance(v, str) for v in saved[key]):
            raise ValueError("Definiciones de microsimulación no válidas.")
    for key in ("engine_version", "model", "created_at"):
        if not isinstance(saved.get(key), str):
            raise ValueError("Metadatos de microsimulación no válidos.")
    travel = saved.get("travel_times_s")
    if (
        not isinstance(travel, list)
        or len(travel) > 200000
        or any(not isinstance(v, numeric) or not math.isfinite(v) or v <= 0 for v in travel)
    ):
        raise ValueError("Distribución de tiempos no válida.")
