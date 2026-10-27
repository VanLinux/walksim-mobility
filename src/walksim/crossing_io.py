"""CSV estricto: una fila por alternativa, máximo dos; SI y UTF-8."""

import csv
import io
from pathlib import Path

from walksim.domain.crossing import CrossingInput, new_case
from walksim.walkway_io import write_rows


def template(path, raw=None):
    x = CrossingInput.parse(raw or {})
    write_rows(path, ["name", *x.to_dict()], [dict(name="Base · cruce", **x.to_dict())])


def import_cases(path):
    p = Path(path)
    if p.stat().st_size > 1024 * 1024:
        raise ValueError("El CSV excede 1 MiB.")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Use CSV UTF-8.") from exc
    header = text.splitlines()[0] if text.strip() else ""
    reader = csv.DictReader(
        io.StringIO(text), delimiter=";" if header.count(";") > header.count(",") else ","
    )
    keys = reader.fieldnames or []
    if len(set(keys)) != len(keys) or set(keys) != {"name", *CrossingInput().to_dict()}:
        raise ValueError("Encabezados incorrectos; descargue la plantilla de Cruce semaforizado.")
    cases = []
    for n, row in enumerate(reader, 2):
        try:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("Columnas incorrectas.")
            raw = {k: v.strip() for k, v in row.items() if k != "name"}
            x = CrossingInput.parse(raw)
            name = row["name"].strip() or f"Caso {n - 1}"
            if len(name) > 200:
                raise ValueError("Nombre demasiado largo.")
            c = new_case(name, x.to_dict())
            c["origins"] = {k: "csv" for k in raw}
            cases.append(c)
            if len(cases) > 2:
                raise ValueError("Use un caso base y una alternativa como máximo.")
        except ValueError as exc:
            raise ValueError(f"Fila {n}: {exc}") from exc
    if not cases:
        raise ValueError("El CSV no contiene escenarios.")
    return cases
