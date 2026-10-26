"""Memoria de senderos compartidos y trazabilidad de BLOS condicionado."""

from walksim.domain.shared import (
    ASSUMPTIONS,
    CHOICES,
    GROUP_LABELS,
    LABELS,
    SUMMARY_LABELS,
    SharedInput,
    active_keys,
    fresh,
)


def sections(study, assets=None):
    from walksim.report import _items, _table, tex_escape

    if not study:
        return ""
    origins = dict(default="Predeterminado", entered="Introducido", observed="Observado", csv="CSV")
    parts = [
        r"\section{Senderos compartidos: peatones y bicicletas}",
        _items(ASSUMPTIONS),
        r"""\subsection{Método de cálculo}
Las tasas de diseño son $q=Q/PHF$ con datos horarios, o $q=4N_{15}$ con conteos
críticos de 15 minutos. Para el peatón representativo de cada sentido,
$F_p=q_{b,s}(1-S_p/S_b)$, $F_m=q_{b,o}(1+S_p/S_b)$ y $F=F_p+0.5F_m$ en eventos/h.
HCM 7, Ecuaciones 24-5 a 24-7 y Exhibit 24-4: los límites superiores de A, B, C, D, E
son 38, 60, 103, 144 y 180 eventos/h. F supera 180. No se asigna PLOS a un sentido sin peatones.

Para BLOS, con ciclista representativo de velocidad $U$, velocidad modal normal
$V_i$ de media $\mu_i$ y desviación $\sigma_i$, se integran las probabilidades
$P(V_i<U(1-x/L))$ para rebases y $P(V_i>UX/L)$ para encuentros adicionales.
Se usa trapecio con segmentos no mayores que 0.01 mi (16.09344 m), aplicado a
peatones y bicicletas; los otros tres grupos del procedimiento HCM se suponen nulos.
La tasa activa por modo es $A_i=(q_i/\mu_i)\int P_i(x)dx/t$ con unidades consistentes.
$M_1=(U/60)\sum_i(q_{o,i}/\mu_i)$ y $M_2$ integra los usuarios opuestos externos,
con $X$ de cero a $L$. $A_T=\sum A_i$ y $M_T=M_1+\sum M_{2,i}$.
Las velocidades del cociente se expresan en las mismas unidades; los resultados
son eventos por ciclista y minuto. Con desviación cero se integra la distribución determinista.

En esta implementación, los pasos de bloqueo estimado por carriles se sustituyen
por una probabilidad $P_T$ documentada de campo: $P_T=n_{demorados}/n_{intentos}$,
o una probabilidad introducida con sustento. Una muestra de cero intentos no
permite inferir probabilidad nula. No se presupone la probabilidad cuando faltan datos.
Esta variante debe identificarse como BLOS condicionado a la observación, y no
como estimación automática completa de bloqueo por carriles del HCM.

$DP_m=A_T P_T PHF$, $DP=\min(0.5DP_m,1.5)$,
$E=M_T+10A_T$, $RW=0.3048/W_m$ y
$BLOS=5.446-0.00809E-15.86RW-0.287CL-DP$.
Se conserva la corrección PHF de calibración de DPm incluso con conteos de 15 min.
El ancho admitido para BLOS es 8--20 ft. Exhibit 24-5 usa límites inferiores
estrictos 4.0, 3.5, 3.0, 2.5 y 2.0 para A--E; F es menor o igual a 2.0.
Si $E\leq5$ se asigna A; si $5<E\leq10$ se asigna B salvo que el score ya produzca A.
El ajuste no altera el score original. PLOS y BLOS evalúan experiencia de circulación,
no capacidad garantizada, seguridad vial ni cumplimiento de accesibilidad.

Las bicicletas son vehículos SUMO con IDM y subcarriles; los peatones usan striping.
La sección contiene dos mitades direccionales compartidas por ambos modos. La
línea central sólo modifica la regresión, no prohíbe el rebase en la microsimulación.
Los eventos observados invierten el orden longitudinal de dos usuarios entre muestras
de 0.5 s; se cuentan una vez por par. La referencia de bicicleta se corrige del frente
al centro con longitud 1.6 m. Las tasas por observador dividen incidencias entre
exposición observada en usuario segundos; no se clasifican como LOS simulado.

\textbf{Fuentes:} HCM 7, capítulo 24, páginas 24-5 y 24-15--26; FHWA-HRT-05-137 y
FHWA-HRT-05-138 para el origen del método; documentación oficial SUMO Bicycles,
Pedestrians, Sublane y Opposite Direction Driving. CROW se limita a interpretación
cualitativa de convivencia y alternativas; no se implementa su diseño integral de redes.
""",
    ]
    compare = []
    for c in study["cases"]:
        a = c["analytical"] if fresh(c, "analytical") else None
        text = "Borrador o datos modificados"
        if a:
            text = "; ".join(
                r["direction"]
                + ": PLOS "
                + str(r["pedestrian"]["los"] if r["pedestrian"] else "N/A")
                + ", BLOS "
                + str(r["bicycle"]["los"] if r["bicycle"] else "N/A")
                for r in a["directions"]
            )
        compare.append((c["name"], text))
    parts += [r"\subsection{Alternativas}", _table(compare)]
    for c in study["cases"]:
        parts.append("\\subsection{" + tex_escape(c["name"]) + "}")
        a = c["analytical"] if fresh(c, "analytical") else None
        s = c["simulation"] if fresh(c, "simulation") else None
        if not a:
            parts.append("Datos modificados o incompletos: se excluyen sus resultados anteriores.")
            continue
        x = SharedInput.parse(c["inputs"])
        rows = []
        for k in active_keys(x):
            v = a["inputs"][k]
            if k in CHOICES:
                v = next(label for label, value in CHOICES[k] if value == v)
            rows.append(
                (
                    LABELS[k],
                    str(v if v != "" else "Sin dato") + " [" + origins[c["origins"][k]] + "]",
                )
            )
        parts += [
            r"\subsubsection*{Entradas y procedencia}",
            _table(rows),
            r"\subsubsection*{Flujos de diseño}",
            _table([(GROUP_LABELS[k] + " (usuarios/h)", v) for k, v in a["flows"].items()]),
        ]
        for r in a["directions"]:
            parts.append("\\paragraph{Sentido " + r["direction"] + "}")
            p, b = r["pedestrian"], r["bicycle"]
            if p:
                parts.append(
                    _table(
                        [
                            ("PLOS", p["los"]),
                            ("Rebases por peatón h", p["passing_h"]),
                            ("Encuentros por peatón h", p["meeting_h"]),
                            ("Tasa ponderada por peatón h", p["weighted_h"]),
                        ]
                    )
                )
            if b:
                parts.append(
                    _table(
                        [
                            ("BLOS condicionado", b["los"]),
                            ("Score BLOS", b["score"]),
                            ("Clasificación sin ajuste por bajo volumen", b["raw_los"]),
                            ("Rebases activos por ciclista min", b["active_min"]),
                            ("Encuentros por ciclista min", b["meetings_min"]),
                            ("Tasa ponderada por ciclista min", b["weighted_min"]),
                            ("Probabilidad documentada de demora", b["probability_delay"]),
                            ("DPm (por ciclista min)", b["delayed_min"]),
                            ("Factor DP", b["delay_factor"]),
                        ]
                    )
                )
                if b["reason"]:
                    parts.append(tex_escape(b["reason"]))
        if a["warnings"]:
            parts.append(_items(a["warnings"]))
        if not s:
            continue
        parts += [
            r"\subsubsection*{Microsimulación}",
            _table(
                [
                    ("Motor", s["engine_version"]),
                    ("Modelo", s["model"]),
                    ("Fecha UTC", s["created_at"]),
                    ("Muestreo (s)", s["sample_s"]),
                ]
            ),
            _table([(SUMMARY_LABELS[k], v) for k, v in s["summary"].items()]),
        ]
        for g, row in s["groups"].items():
            parts.append("\\paragraph{" + tex_escape(GROUP_LABELS[g]) + "}")
            parts.append(
                _table(
                    [
                        ("Generados", row["generated"]),
                        ("Completados", row["completed"]),
                        ("Completados de cohorte", row["cohort_completed"]),
                        ("Tiempo medio de cohorte (s)", row["mean_trip_s"]),
                        ("P95 (s)", row["p95_trip_s"]),
                        ("Velocidad espacial (m/s)", row["speed_mps"]),
                        ("Tiempo perdido medio (s)", row["mean_loss_s"]),
                        ("Exposición observada (usuario s)", s["incidence"][g]["exposure_s"]),
                        (
                            "Tasa ponderada observada ("
                            + ("por peatón h" if g.startswith("P") else "por ciclista min")
                            + ")",
                            s["incidence"][g]["weighted_rate"],
                        ),
                    ]
                )
            )
        key = "shared:" + c["id"]
        if assets and key in assets:
            parts.append(
                "\\begin{figure}[htbp]\\centering\n\\includegraphics[width=\\linewidth]{\\detokenize{"
                + assets[key]
                + "}}\n\\caption{"
                + tex_escape(c["name"] + " · ocupación y eventos")
                + "}\\end{figure}"
            )
        if s["warnings"]:
            parts.append(_items(s["warnings"]))
    return "\n".join(parts)
