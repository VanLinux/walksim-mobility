"""Senderos compartidos: PLOS HCM y BLOS con probabilidad de demora documentada."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

CHOICES = {
    "task": [
        ("Peatones y ciclistas", "both"),
        ("Sólo PLOS peatonal", "ped"),
        ("Sólo BLOS ciclista", "bike"),
    ],
    "basis": [("Demanda horaria + PHF", "hourly"), ("Conteos críticos de 15 min", "count")],
    "arrival": [("Uniforme", "uniform"), ("Aleatoria (Poisson)", "random")],
    "centerline": [("Sin línea central", "no"), ("Con línea central", "yes")],
    "delay_source": [
        ("Conteos de intentos y demorados", "counts"),
        ("Probabilidad documentada", "probability"),
    ],
}
LABELS = dict(
    task="Análisis solicitado",
    basis="Datos de demanda",
    arrival="Llegadas",
    centerline="Línea central",
    delay_source="Fuente de demora de rebases",
    length_m="Longitud (m)",
    width_m="Ancho útil total (m)",
    phf="PHF",
    ped_ab="Peatones A → B (peat/h)",
    ped_ba="Peatones B → A (peat/h)",
    bike_ab="Bicicletas A → B (bic/h)",
    bike_ba="Bicicletas B → A (bic/h)",
    count_ped_ab="Conteo peatonal A → B (15 min)",
    count_ped_ba="Conteo peatonal B → A (15 min)",
    count_bike_ab="Conteo ciclista A → B (15 min)",
    count_bike_ba="Conteo ciclista B → A (15 min)",
    ped_speed="Velocidad peatonal media (m/s)",
    bike_speed="Velocidad ciclista media (m/s)",
    ped_sd="Desviación de velocidad peatonal (m/s)",
    bike_sd="Desviación de velocidad ciclista (m/s)",
    attempts_ab="Intentos de rebase observados A → B",
    attempts_ba="Intentos de rebase observados B → A",
    delayed_ab="Rebases demorados observados A → B",
    delayed_ba="Rebases demorados observados B → A",
    probability_ab="Probabilidad documentada A → B (0–1)",
    probability_ba="Probabilidad documentada B → A (0–1)",
    duration_s="Periodo observado (s)",
    warmup_s="Calentamiento (s)",
    clearance_s="Despeje adicional máximo (s)",
    bin_s="Intervalo de serie (s)",
    seed="Semilla",
)
ASSUMPTIONS = [
    "HCM 7, capítulo 24: PLOS usa Fp = qb,s(1−Sp/Sb), Fm = qb,o(1+Sp/Sb) y F = Fp+0.5Fm; "
    "tasas de diseño ajustadas una sola vez por PHF o conteo de 15 min multiplicado por cuatro.",
    "PLOS se evalúa para un peatón representativo por sentido. No se asigna PLOS de un sentido "
    "sin demanda peatonal; los eventos y el LOS no constituyen una medida de seguridad.",
    "BLOS calcula reuniones y rebases activos con distribuciones normales de velocidad, "
    "integración trapezoidal en segmentos de hasta 0.01 mi y dos grupos: peatones y bicicletas. "
    "Corredores, patinadores y bicicletas infantiles se suponen ausentes.",
    "La probabilidad de rebase demorado procede de intentos y demorados observados, o de un "
    "valor documentado por el analista. Sustituye la estimación de bloqueo "
    "de los pasos 4–5 del HCM. "
    "No se estima automáticamente con el ancho ni se toma de la microsimulación.",
    "El BLOS se informa sólo con probabilidad de demora disponible y ancho entre 8 y 20 ft "
    "(2.4384–6.096 m), para sendero pavimentado sin separación por modo. Cambiar el ancho "
    "manteniendo la misma probabilidad produce una comparación condicional.",
    "DPm = AT × PT × PHF conserva la corrección de calibración del HCM incluso con conteos "
    "de 15 min: en esa modalidad PHF sólo se requiere para DPm de BLOS.",
    "SUMO usa bicicletas como vehículos, peatones striping y movimiento lateral por subcarriles. "
    "La sección se representa por dos mitades direccionales compartidas por ambos modos, "
    "con posibilidad de rebase por la mitad contraria según las reglas del motor.",
    "El escenario usa bicicletas de 1.6 m de largo y 0.65 m de ancho, separación lateral "
    "mínima de 0.3 m y buffer peatón–vehículo de 0.5 m, como supuestos de modelo no calibrados.",
    "La línea central interviene en la regresión BLOS; la simulación mantiene las dos mitades "
    "direccionales y no interpreta esa línea como una prohibición de rebase.",
    "Encuentros y rebases simulados se detectan al cambiar el orden longitudinal de dos usuarios "
    "presentes en muestras consecutivas de 0.5 s. Se cuenta cada par una sola vez y se excluye "
    "el calentamiento; son eventos geométricos, no colisiones ni validación del LOS.",
    "Las velocidades individuales deseadas son normales recortadas al rango 0.2–15 m/s; "
    "en modo Sólo PLOS se usan velocidades constantes. Estos perfiles de simulación no "
    "calibran la distribución analítica de velocidades ni representan un modelo ciclista validado.",
    "Las estadísticas de viaje corresponden a la cohorte generada durante observación que "
    "completa antes del límite de despeje. Se informan pendientes y tamaño de muestra.",
    "CROW se usa como marco cualitativo de convivencia y separación. No se asignan mínimos "
    "normativos ni se automatiza su metodología de diseño de redes.",
]
SUMMARY_LABELS = dict(
    generated="Usuarios generados",
    started="Usuarios iniciados",
    completed="Usuarios completados",
    pending="Usuarios pendientes",
    cohort_generated="Generados en observación",
    cohort_completed="Completados de cohorte",
    meetings_pb="Encuentros peatón–bicicleta observados",
    passes_bp="Bicicletas que rebasan peatones",
    meetings_bb="Encuentros entre bicicletas",
    passes_bb="Rebases entre bicicletas",
    clearance_s="Despeje completo adicional (s)",
)
GROUP_LABELS = {
    "P.AB": "Peatones A → B",
    "P.BA": "Peatones B → A",
    "B.AB": "Bicicletas A → B",
    "B.BA": "Bicicletas B → A",
}


@dataclass
class SharedInput:
    task: str = "both"
    basis: str = "hourly"
    arrival: str = "random"
    centerline: str = "no"
    delay_source: str = "counts"
    length_m: float = 200
    width_m: float = 3.048
    phf: float = 0.85
    ped_ab: float = 100
    ped_ba: float = 100
    bike_ab: float = 150
    bike_ba: float = 150
    count_ped_ab: float = 25
    count_ped_ba: float = 25
    count_bike_ab: float = 38
    count_bike_ba: float = 38
    ped_speed: float = 1.519936
    bike_speed: float = 5.722112
    ped_sd: float = 0.268224
    bike_sd: float = 1.519936
    attempts_ab: str = ""
    attempts_ba: str = ""
    delayed_ab: str = ""
    delayed_ba: str = ""
    probability_ab: str = ""
    probability_ba: str = ""
    duration_s: float = 600
    warmup_s: float = 120
    clearance_s: float = 600
    bin_s: float = 30
    seed: int = 42

    def to_dict(self):
        return asdict(self)

    @classmethod
    def parse(cls, raw):
        x = cls()
        if not isinstance(raw, dict) or set(raw) - set(x.to_dict()):
            raise ValueError("Campos de sendero desconocidos.")
        for k, options in CHOICES.items():
            value = raw.get(k, getattr(x, k))
            if value not in {v for _, v in options}:
                raise ValueError(LABELS[k] + ": opción desconocida.")
            setattr(x, k, value)
        for k in active_keys(x):
            if k in CHOICES:
                continue
            v = raw.get(k, getattr(x, k))
            optional = k.startswith(("attempts_", "delayed_", "probability_"))
            if optional and v == "":
                setattr(x, k, "")
                continue
            try:
                if isinstance(v, bool):
                    raise ValueError()
                v = float(str(v).replace(",", "."))
                if not math.isfinite(v):
                    raise ValueError()
            except (TypeError, ValueError) as exc:
                raise ValueError(LABELS[k] + ": introduzca un número finito.") from exc
            if k in {"seed"} or k.startswith(("attempts_", "delayed_")):
                if v != int(v):
                    raise ValueError(LABELS[k] + ": debe ser entero.")
                v = int(v)
            if k == "length_m":
                lo, hi = 20, 2000
            elif k == "width_m":
                lo, hi = 1.6, 10
            elif k == "phf":
                lo, hi = 0.05, 1
            elif k == "ped_speed":
                lo, hi = 0.2, 3
            elif k == "bike_speed":
                lo, hi = 0.5, 15
            elif k.endswith("_sd"):
                lo, hi = 0, 5
            elif k == "duration_s":
                lo, hi = 60, 3600
            elif k == "warmup_s":
                lo, hi = 0, 600
            elif k == "clearance_s":
                lo, hi = 0, 1800
            elif k == "bin_s":
                lo, hi = 0.5, 600
            elif k == "seed":
                lo, hi = 0, 2147483647
            elif k.startswith("probability_"):
                lo, hi = 0, 1
            elif optional:
                lo, hi = 0, 1000000
            else:
                lo, hi = 0, 10000
            if not lo <= v <= hi:
                raise ValueError(f"{LABELS[k]}: rango permitido {lo}–{hi}.")
            setattr(x, k, v)
        if x.bike_speed <= x.ped_speed:
            raise ValueError(
                "La velocidad ciclista debe superar la velocidad peatonal para este procedimiento."
            )
        if x.bin_s > x.duration_s:
            raise ValueError("El intervalo de serie supera la observación.")
        if x.task != "ped" and x.delay_source == "counts":
            for d in ["ab", "ba"]:
                n = getattr(x, "attempts_" + d)
                k = getattr(x, "delayed_" + d)
                if n != "" and k != "" and (k > n or n == 0 and k):
                    raise ValueError("Los demorados no pueden superar los intentos.")
        return x


def active_keys(x):
    keys = [
        "task",
        "basis",
        "arrival",
        "length_m",
        "width_m",
        "ped_speed",
        "bike_speed",
        "duration_s",
        "warmup_s",
        "clearance_s",
        "bin_s",
        "seed",
    ]
    keys += (
        ["ped_ab", "ped_ba", "bike_ab", "bike_ba"]
        if x.basis == "hourly"
        else ["count_ped_ab", "count_ped_ba", "count_bike_ab", "count_bike_ba"]
    )
    if x.basis == "hourly" or x.task != "ped":
        keys += ["phf"]
    if x.task != "ped":
        keys += ["ped_sd", "bike_sd", "centerline", "delay_source"]
        keys += (
            ["attempts_ab", "attempts_ba", "delayed_ab", "delayed_ba"]
            if x.delay_source == "counts"
            else ["probability_ab", "probability_ba"]
        )
    return keys


def flows(x):
    return {
        g: (
            getattr(x, ("ped_" if g[0] == "P" else "bike_") + g[2:].lower()) / x.phf
            if x.basis == "hourly"
            else 4 * getattr(x, ("count_ped_" if g[0] == "P" else "count_bike_") + g[2:].lower())
        )
        for g in GROUP_LABELS
    }


def signature(raw):
    return hashlib.sha256(
        json.dumps(SharedInput.parse(raw).to_dict(), sort_keys=True).encode()
    ).hexdigest()


def plos(event_rate):
    return next(
        (
            grade
            for grade, limit in zip("ABCDE", [38, 60, 103, 144, 180], strict=True)
            if event_rate <= limit
        ),
        "F",
    )


def blos_grade(score):
    return next(
        (grade for grade, lower in zip("ABCDE", [4, 3.5, 3, 2.5, 2], strict=True) if score > lower),
        "F",
    )


def cdf(value, mean, sd):
    if sd == 0:
        return float(value > mean)
    return 0.5 * (1 + math.erf((value - mean) / (sd * math.sqrt(2))))


def event_rates(length, u, mean, sd, rate, meeting=False):
    if not rate:
        return 0.0
    if sd == 0:
        fraction = min(mean / u, 1) if meeting else max(1 - mean / u, 0)
    else:
        n = math.ceil(length / 16.09344)
        values = [
            1 - cdf(u * i / n, mean, sd) if meeting else cdf(u * (1 - i / n), mean, sd)
            for i in range(n + 1)
        ]
        fraction = (sum(values) - 0.5 * (values[0] + values[-1])) / n
    return rate * u / (60 * mean) * fraction


def evaluate_shared(raw):
    x = SharedInput.parse(raw)
    q = flows(x)
    directions = []
    warnings = []
    for d, o in [("AB", "BA"), ("BA", "AB")]:
        p, qb, qo = q["P." + d], q["B." + d], q["B." + o]
        fp = qb * (1 - x.ped_speed / x.bike_speed)
        fm = qo * (1 + x.ped_speed / x.bike_speed)
        f = fp + 0.5 * fm
        pedestrian = (
            dict(passing_h=fp, meeting_h=fm, weighted_h=f, los=plos(f) if p > 0 else None)
            if x.task != "bike"
            else None
        )
        bicycle = None
        if x.task != "ped":
            active = event_rates(x.length_m, x.bike_speed, x.ped_speed, x.ped_sd, q["P." + d])
            active += event_rates(x.length_m, x.bike_speed, x.bike_speed, x.bike_sd, qb)
            m1 = x.bike_speed / 60 * (q["P." + o] / x.ped_speed + qo / x.bike_speed)
            meetings = m1 + event_rates(
                x.length_m, x.bike_speed, x.ped_speed, x.ped_sd, q["P." + o], True
            )
            meetings += event_rates(x.length_m, x.bike_speed, x.bike_speed, x.bike_sd, qo, True)
            pt = None
            reason = ""
            if x.delay_source == "probability":
                value = getattr(x, "probability_" + d.lower())
                pt = float(value) if value != "" else None
            else:
                n, k = getattr(x, "attempts_" + d.lower()), getattr(x, "delayed_" + d.lower())
                if n != "" and k != "" and n > 0:
                    pt = k / n
            if qb <= 0:
                reason = "Sin demanda ciclista en este sentido."
            elif not 2.4384 <= x.width_m <= 6.096:
                reason = "Ancho fuera del dominio BLOS de 8–20 ft."
            elif pt is None:
                reason = "Falta probabilidad documentada o muestra válida de rebases demorados."
            weighted = meetings + 10 * active
            dp = active * pt * x.phf if pt is not None else None
            factor = min(dp * 0.5, 1.5) if dp is not None else None
            score = (
                5.446
                - 0.00809 * weighted
                - 15.86 * 0.3048 / x.width_m
                - 0.287 * (x.centerline == "yes")
                - factor
                if not reason
                else None
            )
            grade = blos_grade(score) if score is not None else None
            adjusted = grade
            if grade is not None:
                if weighted <= 5:
                    adjusted = "A"
                elif weighted <= 10 and grade != "A":
                    adjusted = "B"
            bicycle = dict(
                active_min=active,
                meetings_min=meetings,
                weighted_min=weighted,
                probability_delay=pt,
                delayed_min=dp,
                delay_factor=factor,
                score=score,
                raw_los=grade,
                los=adjusted,
                reason=reason,
            )
        directions.append(dict(direction=d, pedestrian=pedestrian, bicycle=bicycle))
    if x.task != "ped":
        warnings.append(
            "BLOS condicionado a la probabilidad de demora introducida. "
            "Al cambiar ancho o demanda revise esa probabilidad."
        )
        if x.ped_sd > x.ped_speed / 3 or x.bike_sd > x.bike_speed / 3:
            warnings.append(
                "La distribución normal de velocidad tiene una cola negativa apreciable; "
                "revise media y desviación antes de interpretar BLOS."
            )
    return dict(
        inputs=x.to_dict(),
        signature=signature(raw),
        flows=q,
        directions=directions,
        warnings=warnings,
        assumptions=ASSUMPTIONS,
        created_at=datetime.now(UTC).isoformat(),
    )


def new_case(name="Base · sendero compartido", inputs=None):
    raw = copy.deepcopy({**SharedInput().to_dict(), **(inputs or {})})
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
    if (
        not isinstance(study, dict)
        or not isinstance(study.get("cases"), list)
        or not 1 <= len(study["cases"]) <= 30
    ):
        raise ValueError("Estudio de senderos incorrecto.")
    ids = set()
    for c in study["cases"]:
        if not isinstance(c.get("id"), str) or not 1 <= len(c["id"]) <= 100 or c["id"] in ids:
            raise ValueError("Identificador de sendero incorrecto.")
        ids.add(c["id"])
        if not isinstance(c.get("name"), str) or not 1 <= len(c["name"]) <= 200:
            raise ValueError("Nombre de sendero incorrecto.")
        raw = c["inputs"]
        if not isinstance(raw, dict) or set(raw) != set(SharedInput().to_dict()):
            raise ValueError("Borrador de sendero incompleto.")
        for k, v in raw.items():
            if k in CHOICES:
                if v not in {v for _, v in CHOICES[k]}:
                    raise ValueError("Opción de sendero desconocida.")
            elif type(v) not in (int, float, str):
                raise ValueError("Dato de sendero incorrecto.")
        if (
            not isinstance(c["origins"], dict)
            or set(c["origins"]) != set(raw)
            or any(
                v not in {"default", "entered", "observed", "csv"} for v in c["origins"].values()
            )
        ):
            raise ValueError("Procedencia de sendero incorrecta.")
        a = c.get("analytical")
        if a is not None:
            expected = evaluate_shared(a["inputs"])
            if any(a[k] != expected[k] for k in ("signature", "flows", "directions")):
                raise ValueError("Análisis de sendero inconsistente.")
        if c.get("simulation") is not None:
            validate_simulation(c["simulation"])
    if study.get("selected_id") not in ids:
        raise ValueError("Sendero seleccionado desconocido.")
    return copy.deepcopy(study)


def validate_simulation(s):
    x = SharedInput.parse(s["inputs"])
    if s["signature"] != signature(s["inputs"]) or set(s["summary"]) != set(SUMMARY_LABELS):
        raise ValueError("Resumen de sendero inconsistente.")
    expected = evaluate_shared(s["inputs"])
    if not isinstance(s.get("analytical"), dict) or any(
        s["analytical"].get(k) != expected[k] for k in ("signature", "flows", "directions")
    ):
        raise ValueError("Referencia analítica de simulación inconsistente.")
    m = s["summary"]
    for k, v in m.items():
        if v is None and k == "clearance_s":
            continue
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
            raise ValueError("Indicador de sendero incorrecto.")
    for k in (
        "generated",
        "started",
        "completed",
        "pending",
        "cohort_generated",
        "cohort_completed",
    ):
        if type(m[k]) is not int or not 0 <= m[k] <= 10000:
            raise ValueError("Conteo de sendero incorrecto.")
    if (
        m["generated"] != m["completed"] + m["pending"]
        or not m["cohort_completed"] <= m["cohort_generated"] <= m["generated"]
    ):
        raise ValueError("No se conserva la demanda del sendero.")
    if not m["completed"] <= m["started"] <= m["generated"]:
        raise ValueError("Conteos de inicio inconsistentes.")
    for key in ("meetings_pb", "passes_bp", "meetings_bb", "passes_bb"):
        if type(m[key]) is not int:
            raise ValueError("Conteo de eventos incorrecto.")
    if set(s["groups"]) != set(GROUP_LABELS):
        raise ValueError("Grupos de usuarios incompletos.")
    for group in s["groups"].values():
        if set(group) != {
            "generated",
            "completed",
            "cohort_completed",
            "mean_trip_s",
            "p95_trip_s",
            "speed_mps",
            "mean_loss_s",
        }:
            raise ValueError("Estadísticos de grupo incompletos.")
        if any(type(group[k]) is not int for k in ("generated", "completed", "cohort_completed")):
            raise ValueError("Conteo de grupo incorrecto.")
        if not 0 <= group["cohort_completed"] <= group["completed"] <= group["generated"]:
            raise ValueError("Cohorte de grupo incorrecta.")
        for v in group.values():
            if v is None and not group["cohort_completed"]:
                continue
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError("Estadístico de grupo incorrecto.")
    if (
        sum(g["generated"] for g in s["groups"].values()) != m["generated"]
        or sum(g["completed"] for g in s["groups"].values()) != m["completed"]
    ):
        raise ValueError("Conteos por grupo inconsistentes.")
    if sum(g["cohort_completed"] for g in s["groups"].values()) != m["cohort_completed"]:
        raise ValueError("Muestra de cohorte inconsistente.")
    if not isinstance(s["incidence"], dict) or set(s["incidence"]) != set(GROUP_LABELS):
        raise ValueError("Exposición por grupo incompleta.")
    for g, v in s["incidence"].items():
        if set(v) != {
            "exposure_s",
            "meetings",
            "passes",
            "meeting_rate",
            "passing_rate",
            "weighted_rate",
        }:
            raise ValueError("Tasas de eventos incompletas.")
        if (
            type(v["exposure_s"]) not in (int, float)
            or not 0 <= v["exposure_s"] <= s["groups"][g]["generated"] * x.duration_s + 1e-6
        ):
            raise ValueError("Exposición de grupo incorrecta.")
        if any(type(v[k]) is not int or v[k] < 0 for k in ("meetings", "passes")):
            raise ValueError("Incidencias de grupo incorrectas.")
        unit = 3600 if g.startswith("P") else 60
        for field, count in [("meeting_rate", "meetings"), ("passing_rate", "passes")]:
            expected = v[count] * unit / v["exposure_s"] if v["exposure_s"] else None
            if expected is None:
                if v[field] is not None:
                    raise ValueError("Tasa sin exposición.")
            elif type(v[field]) not in (int, float) or not math.isclose(
                v[field], expected, abs_tol=1e-6
            ):
                raise ValueError("Tasa y exposición inconsistentes.")
        expected = (
            (
                v["passing_rate"] + 0.5 * v["meeting_rate"]
                if g.startswith("P")
                else v["meeting_rate"] + 10 * v["passing_rate"]
            )
            if v["exposure_s"]
            else None
        )
        if expected is None:
            if v["weighted_rate"] is not None:
                raise ValueError("Tasa ponderada sin exposición.")
        elif type(v["weighted_rate"]) not in (int, float) or not math.isclose(
            v["weighted_rate"], expected, abs_tol=1e-6
        ):
            raise ValueError("Tasa ponderada incorrecta.")
    if len(s["series"]) != math.ceil(x.duration_s / x.bin_s):
        raise ValueError("Serie de sendero incompleta.")
    for i, row in enumerate(s["series"]):
        if set(row) != {
            "time_s",
            "interval_s",
            "ped_occupancy",
            "bike_occupancy",
            "meetings_pb",
            "passes_bp",
            "meetings_bb",
            "passes_bb",
        }:
            raise ValueError("Indicadores de serie incompletos.")
        if not math.isclose(row["time_s"], i * x.bin_s, abs_tol=1e-6) or not math.isclose(
            row["interval_s"], min(x.bin_s, x.duration_s - i * x.bin_s), abs_tol=1e-6
        ):
            raise ValueError("Intervalo de sendero incorrecto.")
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in row.values()):
            raise ValueError("Serie de sendero incorrecta.")
    for mode, column in [("P", "ped_occupancy"), ("B", "bike_occupancy")]:
        if not math.isclose(
            sum(r[column] * r["interval_s"] for r in s["series"]),
            sum(v["exposure_s"] for g, v in s["incidence"].items() if g.startswith(mode)),
            abs_tol=1e-6,
        ):
            raise ValueError("Ocupación y exposición inconsistentes.")
    for key in ("meetings_pb", "passes_bp", "meetings_bb", "passes_bb"):
        if sum(r[key] for r in s["series"]) != m[key]:
            raise ValueError("Eventos y serie inconsistentes.")
    if (
        not isinstance(s["engine_version"], str)
        or not isinstance(s["created_at"], str)
        or s.get("sample_s") != 0.5
    ):
        raise ValueError("Metadatos de sendero incorrectos.")
    if not isinstance(s["warnings"], list) or any(not isinstance(v, str) for v in s["warnings"]):
        raise ValueError("Notas de sendero incorrectas.")
