"""Secciones del informe Walkway: escenarios, trazabilidad y comparación."""

from __future__ import annotations

from walksim.domain.walkway import signature


def current_result(case, kind):
    try:
        saved = case.get(kind)
        return saved if saved and saved["signature"] == signature(case["inputs"]) else None
    except ValueError:
        return None


def sections(study: dict, assets: dict[str, str] | None = None) -> str:
    # Import lazy: report.py uses this module only after its helpers are defined.
    from walksim.domain.walkway import WalkwayInput
    from walksim.report import _items, _table, display, tex_escape
    from walksim.ui.walkway_labels import INPUT_LABELS, ORIGIN_LABELS
    from walksim.walkway_io import input_keys

    if not study:
        return ""
    parts = [
        r"\section{Walkway 3: escenarios de operación y diseño}",
        r"""Los escenarios comparten el procedimiento de espacio del HCM 7, capítulo 24.
El PHF se aplica una sola vez a demanda horaria. El conteo directo se refiere a 15 min
para flujo aleatorio o a 5 min para pelotones. El diseño es condicional a la velocidad
representativa introducida, no una predicción calibrada de velocidad.

Las etiquetas [Analítico], [Microsimulación] y [Derivado] identifican el origen.
El LOS por espacio global de microsimulación es indicativo: no mide la zona crítica local.
El margen de diseño evita igualar un límite inferior estricto de la tabla LOS.
""",
    ]
    summary = []
    for case in study["cases"]:
        a = current_result(case, "analytical")
        s = current_result(case, "simulation")
        summary.append(
            (
                case["name"],
                (
                    "LOS "
                    + a["metrics"]["LOS operativo"]
                    + "; ancho útil "
                    + display(a["metrics"]["Ancho efectivo evaluado (m)"])
                    + " m; v/c "
                    + display(a["metrics"]["Relación demanda/capacidad"])
                )
                if a
                else "Pendiente de cálculo",
            )
        )
        if s:
            summary.append(
                (
                    case["name"] + " · microsimulación",
                    display(s["directions"]["total"]["mean_s"]) + " s de tiempo medio de cohorte",
                )
            )
    parts.append(_table(summary))
    for case in study["cases"]:
        a = current_result(case, "analytical")
        s = current_result(case, "simulation")
        parts.append("\\subsection{" + tex_escape(case["name"]) + "}\n")
        if not a:
            parts.append(
                "El escenario contiene un borrador o datos modificados; "
                "se excluyen sus resultados anteriores de esta comparación.\n"
            )
            continue
        parts.append("\\subsubsection*{Datos y procedencia}\n")
        parts.append(
            _table(
                [
                    (
                        INPUT_LABELS.get(k, k),
                        str(v)
                        + " ["
                        + ORIGIN_LABELS.get(case["origins"].get(k, "default"), "Predeterminado")
                        + "]",
                    )
                    for k, v in a["inputs"].items()
                    if k in input_keys(WalkwayInput.parse(a["inputs"]))
                ]
            )
        )
        parts.append("\\subsubsection*{[Analítico] Ecuaciones y resultados}\n")
        parts.append("\\begin{gather*}\n" + " \\\\\n".join(a["equations"]) + "\n\\end{gather*}\n")
        parts.append(_table(list(a["metrics"].items())))
        parts.append(_table(list(zip("ABCDE", a["thresholds"], strict=True))))
        parts.append(
            "Los límites anteriores son inferiores estrictos, en m²/peatón; "
            "F incluye el último límite.\n"
        )
        parts.append(_items(a["assumptions"] + a["warnings"]))
        parts.append("\\textbf{Fuente:} " + tex_escape(a["source"]) + "\n")
        if any(v == "default" for v in case["origins"].values()):
            parts.append(
                "\\textbf{Procedencia:} el escenario conserva valores predeterminados; "
                "revise su representatividad antes de interpretar el diseño.\n"
            )
        if not s:
            parts.append("Microsimulación pendiente o desactualizada para estas entradas.\n")
            continue
        parts.append("\\subsubsection*{[Microsimulación] Configuración y mediciones}\n")
        parts.append(
            _table(
                [
                    ("Motor", s["engine_version"]),
                    ("Modelo peatonal", s["model"]),
                    ("Fecha UTC", s["created_at"]),
                    ("Semilla", s["inputs"]["seed"]),
                    ("Calentamiento (s)", s["inputs"]["warmup_s"]),
                    ("Observación (s)", s["inputs"]["duration_s"]),
                    ("Intervalo gráfico (s)", s["inputs"]["bin_s"]),
                ]
            )
        )
        labels = dict(
            generated="Peatones generados",
            started="Peatones iniciados",
            completed="Recorridos completados totales",
            unfinished="Inconclusos al terminar el despeje",
            not_started="Pendientes de iniciar",
            cohort_entered="Entradas de cohorte observada",
            cohort_completed="Completados de cohorte",
            mean_occupancy="Ocupación media (peat)",
            max_occupancy="Ocupación máxima global (peat)",
            density="Densidad global (peat/m²)",
            space="Espacio global equivalente (m²/peat)",
            los_indicative="LOS global indicativo",
            entered_pph="Tasa de entrada observada (peat/h)",
            exited_pph="Tasa de salida observada (peat/h)",
        )
        parts.append(_table([(labels[k], v) for k, v in s["summary"].items()]))
        for direction, title in [("total", "Ambos sentidos"), ("ab", "A → B"), ("ba", "B → A")]:
            parts.append("\\paragraph{" + tex_escape(title) + "}\n")
            labels = dict(
                count="Recorridos completados",
                mean_s="Tiempo medio (s)",
                min_s="Mínimo (s)",
                max_s="Máximo (s)",
                p50_s="P50 (s)",
                p85_s="P85 (s)",
                p95_s="P95 (s)",
                spatial_speed_mps="Velocidad espacial de cohorte (m/s)",
                mean_speed_mps="Media de velocidades individuales (m/s)",
                mean_loss_s="Tiempo perdido medio (s)",
            )
            parts.append(
                _table(
                    [
                        (labels[k], "N/A" if v is None else v)
                        for k, v in s["directions"][direction].items()
                    ]
                )
            )
        parts.append("\\subsubsection*{[Derivado] Comparación analítica y simulada}\n")
        rows = []
        for row in s["comparison"]:

            def value(v):
                return "N/A" if v is None else display(v)

            rows.append(
                (
                    row["label"] + " (" + row["unit"] + ")",
                    "Analítico "
                    + value(row["analytical"])
                    + "; simulado "
                    + value(row["simulated"])
                    + "; cambio "
                    + value(row["delta_pct"])
                    + " %",
                )
            )
        parts.append(_table(rows))
        if assets and case["id"] in assets:
            # Asset names are produced internally from hexadecimal IDs and fingerprints.
            path = assets[case["id"]]
            parts.append(
                "\\begin{figure}[htbp]\\centering\n\\includegraphics[width=\\linewidth]{\\detokenize{"
                + path
                + "}}\n\\caption{"
                + tex_escape(case["name"] + " · series y distribución de tiempos [Derivado]")
                + "}\\end{figure}\n"
            )
        parts.append(_items(s["definitions"] + s["warnings"]))
    parts.append(r"""\subsection{Interpretación de alternativas}
Compare alternativas bajo las mismas unidades, periodos, tipo de flujo y definiciones.
Una modificación de ancho o demanda puede alterar el LOS analítico; una diferencia con
la microsimulación no demuestra por sí sola error ni validez. Los recorridos pendientes
pueden sesgar las estadísticas de la cohorte completada.
El ancho de diseño redondeado y la demanda admisible incorporan el margen elegido;
no deben presentarse como mínimos normativos de accesibilidad ni capacidades garantizadas.
""")
    return "\n".join(parts)
