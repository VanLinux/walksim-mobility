"""Espacio de trabajo Walkway: escenarios, diseño, comparación y gráficas."""

from __future__ import annotations

import copy
import logging
from html import escape

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from walksim.analysis.figures import draw_walkway
from walksim.domain.walkway import WalkwayInput, evaluate_walkway, new_case, signature
from walksim.report import display
from walksim.sumo.walkway import run_walkway_simulation
from walksim.ui.walkway_labels import INPUT_LABELS
from walksim.walkway_io import import_cases, input_keys, template, write_rows

MODES = [
    ("Evaluar operación", "operation"),
    ("Diseñar ancho para un LOS", "design_width"),
    ("Calcular demanda admisible", "design_demand"),
]
FLOW_TYPES = [("Aleatorio", "random"), ("Pelotones (5 min)", "platoon")]
BASES = [("Demanda horaria + PHF", "hourly"), ("Conteo directo del periodo crítico", "count")]
ORIGINS = {
    "default": "Predeterminado",
    "entered": "Introducido",
    "observed": "Observado",
    "csv": "CSV",
}
LABELS = dict(
    length_m="Longitud (m)",
    width_m="Ancho total (m)",
    obstacles_m="Descuento por obstáculos (m)",
    edges_m="Descuento por bordes (m)",
    flow_ab_pph="Demanda A → B (peat/h)",
    flow_ba_pph="Demanda B → A (peat/h)",
    count_ab="Conteo A → B (peat)",
    count_ba="Conteo B → A (peat)",
    phf="Factor de hora pico (PHF)",
    speed_mps="Velocidad representativa (m/s)",
    slope_pct="Pendiente (%)",
    margin_pct="Margen de diseño (%)",
    share_ab_pct="Reparto A → B (%)",
    duration_s="Periodo observado (s)",
    warmup_s="Calentamiento (s)",
    bin_s="Intervalo de gráfica (s)",
    seed="Semilla",
    platoon_cycle_s="Intervalo entre pelotones (s)",
    platoon_release_s="Duración de cada descarga (s)",
)


class WalkwayWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, raw: dict, parent: QWidget) -> None:
        super().__init__(parent)
        self.raw = copy.deepcopy(raw)

    def run(self) -> None:
        try:
            self.succeeded.emit(run_walkway_simulation(self.raw))
        except Exception as exc:
            logging.getLogger(__name__).exception("No se pudo simular Walkway")
            self.failed.emit(str(exc))


class StableCanvas(FigureCanvasQTAgg):
    def sizeHint(self):  # noqa: N802
        return QSize(720, 470)

    def minimumSizeHint(self):  # noqa: N802
        return QSize(250, 270)


class WalkwayWidget(QWidget):
    changed = Signal()
    busyChanged = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.cases = [new_case()]
        self.selected_id = self.cases[0]["id"]
        self._loading = True
        self.dark = False
        self.worker = None
        self.fields: dict[str, QWidget] = {}
        self._last_plot = None
        self.form_rows: dict[str, QFormLayout] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)
        eyebrow = QLabel("WALKWAY  /  OPERACIÓN Y DISEÑO")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        title = QLabel("Corredores peatonales")
        title.setObjectName("workTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Evalúe un corredor, dimensione su ancho y compare alternativas en un mismo estudio."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.case_selector = QComboBox()
        self.case_selector.setMinimumContentsLength(12)
        self.case_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.case_selector.currentIndexChanged.connect(self.select_case)
        self.duplicate_button = QPushButton("Duplicar escenario")
        self.duplicate_button.clicked.connect(self.duplicate_case)
        self.rename_button = QPushButton("Renombrar")
        self.rename_button.clicked.connect(self.rename_case)
        self.delete_button = QPushButton("Eliminar")
        self.delete_button.clicked.connect(self.delete_case)
        bar.addWidget(self.case_selector, 1)
        for button in (self.duplicate_button, self.rename_button, self.delete_button):
            bar.addWidget(button)
        self.more_button = QPushButton("Opciones")
        menu = QMenu(self.more_button)
        menu.addAction("Renombrar escenario", self.rename_case)
        menu.addAction("Eliminar escenario", self.delete_case)
        self.more_button.setMenu(menu)
        bar.addWidget(self.more_button)
        self.more_button.hide()
        self.case_bar = bar
        layout.addLayout(bar)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        LABELS.update(INPUT_LABELS)
        self.form_page = self._build_form()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form_page)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(280)
        self.splitter.addWidget(scroll)
        self.results = self._build_results()
        self.splitter.addWidget(self.results)
        self.splitter.setSizes([365, 780])
        layout.addWidget(self.splitter, 1)
        self._refresh_selector()
        self._load_current()
        self._loading = False

    @property
    def current(self) -> dict:
        return next(c for c in self.cases if c["id"] == self.selected_id)

    def _combo(self, key, items):
        combo = QComboBox()
        for title, value in items:
            combo.addItem(title, value)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)
        self.fields[key] = combo
        combo.currentIndexChanged.connect(lambda _i, k=key: self._edited(k))
        return combo

    def _row(self, form, key):
        if key not in self.fields:
            entry = QLineEdit()
            entry.setMinimumWidth(80)
            entry.textEdited.connect(lambda _text, k=key: self._edited(k))
            self.fields[key] = entry
        label = QLabel(LABELS.get(key, key))
        label.setWordWrap(True)
        form.addRow(label, self.fields[key])
        self.form_rows[key] = form

    @staticmethod
    def _form(box):
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return form

    def _build_form(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 8, 0)
        box = QGroupBox("01  ·  Pregunta de ingeniería")
        form = self._form(box)
        form.addRow("Objetivo:", self._combo("mode", MODES))
        form.addRow("Tipo de flujo:", self._combo("flow_type", FLOW_TYPES))
        form.addRow("Demanda:", self._combo("demand_basis", BASES))
        self._combo("target_los", [(f"LOS {c} o mejor", c) for c in "ABCDE"])
        self._row(form, "target_los")
        self._row(form, "margin_pct")
        layout.addWidget(box)
        box = QGroupBox("02  ·  Geometría y velocidad")
        form = self._form(box)
        for key in ("length_m", "width_m", "obstacles_m", "edges_m", "speed_mps", "slope_pct"):
            self._row(form, key)
        layout.addWidget(box)
        box = QGroupBox("03  ·  Demanda del periodo crítico")
        form = self._form(box)
        for key in ("flow_ab_pph", "flow_ba_pph", "phf", "count_ab", "count_ba", "share_ab_pct"):
            self._row(form, key)
        self.period_hint = QLabel()
        self.period_hint.setWordWrap(True)
        form.addRow(self.period_hint)
        layout.addWidget(box)
        toggle = QToolButton()
        toggle.setText("Opciones de microsimulación")
        toggle.setCheckable(True)
        toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toggle.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(toggle)
        self.sim_box = QGroupBox("04  ·  Periodos y llegadas")
        form = self._form(self.sim_box)
        for key in (
            "duration_s",
            "warmup_s",
            "bin_s",
            "seed",
            "platoon_cycle_s",
            "platoon_release_s",
        ):
            self._row(form, key)
        layout.addWidget(self.sim_box)
        self.sim_box.hide()
        toggle.toggled.connect(
            lambda checked: (
                self.sim_box.setVisible(checked),
                toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow),
            )
        )
        source = QGroupBox("Origen de los datos editados")
        form = self._form(source)
        self.origin = QComboBox()
        self.origin.addItem("Introducido por el analista", "entered")
        self.origin.addItem("Observado en campo", "observed")
        form.addRow(self.origin)
        note = QLabel(
            "Los valores iniciales se conservan como predeterminados hasta que se editen."
        )
        note.setWordWrap(True)
        note.setObjectName("pageSubtitle")
        form.addRow(note)
        layout.addWidget(source)
        buttons = QGridLayout()
        self.calculate_button = QPushButton("Calcular escenario")
        self.calculate_button.setObjectName("primaryButton")
        self.calculate_button.clicked.connect(self.calculate)
        self.simulate_button = QPushButton("Ejecutar microsimulación")
        self.simulate_button.clicked.connect(self.simulate)
        self.import_button = QPushButton("Importar CSV")
        self.import_button.clicked.connect(self.import_csv)
        self.template_button = QPushButton("Plantilla CSV")
        self.template_button.clicked.connect(self.template_csv)
        buttons.addWidget(self.calculate_button, 0, 0, 1, 2)
        buttons.addWidget(self.simulate_button, 1, 0, 1, 2)
        buttons.addWidget(self.import_button, 2, 0)
        buttons.addWidget(self.template_button, 2, 1)
        layout.addLayout(buttons)
        layout.addStretch()
        return page

    def _build_results(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 0, 0, 0)
        self.status = QLabel("Configure el escenario y calcule sus indicadores.")
        self.status.setWordWrap(True)
        self.status.setObjectName("infoBanner")
        layout.addWidget(self.status)
        grid = QGridLayout()
        self.cards = {}
        self.card_frames = []
        for i, (key, label) in enumerate(
            [
                ("los", "NIVEL DE SERVICIO"),
                ("width", "ANCHO ÚTIL"),
                ("ratio", "DEMANDA / CAPACIDAD"),
                ("time", "TIEMPO LIBRE"),
            ]
        ):
            frame = QFrame()
            frame.setObjectName("metricCard")
            column = QVBoxLayout(frame)
            title = QLabel(label)
            title.setWordWrap(True)
            title.setObjectName("metricLabel")
            value = QLabel("—")
            value.setObjectName("metricValue")
            column.addWidget(title)
            column.addWidget(value)
            grid.addWidget(frame, i // 2, i % 2)
            self.cards[key] = value
            self.card_frames.append(frame)
        layout.addLayout(grid)
        self.output_tabs = QTabWidget()
        self.output_tabs.setUsesScrollButtons(True)
        self.output_tabs.tabBar().setExpanding(False)
        self.overview = QTextBrowser()
        self.output_tabs.addTab(self.overview, "Resultados")
        compare = QWidget()
        cl = QVBoxLayout(compare)
        update = QPushButton("Calcular y comparar todos los escenarios")
        update.clicked.connect(self.compare_all)
        cl.addWidget(update)
        export_comparison = QPushButton("Exportar comparación CSV")
        export_comparison.clicked.connect(self.export_comparison)
        cl.addWidget(export_comparison)
        self.comparison_note = QLabel()
        self.comparison_note.setWordWrap(True)
        self.comparison_note.setObjectName("pageSubtitle")
        cl.addWidget(self.comparison_note)
        self.compare_table = QTableWidget()
        self._configure_table(self.compare_table)
        cl.addWidget(self.compare_table)
        self.paired = QTableWidget()
        self._configure_table(self.paired)
        self.paired.setMinimumHeight(180)
        cl.addWidget(QLabel("Analítico y microsimulación · escenario seleccionado"))
        cl.addWidget(self.paired)
        self.output_tabs.addTab(compare, "Comparar")
        charts = QWidget()
        gl = QVBoxLayout(charts)
        self.chart_selector = QComboBox()
        self.chart_selector.addItem("Resumen de operación", "overview")
        self.chart_selector.addItem("Velocidad de recorridos finalizados", "speed")
        self.chart_selector.currentIndexChanged.connect(self._chart_changed)
        gl.addWidget(self.chart_selector)
        self.figure = Figure(figsize=(8, 5))
        self.canvas = StableCanvas(self.figure)
        self.canvas.setMinimumHeight(320)
        gl.addWidget(self.canvas, 1)
        exports = QHBoxLayout()
        for label, handler in [
            ("Guardar gráfica", self.export_plot),
            ("Exportar series CSV", self.export_series),
        ]:
            b = QPushButton(label)
            b.clicked.connect(handler)
            exports.addWidget(b)
        gl.addLayout(exports)
        self.output_tabs.addTab(charts, "Gráficas")
        self.memory = QTextBrowser()
        self.output_tabs.addTab(self.memory, "Método y datos")
        layout.addWidget(self.output_tabs, 1)
        return page

    @staticmethod
    def _configure_table(table):
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _refresh_selector(self):
        self.case_selector.blockSignals(True)
        self.case_selector.clear()
        for case in self.cases:
            self.case_selector.addItem(case["name"], case["id"])
        self.case_selector.setCurrentIndex(self.case_selector.findData(self.selected_id))
        self.case_selector.blockSignals(False)

    def _load_current(self):
        self._loading = True
        for key, entry in self.fields.items():
            value = self.current["inputs"][key]
            if isinstance(entry, QComboBox):
                entry.setCurrentIndex(entry.findData(value))
            else:
                entry.setText(str(value))
        self._visibility()
        self._loading = False
        self.render()

    def _edited(self, key):
        if self._loading:
            return
        entry = self.fields[key]
        value = entry.currentData() if isinstance(entry, QComboBox) else entry.text()
        self.current["inputs"][key] = value
        self.current["origins"][key] = self.origin.currentData()
        if key == "flow_type" and value == "platoon":
            basis = self.fields["demand_basis"]
            basis.blockSignals(True)
            basis.setCurrentIndex(basis.findData("count"))
            basis.blockSignals(False)
            self.current["inputs"]["demand_basis"] = "count"
            self.current["origins"]["demand_basis"] = "entered"
        self._visibility()
        self.render()
        self.changed.emit()

    def _visibility(self):
        x = self.current["inputs"]
        design = x["mode"] != "operation"
        for key in ("target_los", "margin_pct"):
            self.form_rows[key].setRowVisible(self.fields[key], design)
        self.form_rows["width_m"].setRowVisible(self.fields["width_m"], x["mode"] != "design_width")
        for key in ("flow_ab_pph", "flow_ba_pph"):
            self.form_rows[key].setRowVisible(
                self.fields[key], x["mode"] != "design_demand" and x["demand_basis"] == "hourly"
            )
        for key in ("count_ab", "count_ba"):
            self.form_rows[key].setRowVisible(
                self.fields[key], x["mode"] != "design_demand" and x["demand_basis"] == "count"
            )
        self.form_rows["phf"].setRowVisible(self.fields["phf"], x["demand_basis"] == "hourly")
        self.form_rows["share_ab_pct"].setRowVisible(
            self.fields["share_ab_pct"], x["mode"] == "design_demand"
        )
        for key in ("platoon_cycle_s", "platoon_release_s"):
            self.form_rows[key].setRowVisible(self.fields[key], x["flow_type"] == "platoon")
        self.period_hint.setText(
            "Conteo directo de 5 min; PHF no aplicado."
            if x["flow_type"] == "platoon"
            else (
                "Conteo de los 15 min más cargados; PHF no aplicado."
                if x["demand_basis"] == "count"
                else "La demanda horaria se divide entre PHF una sola vez."
            )
        )

    def select_case(self, *_args):
        if self.case_selector.currentData():
            self.selected_id = self.case_selector.currentData()
            self._load_current()
            self.changed.emit()

    def duplicate_case(self, *_args):
        if len(self.cases) >= 30:
            QMessageBox.information(self, "Escenarios", "Máximo 30 escenarios por estudio.")
            return
        name, ok = QInputDialog.getText(
            self, "Nueva alternativa", "Nombre:", text=f"Alternativa {len(self.cases)}"
        )
        if not ok or not name.strip():
            return
        case = new_case(name.strip(), copy.deepcopy(self.current["inputs"]))
        case["origins"] = copy.deepcopy(self.current["origins"])
        self.cases.append(case)
        self.selected_id = case["id"]
        self._refresh_selector()
        self._load_current()
        self.changed.emit()

    def rename_case(self, *_args):
        name, ok = QInputDialog.getText(
            self, "Renombrar escenario", "Nombre:", text=self.current["name"]
        )
        if ok and name.strip():
            self.current["name"] = name.strip()
            self._refresh_selector()
            self.render()
            self.changed.emit()

    def delete_case(self, *_args):
        if len(self.cases) == 1:
            return
        if (
            QMessageBox.question(
                self, "Eliminar escenario", "¿Eliminar el escenario seleccionado y sus resultados?"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.cases.remove(self.current)
        self.selected_id = self.cases[0]["id"]
        self._refresh_selector()
        self._load_current()
        self.changed.emit()

    @staticmethod
    def fresh(case, kind):
        try:
            return case.get(kind) and case[kind]["signature"] == signature(case["inputs"])
        except ValueError:
            return False

    def calculate(self, *_args):
        try:
            result = evaluate_walkway(self.current["inputs"])
        except ValueError as exc:
            QMessageBox.warning(self, "Revise los datos", str(exc))
            return False
        self.current["analytical"] = result
        self.render()
        self.changed.emit()
        return True

    def compare_all(self, *_args):
        try:
            calculated = [evaluate_walkway(case["inputs"]) for case in self.cases]
        except ValueError as exc:
            QMessageBox.warning(self, "Comparación", str(exc))
            return
        for case, result in zip(self.cases, calculated, strict=True):
            case["analytical"] = result
        self.render()
        self.output_tabs.setCurrentIndex(1)
        self.changed.emit()

    def simulate(self, *_args):
        if self.worker or not self.calculate():
            return
        self._running_id = self.selected_id
        self.worker = WalkwayWorker(self.current["inputs"], self)
        self.worker.succeeded.connect(self._simulated)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.setEnabled(False)
        self.status.setText("Microsimulación en curso…")
        self.busyChanged.emit(True)
        self.worker.start()

    def _simulated(self, result):
        case = next(c for c in self.cases if c["id"] == self._running_id)
        case["simulation"] = result
        self.render()
        self.changed.emit()

    def _failed(self, _detail):
        self.status.setText("No fue posible completar la microsimulación.")
        QMessageBox.warning(
            self,
            "Microsimulación",
            "Revise los datos y la instalación. El detalle técnico está disponible en la terminal.",
        )

    def _finished(self):
        self.setEnabled(True)
        self.worker.deleteLater()
        self.worker = None
        self.busyChanged.emit(False)

    def render(self):
        case = self.current
        a = case["analytical"] if self.fresh(case, "analytical") else None
        sim = case["simulation"] if self.fresh(case, "simulation") else None
        self.status.setText(
            "Escenario calculado · " + case["name"]
            if a
            else "Datos modificados o sin calcular · calcule para actualizar los resultados."
        )
        for key in self.cards:
            self.cards[key].setText("—")
        if a:
            m = a["metrics"]
            self.cards["los"].setText(m["LOS operativo"])
            self.cards["width"].setText(f"{m['Ancho efectivo evaluado (m)']:.2f} m")
            self.cards["ratio"].setText(f"{m['Relación demanda/capacidad']:.2f}")
            self.cards["time"].setText(f"{m['Tiempo libre nominal (s)']:.1f} s")
            body = "<h3>Evaluación analítica</h3>" + self._html_table(m.items())
            notes = a["warnings"] + [t for t in a["assumptions"]]
            if any(
                case["origins"].get(k) == "default"
                for k in input_keys(WalkwayInput.parse(case["inputs"]))
            ):
                notes.insert(
                    0, "Se conservan valores predeterminados. Revise su origen en Método y datos."
                )
            if sim:
                s = sim["summary"]
                body += "<h3>Microsimulación · periodo observado</h3>" + self._html_table(
                    [
                        ("Peatones generados", s["generated"]),
                        ("Completados de la cohorte", s["cohort_completed"]),
                        ("Pendientes al finalizar el despeje", s["unfinished"] + s["not_started"]),
                        ("Densidad media global (peat/m²)", s["density"]),
                        ("Tiempo medio de la cohorte (s)", sim["directions"]["total"]["mean_s"]),
                    ]
                )
                notes += sim["warnings"]
            self.overview.setHtml(
                body
                + "<h3>Observaciones y supuestos</h3><ul>"
                + "".join("<li>" + escape(n) + "</li>" for n in dict.fromkeys(notes))
                + "</ul>"
            )
        else:
            self.overview.setHtml(
                "<h2>Un estudio, varias alternativas</h2><p>Elija qué desea resolver "
                "y capture los datos del corredor. Calcule el escenario para "
                "obtener su evaluación.</p>"
                "<p>Puede duplicar el escenario Base y modificar un dato para "
                "comparar alternativas.</p>"
            )
        self._render_comparison(sim)
        data = case["inputs"]
        if a:
            data = {k: data[k] for k in input_keys(WalkwayInput.parse(data))}
        provenance = case["origins"]
        self.memory.setHtml(
            "<h3>Datos y procedencia</h3>"
            + self._html_table(
                [
                    (
                        LABELS.get(k, k),
                        str(v)
                        + " · "
                        + ORIGINS.get(provenance.get(k, "default"), "Predeterminado"),
                    )
                    for k, v in data.items()
                ]
            )
            + ("<h3>Fuente y alcance</h3><p>" + escape(a["source"]) + "</p>" if a else "")
            + (
                "<ul>" + "".join("<li>" + escape(t) + "</li>" for t in sim["definitions"]) + "</ul>"
                if sim
                else ""
            )
        )
        plot_key = (id(sim), self.dark, self.chart_selector.currentData())
        if plot_key != self._last_plot:
            draw_walkway(self.figure, sim, self.dark, self.chart_selector.currentData())
            self.canvas.draw_idle()
            self._last_plot = plot_key

    @staticmethod
    def _html_table(rows):
        return (
            '<table width="100%" cellpadding="5">'
            + "".join(
                "<tr><td>"
                + escape(str(k))
                + "</td><td><b>"
                + escape("N/A" if v is None else display(v))
                + "</b></td></tr>"
                for k, v in rows
            )
            + "</table>"
        )

    def _render_comparison(self, sim):
        definitions = {
            tuple(
                str(c["inputs"][k]) for k in ("flow_type", "duration_s", "warmup_s", "demand_basis")
            )
            for c in self.cases
        }
        self.comparison_note.setText(
            "Los escenarios usan distintos periodos o definiciones de demanda; "
            "revise su comparabilidad."
            if len(definitions) > 1
            else "Escenarios con la misma definición de demanda y periodos. "
            "Las microsimulaciones pendientes se muestran como N/A."
        )
        headers = [
            "Escenario",
            "LOS",
            "Ancho útil (m)",
            "v/c",
            "Espacio (m²/peat)",
            "Tiempo libre (s)",
            "Microsim. (s)",
        ]
        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setHorizontalHeaderLabels(headers)
        self.compare_table.setRowCount(len(self.cases))
        for i, case in enumerate(self.cases):
            a = case["analytical"] if self.fresh(case, "analytical") else None
            s = case["simulation"] if self.fresh(case, "simulation") else None
            m = a["metrics"] if a else {}
            values = [
                case["name"],
                m.get("LOS operativo", "Pendiente"),
                m.get("Ancho efectivo evaluado (m)"),
                m.get("Relación demanda/capacidad"),
                m.get("Espacio estimado (m²/peatón)"),
                m.get("Tiempo libre nominal (s)"),
                s["directions"]["total"]["mean_s"] if s else None,
            ]
            for j, value in enumerate(values):
                self.compare_table.setItem(
                    i, j, QTableWidgetItem("N/A" if value is None else display(value))
                )
        rows = sim["comparison"] if sim else []
        self.paired.setColumnCount(4)
        self.paired.setHorizontalHeaderLabels(["Indicador", "Analítico", "Simulado", "Cambio (%)"])
        self.paired.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = [
                row["label"] + " (" + row["unit"] + ")",
                row["analytical"],
                row["simulated"],
                row["delta_pct"],
            ]
            for j, value in enumerate(values):
                self.paired.setItem(
                    i, j, QTableWidgetItem("N/A" if value is None else display(value))
                )

    def _chart_changed(self, *_args):
        self.render()
        self.changed.emit()

    def set_dark(self, dark):
        self.dark = dark
        self.render()

    def export_state(self):
        return copy.deepcopy(
            dict(
                cases=self.cases,
                selected_id=self.selected_id,
                chart=self.chart_selector.currentData(),
            )
        )

    def restore(self, study):
        if study:
            self.cases = copy.deepcopy(study["cases"])
            self.selected_id = study["selected_id"]
        else:
            self.cases = [new_case()]
            self.selected_id = self.cases[0]["id"]
        self.chart_selector.blockSignals(True)
        self.chart_selector.setCurrentIndex(
            self.chart_selector.findData(study.get("chart", "overview"))
        )
        self.chart_selector.blockSignals(False)
        self._refresh_selector()
        self._load_current()

    def import_csv(self, *_args):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar escenarios Walkway", "", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            cases = import_cases(path)
            if len(self.cases) + len(cases) > 30:
                raise ValueError("El estudio admite máximo 30 escenarios.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "CSV no importado", str(exc))
            return
        self.cases.extend(cases)
        self.selected_id = cases[0]["id"]
        self._refresh_selector()
        self._load_current()
        self.changed.emit()

    def template_csv(self, *_args):
        path, _ = QFileDialog.getSaveFileName(
            self, "Plantilla de la tarea actual", "walkway.csv", "CSV (*.csv)"
        )
        if path:
            try:
                template(path, self.current["inputs"])
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Plantilla", str(exc))

    def export_plot(self, *_args):
        if not self.fresh(self.current, "simulation"):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar gráficas", "walkway.png", "PNG (*.png);;PDF (*.pdf)"
        )
        if path:
            try:
                self.figure.savefig(path, dpi=180, facecolor=self.figure.get_facecolor())
            except OSError as exc:
                QMessageBox.warning(self, "Gráfica", str(exc))

    def export_comparison(self, *_args):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar comparación", "comparacion.csv", "CSV (*.csv)"
        )
        if not path:
            return
        headers = [
            self.compare_table.horizontalHeaderItem(i).text()
            for i in range(self.compare_table.columnCount())
        ]
        rows = [
            {header: self.compare_table.item(i, j).text() for j, header in enumerate(headers)}
            for i in range(self.compare_table.rowCount())
        ]
        try:
            write_rows(path, headers, rows)
        except OSError as exc:
            QMessageBox.warning(self, "Comparación", str(exc))

    def export_series(self, *_args):
        if not self.fresh(self.current, "simulation"):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar series", "series_walkway.csv", "CSV (*.csv)"
        )
        if path:
            try:
                series = self.current["simulation"]["series"]
                write_rows(path, list(series[0]), series)
            except OSError as exc:
                QMessageBox.warning(self, "Series", str(exc))

    def adapt(self, width):
        self.case_bar.setDirection(
            QBoxLayout.Direction.TopToBottom if width < 650 else QBoxLayout.Direction.LeftToRight
        )
        self.splitter.setOrientation(
            Qt.Orientation.Vertical if width < 1050 else Qt.Orientation.Horizontal
        )
        if width < 1050:
            self.form_page.setMinimumHeight(850)
            self.results.setMinimumHeight(700)
        else:
            self.form_page.setMinimumHeight(0)
            self.results.setMinimumHeight(560)
        self.rename_button.setVisible(width >= 650)
        self.delete_button.setVisible(width >= 650)
        self.more_button.setVisible(width < 650)
