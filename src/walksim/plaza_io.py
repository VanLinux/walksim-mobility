"""Matriz OD cuadrada y escenarios completos en CSV de formato largo."""

import csv
import io
from pathlib import Path

from walksim.domain.plaza import PORTS, PlazaInput, active_keys, new_case, number
from walksim.walkway_io import write_rows


def read_csv(path):
    p = Path(path)
    if p.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("El CSV excede 8 MiB.")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Use un archivo UTF-8.") from exc
    first = text.splitlines()[0] if text.strip() else ""
    return csv.reader(
        io.StringIO(text), delimiter=";" if first.count(";") > first.count(",") else ","
    )


def export_matrix(path, matrix):
    write_rows(
        path,
        ["origin", *PORTS],
        [
            dict(origin=p, **dict(zip(PORTS, row, strict=True)))
            for p, row in zip(PORTS, matrix, strict=True)
        ],
    )


def import_matrix(path):
    rows = list(read_csv(path))
    if len(rows) != 5 or rows[0] != ["origin", *PORTS] or any(len(r) != 5 for r in rows):
        raise ValueError("Use la matriz guía: origin,N,S,E,W y cuatro filas N,S,E,W.")
    if [r[0] for r in rows[1:]] != PORTS:
        raise ValueError("Orden de filas requerido: N, S, E, W.")
    matrix = [[number(v, "Celda OD") for v in row[1:]] for row in rows[1:]]
    # Validate all cells, including those hidden by the current geometry.
    PlazaInput.parse(dict(od=matrix))
    return matrix


def template(path, raw=None):
    x = PlazaInput.parse(raw or {})
    keys = [k for k in active_keys(x) if k != "od"]
    rows = []
    for i, p in enumerate(PORTS):
        for j, q in enumerate(PORTS):
            if i != j:
                rows.append(
                    dict(
                        name="Base · plaza",
                        **{k: x.to_dict()[k] for k in keys},
                        origin=p,
                        destination=q,
                        rate_pph=x.od[i][j],
                    )
                )
    write_rows(path, ["name", *keys, "origin", "destination", "rate_pph"], rows)


def import_cases(path):
    reader = read_csv(path)
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV vacío.") from exc
    required = {"name", "template", "arrival", "origin", "destination", "rate_pph"}
    allowed = {*PlazaInput().to_dict(), "name", "origin", "destination", "rate_pph"} - {"od"}
    if len(set(headers)) != len(headers) or not required <= set(headers) or set(headers) - allowed:
        raise ValueError("Encabezados incorrectos. Descargue la plantilla de escenarios de Plaza.")
    groups = {}
    for n, values in enumerate(reader, 2):
        if len(values) != len(headers):
            raise ValueError(f"Fila {n}: cantidad de columnas incorrecta.")
        row = {k: v.strip() for k, v in zip(headers, values, strict=True)}
        name = row.pop("name")
        if not 1 <= len(name) <= 200:
            raise ValueError(f"Fila {n}: nombre vacío o demasiado largo.")
        p, q, rate = (
            row.pop("origin"),
            row.pop("destination"),
            number(row.pop("rate_pph"), f"Fila {n}"),
        )
        if p not in PORTS or q not in PORTS or p == q or not 0 <= rate <= 20000:
            raise ValueError(f"Fila {n}: par OD o tasa incorrectos.")
        if name not in groups:
            groups[name] = dict(raw=row, matrix=[[0.0] * 4 for _ in range(4)], pairs=set())
        group = groups[name]
        if group["raw"] != row or (p, q) in group["pairs"]:
            raise ValueError(
                f"Fila {n}: geometría inconsistente o par OD repetido en el escenario."
            )
        group["pairs"].add((p, q))
        group["matrix"][PORTS.index(p)][PORTS.index(q)] = rate
        if len(groups) > 30:
            raise ValueError("Máximo 30 escenarios.")
    cases = []
    for name, g in groups.items():
        if len(g["pairs"]) != 12:
            raise ValueError(
                f"{name}: incluya los doce pares OD; use cero para movimientos inactivos."
            )
        raw = {**g["raw"], "od": g["matrix"]}
        x = PlazaInput.parse(raw)
        if set(active_keys(x)) - {*raw}:
            raise ValueError(f"{name}: faltan columnas de la tarea. Descargue su plantilla.")
        # Do not silently discard positive demand at an inactive port.
        if x.od != g["matrix"]:
            raise ValueError(f"{name}: existe demanda en un acceso inactivo.")
        c = new_case(name, x.to_dict())
        c["origins"].update({k: "csv" for k in raw})
        cases.append(c)
    if not cases:
        raise ValueError("El CSV no contiene escenarios.")
    return cases
