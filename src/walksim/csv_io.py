"""Plantillas CSV específicas por análisis e importación validada de lotes."""

from __future__ import annotations

import csv
import io
from dataclasses import asdict
from pathlib import Path

from walksim.domain.analysis import METHODS, calculate
from walksim.domain.models import CorridorScenario
from walksim.project import atomic_write

SIMULATION_FIELDS = tuple(asdict(CorridorScenario()))


def write_template(path: str | Path, method: str) -> None:
    if method == "simulation":
        sample = asdict(CorridorScenario())
    else:
        sample = {f.key: f.default for f in METHODS[method].fields}
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["analysis", "name", *sample])
    writer.writeheader()
    writer.writerow({"analysis": method, "name": "Ejemplo editable", **sample})
    atomic_write(path, "\ufeff" + output.getvalue())


def read_csv(path: str | Path) -> tuple[str, list[dict]]:
    target = Path(path)
    if target.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("El CSV excede el límite de 8 MiB.")
    try:
        content = target.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("Guarde el CSV en codificación UTF-8.") from exc
    first = content.splitlines()[0] if content.strip() else ""
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    headers = reader.fieldnames
    if not headers or len(set(headers)) != len(headers):
        raise ValueError("El CSV está vacío o repite encabezados.")
    records = []
    method = None
    for number, row in enumerate(reader, 2):
        if not any(row.values()):
            continue
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"Fila {number}: cantidad de columnas incorrecta.")
        current = row.get("analysis", "").strip()
        if method is None:
            method = current
            if method != "simulation" and method not in METHODS:
                raise ValueError(f"Fila {number}: análisis desconocido.")
            keys = (
                SIMULATION_FIELDS
                if method == "simulation"
                else tuple(f.key for f in METHODS[method].fields)
            )
            if set(headers) != {"analysis", "name", *keys}:
                raise ValueError(
                    "Los encabezados no coinciden con la plantilla del análisis. "
                    "Descargue su plantilla y conserve los nombres de las columnas."
                )
        if current != method:
            raise ValueError(f"Fila {number}: use un solo tipo de análisis por CSV.")
        raw = {key: row[key].strip() for key in keys}
        try:
            if method == "simulation":
                values = {key: float(value.replace(",", ".")) for key, value in raw.items()}
                if not values["seed"].is_integer() or not 0 <= values["seed"] <= 2147483647:
                    raise ValueError("La semilla debe ser un entero entre 0 y 2147483647.")
                values["seed"] = int(values["seed"])
                scenario = CorridorScenario(**values)
                import math

                if not all(math.isfinite(v) for v in values.values()) or scenario.validate():
                    raise ValueError("Parámetros del corredor fuera de rango.")
                records.append(asdict(scenario))
            else:
                result = calculate(method, raw, row["name"]).to_dict()
                result["data_source"] = f"CSV: {target.name}, fila {number}"
                records.append(result)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"Fila {number}: {exc}") from exc
        if len(records) > 1000:
            raise ValueError("Use como máximo 1000 casos por CSV.")
    if not records:
        raise ValueError("El CSV no contiene casos.")
    if method == "simulation" and len(records) != 1:
        raise ValueError("La plantilla de microsimulación admite un escenario por archivo.")
    return method, records
