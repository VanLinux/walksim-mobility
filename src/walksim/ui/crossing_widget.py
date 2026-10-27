"""Cruce semaforizado: datos esenciales, cuatro tarjetas y una alternativa."""

from __future__ import annotations

import copy
import logging
from html import escape

from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from walksim.analysis.crossing_figures import draw_crossing
from walksim.crossing_io import import_cases, template
from walksim.domain.crossing import (
    ASSUMPTIONS,
    LABELS,
    SUMMARY_LABELS,
    evaluate_crossing,
    fresh,
    new_case,
)
from walksim.report import display
from walksim.sumo.crossing import run_crossing_simulation
from walksim.ui.access_widget import AccessWidget
from walksim.ui.walkway_widget import ORIGINS


class CrossingWorker(QThread):
    succeeded = Signal(dict)
    failed = Signal(str)

    def __init__(self, raw, parent):
        super().__init__(parent)
        self.raw = copy.deepcopy(raw)

    def run(self):
        try:
            self.succeeded.emit(run_crossing_simulation(self.raw))
        except Exception as exc:
            logging.getLogger(__name__).exception("No se pudo simular el cruce")
            self.failed.emit(str(exc))


class CrossingDiagram(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(130)
        self.dark = False

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        ink = QColor("#E7E8E9" if self.dark else "#30343B")
        p.fillRect(QRectF(8, 30, w - 16, 70), QColor("#404349" if self.dark else "#E7E9EC"))
        p.setPen(QPen(QColor("#92979F"), 1, Qt.PenStyle.DashLine))
        p.drawLine(12, 65, w - 12, 65)
        for y in range(35, 99, 10):
            p.fillRect(QRectF(w * 0.42, y, w * 0.16, 5), QColor("#B6BEC5"))
        p.setPen(ink)
        p.drawText(QRectF(0, 4, w, 22), Qt.AlignmentFlag.AlignCenter, "Acera A   ↓")
        p.drawText(QRectF(0, 104, w, 22), Qt.AlignmentFlag.AlignCenter, "Acera B   ↑")
        p.drawText(QRectF(14, 34, w * 0.3, 24), Qt.AlignmentFlag.AlignCenter, "→ Vehículos")
        p.drawText(QRectF(w * 0.62, 70, w * 0.32, 24), Qt.AlignmentFlag.AlignCenter, "Vehículos ←")
        p.end()


class CrossingWidget(AccessWidget):
    fresh = staticmethod(fresh)
    case_factory = staticmethod(new_case)
    export_stem = "cruce"
    title = "Cruce semaforizado"
    eyebrow = "CRUCE PEATONAL  /  ESPERA Y OPERACIÓN"
    subtitle = "Un cruce, sus peatones y una alternativa para comparar."
    compare_label = "Actualizar referencias"
    metrics = [
        ("reference", "RECORRIDO DE REFERENCIA"),
        ("wait", "ESPERA MEDIA"),
        ("queue", "COLA MÁXIMA · A / B"),
        ("complete", "CRUZARON / PROGRAMADOS"),
    ]

    def _row(self, form, key):
        entry = QLineEdit()
        entry.setMinimumWidth(70)
        entry.textEdited.connect(lambda _t, k=key: self._edited(k))
        self.fields[key] = entry
        label = QLabel(LABELS[key])
        label.setWordWrap(True)
        form.addRow(label, entry)
        self.form_rows[key] = form

    def _build_form(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 8, 0)
        self.diagram = CrossingDiagram()
        layout.addWidget(self.diagram)
        for title, keys in [
            ("01 · Cruce y peatones", ["length_m", "width_m", "ped_ab", "ped_ba", "speed_mps"]),
            ("02 · Señalización", ["cycle_s", "walk_s", "clearance_s"]),
            ("03 · Vehículos", ["vehicles_ph"]),
        ]:
            box = QGroupBox(title)
            form = self._form(box)
            for key in keys:
                self._row(form, key)
            layout.addWidget(box)
        note = QLabel(
            "El despeje permite terminar a quien ya cruza. No abre nuevas entradas. "
            "La vía se representa con un carril equivalente por sentido a 30 km/h."
        )
        note.setWordWrap(True)
        note.setObjectName("pageSubtitle")
        layout.addWidget(note)
        advanced = QGroupBox("Opciones de simulación")
        advanced.setCheckable(True)
        advanced.setChecked(False)
        self.advanced_body = QWidget()
        form = self._form(self.advanced_body)
        for key in ("duration_s", "seed"):
            self._row(form, key)
        al = QVBoxLayout(advanced)
        al.addWidget(self.advanced_body)
        self.advanced_body.hide()
        advanced.toggled.connect(self.advanced_body.setVisible)
        layout.addWidget(advanced)
        self.origin = QComboBox()
        self.origin.addItem("Dato introducido por el analista", "entered")
        self.origin.addItem("Dato observado en campo", "observed")
        layout.addWidget(self.origin)
        buttons = QGridLayout()
        for i, (text, handler) in enumerate(
            [
                ("Calcular referencia L/v", self.calculate),
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

    def _visibility(self):
        pass

    def _edited(self, key):
        if not self._loading:
            self.current["inputs"][key] = self.fields[key].text()
            self.current["origins"][key] = self.origin.currentData()
            self.render()
            self.changed.emit()

    def duplicate_case(self, *_args):
        if len(self.cases) == 2:
            QMessageBox.information(
                self,
                "Alternativas",
                "Use el caso base y una alternativa. Puede eliminar una para crear otra.",
            )
            return
        c = new_case("Alternativa", self.current["inputs"])
        c["origins"] = copy.deepcopy(self.current["origins"])
        self.cases.append(c)
        self.selected_id = c["id"]
        self._refresh_selector()
        self._load_current()
        self.changed.emit()

    def calculate(self, *_args):
        try:
            self.current["analytical"] = evaluate_crossing(self.current["inputs"])
        except ValueError as exc:
            QMessageBox.warning(self, self.title, str(exc))
            return False
        self.render()
        self.changed.emit()
        return True

    def compare_all(self, *_args):
        try:
            values = [evaluate_crossing(c["inputs"]) for c in self.cases]
        except ValueError as exc:
            QMessageBox.warning(self, "Comparación", str(exc))
            return
        for c, a in zip(self.cases, values, strict=True):
            c["analytical"] = a
        self.render()
        self.output_tabs.setCurrentIndex(1)
        self.changed.emit()

    def simulate(self, *_args):
        if self.worker or not self.calculate():
            return
        self._running_id = self.selected_id
        self.worker = CrossingWorker(self.current["inputs"], self)
        self.worker.succeeded.connect(self._simulated)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.status.setText("Simulando peatones, vehículos y señalización…")
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
            else "Capture sus datos. Calcule la referencia o simule para obtener espera y colas."
        )
        for card in self.cards.values():
            card.setText("—")
        body = (
            "<h3>Un cruce y cuatro resultados</h3><p>El recorrido L/v es una referencia "
            "sin espera. Simule sus datos para medir espera, colas y cruces completados. "
            "Las aceras A y B corresponden al esquema de entrada.</p>"
        )
        if a:
            self.cards["reference"].setText(f"{a['reference_s']:.1f} s")
            body = "<h3>Referencia geométrica</h3>" + self._html_table(
                [
                    ("Recorrido L/v (s), sin espera", a["reference_s"]),
                    ("Verde vehicular (s)", a["vehicle_green_s"]),
                ]
            )
        if s:
            m = s["summary"]
            self.cards["wait"].setText(
                f"{m['mean_wait_s']:.1f} s" if m["mean_wait_s"] is not None else "N/A"
            )
            self.cards["queue"].setText(f"{m['max_queue_ab']} / {m['max_queue_ba']} peat")
            self.cards["complete"].setText(f"{m['completed']} / {m['generated']}")
            body += "<h3>Simulación</h3>" + self._html_table(
                [(SUMMARY_LABELS[k], v) for k, v in m.items()]
            )
            for d, name in [("AB", "Acera A → B"), ("BA", "Acera B → A")]:
                r = s["directions"][d]
                body += (
                    "<h3>"
                    + name
                    + "</h3>"
                    + self._html_table(
                        [
                            ("Espera media (s)", r["mean_wait_s"]),
                            ("Muestra de espera", r["entered"]),
                            ("Completados", r["completed"]),
                            ("Pendientes", r["pending"]),
                        ]
                    )
                )
            body += "<p>Colas muestreadas cada 0.5 s; la media de espera usa a quienes "
            body += "ya iniciaron el cruce. La simulación parte vacía y conserva dos ciclos "
            body += "adicionales tras el fin de llegadas.</p>"
        notes = s["warnings"] if s else a["warnings"] if a else []
        body += "<ul>" + "".join("<li>" + escape(n) + "</li>" for n in notes) + "</ul>"
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
        self.comparison_note.setText(
            "Simule cada caso por separado. Compare con igual demanda, "
            "velocidad, duración y semilla; las llegadas serán las mismas."
        )
        if len(self.cases) == 2:
            keys = ("ped_ab", "ped_ba", "vehicles_ph", "speed_mps", "duration_s", "seed")
            if any(
                str(self.cases[0]["inputs"][k]) != str(self.cases[1]["inputs"][k]) for k in keys
            ):
                self.comparison_note.setText(
                    "Las alternativas tienen distinta demanda, velocidad "
                    "o configuración de simulación. Revise la comparabilidad."
                )
        headers = [
            "Escenario",
            "L/v (s)",
            "Espera (s)",
            "Cola A",
            "Cola B",
            "Cruzaron",
            "Pendientes",
        ]
        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setHorizontalHeaderLabels(headers)
        self.compare_table.setRowCount(len(self.cases))
        for i, case in enumerate(self.cases):
            ca = case["analytical"] if fresh(case, "analytical") else {}
            cs = case["simulation"]["summary"] if fresh(case, "simulation") else {}
            values = [
                case["name"],
                ca.get("reference_s"),
                cs.get("mean_wait_s"),
                cs.get("max_queue_ab"),
                cs.get("max_queue_ba"),
                cs.get("completed"),
                cs.get("pending"),
            ]
            for j, v in enumerate(values):
                self.compare_table.setItem(
                    i, j, QTableWidgetItem("N/A" if v is None else display(v))
                )
        self.diagram.dark = self.dark
        self.diagram.update()
        key = (repr(c["inputs"]), id(s), self.dark)
        if self._last_plot != key:
            draw_crossing(self.figure, c["inputs"], s, self.dark)
            self.canvas.draw_idle()
            self._last_plot = key

    def import_csv(self, *_args):
        path, _ = QFileDialog.getOpenFileName(self, "Importar cruce", "", "CSV (*.csv)")
        if not path:
            return
        try:
            cases = import_cases(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "CSV", str(exc))
            return
        if any(c.get("analytical") or c.get("simulation") for c in self.cases):
            answer = QMessageBox.question(
                self, "Importar cruce", "Se reemplazarán los casos de este módulo. ¿Continuar?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.cases = cases
        self.selected_id = cases[0]["id"]
        self._refresh_selector()
        self._load_current()
        self.changed.emit()

    def template_csv(self, *_args):
        path, _ = QFileDialog.getSaveFileName(
            self, "Plantilla del cruce", "cruce_guia.csv", "CSV (*.csv)"
        )
        if path:
            try:
                template(path, self.current["inputs"])
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "Plantilla", str(exc))

    def restore(self, study):
        self.cases = copy.deepcopy(study["cases"]) if study else [new_case()]
        self.selected_id = study["selected_id"] if study else self.cases[0]["id"]
        self._refresh_selector()
        self._load_current()
