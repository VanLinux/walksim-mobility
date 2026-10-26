"""Memoria de plazas: demanda, geometría, estadísticos OD y mapas de celda."""

from walksim.domain.plaza import (
    ASSUMPTIONS,
    CHOICES,
    LABELS,
    NAMES,
    PORTS,
    SUMMARY_LABELS,
    PlazaInput,
    active_keys,
    fresh,
)


def sections(study, assets=None):
    from walksim.report import _items, _table, display, tex_escape

    if not study:
        return ""
    origins = dict(default="Predeterminado", entered="Introducido", observed="Observado", csv="CSV")
    parts = [
        r"\section{Plazas y flujos cruzados: demanda local y distribución espacial}",
        _items(ASSUMPTIONS),
        r"""\subsection{Método y unidades}
La matriz $q_{ij}$ contiene tasas en peat/h, con diagonal cero.
$Q_i=\sum_j q_{ij}$ y $p_{ij}=q_{ij}/Q_i$ describen generación local y reparto de destinos.
Las llegadas son uniformes o Poisson por OD. El área de cada plantilla se obtiene del
polígono de circulación; los accesos exteriores se excluyen del mapa y se incluyen
en los tiempos de recorrido. Los cruces en + y T se construyen con brazos conectados
a un área central rectangular para respetar sus límites geométricos.

Las posiciones FCD del motor se muestrean cada segundo. Se integra la ocupación de
cada celda $k$ con retención de la posición entre muestras:
$P_k=\sum_t n_k(t)\Delta t$ (peatón s),
$\bar D_k=P_k/(A_k T)$ y $D_{k,\max}=\max_t n_k(t)/A_k$.
$A_k$ es el área de la celda recortada por el polígono; los bordes no usan un
área rectangular completa cuando parte de ella está fuera del recinto.
La permanencia media observada es $P_k/U_k$, donde $U_k$ son visitantes distintos
registrados. Puede haber visitas menores que la frecuencia de muestreo.
El área global satisface $\bar N=\sum_k P_k/T$ y $\bar D=\bar N/A$.
Las celdas críticas se ordenan por densidad media; no representan umbrales de seguridad.

La cohorte contiene personas generadas durante observación y completadas antes
del límite de despeje. Sus tiempos incluyen demoras de inserción y accesos. La velocidad
espacial se calcula como $\sum_i L_i/\sum_i t_i$. El tiempo perdido procede de personinfo
del motor. P95 usa interpolación lineal entre estadísticos de orden. Los pendientes
se informan por separado y pueden sesgar los tiempos completados. No se asigna LOS
HCM ni se interpretan los mapas como una calibración o un motor Social Force propio.

\textbf{Referencias:} documentación oficial Eclipse SUMO, Pedestrians, PlainXML
(walkingArea), FCDOutput y TripInfo. El modelo peatonal usado es striping.
""",
    ]
    compare = []
    for c in study["cases"]:
        a = c["analytical"] if fresh(c, "analytical") else None
        s = c["simulation"] if fresh(c, "simulation") else None
        text = "Borrador o datos modificados"
        if a:
            text = f"Área {display(a['area_m2'])} m²; demanda {display(a['total_pph'])} peat/h"
        if s:
            text += "; tiempo medio " + display(s["summary"]["mean_trip_s"]) + " s"
        compare.append((c["name"], text))
    parts += [r"\subsection{Alternativas}", _table(compare)]
    for c in study["cases"]:
        parts.append("\\subsection{" + tex_escape(c["name"]) + "}")
        a = c["analytical"] if fresh(c, "analytical") else None
        s = c["simulation"] if fresh(c, "simulation") else None
        if not a:
            parts.append("Datos modificados o incompletos: se excluyen sus resultados anteriores.")
            continue
        x = PlazaInput.parse(c["inputs"])
        rows = []
        for k in active_keys(x):
            if k == "od":
                continue
            v = a["inputs"][k]
            if k in CHOICES:
                v = next(label for label, value in CHOICES[k] if value == v)
            rows.append((LABELS[k], str(v) + " [" + origins[c["origins"][k]] + "]"))
        parts += [
            r"\subsubsection*{Entradas y procedencia}",
            _table(rows),
            "\\textbf{Origen de la matriz OD:} " + tex_escape(origins[c["origins"]["od"]]),
            r"\subsubsection*{Matriz OD local en peat/h}",
            r"\begin{longtable}{lrrrr}\toprule "
            r"Origen / Destino & Norte & Sur & Este & Oeste\\\midrule",
        ]
        for p, row in zip(PORTS, x.od, strict=True):
            parts.append(NAMES[p] + " & " + " & ".join(display(v) for v in row) + r"\\")
        parts += [
            r"\bottomrule\end{longtable}",
            _table(
                [
                    ("Área de circulación (m²)", a["area_m2"]),
                    ("Demanda total (peat/h)", a["total_pph"]),
                ]
            ),
        ]
        if not s:
            continue
        parts += [
            r"\subsubsection*{Microsimulación y mapas}",
            _table(
                [
                    ("Versión del motor", s["engine_version"]),
                    ("Modelo", s["model"]),
                    ("Fecha UTC", s["created_at"]),
                    ("Muestreo espacial (s)", s["sample_s"]),
                ]
            ),
            _table([(SUMMARY_LABELS[k], v) for k, v in s["summary"].items()]),
        ]
        parts.append(r"\subsubsection*{Estadísticos por movimiento}")
        for r in s["od"]:
            parts.append(
                "\\paragraph{"
                + tex_escape(NAMES[r["origin"]] + " a " + NAMES[r["destination"]])
                + "}"
            )
            parts.append(
                _table(
                    [
                        ("Tasa nominal (peat/h)", r["rate_pph"]),
                        ("Generados", r["generated"]),
                        ("Completados totales", r["completed"]),
                        ("Completados de cohorte", r["cohort_completed"]),
                        ("Tiempo medio de cohorte (s)", r["mean_trip_s"]),
                        ("P95 (s)", r["p95_trip_s"]),
                        ("Velocidad espacial (m/s)", r["spatial_speed_mps"]),
                        ("Tiempo perdido medio (s)", r["mean_loss_s"]),
                    ]
                )
            )
        parts.append(r"\subsubsection*{Celdas críticas por densidad media}")
        for i in s["critical_cells"]:
            cell = s["cells"][i]
            parts.append(
                _table(
                    [
                        ("Celda (columna, fila)", f"({cell['ix'] + 1}, {cell['iy'] + 1})"),
                        ("Área real (m²)", cell["area_m2"]),
                        ("Densidad media (peat/m²)", cell["mean_density"]),
                        ("Máximo muestreado (peat/m²)", cell["max_density"]),
                        ("Ocupación acumulada (peatón s)", cell["person_seconds"]),
                        ("Visitantes distintos", cell["visitors"]),
                        ("Permanencia media (s)", cell["mean_stay_s"]),
                    ]
                )
            )
        for view, label in [
            ("mean_density", "Densidad media"),
            ("max_density", "Densidad máxima muestreada"),
            ("person_seconds", "Ocupación acumulada"),
            ("mean_stay_s", "Permanencia media por visitante"),
        ]:
            key = "plaza:" + c["id"] + ":" + view
            if assets and key in assets:
                parts.append(
                    "\\begin{figure}[htbp]\\centering\n"
                    "\\includegraphics[width=\\linewidth]{\\detokenize{" + assets[key] + "}}\n"
                    "\\caption{" + tex_escape(c["name"] + " · " + label) + "}\\end{figure}"
                )
        if s["warnings"]:
            parts.append(_items(s["warnings"]))
    return "\n".join(parts)
