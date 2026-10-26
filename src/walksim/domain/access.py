"""Accesos: capacidad, Erlang C y contratos de proyectos, en unidades SI."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

ENUMS = {
    "layout": {"access", "metro_entry", "metro_exit"},
    "device": {"free", "door", "turnstile", "control"},
    "arrival": {"uniform", "random", "intermittent", "batch"},
    "service": {"constant", "exponential"},
    "service_basis": {"time", "rate"},
}
LABELS = dict(
    layout="Plantilla",
    device="Dispositivo",
    arrival="Patrón de llegada",
    service="Distribución del servicio",
    service_basis="Dato de servicio",
    devices="Número de dispositivos",
    service_s="Tiempo medio por dispositivo (s/peat)",
    service_pph="Tasa por dispositivo (peat/h)",
    rate_pph="Demanda media (peat/h)",
    passengers="Pasajeros por descarga",
    cycle_s="Intervalo entre descargas / picos (s)",
    release_s="Duración de descarga / pico (s)",
    approach_m="Recorrido de aproximación (m)",
    transfer_m="Vestíbulo / pasillo intermedio (m)",
    exit_m="Recorrido final (m)",
    width_m="Ancho útil de recorridos (m)",
    speed_mps="Velocidad de caminata (m/s)",
    waiting_length_m="Largo del área de espera (m)",
    waiting_width_m="Ancho del área de espera (m)",
    stairs="Número de escaleras",
    stair_pph="Capacidad por escalera (peat/h)",
    platform_m2="Área de espera de escaleras / andén (m²)",
    duration_s="Periodo observado (s)",
    warmup_s="Calentamiento (s)",
    clearance_s="Despeje adicional máximo (s)",
    bin_s="Intervalo de gráfica (s)",
    seed="Semilla",
)
CHOICES = {
    "layout": [
        ("Acceso individual", "access"),
        ("Metro · entrada", "metro_entry"),
        ("Metro · descarga del tren", "metro_exit"),
    ],
    "device": [
        ("Torniquete", "turnstile"),
        ("Puerta", "door"),
        ("Filtro / control", "control"),
        ("Acceso libre", "free"),
    ],
    "arrival": [
        ("Uniforme", "uniform"),
        ("Aleatoria (Poisson)", "random"),
        ("Intermitente con micropicos", "intermittent"),
        ("Descarga masiva", "batch"),
    ],
    "service": [("Tiempo constante", "constant"), ("Tiempo exponencial", "exponential")],
    "service_basis": [("Tiempo medio", "time"), ("Tasa de servicio", "rate")],
}
ASSUMPTIONS = [
    "Modelo híbrido: SUMO striping calcula los recorridos planos; eventos discretos resuelven "
    "una fila común FCFS por estación, sin abandono ni prioridades.",
    "El servicio y las escaleras se representan por capacidades introducidas. La escalera es "
    "un punto de servicio equivalente; no se simulan peldaños ni geometría vertical.",
    "Las filas tienen almacenamiento ilimitado. El área sólo convierte acumulación en densidad; "
    "no impone bloqueo, derrame físico ni realimentación hacia los recorridos anteriores.",
    "Cada tramo peatonal se simula por separado. El flujo entre tramos se conserva mediante "
    "los instantes de salida del servicio; no existe interacción espacial entre tramos.",
    "Cola excluye personas atendidas. Acumulación del área incluye cola y personas en servicio. "
    "Densidad es global por área, sin umbrales normativos ni mapa local.",
    "El periodo observado excluye calentamiento. Después cesan las llegadas y se permite el "
    "despeje configurado. Los pendientes y las esperas censuradas se informan explícitamente.",
    "Erlang C sólo aplica a un acceso con llegadas Poisson, servicio exponencial y rho < 1. "
    "Es una referencia estacionaria, distinta de la simulación híbrida finita.",
]


@dataclass
class AccessInput:
    layout: str = "access"
    device: str = "turnstile"
    arrival: str = "uniform"
    service: str = "constant"
    service_basis: str = "time"
    devices: int = 2
    service_s: float = 2.0
    service_pph: float = 1800
    rate_pph: float = 2400
    passengers: int = 300
    cycle_s: float = 180
    release_s: float = 30
    approach_m: float = 15
    transfer_m: float = 20
    exit_m: float = 15
    width_m: float = 3
    speed_mps: float = 1.2
    waiting_length_m: float = 10
    waiting_width_m: float = 5
    stairs: int = 1
    stair_pph: float = 3600
    platform_m2: float = 100
    duration_s: float = 600
    warmup_s: float = 60
    clearance_s: float = 600
    bin_s: float = 30
    seed: int = 42

    def to_dict(self):
        return asdict(self)

    @classmethod
    def parse(cls, raw):
        x = cls()
        if not isinstance(raw, dict) or set(raw) - set(x.to_dict()):
            raise ValueError("Campos de acceso desconocidos.")
        for k, allowed in ENUMS.items():
            v = raw.get(k, getattr(x, k))
            if v not in allowed:
                raise ValueError(f"{LABELS[k]}: opción desconocida.")
            setattr(x, k, v)
        for k in active_keys(x):
            if k in ENUMS:
                continue
            try:
                value = raw.get(k, getattr(x, k))
                if isinstance(value, bool):
                    raise ValueError()
                value = float(str(value).replace(",", "."))
                if not math.isfinite(value):
                    raise ValueError()
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{LABELS[k]}: introduzca un número finito.") from exc
            if k in {"devices", "stairs", "passengers", "seed"}:
                if value != int(value):
                    raise ValueError(f"{LABELS[k]}: debe ser entero.")
                value = int(value)
            limits = {
                "devices": (1, 100),
                "stairs": (1, 100),
                "passengers": (1, 10000),
                "seed": (0, 2147483647),
                "rate_pph": (0, 40000),
                "service_s": (0.05, 600),
                "service_pph": (6, 72000),
                "stair_pph": (6, 72000),
                "approach_m": (5, 500),
                "transfer_m": (5, 500),
                "exit_m": (5, 500),
                "width_m": (0.5, 20),
                "speed_mps": (0.2, 3),
                "waiting_length_m": (0.1, 1000),
                "waiting_width_m": (0.1, 1000),
                "platform_m2": (0.1, 100000),
                "duration_s": (60, 14400),
                "warmup_s": (0, 3600),
                "clearance_s": (0, 7200),
                "bin_s": (1, 600),
                "cycle_s": (1, 3600),
                "release_s": (0.1, 3600),
            }
            lo, hi = limits[k]
            if not lo <= value <= hi:
                raise ValueError(f"{LABELS[k]}: rango permitido {lo}–{hi}.")
            setattr(x, k, value)
        if x.arrival in {"batch", "intermittent"} and x.release_s > x.cycle_s:
            raise ValueError("La duración de la descarga no puede superar su intervalo.")
        if x.bin_s > x.duration_s:
            raise ValueError("El intervalo de gráfica debe ser menor o igual al periodo observado.")
        return x


def active_keys(x):
    keys = ["layout", "device", "arrival"] + [
        "approach_m",
        "exit_m",
        "width_m",
        "speed_mps",
        "duration_s",
        "warmup_s",
        "clearance_s",
        "bin_s",
        "seed",
    ]
    if x.device != "free" or x.layout != "access":
        keys += ["service"]
    if x.device != "free":
        keys += [
            "service_basis",
            "devices",
            "service_s" if x.service_basis == "time" else "service_pph",
            "waiting_length_m",
            "waiting_width_m",
        ]
    if x.arrival == "batch":
        keys += ["passengers", "cycle_s", "release_s"]
    else:
        keys += ["rate_pph"]
        if x.arrival == "intermittent":
            keys += ["cycle_s", "release_s"]
    if x.layout != "access":
        keys += ["transfer_m", "stairs", "stair_pph", "platform_m2"]
    return keys


def signature(raw):
    return hashlib.sha256(
        json.dumps(AccessInput.parse(raw).to_dict(), sort_keys=True).encode()
    ).hexdigest()


def stages(x):
    result = []
    if x.device != "free":
        mean = x.service_s if x.service_basis == "time" else 3600 / x.service_pph
        result.append(
            dict(
                key="gate",
                label=dict(door="Puertas", turnstile="Torniquetes", control="Filtro / control")[
                    x.device
                ],
                servers=x.devices,
                mean_s=mean,
                area_m2=x.waiting_length_m * x.waiting_width_m,
            )
        )
    if x.layout != "access":
        stair = dict(
            key="stairs",
            label="Escaleras · capacidad equivalente",
            servers=x.stairs,
            mean_s=3600 / x.stair_pph,
            area_m2=x.platform_m2,
        )
        result.insert(0 if x.layout == "metro_exit" else len(result), stair)
    return result


def erlang_c(rate, mean, servers):
    rho = rate * mean / (3600 * servers)
    if rho >= 1:
        return None
    if rate == 0:
        return dict(probability_wait=0.0, mean_wait_s=0.0, mean_queue=0.0)
    # Stable Erlang B recursion, then B -> C; avoids factorial overflow.
    offered, b = rate * mean / 3600, 1.0
    for n in range(1, servers + 1):
        b = offered * b / (n + offered * b)
    c = b / (1 - rho + rho * b)
    wait = c * mean / (servers * (1 - rho))
    return dict(probability_wait=c, mean_wait_s=wait, mean_queue=rate / 3600 * wait)


def evaluate_access(raw):
    x = AccessInput.parse(raw)
    rate = x.passengers * 3600 / x.cycle_s if x.arrival == "batch" else x.rate_pph
    ss = stages(x)
    capacity = min((s["servers"] * 3600 / s["mean_s"] for s in ss), default=None)
    ratio = rate / capacity if capacity else None
    metrics = {
        "Demanda media nominal (peat/h)": rate,
        "Capacidad de servicio (peat/h)": capacity,
        "Demanda / capacidad": ratio,
        "Crecimiento nominal si sobrecarga (peat/min)": max(0, rate - capacity) / 60
        if capacity
        else 0,
    }
    if x.arrival == "batch" and capacity:
        metrics.update(
            {
                "Capacidad de servicio por intervalo (peat)": capacity * x.cycle_s / 3600,
                "Reserva nominal por intervalo (peat)": capacity * x.cycle_s / 3600 - x.passengers,
                "Cota de atención de una descarga aislada (s)": x.passengers / capacity * 3600,
            }
        )
    warnings = []
    if ratio is not None and ratio >= 1:
        warnings.append(
            "La demanda nominal alcanza o supera el servicio; no existe régimen "
            "estacionario estable. La simulación finita conserva los pendientes."
        )
    reference = None
    if x.layout == "access" and ss and x.arrival == "random" and x.service == "exponential":
        reference = erlang_c(rate, ss[0]["mean_s"], ss[0]["servers"])
    return dict(
        inputs=x.to_dict(),
        signature=signature(raw),
        metrics=metrics,
        stages=ss,
        reference=reference,
        warnings=warnings,
        assumptions=ASSUMPTIONS,
        created_at=datetime.now(UTC).isoformat(),
    )


def new_case(name="Base · acceso", inputs=None):
    raw = {**AccessInput().to_dict(), **(inputs or {})}
    return dict(
        id=uuid.uuid4().hex,
        name=name,
        inputs=raw,
        origins={k: "default" for k in raw},
        analytical=None,
        simulation=None,
    )


def fresh(case, kind):
    try:
        return bool(case.get(kind)) and case[kind]["signature"] == signature(case["inputs"])
    except (ValueError, KeyError):
        return False


def validate_study(study):
    if study == {}:
        return {}
    if not isinstance(study, dict) or not isinstance(study.get("cases"), list):
        raise ValueError("Estudio de accesos incorrecto.")
    cases = study["cases"]
    if not 1 <= len(cases) <= 30:
        raise ValueError("Accesos admite de 1 a 30 escenarios.")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise ValueError("Escenario de accesos incorrecto.")
        if case["id"] in ids or not 1 <= len(case["id"]) <= 100:
            raise ValueError("Identificador repetido o incorrecto.")
        ids.add(case["id"])
        if not isinstance(case.get("name"), str) or not 1 <= len(case["name"]) <= 200:
            raise ValueError("Nombre de acceso incorrecto.")
        raw = case.get("inputs")
        if not isinstance(raw, dict) or set(raw) != set(AccessInput().to_dict()):
            raise ValueError("Datos de acceso incompletos.")
        for k, v in raw.items():
            if k in ENUMS:
                if v not in ENUMS[k]:
                    raise ValueError("Opción de acceso desconocida.")
            elif not isinstance(v, (str, int, float)) or isinstance(v, bool):
                raise ValueError("Borrador de acceso incorrecto.")
        origins = case.get("origins")
        if (
            not isinstance(origins, dict)
            or set(origins) != set(raw)
            or any(v not in {"default", "entered", "observed", "csv"} for v in origins.values())
        ):
            raise ValueError("Procedencia de datos incorrecta.")
        a, s = case.get("analytical"), case.get("simulation")
        if a is not None:
            expected = evaluate_access(a["inputs"])
            if any(
                a.get(k) != expected[k] for k in ("signature", "metrics", "stages", "reference")
            ):
                raise ValueError("Resultado analítico de acceso inconsistente.")
        if s is not None:
            validate_simulation(s)
    if study.get("selected_id") not in ids:
        raise ValueError("Escenario de acceso seleccionado desconocido.")
    return copy.deepcopy(study)


def validate_simulation(s):
    if not isinstance(s, dict) or s.get("signature") != signature(s["inputs"]):
        raise ValueError("Resultado de accesos inconsistente.")
    from walksim.access_labels import STAGE_LABELS, SUMMARY_LABELS

    summary = s["summary"]
    if not isinstance(summary, dict) or set(summary) != set(SUMMARY_LABELS):
        raise ValueError("Indicadores de acceso incompletos.")
    nullable = {"mean_wait_s", "max_wait_s", "p95_wait_s", "mean_trip_s", "clearance_s"}
    for k, v in summary.items():
        if v is None and k in nullable:
            continue
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
            raise ValueError("Indicador de acceso incorrecto.")
    for k in ("generated", "completed", "pending", "cohort_generated", "cohort_completed"):
        if type(summary[k]) is not int or summary[k] < 0:
            raise ValueError("Conteos de acceso incorrectos.")
    if summary["generated"] != summary["completed"] + summary["pending"]:
        raise ValueError("No se conserva la demanda de accesos.")
    if not 0 <= summary["cohort_completed"] <= summary["cohort_generated"] <= summary["generated"]:
        raise ValueError("Cohorte de accesos incorrecta.")
    x = AccessInput.parse(s["inputs"])
    expected_stages = stages(x)
    if len(s["stages"]) != len(expected_stages):
        raise ValueError("Estaciones de servicio incorrectas.")
    for stage, expected in zip(s["stages"], expected_stages, strict=True):
        if not isinstance(stage, dict) or set(stage) != {"key", "label", *STAGE_LABELS}:
            raise ValueError("Indicadores de estación incompletos.")
        for k in (
            "arrived",
            "processed",
            "pending",
            "wait_sample",
            "wait_censored",
            "pending_at_observation_end",
            "max_queue",
            "max_accumulation",
        ):
            if type(stage[k]) is not int or not 0 <= stage[k] <= summary["generated"]:
                raise ValueError("Conteo de estación incorrecto.")
        for k in STAGE_LABELS:
            if stage[k] is None and k in {"mean_wait_s", "max_wait_s", "p95_wait_s"}:
                continue
            if type(stage[k]) not in (int, float) or not math.isfinite(stage[k]) or stage[k] < 0:
                raise ValueError("Indicador de estación incorrecto.")
        if any(stage.get(k) != v for k, v in expected.items()):
            raise ValueError("Capacidades de servicio inconsistentes.")
        if stage["processed"] + stage["pending"] != stage["arrived"]:
            raise ValueError("Conteos de servicio inconsistentes.")
    series_keys = {"time_s", "interval_s", "generated", "completed", "mean_system"}
    for stage in expected_stages:
        series_keys.update({stage["key"] + "_queue", stage["key"] + "_density"})
    for i, row in enumerate(s["series"]):
        if (
            not isinstance(row, dict)
            or set(row) != series_keys
            or not math.isclose(row["time_s"], i * x.bin_s, abs_tol=1e-7)
            or not math.isclose(
                row["interval_s"], min(x.bin_s, x.duration_s - i * x.bin_s), abs_tol=1e-7
            )
        ):
            raise ValueError("Intervalos de acceso incorrectos.")
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in row.values()):
            raise ValueError("Valores de serie incorrectos.")
    if sum(row["generated"] for row in s["series"]) != summary["cohort_generated"]:
        raise ValueError("Cohorte y serie inconsistentes.")
    hist = s["histogram"]
    if not isinstance(hist, list) or len(hist) != (20 if summary["cohort_completed"] else 0):
        raise ValueError("Histograma de espera incorrecto.")
    for row in hist:
        if (
            not isinstance(row, dict)
            or set(row) != {"start_s", "end_s", "count"}
            or type(row["count"]) is not int
            or row["count"] < 0
            or type(row["start_s"]) not in (int, float)
            or type(row["end_s"]) not in (int, float)
            or not 0 <= row["start_s"] < row["end_s"]
        ):
            raise ValueError("Intervalo de histograma incorrecto.")
    if sum(row["count"] for row in s["histogram"]) != summary["cohort_completed"]:
        raise ValueError("Muestra de espera inconsistente.")
    for key in ("warnings", "definitions"):
        if not isinstance(s[key], list) or not all(isinstance(v, str) for v in s[key]):
            raise ValueError("Notas de simulación incorrectas.")
    for row in s["train_residuals"]:
        if (
            set(row) != {"time_s", "remaining"}
            or type(row["remaining"]) is not int
            or not 0 <= row["remaining"] <= summary["generated"]
            or type(row["time_s"]) not in (int, float)
            or not 0 < row["time_s"] < x.warmup_s + x.duration_s
        ):
            raise ValueError("Acumulación entre descargas incorrecta.")
    if len(s["series"]) != math.ceil(x.duration_s / x.bin_s):
        raise ValueError("Series de acceso incompletas.")
    if abs(sum(r["interval_s"] for r in s["series"]) - x.duration_s) > 1e-6:
        raise ValueError("Periodo de series incorrecto.")

    def check(value):
        if isinstance(value, dict):
            for v in value.values():
                check(v)
        elif isinstance(value, list):
            for v in value:
                check(v)
        elif isinstance(value, (int, float)) and (not math.isfinite(value) or value < 0):
            raise ValueError("Indicador de simulación no válido.")

    for item in (summary, s["series"], s["stages"], s["histogram"]):
        check(item)
    if not isinstance(s.get("engine_version"), str) or not isinstance(s.get("created_at"), str):
        raise ValueError("Metadatos de simulación incorrectos.")
