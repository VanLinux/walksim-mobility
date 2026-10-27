"""Reporte de cruce: metodología, entradas, cuatro resultados y pendientes."""

from walksim.domain.crossing import ASSUMPTIONS, LABELS, SUMMARY_LABELS, fresh


def sections(study, assets=None):
    from walksim.report import _items, _table, display, tex_escape

    if not study:
        return ""
    parts = [
        r"\section{Cruce peatonal semaforizado}",
        _items(ASSUMPTIONS),
        r"""
\subsection{Método}
El recorrido de referencia es $t_0=L/v$. El ciclo satisface
$C=G_v+3+G_p+D_p$, donde $G_p$ permite iniciar el cruce y $D_p$ es el
intervalo de despeje con todas las señales en rojo. Este reparto es una
hipótesis operativa editable, no una verificación normativa.

El motor genera una red con un paso de longitud $L$ y ancho $W$, y dos carriles
vehiculares equivalentes de ancho $L/2$. Se simula cada alternativa con llegadas
Poisson independientes por sentido, desde una red vacía durante $T+2C$ segundos;
las llegadas terminan en $T$. No se elimina un periodo de calentamiento.
No se comparan las colas o esperas con categorías LOS del HCM.

En FCD, una persona inicia al aparecer por primera vez en el enlace de cruce y
completa al aparecer en el área peatonal de salida. En las muestras de 0.5 s se
acumula $w_i=\sum_t 0.5\,\mathbb{1}(v_i<0.1)$ antes de su primera entrada.
La media es $\bar w=\sum_{i\in I}w_i/|I|$, con $I$ igual a quienes ya iniciaron,
incluso si aún están cruzando. Los que aún esperan no forman parte de esa media.
La cola máxima por acera es el máximo muestreado del número de personas detenidas
antes de entrar. No incluye demanda aún no insertada. Se conservan los tamaños
de muestra y los pendientes para mostrar el posible sesgo por censura.

\textbf{Fuentes:} Eclipse SUMO, documentación oficial Pedestrians, PlainXML,
Traffic Lights y FCDOutput. El capítulo 24 del HCM 7 excluye los cruces de vía;
este módulo utiliza simulación operativa, sin atribuirle una metodología LOS HCM.
""",
    ]
    origins = dict(default="Predeterminado", entered="Introducido", observed="Observado", csv="CSV")
    for c in study["cases"]:
        parts.append("\\subsection{" + tex_escape(c["name"]) + "}")
        a = c["analytical"] if fresh(c, "analytical") else None
        s = c["simulation"] if fresh(c, "simulation") else None
        if not a:
            parts.append("Borrador o datos modificados; no se incluyen resultados anteriores.")
            continue
        parts += [
            r"\subsubsection*{Entradas y procedencia}",
            _table(
                [
                    (LABELS[k], str(v) + " [" + origins[c["origins"][k]] + "]")
                    for k, v in a["inputs"].items()
                ]
            ),
            _table(
                [
                    ("Recorrido L/v (s), sin espera", a["reference_s"]),
                    ("Verde vehicular (s)", a["vehicle_green_s"]),
                ]
            ),
        ]
        if not s:
            parts.append(_items(a["warnings"]) if a["warnings"] else "")
            continue
        parts += [
            r"\subsubsection*{Resultados simulados}",
            _table([(SUMMARY_LABELS[k], v) for k, v in s["summary"].items()]),
        ]
        for d, label in [("AB", "Acera A a B"), ("BA", "Acera B a A")]:
            parts += [
                "\\paragraph{" + label + "}",
                _table(
                    [
                        (SUMMARY_LABELS[k], v)
                        for k, v in s["directions"][d].items()
                        if k not in {"max_queue_ab", "max_queue_ba"}
                    ]
                ),
            ]
        parts += [
            _table(
                [
                    ("Motor", s["engine_version"]),
                    ("Fecha UTC", s["created_at"]),
                    ("Colisiones/solapamientos registrados", s["collisions"]),
                ]
            ),
            _items(s["warnings"]) if s["warnings"] else "",
        ]
        key = "crossing:" + c["id"]
        if assets and key in assets:
            parts.append(
                "\\begin{figure}[htbp]\\centering\n"
                "\\includegraphics[width=\\linewidth]{\\detokenize{" + assets[key] + "}}\n"
                "\\caption{" + tex_escape(c["name"] + " · Colas y ciclo") + "}\\end{figure}"
            )
    if len(study["cases"]) == 2:
        parts += [
            r"\subsection{Comparación de alternativas}",
            _table(
                [
                    (
                        c["name"],
                        "Espera media (s): "
                        + display(c["simulation"]["summary"]["mean_wait_s"])
                        + "; pendientes: "
                        + str(c["simulation"]["summary"]["pending"]),
                    )
                    for c in study["cases"]
                    if fresh(c, "simulation")
                ]
            ),
            "Compare con igual demanda, velocidad, duración y semilla. "
            "Los resultados no constituyen una evaluación de seguridad "
            "ni una optimización de señales.",
        ]
    return "\n".join(parts)
