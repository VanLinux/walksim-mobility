"""Senderos compartidos: análisis de eventos y nivel de servicio por sentido."""

from __future__ import annotations

import copy
import logging
from html import escape

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from walksim.analysis.shared_figures import draw_shared
from walksim.domain.shared import (
    ASSUMPTIONS,
    CHOICES,
    GROUP_LABELS,
    LABELS,
    SUMMARY_LABELS,
    SharedInput,
    active_keys,
    evaluate_shared,
    fresh,
    new_case,
)
from walksim.report import display
from walksim.shared_io import import_cases, template
from walksim.sumo.shared import run_shared_simulation
from walksim.ui.access_widget import AccessWidget
from walksim.ui.walkway_widget import ORIGINS
from walksim.walkway_io import write_rows


class SharedWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, raw, parent):
        super().__init__(parent)
        self.raw = copy.deepcopy(raw)

    def run(self):
        try:
            self.succeeded.emit(run_shared_simulation(self.raw))
        except Exception as exc:
            logging.getLogger(__name__).exception("No se pudo simular el sendero compartido")
            self.failed.emit(str(exc))


class SharedWidget(AccessWidget):
    fresh = staticmethod(fresh)
    case_factory = staticmethod(new_case)
    export_stem = "sendero"
    title = "Senderos compartidos"
    eyebrow = "SHARED PATH  /  PEATONES Y BICICLETAS"
    subtitle = "Evalúe el nivel de servicio por sentido y compare la convivencia de ambos modos."
    compare_label = "Calcular y comparar todos los escenarios"
    metrics = [
        ("plos_ab", "PLOS · A → B"),
        ("plos_ba", "PLOS · B → A"),
        ("blos_ab", "BLOS · A → B"),
        ("blos_ba", "BLOS · B → A"),
    ]

    def _row(self, form, key):
        if key in CHOICES:
            self._combo(key, CHOICES[key])
        else:
            entry = QLineEdit()
            entry.setMinimumWidth(70)
            if key.startswith(("attempts_", "delayed_", "probability_")):
                entry.setPlaceholderText("Sin dato")
            entry.textEdited.connect(lambda _t, k=key: self._edited(k))
            self.fields[key] = entry
        label = QLabel(LABELS[key])
        label.setWordWrap(True)
        form.addRow(label, self.fields[key])
        self.form_rows[key] = form

    def _build_form(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 8, 0)
        for title, keys in [
            ("01 · Análisis y sendero", ["task", "basis", "length_m", "width_m", "centerline"]),
            (
                "02 · Demanda por sentido",
                [
                    "ped_ab",
                    "ped_ba",
                    "bike_ab",
                    "bike_ba",
                    "count_ped_ab",
                    "count_ped_ba",
                    "count_bike_ab",
                    "count_bike_ba",
                    "phf",
                ],
            ),
            ("03 · Velocidades", ["ped_speed", "bike_speed", "ped_sd", "bike_sd"]),
            (
                "04 · Demora documentada de rebases",
                [
                    "delay_source",
                    "attempts_ab",
                    "delayed_ab",
                    "attempts_ba",
                    "delayed_ba",
                    "probability_ab",
                    "probability_ba",
                ],
            ),
            (
                "05 · Microsimulación",
                ["arrival", "duration_s", "warmup_s", "clearance_s", "bin_s", "seed"],
            ),
        ]:
            box = QGroupBox(title)
            form = self._form(box)
            for k in keys:
                self._row(form, k)
            if "delay_source" in keys:
                self.delay_box = box
                note = QLabel(
                    "BLOS necesita la probabilidad de demora. Introduzca una muestra de campo "
                    "o una probabilidad sustentada. Sin ese dato se muestran los eventos "
                    "y BLOS queda N/A."
                )
                note.setWordWrap(True)
                note.setObjectName("pageSubtitle")
                form.addRow(note)
            layout.addWidget(box)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("pageSubtitle")
        layout.addWidget(self.hint)
        self.origin = QComboBox()
        self.origin.addItem("Dato introducido por el analista", "entered")
        self.origin.addItem("Dato observado en campo", "observed")
        layout.addWidget(self.origin)
        controls = QGridLayout()
        for i, (text, handler) in enumerate(
            [
                ("Calcular nivel de servicio", self.calculate),
                ("Simular mis datos", self.simulate),
                ("Importar CSV", self.import_csv),
                ("Plantilla CSV", self.template_csv),
            ]
        ):
            b = QPushButton(text)
            b.clicked.connect(handler)
            if i < 2:
                controls.addWidget(b, i, 0, 1, 2)
                if i == 1:
                    b.setObjectName("primaryButton")
            else:
                controls.addWidget(b, 2, i - 2)
        layout.addLayout(controls)
        layout.addStretch()
        return page

    def _build_results(self):
        page = super()._build_results()
        self.comparison_note.setText(
            "Mantenga unidades, periodos y demanda comparables. "
            "Al cambiar ancho o demanda revise la probabilidad documentada de demora."
        )
        b = QPushButton("Exportar resultados por grupo CSV")
        b.clicked.connect(self.export_groups)
        self.output_tabs.widget(2).layout().addWidget(b)
        return page

    def _visibility(self):
        raw = self.current["inputs"]
        x = SharedInput(**{k: raw[k] for k in CHOICES})
        active = set(active_keys(x))
        for k, form in self.form_rows.items():
            form.setRowVisible(self.fields[k], k in active)
        self.delay_box.setVisible(x.task != "ped")
        self.hint.setText(
            "Conteos de 15 min × 4; PHF sólo corrige DPm de BLOS."
            if x.basis == "count"
            else "Las cuatro demandas horarias se dividen entre PHF una sola vez."
        )

    def _edited(self, key):
        if self._loading:
            return
        entry = self.fields[key]
        self.current["inputs"][key] = (
            entry.currentData() if isinstance(entry, QComboBox) else entry.text()
        )
        self.current["origins"][key] = self.origin.currentData()
        self._visibility()
        self.render()
        self.changed.emit()

    def calculate(self, *_args):
        try:
            a = evaluate_shared(self.current["inputs"])
        except ValueError as exc:
            QMessageBox.warning(self, "Datos del sendero", str(exc))
            return False
        self.current["analytical"] = a
        self.render()
        self.changed.emit()
        return True

    def compare_all(self, *_args):
        try:
            calculated = [evaluate_shared(c["inputs"]) for c in self.cases]
        except ValueError as exc:
            QMessageBox.warning(self, "Comparación", str(exc))
            return
        for c, a in zip(self.cases, calculated, strict=True):
            c["analytical"] = a
        self.render()
        self.output_tabs.setCurrentIndex(1)
        self.changed.emit()

    def duplicate_case(self, *_args):
        if len(self.cases) >= 30:
            QMessageBox.information(self, "Escenarios", "Máximo 30 escenarios por módulo.")
            return
        name, ok = QInputDialog.getText(
            self, "Duplicar sendero", "Nombre:", text=f"Alternativa {len(self.cases)}"
        )
        if ok and name.strip():
            c = new_case(name.strip()[:200], self.current["inputs"])
            c["origins"] = copy.deepcopy(self.current["origins"])
            self.cases.append(c)
            self.selected_id = c["id"]
            self._refresh_selector()
            self._load_current()
            self.changed.emit()

    def simulate(self, *_args):
        if self.worker or not self.calculate():
            return
        self._running_id = self.selected_id
        self.worker = SharedWorker(self.current["inputs"], self)
        self.worker.succeeded.connect(self._simulated)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.status.setText("Simulando peatones y bicicletas en el sendero…")
        self.setEnabled(False)
        self.busyChanged.emit(True)
        self.worker.start()

    def render(self):
        c = self.current
        a = c["analytical"] if fresh(c, "analytical") else None
        s = c["simulation"] if fresh(c, "simulation") else None
        self.status.setText(
            "Resultados actuales · " + c["name"]
            if a
            else "Configure el sendero y calcule los indicadores por sentido."
        )
        for card in self.cards.values():
            card.setText("—")
        body = "<h2>Dos perspectivas del mismo sendero</h2><p>El PLOS mide la experiencia peatonal "
        body += (
            "ante encuentros y rebases ciclistas. El BLOS incorpora eventos, ancho, "
            "línea central y demora documentada.</p>"
        )
        if a:
            body = "<h3>Demanda de diseño</h3>" + self._html_table(
                [(GROUP_LABELS[g] + " (usuarios/h)", v) for g, v in a["flows"].items()]
            )
            for row in a["directions"]:
                d = row["direction"]
                body += "<h3>Sentido " + ("A → B" if d == "AB" else "B → A") + "</h3>"
                p, b = row["pedestrian"], row["bicycle"]
                if p:
                    self.cards["plos_" + d.lower()].setText(p["los"] or "N/A")
                    body += self._html_table(
                        [
                            ("PLOS", p["los"]),
                            ("Rebases por peatón·h", p["passing_h"]),
                            ("Encuentros por peatón·h", p["meeting_h"]),
                            ("Eventos ponderados por peatón·h", p["weighted_h"]),
                        ]
                    )
                if b:
                    self.cards["blos_" + d.lower()].setText(b["los"] or "N/A")
                    body += self._html_table(
                        [
                            ("BLOS condicionado", b["los"]),
                            ("Score BLOS", b["score"]),
                            ("Rebases activos por ciclista·min", b["active_min"]),
                            ("Encuentros por ciclista·min", b["meetings_min"]),
                            ("Eventos ponderados por ciclista·min", b["weighted_min"]),
                            ("Probabilidad de demora", b["probability_delay"]),
                            ("Rebases demorados por ciclista·min", b["delayed_min"]),
                            ("Factor DP", b["delay_factor"]),
                        ]
                    )
                    if b["reason"]:
                        body += "<p>" + escape(b["reason"]) + "</p>"
            body += "<ul>" + "".join("<li>" + escape(n) + "</li>" for n in a["warnings"]) + "</ul>"
        if s:
            body += "<h3>Microsimulación</h3>" + self._html_table(
                [(SUMMARY_LABELS[k], v) for k, v in s["summary"].items()]
            )
            for g, row in s["groups"].items():
                body += (
                    "<h4>"
                    + GROUP_LABELS[g]
                    + "</h4>"
                    + self._html_table(
                        [
                            ("Muestra completada de cohorte", row["cohort_completed"]),
                            ("Tiempo medio (s)", row["mean_trip_s"]),
                            ("P95 (s)", row["p95_trip_s"]),
                            ("Velocidad espacial (m/s)", row["speed_mps"]),
                            ("Exposición observada (usuario·s)", s["incidence"][g]["exposure_s"]),
                            (
                                "Tasa ponderada observada ("
                                + ("por peatón·h" if g.startswith("P") else "por ciclista·min")
                                + ")",
                                s["incidence"][g]["weighted_rate"],
                            ),
                        ]
                    )
                )
            body += "<ul>" + "".join("<li>" + escape(n) + "</li>" for n in s["warnings"]) + "</ul>"
        self.overview.setHtml(body)
        self.memory.setHtml(
            "<h3>Método y alcance</h3><ul>"
            + "".join("<li>" + escape(n) + "</li>" for n in ASSUMPTIONS)
            + "</ul><h3>Datos y procedencia</h3>"
            + self._html_table(
                [
                    (LABELS[k], str(v) + " · " + ORIGINS[c["origins"][k]])
                    for k, v in c["inputs"].items()
                ]
            )
        )
        headers = [
            "Escenario",
            "PLOS AB",
            "PLOS BA",
            "BLOS AB",
            "BLOS BA",
            "Score AB",
            "Score BA",
            "Tiempo peatonal (s)",
            "Tiempo ciclista (s)",
            "Pendientes",
        ]
        rows = []
        for case in self.cases:
            ca = case["analytical"] if fresh(case, "analytical") else None
            cs = case["simulation"] if fresh(case, "simulation") else None
            values = [case["name"]]
            for mode in ["pedestrian", "bicycle"]:
                values += (
                    [r[mode]["los"] if r[mode] else None for r in ca["directions"]]
                    if ca
                    else [None, None]
                )
            values += (
                [r["bicycle"]["score"] if r["bicycle"] else None for r in ca["directions"]]
                if ca
                else [None, None]
            )
            for mode in ["P", "B"]:
                population = (
                    [g for k, g in cs["groups"].items() if k.startswith(mode)] if cs else []
                )
                n = sum(g["cohort_completed"] for g in population)
                values.append(
                    sum(
                        g["mean_trip_s"] * g["cohort_completed"]
                        for g in population
                        if g["mean_trip_s"] is not None
                    )
                    / n
                    if n
                    else None
                )
            values.append(cs["summary"]["pending"] if cs else None)
            rows.append(values)
        from PySide6.QtWidgets import QTableWidgetItem

        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setHorizontalHeaderLabels(headers)
        self.compare_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                self.compare_table.setItem(
                    i, j, QTableWidgetItem("N/A" if v is None else display(v))
                )
        key = (id(a), id(s), self.dark)
        if key != self._last_plot:
            draw_shared(self.figure, a, s, self.dark)
            self.canvas.draw_idle()
            self._last_plot = key

    def restore(self, study):
        self.cases = copy.deepcopy(study["cases"]) if study else [new_case()]
        self.selected_id = study["selected_id"] if study else self.cases[0]["id"]
        self._refresh_selector()
        self._load_current()

    def import_csv(self, *_args):
        path, _ = QFileDialog.getOpenFileName(self, "Importar senderos", "", "CSV (*.csv)")
        if not path:
            return
        try:
            cases = import_cases(path)
            if len(cases) + len(self.cases) > 30:
                raise ValueError("Máximo 30 escenarios por módulo.")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "CSV", str(exc))
            return
        self.cases.extend(cases)
        self.selected_id = cases[0]["id"]
        self._refresh_selector()
        self._load_current()
        self.changed.emit()

    def template_csv(self, *_args):
        path, _ = QFileDialog.getSaveFileName(
            self, "Plantilla de sendero", "sendero.csv", "CSV (*.csv)"
        )
        if path:
            try:
                template(path, self.current["inputs"])
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "CSV", str(exc))

    def export_groups(self):
        if not fresh(self.current, "simulation"):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Resultados por grupo", "grupos_sendero.csv", "CSV (*.csv)"
        )
        if path:
            try:
                s = self.current["simulation"]
                rows = [dict(group=g, **r, **s["incidence"][g]) for g, r in s["groups"].items()]
                write_rows(path, list(rows[0]), rows)
            except OSError as exc:
                QMessageBox.warning(self, "CSV", str(exc))
