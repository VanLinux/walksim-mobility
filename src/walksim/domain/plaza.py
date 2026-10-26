"""Plantillas de plaza, matriz OD local y contratos de resultados."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

PORTS = ["N", "S", "E", "W"]
NAMES = dict(N="Norte", S="Sur", E="Este", W="Oeste")
CHOICES = {
    "template": [
        ("Plaza rectangular", "rectangle"),
        ("Vestíbulo rectangular", "hall"),
        ("Cruce en +", "cross"),
        ("Cruce en T", "tee"),
    ],
    "accesses": [
        ("Dos · Este y Oeste", "2"),
        ("Tres · Sur, Este y Oeste", "3"),
        ("Cuatro · Norte, Sur, Este y Oeste", "4"),
    ],
    "arrival": [("Uniforme", "uniform"), ("Aleatoria (Poisson)", "random")],
}
LABELS = dict(
    template="Plantilla",
    accesses="Accesos",
    arrival="Llegadas por OD",
    length_m="Dimensión Este–Oeste (m)",
    height_m="Dimensión Norte–Sur (m)",
    arm_m="Ancho de brazos del cruce (m)",
    approach_m="Longitud de cada acceso (m)",
    width_n_m="Ancho acceso Norte (m)",
    width_s_m="Ancho acceso Sur (m)",
    width_e_m="Ancho acceso Este (m)",
    width_w_m="Ancho acceso Oeste (m)",
    speed_mps="Velocidad representativa (m/s)",
    cell_m="Lado de celda solicitado (m)",
    duration_s="Periodo observado (s)",
    warmup_s="Calentamiento (s)",
    clearance_s="Despeje máximo adicional (s)",
    bin_s="Intervalo de serie (s)",
    seed="Semilla",
    od="Matriz OD local (peat/h)",
)
VIEWS = [
    ("Densidad media", "mean_density"),
    ("Densidad máxima muestreada", "max_density"),
    ("Ocupación acumulada", "person_seconds"),
    ("Permanencia media por visitante", "mean_stay_s"),
]
ASSUMPTIONS = [
    "Matriz OD local en peat/h: cada celda es una tasa absoluta. Las sumas por fila definen "
    "el flujo de origen y sus proporciones de destinos; la diagonal debe ser cero.",
    "El motor striping simula accesos y un área peatonal común definida por la plantilla. "
    "El mapa deriva de posiciones FCD de esa microsimulación, muestreadas cada segundo.",
    "El área del mapa excluye los accesos exteriores. Las celdas de borde usan su área real "
    "dentro del polígono; no se comparan celdas con denominadores distintos sin revisar sus áreas.",
    "Cada posición se mantiene hasta el siguiente segundo (integración rectangular). Los "
    "máximos son muestreados; una visita menor que un segundo puede no registrarse.",
    "Ocupación acumulada se expresa en peatón·s; permanencia media divide ese tiempo entre "
    "visitantes distintos observados en cada celda. Una persona puede visitar varias celdas.",
    "Tiempos, velocidad espacial y tiempo perdido por OD corresponden a la cohorte generada "
    "durante observación que completa el recorrido antes del límite de despeje, incluidos accesos.",
    "Calentamiento se excluye de los mapas y series. Pendientes y completados incluyen toda "
    "la demanda generada. Los pendientes pueden sesgar las estadísticas de quienes terminaron.",
    "Las trayectorias dependen de las aproximaciones de striping. Cruces geométricos de OD "
    "son descriptores de demanda; no son colisiones, conflictos de seguridad ni PLOS HCM.",
]
SUMMARY_LABELS = dict(
    generated="Generados (incluye calentamiento)",
    started="Iniciados",
    completed="Recorridos completados",
    pending="Pendientes al límite de despeje",
    cohort_generated="Generados en observación",
    cohort_completed="Completados de cohorte",
    completed_pct="Porcentaje completado total (%)",
    mean_trip_s="Tiempo medio de cohorte (s)",
    p95_trip_s="P95 del tiempo de cohorte (s)",
    spatial_speed_mps="Velocidad espacial de cohorte (m/s)",
    mean_loss_s="Tiempo perdido medio de cohorte (s)",
    mean_occupancy="Ocupación media del área",
    max_occupancy="Ocupación máxima muestreada del área",
    mean_density="Densidad media global (peat/m²)",
    max_cell_density="Densidad máxima muestreada en celda (peat/m²)",
    outside_samples="Posiciones del área fuera del polígono",
    clearance_s="Despeje adicional completo (s)",
)


@dataclass
class PlazaInput:
    template: str = "rectangle"
    accesses: str = "4"
    arrival: str = "uniform"
    length_m: float = 24
    height_m: float = 18
    arm_m: float = 6
    approach_m: float = 10
    width_n_m: float = 4
    width_s_m: float = 4
    width_e_m: float = 4
    width_w_m: float = 4
    speed_mps: float = 1.2
    cell_m: float = 2
    duration_s: float = 600
    warmup_s: float = 60
    clearance_s: float = 300
    bin_s: float = 30
    seed: int = 42
    od: list | None = None

    def __post_init__(self):
        if self.od is None:
            self.od = [[0 if i == j else 200 for j in range(4)] for i in range(4)]

    def to_dict(self):
        return asdict(self)

    @classmethod
    def parse(cls, raw):
        x = cls()
        if not isinstance(raw, dict) or set(raw) - set(x.to_dict()):
            raise ValueError("Campos de plaza desconocidos.")
        for k, choices in CHOICES.items():
            v = raw.get(k, getattr(x, k))
            if v not in {v for _label, v in choices}:
                raise ValueError(f"{LABELS[k]}: opción desconocida.")
            setattr(x, k, v)
        if x.template in {"cross", "tee"}:
            x.accesses = "4" if x.template == "cross" else "3"
        limits = dict(
            length_m=(8, 100),
            height_m=(8, 100),
            arm_m=(2, 30),
            approach_m=(5, 50),
            speed_mps=(0.2, 3),
            cell_m=(0.5, 10),
            duration_s=(60, 3600),
            warmup_s=(0, 600),
            clearance_s=(0, 1200),
            bin_s=(1, 600),
            seed=(0, 2147483647),
        )
        limits.update({"width_" + p.lower() + "_m": (0.8, 20) for p in PORTS})
        for k in active_keys(x):
            if k in CHOICES or k == "od":
                continue
            v = number(raw.get(k, getattr(x, k)), LABELS[k])
            lo, hi = limits[k]
            if not lo <= v <= hi or (k == "seed" and int(v) != v):
                raise ValueError(f"{LABELS[k]}: rango permitido {lo}–{hi}.")
            setattr(x, k, int(v) if k == "seed" else v)
        if x.arm_m >= min(x.length_m, x.height_m) - 1 and x.template in {"cross", "tee"}:
            raise ValueError("El ancho de brazos debe ser menor que las dimensiones del cruce.")
        if x.bin_s > x.duration_s:
            raise ValueError("El intervalo de serie no puede superar la observación.")
        for p in ports(x):
            side = x.length_m if p in {"N", "S"} else x.height_m
            if x.template in {"cross", "tee"}:
                side = x.arm_m
            if getattr(x, "width_" + p.lower() + "_m") > side:
                raise ValueError(f"El ancho de {NAMES[p]} supera el lado o brazo disponible.")
        matrix = raw.get("od", x.od)
        if (
            not isinstance(matrix, list)
            or len(matrix) != 4
            or any(not isinstance(row, list) or len(row) != 4 for row in matrix)
        ):
            raise ValueError("La matriz OD debe tener cuatro filas y cuatro columnas.")
        selected = ports(x)
        x.od = [[0.0] * 4 for _ in range(4)]
        for i, origin in enumerate(PORTS):
            for j, destination in enumerate(PORTS):
                if origin not in selected or destination not in selected:
                    continue
                value = number(matrix[i][j], f"OD {origin} → {destination}")
                if value < 0 or value > 20000 or (i == j and value):
                    raise ValueError("Las tasas OD deben estar entre 0 y 20 000; diagonal cero.")
                x.od[i][j] = value
        nx, ny = math.ceil(x.length_m / x.cell_m), math.ceil(x.height_m / x.cell_m)
        if nx * ny > 2500:
            raise ValueError("La malla supera 2500 celdas. Aumente el lado de celda.")
        return x


def number(value, label):
    try:
        if isinstance(value, bool):
            raise ValueError()
        v = float(str(value).replace(",", "."))
        if not math.isfinite(v):
            raise ValueError()
        return v
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: introduzca un número finito.") from exc


def ports(x):
    count = "4" if x.template == "cross" else "3" if x.template == "tee" else x.accesses
    return PORTS if count == "4" else ["S", "E", "W"] if count == "3" else ["E", "W"]


def active_keys(x):
    keys = [
        "template",
        "arrival",
        "length_m",
        "height_m",
        "approach_m",
        "speed_mps",
        "cell_m",
        "duration_s",
        "warmup_s",
        "clearance_s",
        "bin_s",
        "seed",
        "od",
    ]
    keys += ["arm_m"] if x.template in {"cross", "tee"} else ["accesses"]
    keys += ["width_" + p.lower() + "_m" for p in ports(x)]
    return keys


def polygon(x):
    a, b = x.length_m / 2, x.height_m / 2
    if x.template in {"rectangle", "hall"}:
        return [(-a, -b), (a, -b), (a, b), (-a, b)]
    w = x.arm_m / 2
    if x.template == "tee":
        return [(-a, -w), (-w, -w), (-w, -b), (w, -b), (w, -w), (a, -w), (a, w), (-a, w)]
    return [
        (-a, -w),
        (-w, -w),
        (-w, -b),
        (w, -b),
        (w, -w),
        (a, -w),
        (a, w),
        (w, w),
        (w, b),
        (-w, b),
        (-w, w),
        (-a, w),
    ]


def area(poly):
    return (
        abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1], strict=True)
            )
        )
        / 2
    )


def clipped(poly, lo_x, hi_x, lo_y, hi_y):
    result = poly
    for axis, bound, sign in [(0, lo_x, 1), (0, hi_x, -1), (1, lo_y, 1), (1, hi_y, -1)]:
        output = []
        for p, q in zip(result, result[1:] + result[:1], strict=True):
            p_in, q_in = sign * (p[axis] - bound) >= 0, sign * (q[axis] - bound) >= 0
            if p_in:
                output.append(p)
            if p_in != q_in:
                f = (bound - p[axis]) / (q[axis] - p[axis])
                output.append((p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])))
        result = output
        if not result:
            break
    return result


def inside(x, px, py):
    if not -x.length_m / 2 <= px <= x.length_m / 2 or not -x.height_m / 2 <= py <= x.height_m / 2:
        return False
    if x.template in {"rectangle", "hall"}:
        return True
    w = x.arm_m / 2
    return abs(py) <= w or (abs(px) <= w and (x.template == "cross" or py <= w))


def grid(x):
    nx, ny = math.ceil(x.length_m / x.cell_m), math.ceil(x.height_m / x.cell_m)
    dx, dy = x.length_m / nx, x.height_m / ny
    poly = polygon(x)
    cells = []
    for iy in range(ny):
        for ix in range(nx):
            left, bottom = -x.length_m / 2 + ix * dx, -x.height_m / 2 + iy * dy
            cells.append(
                dict(
                    ix=ix,
                    iy=iy,
                    x_m=left,
                    y_m=bottom,
                    width_m=dx,
                    height_m=dy,
                    area_m2=area(clipped(poly, left, left + dx, bottom, bottom + dy)),
                )
            )
    return cells


def signature(raw):
    return hashlib.sha256(
        json.dumps(PlazaInput.parse(raw).to_dict(), sort_keys=True).encode()
    ).hexdigest()


def evaluate_plaza(raw):
    x = PlazaInput.parse(raw)
    total = sum(map(sum, x.od))
    access = []
    for i, p in enumerate(PORTS):
        if p in ports(x):
            access.append(
                dict(port=p, origin_pph=sum(x.od[i]), destination_pph=sum(row[i] for row in x.od))
            )
    return dict(
        inputs=x.to_dict(),
        signature=signature(raw),
        area_m2=area(polygon(x)),
        total_pph=total,
        accesses=access,
        polygon=[list(p) for p in polygon(x)],
        expected_people=total * (x.duration_s + x.warmup_s) / 3600,
        assumptions=ASSUMPTIONS,
        created_at=datetime.now(UTC).isoformat(),
    )


def new_case(name="Base · plaza", inputs=None):
    raw = copy.deepcopy({**PlazaInput().to_dict(), **(inputs or {})})
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
        raise ValueError("Estudio de plazas incorrecto.")
    ids = set()
    for c in study["cases"]:
        if (
            not isinstance(c, dict)
            or not isinstance(c.get("id"), str)
            or not 1 <= len(c["id"]) <= 100
            or c["id"] in ids
        ):
            raise ValueError("Identificador de plaza incorrecto.")
        ids.add(c["id"])
        if not isinstance(c.get("name"), str) or not 1 <= len(c["name"]) <= 200:
            raise ValueError("Nombre de plaza incorrecto.")
        raw = c["inputs"]
        if not isinstance(raw, dict) or set(raw) != set(PlazaInput().to_dict()):
            raise ValueError("Borrador de plaza incompleto.")
        for k, v in raw.items():
            if k in CHOICES:
                if v not in {v for _label, v in CHOICES[k]}:
                    raise ValueError("Opción de plaza desconocida.")
            elif k == "od":
                if (
                    not isinstance(v, list)
                    or len(v) != 4
                    or any(not isinstance(r, list) or len(r) != 4 for r in v)
                ):
                    raise ValueError("Borrador OD incorrecto.")
                if any(type(n) not in (str, int, float) for r in v for n in r):
                    raise ValueError("Celda OD incorrecta.")
            elif type(v) not in (str, int, float):
                raise ValueError("Campo de plaza incorrecto.")
        if (
            not isinstance(c["origins"], dict)
            or set(c["origins"]) != set(raw)
            or any(
                v not in {"default", "entered", "observed", "csv"} for v in c["origins"].values()
            )
        ):
            raise ValueError("Procedencia de plaza incorrecta.")
        a = c.get("analytical")
        if a is not None:
            expected = evaluate_plaza(a["inputs"])
            for k in ("signature", "area_m2", "total_pph", "accesses", "expected_people"):
                if a[k] != expected[k]:
                    raise ValueError("Análisis de plaza inconsistente.")
        s = c.get("simulation")
        if s is not None:
            validate_simulation(s)
    if study.get("selected_id") not in ids or study.get("view", "mean_density") not in {
        v for _, v in VIEWS
    }:
        raise ValueError("Selección de plaza incorrecta.")
    return copy.deepcopy(study)


def validate_simulation(s):
    x = PlazaInput.parse(s["inputs"])
    if s["signature"] != signature(s["inputs"]) or set(s["summary"]) != set(SUMMARY_LABELS):
        raise ValueError("Resumen de plaza inconsistente.")
    m = s["summary"]
    nullable = {
        "completed_pct",
        "mean_trip_s",
        "p95_trip_s",
        "spatial_speed_mps",
        "mean_loss_s",
        "clearance_s",
    }
    for k, v in m.items():
        if v is None and k in nullable:
            continue
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
            raise ValueError("Indicador del resumen incorrecto.")
    for k in (
        "generated",
        "started",
        "completed",
        "pending",
        "cohort_generated",
        "cohort_completed",
    ):
        if type(m[k]) is not int or not 0 <= m[k] <= 10000:
            raise ValueError("Conteo de plaza incorrecto.")
    if (
        m["generated"] != m["completed"] + m["pending"]
        or not m["completed"] <= m["started"] <= m["generated"]
        or not m["cohort_completed"] <= m["cohort_generated"] <= m["generated"]
    ):
        raise ValueError("No se conserva la demanda de plaza.")
    expected_pct = 100 * m["completed"] / m["generated"] if m["generated"] else None
    if m["completed_pct"] != expected_pct:
        raise ValueError("Porcentaje completado inconsistente.")
    if not math.isclose(m["mean_density"] * area(polygon(x)), m["mean_occupancy"], abs_tol=1e-6):
        raise ValueError("Densidad global inconsistente.")
    cells = grid(x)
    if len(s["cells"]) != len(cells):
        raise ValueError("Malla incompleta.")
    extra = {"mean_density", "max_density", "person_seconds", "mean_stay_s", "visitors"}
    for cell, expected in zip(s["cells"], cells, strict=True):
        if set(cell) != set(expected) | extra or any(cell[k] != v for k, v in expected.items()):
            raise ValueError("Geometría de celda inconsistente.")
        if (
            any(
                type(cell[k]) not in (int, float) or not math.isfinite(cell[k]) or cell[k] < 0
                for k in extra
            )
            or type(cell["visitors"]) is not int
        ):
            raise ValueError("Indicador de celda incorrecto.")
        if cell["area_m2"] > 1e-9 and not math.isclose(
            cell["mean_density"] * cell["area_m2"] * x.duration_s,
            cell["person_seconds"],
            abs_tol=1e-6,
        ):
            raise ValueError("Densidad de celda inconsistente.")
        if not math.isclose(
            cell["mean_stay_s"] * cell["visitors"], cell["person_seconds"], abs_tol=1e-6
        ):
            raise ValueError("Permanencia de celda inconsistente.")
        if cell["max_density"] + 1e-8 < cell["mean_density"]:
            raise ValueError("Máximo de celda incorrecto.")
    if not math.isclose(
        sum(c["person_seconds"] for c in s["cells"]) / x.duration_s,
        m["mean_occupancy"],
        abs_tol=1e-6,
    ):
        raise ValueError("Mapa y ocupación inconsistentes.")
    if len(s["series"]) != math.ceil(x.duration_s / x.bin_s):
        raise ValueError("Serie incompleta.")
    for i, row in enumerate(s["series"]):
        if set(row) != {"time_s", "interval_s", "occupancy", "density"} or not math.isclose(
            row["time_s"], i * x.bin_s, abs_tol=1e-6
        ):
            raise ValueError("Intervalo de plaza incorrecto.")
        if not math.isclose(
            row["interval_s"], min(x.bin_s, x.duration_s - i * x.bin_s), abs_tol=1e-6
        ):
            raise ValueError("Duración de intervalo incorrecta.")
    if not math.isclose(
        sum(row["occupancy"] * row["interval_s"] for row in s["series"]),
        m["mean_occupancy"] * x.duration_s,
        abs_tol=1e-6,
    ):
        raise ValueError("Serie y mapa inconsistentes.")
    indices = s["critical_cells"]
    if (
        not isinstance(indices, list)
        or len(indices) > 5
        or len(set(indices)) != len(indices)
        or any(type(i) is not int or not 0 <= i < len(cells) for i in indices)
    ):
        raise ValueError("Celdas críticas incorrectas.")
    expected_od = {
        (p, q)
        for p in ports(x)
        for q in ports(x)
        if p != q and x.od[PORTS.index(p)][PORTS.index(q)] > 0
    }
    if {(r["origin"], r["destination"]) for r in s["od"]} != expected_od:
        raise ValueError("Resultados OD incompletos.")
    if (
        sum(r["generated"] for r in s["od"]) != m["generated"]
        or sum(r["completed"] for r in s["od"]) != m["completed"]
    ):
        raise ValueError("Conteos OD inconsistentes.")

    od_keys = {
        "origin",
        "destination",
        "rate_pph",
        "generated",
        "completed",
        "cohort_completed",
        "mean_trip_s",
        "p95_trip_s",
        "spatial_speed_mps",
        "mean_loss_s",
    }
    if len(s["od"]) != len(expected_od):
        raise ValueError("OD repetidos.")
    for row in s["od"]:
        if set(row) != od_keys:
            raise ValueError("Estadísticos OD incompletos.")
        if row["rate_pph"] != x.od[PORTS.index(row["origin"])][PORTS.index(row["destination"])]:
            raise ValueError("Demanda OD inconsistente.")
        for k in ("generated", "completed", "cohort_completed"):
            if type(row[k]) is not int or not 0 <= row[k] <= 10000:
                raise ValueError("Conteo OD incorrecto.")
        if not row["cohort_completed"] <= row["completed"] <= row["generated"]:
            raise ValueError("Cohorte OD inconsistente.")
        for k in ("mean_trip_s", "p95_trip_s", "spatial_speed_mps", "mean_loss_s"):
            v = row[k]
            if v is None and not row["cohort_completed"]:
                continue
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError("Estadístico OD incorrecto.")
    if s.get("model") != "striping" or s.get("sample_s") != 1:
        raise ValueError("Modelo espacial desconocido.")

    def check(v):
        if isinstance(v, dict):
            for n in v.values():
                check(n)
        elif isinstance(v, list):
            for n in v:
                check(n)
        elif type(v) in (int, float) and (not math.isfinite(v) or v < 0):
            raise ValueError("Indicador de plaza incorrecto.")

    for obj in (m, s["series"], s["od"]):
        check(obj)
    for cell in s["cells"]:
        check({k: cell[k] for k in extra})
    if not isinstance(s["engine_version"], str) or not isinstance(s["created_at"], str):
        raise ValueError("Metadatos de plaza incorrectos.")
    if not isinstance(s["warnings"], list) or any(not isinstance(v, str) for v in s["warnings"]):
        raise ValueError("Notas de plaza incorrectas.")
