"""Espacio de trabajo de accesos y colas; reutiliza controles del workbench Walkway."""

from __future__ import annotations

import copy
import logging
from html import escape

from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QBoxLayout,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from walksim.access_io import import_cases, template
from walksim.access_labels import STAGE_LABELS, SUMMARY_LABELS
from walksim.analysis.access_figures import draw_access
from walksim.domain.access import (
    ASSUMPTIONS,
    CHOICES,
    LABELS,
    AccessInput,
    active_keys,
    evaluate_access,
    fresh,
    new_case,
)
from walksim.report import display
from walksim.sumo.access import run_access_simulation
from walksim.ui.walkway_widget import ORIGINS, StableCanvas, WalkwayWidget


class AccessWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, raw, parent):
        super().__init__(parent)
        self.raw = copy.deepcopy(raw)

    def run(self):
        try:
            self.succeeded.emit(run_access_simulation(self.raw))
        except Exception as exc:
            logging.getLogger(__name__).exception("No se pudo simular el acceso")
            self.failed.emit(str(exc))


class AccessWidget(WalkwayWidget):
    fresh = staticmethod(fresh)

    def __init__(self):
        QWidget.__init__(self)
        self.export_stem = "accesos"
        self.cases = [new_case()]
        self.selected_id = self.cases[0]["id"]
        self._loading, self.dark, self.worker, self._last_plot = True, False, None, None
        self.fields, self.form_rows = {}, {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        for text, style in [
            ("ACCESS & QUEUE  /  CAPACIDAD Y ESPERA", "eyebrow"),
            ("Accesos y colas", "workTitle"),
            (
                "Compare dispositivos, descargas y alternativas de una estación sencilla.",
                "pageSubtitle",
            ),
        ]:
            label = QLabel(text)
            label.setObjectName(style)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.case_bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.case_selector = QComboBox()
        self.case_selector.setMinimumContentsLength(10)
        self.case_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.case_selector.currentIndexChanged.connect(self.select_case)
        self.case_bar.addWidget(self.case_selector, 1)
        for key, text, handler in [
            ("duplicate", "Duplicar escenario", self.duplicate_case),
            ("rename", "Renombrar", self.rename_case),
            ("delete", "Eliminar", self.delete_case),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            setattr(self, key + "_button", b)
            self.case_bar.addWidget(b)
        self.more_button = QPushButton("Opciones")
        menu = QMenu(self.more_button)
        menu.addAction("Renombrar escenario", self.rename_case)
        menu.addAction("Eliminar escenario", self.delete_case)
        self.more_button.setMenu(menu)
        self.case_bar.addWidget(self.more_button)
        layout.addLayout(self.case_bar)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.form_page = self._build_form()
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(280)
        scroll.setWidget(self.form_page)
        self.splitter.addWidget(scroll)
        self.results = self._build_results()
        self.splitter.addWidget(self.results)
        self.splitter.setSizes([380, 760])
        layout.addWidget(self.splitter, 1)
        self._refresh_selector()
        self._load_current()
        self._loading = False

    def _row(self, form, key):
        if key in CHOICES:
            self._combo(key, CHOICES[key])
        else:
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
        groups = [
            (
                "01  ·  Instalación y demanda",
                ["layout", "device", "arrival", "rate_pph", "passengers", "cycle_s", "release_s"],
            ),
            (
                "02  ·  Atención",
                ["devices", "service_basis", "service_s", "service_pph", "service"],
            ),
            (
                "03  ·  Recorridos y área de espera",
                [
                    "approach_m",
                    "exit_m",
                    "width_m",
                    "speed_mps",
                    "waiting_length_m",
                    "waiting_width_m",
                ],
            ),
            (
                "04  ·  Metro · capacidad equivalente",
                ["transfer_m", "stairs", "stair_pph", "platform_m2"],
            ),
            (
                "05  ·  Periodos y reproducibilidad",
                ["duration_s", "warmup_s", "clearance_s", "bin_s", "seed"],
            ),
        ]
        for title, keys in groups:
            box = QGroupBox(title)
            form = self._form(box)
            for key in keys:
                self._row(form, key)
            if "stairs" in keys:
                self.metro_box = box
            layout.addWidget(box)
        note = QLabel(
            "Las capacidades iniciales son ejemplos editables. Sustitúyalas por datos "
            "observados o valores sustentados para su instalación."
        )
        note.setObjectName("pageSubtitle")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.origin = QComboBox()
        self.origin.addItem("Dato introducido por el analista", "entered")
        self.origin.addItem("Dato observado en campo", "observed")
        layout.addWidget(self.origin)
        buttons = QGridLayout()
        for i, (text, handler) in enumerate(
            [
                ("Calcular capacidad", self.calculate),
                ("Simular mis datos", self.simulate),
                ("Importar CSV", self.import_csv),
                ("Plantilla CSV", self.template_csv),
            ]
        ):
            b = QPushButton(text)
            b.clicked.connect(handler)
            if i < 2:
                buttons.addWidget(b, i, 0, 1, 2)
                if i == 1:
                    b.setObjectName("primaryButton")
            else:
                buttons.addWidget(b, 2, i - 2)
        layout.addLayout(buttons)
        layout.addStretch()
        return page

    def _build_results(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 0, 0, 0)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("infoBanner")
        layout.addWidget(self.status)
        grid = QGridLayout()
        self.cards = {}
        for i, (key, text) in enumerate(
            [
                ("capacity", "CAPACIDAD DE SERVICIO"),
                ("ratio", "DEMANDA / CAPACIDAD"),
                ("wait", "ESPERA MEDIA"),
                ("pending", "PENDIENTES"),
            ]
        ):
            frame = QFrame()
            frame.setObjectName("metricCard")
            cl = QVBoxLayout(frame)
            label = QLabel(text)
            label.setWordWrap(True)
            label.setObjectName("metricLabel")
            value = QLabel("—")
            value.setObjectName("metricValue")
            cl.addWidget(label)
            cl.addWidget(value)
            grid.addWidget(frame, i // 2, i % 2)
            self.cards[key] = value
        layout.addLayout(grid)
        self.output_tabs = QTabWidget()
        self.output_tabs.setUsesScrollButtons(True)
        self.output_tabs.tabBar().setExpanding(False)
        self.overview = QTextBrowser()
        self.output_tabs.addTab(self.overview, "Resultados")
        comparison = QWidget()
        cl = QVBoxLayout(comparison)
        self.comparison_note = QLabel("Compare alternativas con igual demanda, periodos y semilla.")
        self.comparison_note.setWordWrap(True)
        cl.addWidget(self.comparison_note)
        for text, handler in [
            ("Calcular capacidades de todos los casos", self.compare_all),
            ("Exportar comparación CSV", self.export_comparison),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            cl.addWidget(b)
        self.compare_table = QTableWidget()
        self._configure_table(self.compare_table)
        cl.addWidget(self.compare_table)
        self.output_tabs.addTab(comparison, "Comparar")
        charts = QWidget()
        gl = QVBoxLayout(charts)
        self.figure = Figure(figsize=(8, 5))
        self.canvas = StableCanvas(self.figure)
        self.canvas.setMinimumHeight(320)
        gl.addWidget(self.canvas, 1)
        exports = QHBoxLayout()
        for text, handler in [
            ("Guardar gráfica", self.export_plot),
            ("Exportar series CSV", self.export_series),
        ]:
            b = QPushButton(text)
            b.clicked.connect(handler)
            exports.addWidget(b)
        gl.addLayout(exports)
        self.output_tabs.addTab(charts, "Gráficas")
        self.memory = QTextBrowser()
        self.output_tabs.addTab(self.memory, "Método y datos")
        layout.addWidget(self.output_tabs, 1)
        return page

    def _edited(self, key):
        if self._loading:
            return
        entry = self.fields[key]
        value = entry.currentData() if isinstance(entry, QComboBox) else entry.text()
        self.current["inputs"][key] = value
        self.current["origins"][key] = self.origin.currentData()
        if key == "layout" and value == "metro_exit":
            arrival = self.fields["arrival"]
            arrival.blockSignals(True)
            arrival.setCurrentIndex(arrival.findData("batch"))
            arrival.blockSignals(False)
            self.current["inputs"]["arrival"] = "batch"
            self.current["origins"]["arrival"] = "entered"
        self._visibility()
        self.render()
        self.changed.emit()

    def _visibility(self):
        raw = self.current["inputs"]
        # Only enums are needed to select relevant rows; incomplete numeric drafts are preserved.
        x = AccessInput(**{k: raw[k] for k in CHOICES})
        active = set(active_keys(x))
        for key, form in self.form_rows.items():
            form.setRowVisible(self.fields[key], key in active)
        self.metro_box.setVisible(x.layout != "access")

    def rename_case(self, *_args):
        name, ok = QInputDialog.getText(
            self, "Renombrar escenario", "Nombre:", text=self.current["name"]
        )
        if ok and name.strip():
            self.current["name"] = name.strip()[:200]
            self._refresh_selector()
            self.render()
            self.changed.emit()

    def calculate(self, *_args):
        try:
            a = evaluate_access(self.current["inputs"])
        except ValueError as exc:
            QMessageBox.warning(self, "Datos del acceso", str(exc))
            return False
        self.current["analytical"] = a
        self.render()
        self.changed.emit()
        return True

    def compare_all(self, *_args):
        try:
            calculated = [evaluate_access(c["inputs"]) for c in self.cases]
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
            self, "Duplicar escenario", "Nombre:", text=f"Alternativa {len(self.cases)}"
        )
        if ok and name.strip():
            case = new_case(name.strip()[:200], self.current["inputs"])
            case["origins"] = copy.deepcopy(self.current["origins"])
            self.cases.append(case)
            self.selected_id = case["id"]
            self._refresh_selector()
            self._load_current()
            self.changed.emit()

    def simulate(self, *_args):
        if self.worker or not self.calculate():
            return
        self._running_id = self.selected_id
        self.worker = AccessWorker(self.current["inputs"], self)
        self.worker.succeeded.connect(self._simulated)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.status.setText("Simulando recorridos y atención del escenario seleccionado…")
        self.setEnabled(False)
        self.busyChanged.emit(True)
        self.worker.start()

    def _failed(self, detail):
        self.status.setText(
            "Simulación sin completar. Puede corregir los datos y volver a ejecutar."
        )
        QMessageBox.warning(self, "Accesos y colas", detail)

    def render(self):
        c = self.current
        a = c["analytical"] if fresh(c, "analytical") else None
        s = c["simulation"] if fresh(c, "simulation") else None
        self.status.setText(
            "Resultados actuales · " + c["name"]
            if a
            else "Configure sus datos y calcule la capacidad. Simule para obtener las colas."
        )
        for card in self.cards.values():
            card.setText("—")
        body = (
            "<h2>Del acceso a la espera</h2><p>Elija una instalación y un patrón de llegada. "
            "La capacidad se calcula de inmediato; la simulación produce tiempos y colas.</p>"
        )
        if a:
            capacity = a["metrics"]["Capacidad de servicio (peat/h)"]
            ratio = a["metrics"]["Demanda / capacidad"]
            self.cards["capacity"].setText(f"{capacity:,.0f} peat/h" if capacity else "Libre")
            self.cards["ratio"].setText(f"{ratio:.2f}" if ratio is not None else "N/A")
            body = "<h3>Capacidad analítica</h3>" + self._html_table(a["metrics"].items())
            if a["reference"]:
                r = a["reference"]
                body += "<h3>Referencia estacionaria M/M/c</h3>" + self._html_table(
                    [
                        ("Probabilidad de espera", r["probability_wait"]),
                        ("Espera media (s)", r["mean_wait_s"]),
                        ("Cola media", r["mean_queue"]),
                    ]
                )
        if s:
            summary = s["summary"]
            wait = summary["mean_wait_s"]
            self.cards["wait"].setText(f"{wait:.1f} s" if wait is not None else "N/A")
            self.cards["pending"].setText(str(summary["pending"]))
            body += "<h3>Simulación híbrida</h3>" + self._html_table(
                [(SUMMARY_LABELS[k], v) for k, v in summary.items()]
            )
            for stage in s["stages"]:
                body += (
                    "<h3>"
                    + escape(stage["label"])
                    + "</h3>"
                    + self._html_table([(label, stage[k]) for k, label in STAGE_LABELS.items()])
                )
            if s["train_residuals"]:
                body += "<h3>Personas aún en el sistema antes de la siguiente descarga</h3>"
                body += self._html_table(
                    [(f"Instante {r['time_s']:g} s", r["remaining"]) for r in s["train_residuals"]]
                )
        notes = s["warnings"] if s else a["warnings"] if a else []
        body += "<ul>" + "".join("<li>" + escape(n) + "</li>" for n in notes) + "</ul>"
        self.overview.setHtml(body)
        self.memory.setHtml(
            "<h3>Modelo y alcance</h3><ul>"
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
            "Capacidad (peat/h)",
            "Demanda / capacidad",
            "Espera media (s)",
            "P95 (s)",
            "Cola máxima (peat)",
            "Pendientes",
            "Despeje (s)",
        ]
        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setHorizontalHeaderLabels(headers)
        self.compare_table.setRowCount(len(self.cases))
        for i, case in enumerate(self.cases):
            ca = case["analytical"] if fresh(case, "analytical") else None
            cs = case["simulation"] if fresh(case, "simulation") else None
            m, sm = ca["metrics"] if ca else {}, cs["summary"] if cs else {}
            values = [
                case["name"],
                m.get("Capacidad de servicio (peat/h)"),
                m.get("Demanda / capacidad"),
                sm.get("mean_wait_s"),
                sm.get("p95_wait_s"),
                max((st["max_queue"] for st in cs["stages"]), default=0) if cs else None,
                sm.get("pending"),
                sm.get("clearance_s"),
            ]
            for j, v in enumerate(values):
                self.compare_table.setItem(
                    i, j, QTableWidgetItem("N/A" if v is None else display(v))
                )
        plot_key = (id(s), self.dark)
        if self._last_plot != plot_key:
            draw_access(self.figure, s, self.dark)
            self.canvas.draw_idle()
            self._last_plot = plot_key

    def export_state(self):
        return copy.deepcopy(dict(cases=self.cases, selected_id=self.selected_id))

    def restore(self, study):
        self.cases = copy.deepcopy(study["cases"]) if study else [new_case()]
        self.selected_id = study["selected_id"] if study else self.cases[0]["id"]
        self._refresh_selector()
        self._load_current()

    def import_csv(self, *_args):
        path, _ = QFileDialog.getOpenFileName(self, "Importar accesos", "", "CSV (*.csv)")
        if not path:
            return
        try:
            cases = import_cases(path)
            if len(self.cases) + len(cases) > 30:
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
            self, "Plantilla del acceso actual", "accesos.csv", "CSV (*.csv)"
        )
        if path:
            try:
                template(path, self.current["inputs"])
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Plantilla", str(exc))
