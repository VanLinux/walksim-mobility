"""Memoria de cálculo y resultados de accesos en el informe LaTeX."""

from walksim.access_labels import STAGE_LABELS, SUMMARY_LABELS
from walksim.domain.access import ASSUMPTIONS, CHOICES, LABELS, AccessInput, active_keys, fresh


def sections(study, assets=None):
    from walksim.report import _items, _table, display, tex_escape

    if not study:
        return ""

    def notes(items):
        return _items(items) if items else ""

    origin = dict(default="Predeterminado", entered="Introducido", observed="Observado", csv="CSV")
    parts = [
        r"\section{Accesos y colas: capacidad, atención y descarga de pasajeros}",
        notes(ASSUMPTIONS),
        r"""\subsection{Método de cálculo}
Para $c$ dispositivos y tiempo medio $s$ en segundos por peatón,
$\mu=3600/s$ peat/h por dispositivo y $C=c\mu$. En serie, la capacidad nominal
es $C_{\mathrm{serie}}=\min_j C_j$. La relación de demanda y capacidad es
$\rho=\lambda/C$; cuando $\rho\geq1$ no hay equilibrio estacionario estable.
Para descargas de $P$ personas cada $H$ segundos, $\lambda=3600P/H$ y la reserva
nominal por intervalo es $CH/3600-P$. Esta reserva no garantiza despejar cada tren.

Cada estación usa una fila común por orden de llegada. Si el siguiente servidor
queda libre en $f$, la atención empieza en $b_i=\max(a_i,f)$, termina en
$e_i=b_i+s_i$ y la espera es $w_i=b_i-a_i$. Los tiempos $s_i$ son constantes
o exponenciales según la distribución elegida. La cola instantánea cuenta
$a_i\leq t<b_i$ y la acumulación del área cuenta $a_i\leq t<e_i$.
Las medias temporales integran exactamente estos intervalos; los máximos agrupan
eventos simultáneos. La densidad divide acumulación entre área equivalente.

La cohorte se define por generación dentro del periodo observado, sin calentamiento.
La espera total suma las esperas de las estaciones para quienes completaron todo el
recorrido al límite de despeje. Por estación la muestra incluye llegadas durante el
periodo observado que iniciaron servicio antes de ese límite. Los pendientes pueden
sesgar las estadísticas de los atendidos. Los percentiles usan interpolación lineal.
El despeje adicional se mide desde el final de observación hasta la última salida;
se presenta N/A si no terminó toda la demanda. No se generan personas durante el despeje.

La referencia M/M/c se calcula sólo para un acceso Poisson con servicio exponencial
estable. Con $A=\lambda/\mu$, se usa la recurrencia de Erlang B,
$B_0=1$, $B_n=AB_{n-1}/(n+AB_{n-1})$, seguida de
$P(W>0)=B_c/(1-\rho+\rho B_c)$,
$W_q=P(W>0)s/[c(1-\rho)]$ y $L_q=\lambda W_q/3600$.
No se exige igualdad con una simulación finita que incluye aproximaciones peatonales.

\textbf{Referencias:} documentación oficial Eclipse SUMO, Pedestrians y TripInfo;
documentación de GNU Octave Queueing, función erlangc; MIT OpenCourseWare,
15.072J Queues: Theory and Applications. Las capacidades de dispositivos son
entradas del analista, no valores normativos asignados por el software.
""",
    ]
    comparison = []
    for case in study["cases"]:
        a = case["analytical"] if fresh(case, "analytical") else None
        s = case["simulation"] if fresh(case, "simulation") else None
        text = "Pendiente de cálculo"
        if a:
            text = (
                "Capacidad " + display(a["metrics"]["Capacidad de servicio (peat/h)"]) + " peat/h"
            )
        if s:
            text += (
                "; espera "
                + display(s["summary"]["mean_wait_s"])
                + " s; pendientes "
                + str(s["summary"]["pending"])
            )
        comparison.append((case["name"], text))
    parts += [r"\subsection{Comparación de alternativas}", _table(comparison)]
    for case in study["cases"]:
        parts.append("\\subsection{" + tex_escape(case["name"]) + "}")
        a = case["analytical"] if fresh(case, "analytical") else None
        s = case["simulation"] if fresh(case, "simulation") else None
        if not a:
            parts.append("Borrador o datos modificados: se excluyen sus resultados anteriores.")
            continue
        x = AccessInput.parse(case["inputs"])
        rows = []
        for key in active_keys(x):
            value = a["inputs"][key]
            if key in CHOICES:
                value = next(label for label, val in CHOICES[key] if val == value)
            rows.append((LABELS[key], str(value) + " [" + origin[case["origins"][key]] + "]"))
        parts += [
            r"\subsubsection*{Entradas y procedencia}",
            _table(rows),
            r"\subsubsection*{Capacidad analítica}",
            _table(a["metrics"].items()),
            notes(a["warnings"]),
        ]
        if a["reference"]:
            r = a["reference"]
            parts += [
                r"\paragraph{Referencia M/M/c}",
                _table(
                    [
                        ("Probabilidad de espera", r["probability_wait"]),
                        ("Espera media estacionaria (s)", r["mean_wait_s"]),
                        ("Cola media estacionaria", r["mean_queue"]),
                    ]
                ),
            ]
        if not s:
            continue
        parts += [
            r"\subsubsection*{Simulación híbrida}",
            _table(
                [
                    ("Motor de recorridos", s["engine_version"]),
                    ("Modelo peatonal", "striping"),
                    ("Fecha de ejecución (UTC)", s["created_at"]),
                    ("Semilla", x.seed),
                ]
            ),
            _table([(SUMMARY_LABELS[k], v) for k, v in s["summary"].items()]),
        ]
        for stage in s["stages"]:
            parts += [
                "\\paragraph{" + tex_escape(stage["label"]) + "}",
                _table([(label, stage[k]) for k, label in STAGE_LABELS.items()]),
            ]
        if s["train_residuals"]:
            parts += [
                r"\paragraph{Acumulación antes de nuevas descargas}",
                _table(
                    [
                        ("Instante " + display(r["time_s"]) + " s", r["remaining"])
                        for r in s["train_residuals"]
                    ]
                ),
            ]
        if assets and "access:" + case["id"] in assets:
            path = assets["access:" + case["id"]]
            parts.append(
                "\\begin{figure}[htbp]\\centering\n"
                "\\includegraphics[width=\\linewidth]{\\detokenize{" + path + "}}\n"
                "\\caption{" + tex_escape(case["name"] + " · colas, densidad y espera") + "}"
                "\\end{figure}"
            )
        parts.append(notes(s["warnings"]))
    return "\n".join(parts)
