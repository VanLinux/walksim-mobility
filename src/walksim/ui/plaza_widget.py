"""Plazas y flujos cruzados: matriz local editable y mapas derivados de simulación."""

from __future__ import annotations

import copy
import logging
from html import escape

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from walksim.analysis.plaza_figures import draw_plaza
from walksim.domain.plaza import (
    ASSUMPTIONS,
    CHOICES,
    LABELS,
    NAMES,
    PORTS,
    SUMMARY_LABELS,
    VIEWS,
    PlazaInput,
    active_keys,
    evaluate_plaza,
    fresh,
    new_case,
    ports,
)
from walksim.plaza_io import export_matrix, import_cases, import_matrix, template
from walksim.report import display
from walksim.sumo.plaza import run_plaza_simulation
from walksim.ui.access_widget import AccessWidget
from walksim.ui.walkway_widget import ORIGINS
from walksim.walkway_io import write_rows


class PlazaWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, raw, parent):
        super().__init__(parent)
        self.raw = copy.deepcopy(raw)

    def run(self):
        try:
            self.succeeded.emit(run_plaza_simulation(self.raw))
        except Exception as exc:
            logging.getLogger(__name__).exception("No se pudo simular la plaza")
            self.failed.emit(str(exc))


class PlazaWidget(AccessWidget):
    case_factory = staticmethod(new_case)
    fresh = staticmethod(fresh)
    export_stem = "plaza"
    title = "Plazas y flujos cruzados"
    eyebrow = "CROSS-FLOW / PLAZA  ·  DEMANDA LOCAL Y DENSIDAD"
    subtitle = (
        "Defina sus accesos, distribuya los flujos y explore dónde se concentran los peatones."
    )
    compare_label = "Calcular geometría y demanda de todos los casos"
    metrics = [
        ("area", "ÁREA ANALIZADA"),
        ("flow", "DEMANDA OD LOCAL"),
        ("density", "DENSIDAD MEDIA"),
        ("complete", "COMPLETADOS"),
    ]

    def _row(self, form, key):
        # Same controls and validation lifecycle; plaza owns its labels and choices.
        if key in CHOICES:
            self._combo(key, CHOICES[key])
        else:
            from PySide6.QtWidgets import QLineEdit

            entry = QLineEdit()
            entry.setMinimumWidth(70)
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
            (
                "01 · Plantilla y dimensiones",
                ["template", "accesses", "length_m", "height_m", "arm_m", "approach_m"],
            ),
            (
                "02 · Accesos y caminata",
                ["width_n_m", "width_s_m", "width_e_m", "width_w_m", "speed_mps"],
            ),
        ]:
            box = QGroupBox(title)
            form = self._form(box)
            for k in keys:
                self._row(form, k)
            layout.addWidget(box)
        box = QGroupBox("03 · Matriz OD local · peat/h")
        ml = QVBoxLayout(box)
        hint = QLabel(
            "Filas = origen; columnas = destino. Cada valor es una tasa en peat/h. "
            "Las sumas de fila definen el flujo y el reparto de destinos de cada origen."
        )
        hint.setWordWrap(True)
        hint.setObjectName("pageSubtitle")
        ml.addWidget(hint)
        self.matrix = QTableWidget(4, 4)
        self.matrix.setHorizontalHeaderLabels([NAMES[p] for p in PORTS])
        self.matrix.setVerticalHeaderLabels([NAMES[p] for p in PORTS])
        self.matrix.setMinimumHeight(185)
        self.matrix.setAlternatingRowColors(True)
        for i in range(4):
            for j in range(4):
                self.matrix.setItem(i, j, QTableWidgetItem("0"))
        self.matrix.cellChanged.connect(self._matrix_edited)
        ml.addWidget(self.matrix)
        self.matrix_totals = QLabel()
        self.matrix_totals.setWordWrap(True)
        ml.addWidget(self.matrix_totals)
        buttons = QGridLayout()
        for i, (text, handler) in enumerate(
            [
                ("Importar matriz CSV", self.import_matrix_csv),
                ("Exportar matriz CSV", self.export_matrix_csv),
                ("Matriz guía CSV", self.matrix_template),
                ("Vaciar matriz", self.clear_matrix),
            ]
        ):
            b = QPushButton(text)
            b.clicked.connect(handler)
            buttons.addWidget(b, i // 2, i % 2)
        ml.addLayout(buttons)
        layout.addWidget(box)
        box = QGroupBox("04 · Simulación y malla")
        form = self._form(box)
        for k in ["arrival", "duration_s", "warmup_s", "clearance_s", "bin_s", "cell_m", "seed"]:
            self._row(form, k)
        layout.addWidget(box)
        self.origin = QComboBox()
        self.origin.addItem("Dato introducido por el analista", "entered")
        self.origin.addItem("Dato observado en campo", "observed")
        layout.addWidget(self.origin)
        controls = QGridLayout()
        for i, (text, handler) in enumerate(
            [
                ("Calcular geometría y demanda", self.calculate),
                ("Simular mis datos", self.simulate),
                ("Importar escenarios CSV", self.import_csv),
                ("Plantilla de escenarios", self.template_csv),
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
            "Compare casos con igual matriz, periodos, celda y semilla. "
            "Cada microsimulación se ejecuta desde su caso seleccionado."
        )
        self.chart_selector = QComboBox()
        for label, value in VIEWS:
            self.chart_selector.addItem(label, value)
        self.chart_selector.currentIndexChanged.connect(self._chart_changed)
        self.output_tabs.widget(2).layout().insertWidget(0, self.chart_selector)
        extra = QPushButton("Exportar celdas CSV")
        extra.clicked.connect(self.export_cells)
        self.output_tabs.widget(2).layout().addWidget(extra)
        table_page = QWidget()
        tl = QVBoxLayout(table_page)
        note = QLabel(
            "Tiempos y velocidades incluyen accesos y se refieren a la cohorte completada."
        )
        note.setWordWrap(True)
        tl.addWidget(note)
        self.od_table = QTableWidget()
        self._configure_table(self.od_table)
        tl.addWidget(self.od_table)
        export = QPushButton("Exportar resultados OD CSV")
        export.clicked.connect(self.export_od)
        tl.addWidget(export)
        self.output_tabs.insertTab(3, table_page, "Resultados OD")
        return page

    def _load_current(self):
        self._loading = True
        for key, entry in self.fields.items():
            value = self.current["inputs"][key]
            if isinstance(entry, QComboBox):
                entry.setCurrentIndex(entry.findData(value))
            else:
                entry.setText(str(value))
        self._fill_matrix()
        self._visibility()
        self._loading = False
        self.render()

    def _fill_matrix(self):
        self.matrix.blockSignals(True)
        for i, row in enumerate(self.current["inputs"]["od"]):
            for j, v in enumerate(row):
                self.matrix.item(i, j).setText(str(v))
        self.matrix.blockSignals(False)

    def _visibility(self):
        raw = self.current["inputs"]
        x = PlazaInput(**{k: raw[k] for k in CHOICES})
        selected = ports(x)
        active = set(active_keys(x))
        for k, form in self.form_rows.items():
            form.setRowVisible(self.fields[k], k in active)
        for i, p in enumerate(PORTS):
            for j, q in enumerate(PORTS):
                item = self.matrix.item(i, j)
                flags = Qt.ItemFlag.ItemIsSelectable
                if p in selected and q in selected:
                    flags |= Qt.ItemFlag.ItemIsEnabled
                    if i != j:
                        flags |= Qt.ItemFlag.ItemIsEditable
                item.setFlags(flags)

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

    def _matrix_edited(self, i, j):
        if self._loading:
            return
        self.current["inputs"]["od"][i][j] = self.matrix.item(i, j).text()
        self.current["origins"]["od"] = self.origin.currentData()
        self.render()
        self.changed.emit()

    def clear_matrix(self):
        self.current["inputs"]["od"] = [[0.0] * 4 for _ in range(4)]
        self.current["origins"]["od"] = "entered"
        self._fill_matrix()
        self.render()
        self.changed.emit()

    def calculate(self, *_args):
        try:
            a = evaluate_plaza(self.current["inputs"])
        except ValueError as exc:
            QMessageBox.warning(self, "Datos de plaza", str(exc))
            return False
        self.current["analytical"] = a
        self.render()
        self.changed.emit()
        return True

    def compare_all(self, *_args):
        try:
            calculated = [evaluate_plaza(c["inputs"]) for c in self.cases]
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
            self, "Duplicar plaza", "Nombre:", text=f"Alternativa {len(self.cases)}"
        )
        if ok and name.strip():
            c = new_case(name.strip()[:200], copy.deepcopy(self.current["inputs"]))
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
        self.worker = PlazaWorker(self.current["inputs"], self)
        self.worker.succeeded.connect(self._simulated)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.status.setText("Simulando el área común y preparando mapas…")
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
            else "Configure la matriz y calcule la geometría; simule para obtener mapas y tiempos."
        )
        for card in self.cards.values():
            card.setText("—")
        body = (
            "<h2>Un área común, múltiples movimientos</h2><p>Capture las tasas OD "
            "o importe su matriz. "
        )
        body += (
            "El plano muestra la plantilla y los movimientos; al simular "
            "aparecen los mapas de celda.</p>"
        )
        try:
            current = evaluate_plaza(c["inputs"])
            self.matrix_totals.setText(
                " · ".join(
                    NAMES[r["port"]] + f": {r['origin_pph']:g} peat/h" for r in current["accesses"]
                )
            )
        except ValueError:
            self.matrix_totals.setText("Matriz o datos incompletos: puede guardar el borrador.")
        if a:
            self.cards["area"].setText(f"{a['area_m2']:.1f} m²")
            self.cards["flow"].setText(f"{a['total_pph']:,.0f} peat/h")
            body = "<h3>Geometría y demanda</h3>" + self._html_table(
                [
                    ("Área analizada (m²)", a["area_m2"]),
                    ("Demanda total (peat/h)", a["total_pph"]),
                    ("Personas esperadas (incluye calentamiento)", a["expected_people"]),
                ]
            )
            body += "<h3>Flujos por acceso · peat/h</h3>" + self._html_table(
                [
                    (
                        NAMES[r["port"]],
                        f"Origen {r['origin_pph']:g} · Destino {r['destination_pph']:g}",
                    )
                    for r in a["accesses"]
                ]
            )
        if s:
            m = s["summary"]
            self.cards["density"].setText(f"{m['mean_density']:.3f} peat/m²")
            self.cards["complete"].setText(
                f"{m['completed_pct']:.1f} %" if m["completed_pct"] is not None else "N/A"
            )
            body += "<h3>Microsimulación y mapa espacial</h3>" + self._html_table(
                [(SUMMARY_LABELS[k], v) for k, v in m.items()]
            )
            body += "<h3>Celdas con mayor densidad media</h3>" + self._html_table(
                [
                    (
                        f"Celda ({s['cells'][i]['ix'] + 1}, {s['cells'][i]['iy'] + 1})",
                        f"{s['cells'][i]['mean_density']:.3f} peat/m² · "
                        f"área {s['cells'][i]['area_m2']:.2f} m²",
                    )
                    for i in s["critical_cells"]
                ]
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
                    if k != "od"
                ]
            )
        )
        self._table(
            self.compare_table,
            [
                "Escenario",
                "Área (m²)",
                "Demanda (peat/h)",
                "Tiempo medio (s)",
                "Densidad media (peat/m²)",
                "Máximo celda (peat/m²)",
                "Completados (%)",
            ],
            self._comparison_rows(),
        )
        self._table(
            self.od_table,
            [
                "Origen",
                "Destino",
                "Tasa (peat/h)",
                "Generados",
                "Completados",
                "Muestra cohorte",
                "Tiempo medio (s)",
                "P95 (s)",
                "Velocidad espacial (m/s)",
                "Tiempo perdido (s)",
            ],
            [
                [
                    NAMES[r["origin"]],
                    NAMES[r["destination"]],
                    r["rate_pph"],
                    r["generated"],
                    r["completed"],
                    r["cohort_completed"],
                    r["mean_trip_s"],
                    r["p95_trip_s"],
                    r["spatial_speed_mps"],
                    r["mean_loss_s"],
                ]
                for r in s["od"]
            ]
            if s
            else [],
        )
        # Input signature avoids costly redraw while editing unrelated draft text.
        key = (repr(c["inputs"]), id(s), self.dark, self.chart_selector.currentData())
        if key != self._last_plot:
            draw_plaza(self.figure, c["inputs"], s, self.dark, self.chart_selector.currentData())
            self.canvas.draw_idle()
            self._last_plot = key

    def _comparison_rows(self):
        rows = []
        for c in self.cases:
            a = c["analytical"] if fresh(c, "analytical") else None
            s = c["simulation"] if fresh(c, "simulation") else None
            m = s["summary"] if s else {}
            rows.append(
                [
                    c["name"],
                    a["area_m2"] if a else None,
                    a["total_pph"] if a else None,
                    m.get("mean_trip_s"),
                    m.get("mean_density"),
                    m.get("max_cell_density"),
                    m.get("completed_pct"),
                ]
            )
        return rows

    @staticmethod
    def _table(table, headers, rows):
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                table.setItem(i, j, QTableWidgetItem("N/A" if v is None else display(v)))

    def export_state(self):
        return copy.deepcopy(
            dict(
                cases=self.cases,
                selected_id=self.selected_id,
                view=self.chart_selector.currentData(),
            )
        )

    def restore(self, study):
        self.cases = copy.deepcopy(study["cases"]) if study else [new_case()]
        self.selected_id = study["selected_id"] if study else self.cases[0]["id"]
        self.chart_selector.blockSignals(True)
        self.chart_selector.setCurrentIndex(
            self.chart_selector.findData(study.get("view", "mean_density"))
        )
        self.chart_selector.blockSignals(False)
        self._refresh_selector()
        self._load_current()

    def import_csv(self, *_args):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar escenarios de plaza", "", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            cases = import_cases(path)
            if len(self.cases) + len(cases) > 30:
                raise ValueError("Máximo 30 escenarios.")
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
            self, "Escenarios guía", "plaza_escenarios.csv", "CSV (*.csv)"
        )
        if path:
            try:
                template(path, self.current["inputs"])
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "CSV", str(exc))

    def import_matrix_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar matriz OD local", "", "CSV (*.csv)")
        if not path:
            return
        try:
            matrix = import_matrix(path)
            x = PlazaInput.parse({**{k: self.current["inputs"][k] for k in CHOICES}, "od": matrix})
            if x.od != matrix:
                raise ValueError("La matriz tiene demanda en accesos inactivos.")
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Matriz OD", str(exc))
            return
        self.current["inputs"]["od"] = matrix
        self.current["origins"]["od"] = "csv"
        self._fill_matrix()
        self.render()
        self.changed.emit()

    def export_matrix_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar matriz OD", "plaza_od.csv", "CSV (*.csv)"
        )
        if path:
            try:
                export_matrix(
                    path,
                    PlazaInput.parse({k: self.current["inputs"][k] for k in [*CHOICES, "od"]}).od,
                )
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Matriz OD", str(exc))

    def matrix_template(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Matriz guía de los accesos actuales", "plaza_od_guia.csv", "CSV (*.csv)"
        )
        if path:
            try:
                export_matrix(
                    path, PlazaInput.parse({k: self.current["inputs"][k] for k in CHOICES}).od
                )
            except OSError as exc:
                QMessageBox.warning(self, "Matriz OD", str(exc))

    def export_cells(self):
        self._export_data("cells", "celdas_plaza.csv")

    def export_od(self):
        self._export_data("od", "resultados_od_plaza.csv")

    def _export_data(self, key, filename):
        if not fresh(self.current, "simulation"):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resultados", filename, "CSV (*.csv)")
        if path:
            try:
                rows = self.current["simulation"][key]
                if rows:
                    write_rows(path, list(rows[0]), rows)
            except OSError as exc:
                QMessageBox.warning(self, "CSV", str(exc))
