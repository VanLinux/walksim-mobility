"""Un cruce semaforizado, cuatro indicadores; sin clasificación LOS ni diseño normativo."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

LABELS = dict(
    length_m="Longitud del cruce entre aceras (m)",
    width_m="Ancho del paso peatonal (m)",
    ped_ab="Peatones A → B (peat/h)",
    ped_ba="Peatones B → A (peat/h)",
    speed_mps="Velocidad peatonal (m/s)",
    cycle_s="Ciclo del semáforo (s)",
    walk_s="Verde para iniciar el cruce (s)",
    clearance_s="Intervalo de despeje peatonal (s)",
    vehicles_ph="Vehículos totales en ambos sentidos (veh/h)",
    duration_s="Duración de la demanda (s)",
    seed="Semilla",
)
ASSUMPTIONS = [
    "Un cruce semaforizado aislado, recto y sin refugio, giros ni otros cruces. "
    "No se asigna LOS HCM ni se evalúa seguridad vial o cumplimiento normativo.",
    "Referencia de recorrido t = L/v: longitud entre aceras dividida entre velocidad, "
    "sin espera ni congestión. El capítulo 24 del HCM no se aplica a este cruce.",
    "Ciclo fijo: verde vehicular, amarillo vehicular de 3 s, verde peatonal para iniciar "
    "y despeje con todos en rojo. El ciclo empieza con verde vehicular. "
    "Quien ya cruza puede terminar durante el despeje; no se permiten nuevas entradas.",
    "La vía tiene un carril por sentido, cada uno de ancho L/2; son carriles equivalentes "
    "de esta plantilla, no una propuesta de diseño vial. El caudal vehicular se divide "
    "por igual; velocidad deseada 30 km/h, modelo Krauss y sin giros.",
    "Llegadas Poisson independientes por sentido con semilla común entre alternativas. "
    "Velocidad peatonal deseada constante; modelo striping. No hay calibración de campo.",
    "Cola = peatones antes de entrar al paso que avanzan a menos de 0.1 m/s. "
    "Se muestrea cada 0.5 s en las áreas de aproximación y espera, incluyendo accesos saturados. "
    "Los máximos son muestreados y se presentan por acera.",
    "Espera = tiempo detenido antes de entrar al cruce, con muestreo de 0.5 s; "
    "se excluyen recorrido, demoras durante el cruce y demora de inserción. "
    "La media usa peatones que ya entraron al paso antes del cierre de simulación; "
    "los que aún esperan se informan por separado.",
    "Los peatones se generan 10 m antes del área de espera y terminan 10 m después "
    "del área de salida. "
    "Completar el cruce significa salir del paso a la acera opuesta, no terminar el acceso. "
    "Tras cerrar la demanda se simulan dos ciclos más para observar el despeje.",
]
SUMMARY_LABELS = dict(
    generated="Peatones programados",
    inserted="Peatones insertados",
    entered="Peatones que iniciaron el cruce (muestra de espera)",
    completed="Peatones que completaron el cruce",
    pending="Peatones pendientes de completar",
    not_inserted="Peatones pendientes de inserción",
    waiting="Peatones insertados que aún no iniciaron",
    crossing="Peatones aún en el paso",
    mean_wait_s="Espera media antes de iniciar (s)",
    max_queue_ab="Cola máxima en acera A (peat)",
    max_queue_ba="Cola máxima en acera B (peat)",
    completed_pct="Peatones que completaron (%)",
)


@dataclass
class CrossingInput:
    length_m: float = 10
    width_m: float = 4
    ped_ab: float = 180
    ped_ba: float = 120
    speed_mps: float = 1.2
    cycle_s: float = 80
    walk_s: float = 18
    clearance_s: float = 12
    vehicles_ph: float = 600
    duration_s: float = 600
    seed: int = 42

    def to_dict(self):
        return asdict(self)

    @classmethod
    def parse(cls, raw):
        x = cls()
        if not isinstance(raw, dict) or set(raw) - set(LABELS):
            raise ValueError("Campos del cruce desconocidos.")
        bounds = dict(
            length_m=(5, 20),
            width_m=(2, 10),
            ped_ab=(0, 3000),
            ped_ba=(0, 3000),
            speed_mps=(0.3, 2.5),
            cycle_s=(20, 240),
            walk_s=(3, 120),
            clearance_s=(1, 120),
            vehicles_ph=(0, 2000),
            duration_s=(60, 1800),
            seed=(0, 2147483647),
        )
        for k, (lo, hi) in bounds.items():
            try:
                v = raw.get(k, getattr(x, k))
                if isinstance(v, bool):
                    raise ValueError()
                v = float(str(v).replace(",", "."))
                if not math.isfinite(v) or not lo <= v <= hi:
                    raise ValueError()
                if k in {"seed", "cycle_s", "walk_s", "clearance_s", "duration_s"}:
                    if v != int(v):
                        raise ValueError()
                    v = int(v)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(
                    f"{LABELS[k]}: use un valor entre {lo} y {hi}"
                    + (" entero." if k.endswith("_s") or k == "seed" else ".")
                ) from exc
            setattr(x, k, v)
        if x.cycle_s - x.walk_s - x.clearance_s - 3 < 5:
            raise ValueError(
                "El ciclo debe reservar al menos 5 s de verde vehicular y 3 s de amarillo."
            )
        if x.ped_ab + x.ped_ba <= 0:
            raise ValueError("Introduzca demanda peatonal en al menos un sentido.")
        end = x.duration_s + 2 * x.cycle_s
        expected = (x.ped_ab + x.ped_ba + x.vehicles_ph) * x.duration_s / 3600
        if expected > 3000 or expected * end > 2_000_000:
            raise ValueError("Reduzca demanda o duración para mantener una simulación ligera.")
        return x


def signature(raw):
    x = CrossingInput.parse(raw)
    return hashlib.sha256(json.dumps(x.to_dict(), sort_keys=True).encode()).hexdigest()


def evaluate_crossing(raw):
    x = CrossingInput.parse(raw)
    warnings = []
    if x.clearance_s < x.length_m / x.speed_mps:
        warnings.append(
            "El despeje introducido es menor que L/v. Revise los tiempos; "
            "esta comparación es orientativa y no sustituye una norma de diseño."
        )
    return dict(
        inputs=x.to_dict(),
        signature=signature(raw),
        reference_s=x.length_m / x.speed_mps,
        vehicle_green_s=x.cycle_s - x.walk_s - x.clearance_s - 3,
        warnings=warnings,
        created_at=datetime.now(UTC).isoformat(),
    )


def new_case(name="Base · cruce semaforizado", inputs=None):
    raw = {**CrossingInput().to_dict(), **copy.deepcopy(inputs or {})}
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
    except (ValueError, KeyError, TypeError):
        return False


def validate_study(study):
    if study == {}:
        return {}
    if (
        not isinstance(study, dict)
        or not isinstance(study.get("cases"), list)
        or not (1 <= len(study["cases"]) <= 2)
    ):
        raise ValueError("El cruce admite un caso base y una alternativa.")
    ids = set()
    for c in study["cases"]:
        if (
            not isinstance(c, dict)
            or not isinstance(c.get("id"), str)
            or not (1 <= len(c["id"]) <= 100)
            or c["id"] in ids
        ):
            raise ValueError("Identificador de cruce incorrecto.")
        ids.add(c["id"])
        if not isinstance(c.get("name"), str) or not 1 <= len(c["name"]) <= 200:
            raise ValueError("Nombre del cruce incorrecto.")
        raw = c.get("inputs")
        if (
            not isinstance(raw, dict)
            or set(raw) != set(LABELS)
            or any(type(v) not in (int, float, str) for v in raw.values())
        ):
            raise ValueError("Borrador del cruce incorrecto.")
        if (
            not isinstance(c.get("origins"), dict)
            or set(c["origins"]) != set(LABELS)
            or any(
                v not in {"default", "entered", "observed", "csv"} for v in c["origins"].values()
            )
        ):
            raise ValueError("Procedencia del cruce incorrecta.")
        a = c.get("analytical")
        if a is not None:
            expected = evaluate_crossing(a["inputs"])
            if any(a[k] != expected[k] for k in ("signature", "reference_s", "vehicle_green_s")):
                raise ValueError("Referencia de cruce inconsistente.")
        if c.get("simulation") is not None:
            validate_simulation(c["simulation"])
    if study.get("selected_id") not in ids:
        raise ValueError("Cruce seleccionado desconocido.")
    return copy.deepcopy(study)


def validate_simulation(s):
    x = CrossingInput.parse(s["inputs"])
    if s["signature"] != signature(s["inputs"]) or set(s["summary"]) != set(SUMMARY_LABELS):
        raise ValueError("Resumen de cruce incorrecto.")
    if set(s["directions"]) != {"AB", "BA"}:
        raise ValueError("Sentidos de cruce incompletos.")
    for m in [s["summary"], *s["directions"].values()]:
        if set(m) != set(SUMMARY_LABELS):
            raise ValueError("Indicadores de cruce incompletos.")
        for k, v in m.items():
            if v is None and k in {"mean_wait_s", "completed_pct"}:
                continue
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError("Indicadores de cruce no válidos.")
            if k not in {"mean_wait_s", "completed_pct"} and type(v) is not int:
                raise ValueError("Conteos de cruce no enteros.")
        if not (0 <= m["completed"] <= m["entered"] <= m["inserted"] <= m["generated"] <= 5000):
            raise ValueError("Conteos de cruce inconsistentes.")
        if (
            m["pending"] != m["generated"] - m["completed"]
            or m["not_inserted"] != m["generated"] - m["inserted"]
            or m["waiting"] != m["inserted"] - m["entered"]
            or m["crossing"] != m["entered"] - m["completed"]
        ):
            raise ValueError("No se conserva la demanda del cruce.")
        pct = 100 * m["completed"] / m["generated"] if m["generated"] else None
        if m["completed_pct"] != pct or (m["mean_wait_s"] is None) != (m["entered"] == 0):
            raise ValueError("Porcentaje o muestra de espera incorrectos.")
    for k in set(SUMMARY_LABELS) - {"mean_wait_s", "completed_pct", "max_queue_ab", "max_queue_ba"}:
        if s["summary"][k] != sum(v[k] for v in s["directions"].values()):
            raise ValueError("Conteos por sentido inconsistentes.")
    total = s["summary"]["entered"]
    weighted = sum((m["mean_wait_s"] or 0) * m["entered"] for m in s["directions"].values())
    if total and not math.isclose(s["summary"]["mean_wait_s"], weighted / total, abs_tol=1e-6):
        raise ValueError("Media global y muestras por sentido inconsistentes.")
    if (
        s.get("sample_s") != 0.5
        or not isinstance(s.get("engine_version"), str)
        or not isinstance(s.get("created_at"), str)
    ):
        raise ValueError("Metadatos de simulación incorrectos.")
    end = x.duration_s + 2 * x.cycle_s
    if not isinstance(s.get("series"), list) or len(s["series"]) != end * 2:
        raise ValueError("Serie temporal incompleta.")
    for i, r in enumerate(s["series"]):
        if set(r) != {"time_s", "queue_ab", "queue_ba"} or r["time_s"] != i * 0.5:
            raise ValueError("Serie temporal incorrecta.")
        if any(type(r[k]) is not int or not 0 <= r[k] <= 5000 for k in ("queue_ab", "queue_ba")):
            raise ValueError("Cola incorrecta.")
    for d, key in [("AB", "max_queue_ab"), ("BA", "max_queue_ba")]:
        mx = max(r["queue_" + d.lower()] for r in s["series"])
        if s["summary"][key] != mx or s["directions"][d][key] != mx:
            raise ValueError("Máximo de cola inconsistente.")
    if type(s.get("collisions")) is not int or s["collisions"] < 0:
        raise ValueError("Registro de colisiones incorrecto.")
    if not isinstance(s.get("warnings"), list) or any(
        not isinstance(v, str) for v in s["warnings"]
    ):
        raise ValueError("Notas de cruce incorrectas.")
