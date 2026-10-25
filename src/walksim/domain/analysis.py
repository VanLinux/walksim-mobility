"""Análisis peatonal SI con criterios y supuestos explícitos y trazables."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

FT = 0.3048
FT2 = FT * FT
HCM24 = (
    "HCM 7.ª ed. (2022), cap. 24, Exhibits 24-1 a 24-3, ecs. 24-1 a 24-4, pp. 24-4 y 24-10 a 24-14."
)
FHWA = "FHWA-RD-98-107 (1998), sección 3, tabla 21 (áreas de espera)."
GAP = (
    "HCM 7.ª ed., cap. 20, ecs. 20-76 y 20-82: una etapa, peatón individual, sin cesión vehicular."
)
DOCUMENT = (
    "Documento aportado: Análisis y Metodología Peatonal según el HCM 7ma Edición, sección 4.3."
)
SOURCES = {
    "hcm24": HCM24,
    "queue": FHWA,
    "signal": DOCUMENT,
    "unsignal": GAP,
}


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    unit: str
    default: str
    minimum: float = 0.0
    maximum: float = 1e9
    positive: bool = False
    optional: bool = False
    integer: bool = False


@dataclass(frozen=True)
class MethodSpec:
    title: str
    fields: tuple[FieldSpec, ...]
    description: str


WIDTH_FIELDS = (
    FieldSpec("width_m", "Ancho total", "m", "3", positive=True),
    FieldSpec("obstacles_m", "Descuento por obstáculos", "m", "0.2"),
    FieldSpec("edges_m", "Descuento total por bordes", "m", "0.3"),
)
FLOW_FIELDS = (
    FieldSpec("count", "Peatones contados (ambos sentidos)", "peat", "250", integer=True),
    FieldSpec("period_min", "Intervalo del conteo", "min", "15", positive=True, maximum=480),
    FieldSpec("speed_mps", "Velocidad media medida", "m/s", "1.2", positive=True, maximum=3),
)
METHODS = {
    "walkway": MethodSpec(
        "Acera / sendero — aforo y velocidad",
        WIDTH_FIELDS + FLOW_FIELDS,
        "Flujo aleatorio. Use el conteo de los 15 min más cargados y velocidad medida; "
        "M = 60 S / q. Aplicable a pendientes de hasta 5 %. No es el índice PLOS de calle urbana.",
    ),
    "occupancy": MethodSpec(
        "Acera / sendero — ocupación observada",
        WIDTH_FIELDS
        + (
            FieldSpec("length_m", "Longitud del área observada", "m", "10", positive=True),
            FieldSpec(
                "occupants", "Máxima ocupación simultánea observada", "peat", "5", integer=True
            ),
        ),
        "M = área útil / ocupación simultánea. Use una zona representativa del cuello de botella; "
        "la medición es espacial y no equivale a un conteo de paso.",
    ),
    "platoon": MethodSpec(
        "Acera con pelotones — promedio de 5 min",
        WIDTH_FIELDS
        + (
            FieldSpec("count", "Peatones contados en 5 min", "peat", "100", integer=True),
            FieldSpec(
                "speed_mps", "Velocidad media medida", "m/s", "1.0", positive=True, maximum=3
            ),
        ),
        "Tabla específica de flujo en pelotones del HCM, Exhibit 24-2. "
        "El aforo y el espacio corresponden al promedio de 5 min, no al espacio instantáneo "
        "dentro de un grupo. Use ocupación observada para diagnosticar un grupo local.",
    ),
    "queue": MethodSpec(
        "Área de espera / andén — ocupación",
        (
            FieldSpec("area_m2", "Área total", "m²", "30", positive=True),
            FieldSpec("excluded_area_m2", "Área no utilizable", "m²", "3"),
            FieldSpec("occupants", "Ocupación simultánea de diseño", "peat", "35", integer=True),
        ),
        "Personas detenidas: M = área útil / ocupación, D = 1/M. "
        "Criterios de espera de FHWA/Fruin, diferentes de los de circulación.",
    ),
    "signal": MethodSpec(
        "Cruce semaforizado — demora y tiempo de cruce",
        (
            FieldSpec("cycle_s", "Ciclo semafórico C", "s", "90", positive=True, maximum=600),
            FieldSpec("green_s", "WALK efectivo g (admisión)", "s", "25", maximum=600),
            FieldSpec(
                "crossing_m", "Distancia de cruce (opcional)", "m", "", positive=True, optional=True
            ),
            FieldSpec(
                "speed_mps",
                "Velocidad de cruce (opcional)",
                "m/s",
                "",
                positive=True,
                maximum=3,
                optional=True,
            ),
            FieldSpec("clearance_s", "Despeje disponible (opcional)", "s", "", optional=True),
        ),
        "Demora media con llegadas uniformes y cumplimiento de la señal: "
        "d = (C − g)² / (2C). La categoría A–F por demora es la del documento aportado; "
        "no es el PLOS completo de una intersección HCM 7. El despeje se revisa aparte del WALK.",
    ),
    "unsignal": MethodSpec(
        "Cruce sin semáforo — aceptación de brechas",
        (
            FieldSpec("crossing_m", "Distancia de cruce de una etapa", "m", "8", positive=True),
            FieldSpec("speed_mps", "Velocidad de cruce", "m/s", "1.1", positive=True, maximum=3),
            FieldSpec("startup_s", "Arranque y margen final", "s", "3", maximum=120),
            FieldSpec(
                "vehicles_pph", "Flujo vehicular conflictivo total", "veh/h", "600", maximum=20000
            ),
        ),
        "Peatón individual, cruce en una etapa, vehículos con llegadas Poisson "
        "y sin cesión de paso. "
        "tc = L/S + ts; d = (exp(v tc) − v tc − 1)/v. "
        "Se calcula demora por brechas; no el PLOS HCM 7 por satisfacción.",
    ),
    "stairs": MethodSpec(
        "Escalera — flujo ascendente",
        WIDTH_FIELDS
        + (
            FieldSpec(
                "reverse_flow",
                "¿Existe contraflujo menor? (0=no, 1=sí)",
                "",
                "0",
                maximum=1,
                integer=True,
            ),
            FieldSpec("count", "Peatones ascendentes contados", "peat", "150", integer=True),
            FieldSpec(
                "period_min",
                "Intervalo del conteo ascendente",
                "min",
                "15",
                positive=True,
                maximum=480,
            ),
            FieldSpec(
                "speed_mps",
                "Velocidad horizontal media en escalera",
                "m/s",
                "0.5",
                positive=True,
                maximum=3,
            ),
        ),
        "HCM 7, Exhibit 24-3. Analice el flujo ascendente; el contraflujo menor ocupa "
        "0.762 m adicionales. La velocidad es su componente horizontal, "
        "no la velocidad sobre la pendiente. Capacidad de referencia: 15 peat/min/ft.",
    ),
}


@dataclass
class AnalysisResult:
    method: str
    name: str
    inputs: dict[str, float]
    metrics: dict[str, float | str | None]
    equations: list[str]
    steps: list[str]
    assumptions: list[str]
    source: str
    criterion: str
    thresholds: list[float] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_inputs(method: str, raw: dict[str, Any]) -> dict[str, float]:
    if method not in METHODS:
        raise ValueError("Tipo de análisis desconocido.")
    known = {item.key for item in METHODS[method].fields}
    if set(raw) - known:
        raise ValueError("Campos desconocidos: " + ", ".join(sorted(set(raw) - known)))
    values = {}
    for item in METHODS[method].fields:
        value = raw.get(item.key, "")
        if value is None or str(value).strip() == "":
            if item.optional:
                continue
            raise ValueError(f"Falta {item.label}.")
        try:
            number = float(str(value).strip().replace(",", "."))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"{item.label}: escriba un número.") from exc
        if (
            not math.isfinite(number)
            or number < item.minimum
            or number > item.maximum
            or (item.positive and number <= 0)
            or (item.integer and not number.is_integer())
        ):
            raise ValueError(f"{item.label}: valor fuera de rango o formato incorrecto.")
        values[item.key] = number
    return values


def space_los(space: float | None, thresholds: list[float]) -> str:
    if space is None:  # empty facility: no density, no finite M
        return "A"
    for letter, threshold in zip("ABCDE", thresholds, strict=True):
        if space > threshold:
            return letter
    return "F"


def criterion_thresholds(method: str) -> list[float]:
    imperial = {
        "walkway": [60, 40, 24, 15, 8],
        "occupancy": [60, 40, 24, 15, 8],
        "platoon": [530, 90, 40, 23, 11],
        "stairs": [20, 17, 12, 8, 5],
        "queue": [13, 10, 7, 3, 2],
    }
    return [x * FT2 for x in imperial.get(method, [])]


def calculate(method: str, raw: dict[str, Any], name: str = "") -> AnalysisResult:
    x = parse_inputs(method, raw)
    metrics: dict[str, float | str | None] = {}
    equations, steps, assumptions = [], [], [METHODS[method].description]
    thresholds = criterion_thresholds(method)
    source = SOURCES.get(method, HCM24)
    criterion = "LOS por espacio (m²/peatón)"
    if method in ("walkway", "occupancy", "platoon", "stairs"):
        reserve = 0.762 * x.get("reverse_flow", 0)
        width = x["width_m"] - x["obstacles_m"] - x["edges_m"] - reserve
        if width <= 0:
            raise ValueError("El ancho útil debe ser positivo después de todos los descuentos.")
        metrics["Ancho efectivo (m)"] = width
        equations += [r"W_E = W - W_o - W_b - W_r"]
        steps += [
            f"Ancho efectivo: {x['width_m']:g} − {x['obstacles_m']:g} "
            f"− {x['edges_m']:g} − {reserve:g} = {width:.6g} m."
        ]
        if method == "occupancy":
            area = width * x["length_m"]
            density = x["occupants"] / area
            metrics["Área útil observada (m²)"] = area
            equations += [r"A = L W_E", r"D = N/A", r"M = 1/D"]
        else:
            period = 5 if method == "platoon" else x["period_min"]
            q = x["count"] / (period * width)
            density = q / (60 * x["speed_mps"])
            capacity = (18 if method == "platoon" else (15 if method == "stairs" else 23)) / FT
            metrics.update(
                {
                    "Flujo específico (peat/min/m)": q,
                    "Velocidad media de entrada (m/s)": x["speed_mps"],
                    "Capacidad específica de referencia (peat/min/m)": capacity,
                    "Capacidad del ancho útil (peat/h)": capacity * width * 60,
                    "Relación demanda/capacidad": q / capacity,
                    "Intervalo analizado (min)": period,
                }
            )
            equations += [
                r"q = N/(T W_E)",
                r"D = q/(60 S)",
                r"M = 60 S/q",
                r"c = c_{ft}/0.3048",
                r"X = q/c",
            ]
            steps += [
                f"q = {x['count']:g} / ({period:g} × {width:.6g}) = {q:.6g} peat/min/m.",
                f"D = {q:.6g} / (60 × {x['speed_mps']:g}) = {density:.6g} peat/m².",
            ]
            if period != (5 if method == "platoon" else 15):
                assumptions.append(
                    "El intervalo difiere del periodo de referencia HCM; "
                    "la clasificación describe el intervalo introducido, no el pico HCM."
                )
            if q > capacity:
                assumptions.append(
                    "Demanda mayor que la capacidad de referencia: el flujo estacionario "
                    "supuesto no es sostenible. El LOS operativo se informa F."
                )
            assumptions += [
                "El espacio derivado presupone flujo estacionario y velocidad "
                "representativa del mismo periodo. La capacidad es una referencia, "
                "no una garantía de flujo alcanzable."
            ]
        space = 1 / density if density else None
    elif method == "queue":
        area = x["area_m2"] - x["excluded_area_m2"]
        if area <= 0:
            raise ValueError("El área útil debe ser positiva después de descontar obstáculos.")
        density = x["occupants"] / area
        space = 1 / density if density else None
        metrics["Área útil (m²)"] = area
        equations += [r"A_u = A - A_o", r"D = N/A_u", r"M = A_u/N"]
        steps += [f"Área útil = {x['area_m2']:g} − {x['excluded_area_m2']:g} = {area:g} m²."]
        assumptions += [
            "La categoría de espacio no es una evaluación de seguridad de multitudes "
            "ni de evacuación. No se deduce flujo de una población detenida."
        ]
    elif method == "signal":
        if x["green_s"] > x["cycle_s"]:
            raise ValueError("El WALK efectivo g no puede superar el ciclo C.")
        delay = (x["cycle_s"] - x["green_s"]) ** 2 / (2 * x["cycle_s"])
        category = (
            "A"
            if delay < 10
            else "B"
            if delay < 20
            else "C"
            if delay < 30
            else "D"
            if delay < 40
            else "E"
            if delay <= 60
            else "F"
        )
        metrics.update(
            {
                "Demora media (s/peatón)": delay,
                "Categoría por demora (documento)": category,
                "Rojo efectivo peatonal (s)": x["cycle_s"] - x["green_s"],
            }
        )
        equations += [r"d_p = (C-g)^2/(2C)"]
        steps += [
            f"d = ({x['cycle_s']:g} − {x['green_s']:g})² / "
            f"(2 × {x['cycle_s']:g}) = {delay:.6g} s/peatón."
        ]
        pair = ("crossing_m" in x, "speed_mps" in x)
        if pair[0] != pair[1] or ("clearance_s" in x and not all(pair)):
            raise ValueError("Para revisar el cruce, introduzca distancia y velocidad juntas.")
        if all(pair):
            required = x["crossing_m"] / x["speed_mps"]
            metrics["Tiempo de recorrido del cruce (s)"] = required
            equations += [r"t_{cruce} = L/S"]
            if "clearance_s" in x:
                metrics["Margen de despeje (s)"] = x["clearance_s"] - required
                metrics["Comprobación cinemática de despeje"] = (
                    "Suficiente" if x["clearance_s"] >= required else "Insuficiente"
                )
        criterion = "Categoría por demora del documento (no PLOS HCM 7)"
        assumptions += [
            "Llegadas uniformes, señal de tiempo fijo, cumplimiento total y sin "
            "sobresaturación. g es el intervalo de admisión efectivo; no se suma "
            "automáticamente el despeje. La revisión L/S es cinemática y no certifica "
            "el diseño semafórico ni accesibilidad."
        ]
    else:
        tc = x["crossing_m"] / x["speed_mps"] + x["startup_s"]
        v = x["vehicles_pph"] / 3600
        z = v * tc
        if z > 40:
            raise ValueError(
                "El modelo de brechas produce una demora extrema (v tc > 40). "
                "Revise los datos y la aplicabilidad del supuesto sin cesión."
            )
        delay = (
            0.0
            if v == 0
            else ((z * z / 2 + z * z * z / 6) / v if z < 1e-5 else (math.expm1(z) - z) / v)
        )
        metrics.update(
            {
                "Brecha crítica individual (s)": tc,
                "Flujo conflictivo (veh/s)": v,
                "Demora media por brechas (s/peatón)": delay,
                "Probabilidad de brecha suficiente": math.exp(-z),
            }
        )
        equations += [
            r"t_c = L/S + t_s",
            r"v = V/3600",
            r"d_g = (e^{v t_c} - v t_c - 1)/v",
            r"P(gap \ge t_c) = e^{-v t_c}",
        ]
        steps += [
            f"tc = {x['crossing_m']:g}/{x['speed_mps']:g} + {x['startup_s']:g} = {tc:.6g} s.",
            f"v = {x['vehicles_pph']:g}/3600 = {v:.6g} veh/s; demora = {delay:.6g} s.",
        ]
        criterion = "Demora por brechas sin cesión; sin categoría PLOS"
        assumptions += [
            "Si V = 0, se usa el límite d = 0. No se modelan cesión de paso, "
            "pelotones cruzando, refugios por etapas, ni llegadas vehiculares correlacionadas. "
            "El LOS HCM 7 de cruces sin control usa satisfacción; no se deduce de esta demora."
        ]
    if thresholds:
        metrics["Densidad (peat/m²)"] = density
        metrics["Espacio medio (m²/peatón)"] = space
        metrics["LOS por espacio"] = space_los(space, thresholds)
        if metrics.get("Relación demanda/capacidad", 0) > 1:
            metrics["LOS operativo por exceso de demanda"] = "F"
        steps += [
            f"M = {space:.6g} m²/peatón."
            if space is not None
            else "Ocupación o aforo nulo: D = 0; M no tiene valor finito; LOS A."
        ]
    return AnalysisResult(
        method,
        name.strip() or METHODS[method].title,
        x,
        metrics,
        equations,
        steps,
        assumptions,
        source,
        criterion,
        thresholds,
    )
