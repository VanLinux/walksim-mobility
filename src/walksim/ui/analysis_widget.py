"""Formularios por método, captura manual, lotes CSV y memoria de casos."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from walksim.csv_io import read_csv, write_template
from walksim.domain.analysis import METHODS, calculate
from walksim.report import display


class AnalysisWidget(QWidget):
    changed = Signal()
    simulationImported = Signal(dict)
    simulationRequested = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.drafts: dict[str, dict[str, str]] = {}
        self.names: dict[str, str] = {}
        self.results: list[dict] = []
        self.method = ""
        self.inputs: dict[str, QLineEdit] = {}
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        self.selector = QComboBox()
        self.selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.selector.setMinimumContentsLength(15)
        for key, spec in METHODS.items():
            self.selector.addItem(spec.title, key)
        layout.addWidget(QLabel("Seleccione qué desea analizar:"))
        layout.addWidget(self.selector)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setObjectName("infoBanner")
        layout.addWidget(self.description)
        self.input_box = QGroupBox("Datos necesarios del análisis seleccionado")
        self.form = QFormLayout(self.input_box)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.case_name = QLineEdit()
        self.case_name.setPlaceholderText("Nombre del tramo, horario o escenario")
        self.case_name.textChanged.connect(self._edited)
        self.form.addRow("Nombre del caso:", self.case_name)
        layout.addWidget(self.input_box)
        buttons = QGridLayout()
        self.calculate_button = QPushButton("Calcular y añadir al estudio")
        self.calculate_button.setObjectName("primaryButton")
        self.calculate_button.clicked.connect(self.calculate_current)
        self.import_button = QPushButton("Importar casos CSV")
        self.import_button.clicked.connect(self.import_csv)
        self.template_button = QPushButton("Descargar plantilla CSV")
        self.template_button.clicked.connect(self.download_template)
        self.delete_button = QPushButton("Eliminar caso seleccionado")
        self.delete_button.clicked.connect(self.remove_selected)
        for index, button in enumerate(
            (self.calculate_button, self.import_button, self.template_button, self.delete_button)
        ):
            buttons.addWidget(button, index // 2, index % 2)
        self.prepare_button = QPushButton("Preparar microsimulación del caso seleccionado")
        self.prepare_button.clicked.connect(self.prepare_simulation)
        buttons.addWidget(self.prepare_button, 2, 0, 1, 2)
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Caso", "Análisis", "Evaluación", "Fecha UTC"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(160)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate((220, 280, 160, 210)):
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self.show_selected)
        layout.addWidget(self.table)
        self.output = QTextBrowser()
        self.output.setMinimumHeight(260)
        layout.addWidget(self.output)
        self.selector.currentIndexChanged.connect(self._select_method)
        self._select_method()

    def _store_draft(self) -> None:
        if self.method:
            self.drafts[self.method] = {key: widget.text() for key, widget in self.inputs.items()}
            self.names[self.method] = self.case_name.text()

    def _select_method(self, *_args) -> None:
        self._store_draft()
        self._loading = True
        self.method = self.selector.currentData()
        while self.form.rowCount() > 1:
            self.form.removeRow(1)
        self.inputs = {}
        spec = METHODS[self.method]
        self.description.setText(spec.description)
        self.case_name.setText(self.names.get(self.method, ""))
        raw = self.drafts.get(self.method, {})
        for item in spec.fields:
            entry = QLineEdit(raw.get(item.key, item.default))
            entry.setToolTip(
                f"CSV: {item.key}; unidad: {item.unit or 'sin unidad'}. "
                "Se acepta punto o coma decimal. Sin separador de miles."
            )
            entry.textChanged.connect(self._edited)
            label = f"{item.label} ({item.unit}):" if item.unit else item.label + ":"
            label_widget = QLabel(label)
            label_widget.setWordWrap(True)
            self.form.addRow(label_widget, entry)
            self.inputs[item.key] = entry
        self._loading = False
        self.changed.emit()

    def _edited(self, *_args) -> None:
        if not self._loading:
            self._store_draft()
            self.changed.emit()

    def calculate_current(self) -> None:
        self._store_draft()
        try:
            result = calculate(
                self.method, self.drafts[self.method], self.case_name.text()
            ).to_dict()
        except ValueError as exc:
            QMessageBox.warning(self, "Datos del análisis", str(exc))
            return
        result["data_source"] = "Captura manual"
        self.results.append(result)
        self.refresh_results()
        self.table.selectRow(len(self.results) - 1)
        self.changed.emit()

    def refresh_results(self) -> None:
        self.table.setRowCount(len(self.results))
        for row, result in enumerate(self.results):
            metrics = result["metrics"]
            evaluation = metrics.get(
                "LOS por espacio",
                metrics.get(
                    "Categoría por demora (documento)",
                    display(metrics.get("Demora media por brechas (s/peatón)", "")) + " s",
                ),
            )
            for column, text in enumerate(
                (
                    result["name"],
                    METHODS[result["method"]].title,
                    str(evaluation),
                    result["created_at"],
                )
            ):
                self.table.setItem(row, column, QTableWidgetItem(text))
        if not self.results:
            self.output.setPlainText("Calcule un caso o importe un CSV para ver sus resultados.")

    def show_selected(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.results):
            return
        result = self.results[row]
        metrics = "".join(
            "<tr><td>" + escape(key) + "</td><td><b>" + escape(display(value)) + "</b></td></tr>"
            for key, value in result["metrics"].items()
        )
        notes = "".join("<li>" + escape(item) + "</li>" for item in result["assumptions"])
        steps = "".join("<li>" + escape(item) + "</li>" for item in result["steps"])
        self.output.setHtml(
            "<h2>"
            + escape(result["name"])
            + "</h2><p>"
            + escape(result["criterion"])
            + '</p><table cellpadding="5">'
            + metrics
            + "</table><h3>Desarrollo</h3><ol>"
            + steps
            + "</ol><h3>Supuestos y alcance</h3><ul>"
            + notes
            + "</ul><p>"
            + escape(result["source"])
            + "</p><p>Resultado conservado del caso. "
            "Editar el formulario permite calcular un caso nuevo.</p>"
        )

    def prepare_simulation(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self.results):
            QMessageBox.information(
                self, "Seleccione un caso", "Seleccione un resultado de la tabla."
            )
            return
        result = self.results[row]
        if result["method"] not in ("walkway", "platoon"):
            QMessageBox.information(
                self,
                "Microsimulación de corredor",
                "Seleccione un caso de acera o pelotones con aforo y velocidad. "
                "Los demás análisis emplean sus ecuaciones específicas.",
            )
            return
        self.simulationRequested.emit(result)

    def remove_selected(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.results):
            del self.results[row]
            self.refresh_results()
            if self.results:
                self.table.selectRow(min(row, len(self.results) - 1))
            self.changed.emit()

    def import_csv(self, *_args) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar datos", "", "CSV (*.csv)")
        if path:
            self.import_path(path)

    def import_path(self, path: str) -> bool:
        try:
            method, records = read_csv(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "CSV no importado", str(exc))
            return False
        if method == "simulation":
            self.simulationImported.emit(records[0])
        else:
            self.results.extend(records)
            self.refresh_results()
            self.table.selectRow(len(self.results) - 1)
            self.selector.setCurrentIndex(self.selector.findData(method))
            self._loading = True
            for key, entry in self.inputs.items():
                entry.setText(str(records[-1]["inputs"].get(key, "")))
            self.case_name.setText(records[-1]["name"])
            self._loading = False
            self._store_draft()
        self.changed.emit()
        return True

    def download_template(self, *_args) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Plantilla del análisis seleccionado",
            "plantilla_" + self.method + ".csv",
            "CSV (*.csv)",
        )
        if path:
            try:
                write_template(
                    path if path.lower().endswith(".csv") else path + ".csv", self.method
                )
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "No fue posible exportar", str(exc))

    def restore(self, method: str, drafts: dict, names: dict, results: list) -> None:
        self.method = ""
        self.drafts, self.names, self.results = drafts, names, results
        self.selector.blockSignals(True)
        self.selector.setCurrentIndex(self.selector.findData(method))
        self.selector.blockSignals(False)
        self._select_method()
        self.refresh_results()
        if results:
            self.table.selectRow(len(results) - 1)
