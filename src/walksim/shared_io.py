"""Plantillas de senderos por análisis y entradas documentadas de demora."""

import csv
import io
from pathlib import Path

from walksim.domain.shared import SharedInput, active_keys, new_case
from walksim.walkway_io import write_rows


def template(path, raw=None):
    x = SharedInput.parse(raw or {})
    keys = active_keys(x)
    write_rows(
        path, ["name", *keys], [dict(name="Base · sendero", **{k: x.to_dict()[k] for k in keys})]
    )


def import_cases(path):
    p = Path(path)
    if p.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("El CSV excede 8 MiB.")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Use CSV UTF-8.") from exc
    header = text.splitlines()[0] if text.strip() else ""
    reader = csv.DictReader(
        io.StringIO(text), delimiter=";" if header.count(";") > header.count(",") else ","
    )
    keys = reader.fieldnames or []
    if (
        len(set(keys)) != len(keys)
        or not {"name", "task", "basis", "arrival"} <= set(keys)
        or set(keys) - {"name", *SharedInput().to_dict()}
    ):
        raise ValueError("Encabezados incorrectos; descargue la plantilla de Sendero compartido.")
    cases = []
    for n, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"Fila {n}: columnas incorrectas.")
        raw = {k: v.strip() for k, v in row.items() if k != "name"}
        try:
            x = SharedInput.parse(raw)
            missing = set(active_keys(x)) - set(raw)
            if missing:
                raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
            name = row["name"].strip() or f"Caso {n - 1}"
            if len(name) > 200:
                raise ValueError("Nombre demasiado largo.")
            c = new_case(name, x.to_dict())
            c["origins"].update({k: "csv" for k in raw})
            cases.append(c)
        except ValueError as exc:
            raise ValueError(f"Fila {n}: {exc}") from exc
        if len(cases) > 30:
            raise ValueError("Máximo 30 escenarios.")
    if not cases:
        raise ValueError("El CSV no contiene escenarios.")
    return cases
