"""Reporte LaTeX autónomo: identificación, datos, ecuaciones, resultados y fuentes."""

from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

from walksim import __version__
from walksim.domain.analysis import METHODS
from walksim.project import ProjectState, atomic_write

_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "²": r"\ensuremath{^{2}}",
    "³": r"\ensuremath{^{3}}",
    "→": r"\ensuremath{\rightarrow}",
    "←": r"\ensuremath{\leftarrow}",
    "−": "-",
    "–": "--",
    "—": "---",
    "≤": r"\ensuremath{\le}",
    "≥": r"\ensuremath{\ge}",
    "×": r"\ensuremath{\times}",
    ">": r"\ensuremath{>}",
    "<": r"\ensuremath{<}",
    "\n": r"\newline{} ",
}


def tex_escape(value: object) -> str:
    return "".join(
        _ESCAPES.get(char, char if ord(char) >= 32 and ord(char) < 65536 else " ")
        for char in str(value)
    )


def display(value: object) -> str:
    if value is None:
        return "Sin valor finito (ocupación nula)"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("El reporte contiene un número no finito.")
        return f"{value:.6g}"
    return str(value)


def _table(rows: list[tuple[object, object]]) -> str:
    body = "\n".join(tex_escape(k) + " & " + tex_escape(display(v)) + r" \\" for k, v in rows)
    return (
        r"\begin{longtable}{p{0.58\linewidth}p{0.35\linewidth}}"
        "\n"
        r"\toprule\textbf{Concepto} & \textbf{Valor} \\\midrule\endhead"
        "\n" + body + "\n" + r"\bottomrule\end{longtable}" + "\n"
    )


def _items(items: list[str]) -> str:
    return (
        "\\begin{itemize}\n"
        + "\n".join("\\item " + tex_escape(s) for s in items)
        + "\n\\end{itemize}\n"
    )


def build_report(state: ProjectState, assets: dict[str, str] | None = None) -> str:
    if not state.project.analyst.strip():
        raise ValueError("Indique el nombre del analista en la pestaña Proyecto antes de exportar.")
    if (
        not state.analyses
        and not state.simulations
        and not any(c.get("analytical") for c in state.walkway.get("cases", []))
    ):
        raise ValueError("Realice al menos un análisis o una simulación antes de exportar.")
    stamp = datetime.now(ZoneInfo("America/Mexico_City")).strftime("%d/%m/%Y %H:%M")
    parts = [
        r"""\documentclass[11pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\IfFileExists{spanish.ldf}{\usepackage[spanish,es-nodecimaldot]{babel}}
  {\usepackage[english]{babel}}
\usepackage{lmodern}
\usepackage[margin=2.2cm]{geometry}
\usepackage{amsmath,amssymb,booktabs,longtable,array,xcolor,fancyhdr,graphicx}
\usepackage[hidelinks]{hyperref}
\definecolor{ink}{HTML}{30343B}
\pagestyle{fancy}\fancyhf{}
\fancyhead[L]{\small WalkSim Mobility -- Análisis peatonal}
\fancyfoot[C]{\thepage}\setlength{\headheight}{14pt}
\setlength{\parindent}{0pt}\setlength{\parskip}{6pt}
\setlength{\emergencystretch}{3em}
\begin{document}
\begin{center}
{\Huge\bfseries\color{ink} WalkSim Mobility}\par
{\Large Informe técnico de análisis peatonal}\par
""",
        tex_escape(f"Versión {__version__} · Generado el {stamp} (Ciudad de México)") + "\n",
        r"\end{center}",
        "\n\\section{Identificación del estudio}\n",
        _table(
            [
                ("Proyecto", state.project.name),
                ("Ubicación", state.project.location),
                ("Analista responsable", state.project.analyst),
                ("Análisis analíticos incluidos", len(state.analyses)),
                ("Microsimulaciones incluidas", len(state.simulations)),
            ]
        ),
        "\\textbf{Notas del analista:} " + tex_escape(state.project.notes or "Sin notas.") + "\n",
        r"""\section{Objeto, alcance y unidades}
Este informe contiene los casos calculados y las microsimulaciones ejecutadas del estudio.
Cada caso conserva sus propias entradas y fecha de ejecución. Los borradores no calculados
se guardan en el proyecto \texttt{.wksim}, pero no se presentan como resultados.
Se emplean metros, segundos, minutos, peatones y vehículos. Las conversiones son
$1\,\mathrm{ft}=0.3048\,\mathrm{m}$ y
$1\,\mathrm{ft}^2=0.09290304\,\mathrm{m}^2$.

\section{Fundamentos y criterios}
La densidad es $D=N/A$, el espacio es $M=1/D$ y el flujo específico satisface
$q=60 S D$ cuando $S$ se expresa en m/s y $q$ en peat/min/m.
El ancho útil descuenta obstáculos y franjas de borde, sin duplicar sus áreas de influencia.
El LOS por espacio de aceras, pelotones y escaleras emplea las tablas del capítulo 24
HCM 7. Para las áreas de espera se utiliza el criterio de FHWA/Fruin identificado en el caso.
El espacio medio es la medida principal: las tasas de flujo y velocidades son medidas relacionadas.
El resultado no es un índice PLOS de enlace o segmento de calle urbana.

Los límites se convierten desde sus unidades originales sin redondear para clasificar;
las tablas numéricas del informe muestran hasta seis cifras significativas.
En cada tabla de espacio, A corresponde a $M$ mayor que el primer límite;
B, C, D y E corresponden sucesivamente a límites inferiores estrictos y superiores inclusivos;
F corresponde a $M$ menor o igual al último límite.
La convención conservadora de igualdad también se aplica a áreas de espera.

Para cruces semaforizados se calcula demora uniforme y la categoría por demora del documento
aportado. Esta categoría no representa el procedimiento completo de PLOS de intersección HCM 7.
Para cruces sin semáforo se calcula demora por aceptación de brechas de un peatón individual,
en una etapa, sin cesión vehicular. No se asigna un PLOS a partir de esa demora.
Los valores no sustituyen una evaluación de seguridad vial, accesibilidad o evacuación.
""",
    ]
    from walksim.walkway_report import sections

    parts.append(sections(state.walkway, assets))
    if state.analyses:
        parts.append("\\section{Análisis analíticos realizados}\n")
    for index, result in enumerate(state.analyses, 1):
        method = result["method"]
        parts += [
            "\\subsection{" + tex_escape(f"Caso {index}: {result['name']}") + "}\n",
            _table(
                [
                    ("Método", METHODS[method].title),
                    ("Fecha de cálculo (UTC)", result["created_at"]),
                    ("Origen de los datos", result.get("data_source", "Captura manual")),
                    ("Criterio de evaluación", result["criterion"]),
                ]
            ),
            "\\subsubsection*{Datos de entrada}\n",
        ]
        labels = {
            item.key: f"{item.label} ({item.unit})" if item.unit else item.label
            for item in METHODS[method].fields
        }
        parts.append(_table([(labels[k], v) for k, v in result["inputs"].items()]))
        parts.append("\\subsubsection*{Ecuaciones y desarrollo}\n")
        parts += ["\\[" + equation + "\\]\n" for equation in result["equations"]]
        parts += [
            _items(result["steps"]),
            "\\subsubsection*{Resultados}\n",
            _table(list(result["metrics"].items())),
        ]
        if result["thresholds"]:
            parts.append("\\textbf{Límites inferiores estrictos por espacio (m²/peatón):}\n")
            parts.append(_table(list(zip("ABCDE", result["thresholds"], strict=True))))
            parts.append("F: espacio menor o igual al límite de E.\n")
        if method == "signal":
            parts.append(
                _table(
                    [
                        ("A", "d < 10 s"),
                        ("B", "10 ≤ d < 20 s"),
                        ("C", "20 ≤ d < 30 s"),
                        ("D", "30 ≤ d < 40 s"),
                        ("E", "40 ≤ d ≤ 60 s"),
                        ("F", "d > 60 s"),
                    ]
                )
            )
        parts += [
            "\\subsubsection*{Supuestos, interpretación y límites}\n",
            _items(result["assumptions"]),
            "\\textbf{Fuente del procedimiento:} " + tex_escape(result["source"]) + "\n",
        ]
    if state.simulations:
        parts += [
            r"""\section{Microsimulación peatonal}
Eclipse SUMO es el motor de microsimulación; se ejecuta sin interfaz gráfica con el modelo
peatonal \texttt{striping}. Python genera el escenario, procesa las salidas y aplica las
relaciones analíticas. Las demoras de recorrido simuladas no equivalen automáticamente
a demora de control de un cruce. El corredor es recto, de ancho uniforme y sin vehículos,
escaleras ni semáforos. No se atribuye una simulación de esos elementos a los casos analíticos.
"""
        ]
    for index, run in enumerate(state.simulations, 1):
        parts += [
            "\\subsection{" + tex_escape(f"Microsimulación {index}") + "}\n",
            _table(
                [
                    ("Fecha (UTC)", run["created_at"]),
                    ("Versión SUMO", run.get("engine_version", "No registrada")),
                    ("Modelo peatonal", "striping"),
                ]
            ),
            "\\subsubsection*{Escenario utilizado}\n",
        ]
        scenario_labels = dict(
            length_m="Longitud (m)",
            width_m="Ancho útil (m)",
            flow_ab_pph="Flujo A → B (peat/h)",
            flow_ba_pph="Flujo B → A (peat/h)",
            walking_speed_mps="Velocidad de referencia (m/s)",
            analysis_time_s="Demanda activa (s)",
            seed="Semilla",
        )
        parts.append(_table([(scenario_labels[k], v) for k, v in run["scenario"].items()]))
        parts.append(_table([(k, v) for k, v in run.get("measurements", {}).items()]))
        labels = dict(
            completed_walks="Recorridos completados",
            mean_duration_s="Tiempo medio (s)",
            mean_speed_mps="Media de velocidades individuales (m/s)",
            mean_time_loss_s="Tiempo perdido medio (s)",
            mean_route_length_m="Distancia media (m)",
        )
        for key, name in [("total", "Ambos sentidos"), ("ab", "A → B"), ("ba", "B → A")]:
            parts += [
                "\\subsubsection*{" + tex_escape(name) + "}\n",
                _table([(labels[k], v) for k, v in run["result"][key].items()]),
            ]
        parts += [_items(run.get("assumptions", []))]
    parts += [
        r"""\section{Reproducibilidad y revisión}
El proyecto \texttt{.wksim} conserva identificación, borradores, entradas y resultados
por caso. Los CSV incluyen los identificadores del tipo de análisis y las unidades en
los nombres de campo; la guía del repositorio define cada columna.
Para repetir una microsimulación se necesitan los mismos parámetros, semilla y versión
del motor. Los resultados numéricos simulados conservados en el proyecto se pueden revisar
sin disponer de los archivos temporales originales.

Antes de tomar decisiones de diseño, el analista debe revisar la representatividad de aforos,
velocidades, ocupaciones, periodos críticos, geometría y población atendida. Un valor por defecto
es un ejemplo editable, no una observación del sitio. Los promedios espaciales no permiten
inferir densidades locales máximas. La ausencia de ocupación tiene densidad cero y espacio
sin valor finito; no se presenta como un espacio cero.

\section{Referencias}
\begin{enumerate}
\item Transportation Research Board. (2022). \emph{Highway Capacity Manual, 7th Edition}.
Capítulo 24: Exhibits 24-1, 24-2 y 24-3; ecuaciones 24-1 a 24-4.
Capítulo 20: ecuaciones 20-76 y 20-82 (caso restringido sin cesión).
\item Rouphail, Hummer, Milazzo y Allen. (1998). \emph{Capacity Analysis of Pedestrian and
Bicycle Facilities}. FHWA-RD-98-107. Tabla 21.
\url{https://www.fhwa.dot.gov/publications/research/safety/pedbike/98107/section3.cfm}
\item Fruin, J. J. (1971). \emph{Pedestrian Planning and Design}.
\item Documento de trabajo aportado:
\emph{Análisis y Metodología Peatonal según el HCM 7ma Edición}.
Los criterios se han contrastado con el manual y las fuentes específicas de cada caso.
\item Eclipse SUMO. Documentación del modelo peatonal y salidas de simulación.
\url{https://eclipse.dev/sumo/docs/Simulation/Pedestrians.html}
\end{enumerate}
\end{document}
"""
    ]
    return "\n".join(parts)


def write_report(state: ProjectState, path: str) -> None:
    from pathlib import Path

    from matplotlib.backends.backend_agg import FigureCanvasAgg

    from walksim.analysis.figures import report_plot
    from walksim.walkway_report import current_result

    target = Path(path)
    assets = {}
    for case in state.walkway.get("cases", []):
        result = current_result(case, "simulation")
        if result is None:
            continue
        folder = target.parent / (target.stem + "_figuras")
        folder.mkdir(exist_ok=True)
        # IDs from user files need not be filesystem-safe; derive names from hashes.
        import hashlib

        name = "walkway_" + hashlib.sha256(case["id"].encode()).hexdigest()[:16] + ".pdf"
        figure = report_plot(result)
        FigureCanvasAgg(figure)
        figure.savefig(folder / name, format="pdf", bbox_inches="tight")
        figure.clear()
        assets[case["id"]] = (Path(folder.name) / name).as_posix()
    atomic_write(target, build_report(state, assets))
