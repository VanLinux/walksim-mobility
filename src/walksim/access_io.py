"""Plantillas de accesos por tarea, validadas antes de importar cualquier fila."""

import csv
import io
from pathlib import Path

from walksim.domain.access import AccessInput, active_keys, new_case
from walksim.walkway_io import write_rows


def template(path, raw=None):
    x = AccessInput.parse(raw or {})
    keys = active_keys(x)
    write_rows(
        path, ["name", *keys], [dict(name="Base · acceso", **{k: x.to_dict()[k] for k in keys})]
    )


def import_cases(path):
    target = Path(path)
    if target.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("El CSV excede 8 MiB.")
    try:
        content = target.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Use un CSV UTF-8.") from exc
    header = content.splitlines()[0] if content.strip() else ""
    sep = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=sep)
    keys = reader.fieldnames or []
    if (
        len(set(keys)) != len(keys)
        or not {"name", "layout", "device", "arrival"} <= set(keys)
        or set(keys) - {"name", *AccessInput().to_dict()}
    ):
        raise ValueError("Encabezados incorrectos; descargue la plantilla de Accesos y colas.")
    cases = []
    for number, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"Fila {number}: cantidad de columnas incorrecta.")
        raw = {k: v.strip() for k, v in row.items() if k != "name"}
        try:
            x = AccessInput.parse(raw)
            missing = set(active_keys(x)) - set(raw)
            if missing:
                raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
            name = row["name"].strip() or f"Caso {number - 1}"
            if len(name) > 200:
                raise ValueError("El nombre admite máximo 200 caracteres.")
            c = new_case(name, x.to_dict())
            c["origins"].update({k: "csv" for k in raw})
            cases.append(c)
        except ValueError as exc:
            raise ValueError(f"Fila {number}: {exc}") from exc
        if len(cases) > 30:
            raise ValueError("Importe máximo 30 escenarios.")
    if not cases:
        raise ValueError("El CSV no contiene escenarios.")
    return cases
