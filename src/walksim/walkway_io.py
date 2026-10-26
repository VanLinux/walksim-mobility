"""CSV Walkway: plantillas por tarea y exportación de resultados y series."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from walksim.domain.walkway import WalkwayInput, new_case
from walksim.project import atomic_write


def input_keys(x: WalkwayInput) -> list[str]:
    keys = [
        "mode",
        "flow_type",
        "demand_basis",
        "length_m",
        "obstacles_m",
        "edges_m",
        "speed_mps",
        "slope_pct",
    ]
    if x.mode != "design_width":
        keys += ["width_m"]
    if x.mode != "design_demand":
        keys += (
            ["flow_ab_pph", "flow_ba_pph", "phf"]
            if x.demand_basis == "hourly"
            else ["count_ab", "count_ba"]
        )
    else:
        keys += ["share_ab_pct"]
        if x.demand_basis == "hourly":
            keys += ["phf"]
    if x.mode != "operation":
        keys += ["target_los", "margin_pct"]
    keys += ["duration_s", "warmup_s", "bin_s", "seed"]
    if x.flow_type == "platoon":
        keys += ["platoon_cycle_s", "platoon_release_s"]
    return keys


def write_rows(path, headers, rows) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(path, "\ufeff" + stream.getvalue())


def template(path, raw: dict | None = None) -> None:
    x = WalkwayInput.parse(raw or {})
    keys = input_keys(x)
    sample = {key: x.to_dict()[key] for key in keys}
    write_rows(path, ["name", *keys], [dict(name="Base", **sample)])


def import_cases(path) -> list[dict]:
    target = Path(path)
    if target.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("El CSV excede 8 MiB.")
    try:
        content = target.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("El CSV debe estar codificado en UTF-8.") from exc
    header = content.splitlines()[0] if content.strip() else ""
    delimiter = ";" if header.count(";") > header.count(",") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    keys = reader.fieldnames or []
    if (
        len(set(keys)) != len(keys)
        or not {"name", "mode", "flow_type", "demand_basis"} <= set(keys)
        or set(keys) - {"name", *WalkwayInput().to_dict()}
    ):
        raise ValueError("Encabezados no válidos. Descargue la plantilla de Walkway.")
    cases = []
    for number, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f"Fila {number}: cantidad de columnas incorrecta.")
        raw = {k: v.strip() for k, v in row.items() if k != "name"}
        try:
            parsed = WalkwayInput.parse(raw)
            missing = set(input_keys(parsed)) - set(raw)
            if missing:
                raise ValueError("Faltan columnas: " + ", ".join(sorted(missing)))
            case = new_case(row["name"].strip() or f"Caso {number - 1}", parsed.to_dict())
            case["origins"].update({k: "csv" for k in raw})
            cases.append(case)
        except ValueError as exc:
            raise ValueError(f"Fila {number}: {exc}") from exc
        if len(cases) > 30:
            raise ValueError("Importe como máximo 30 escenarios.")
    if not cases:
        raise ValueError("El CSV no contiene escenarios.")
    return cases
