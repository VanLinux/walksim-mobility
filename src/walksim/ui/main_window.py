"""Ventana principal de WalkSim Mobility."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from walksim import __version__
from walksim.domain.models import CorridorScenario, DirectionResult
from walksim.sumo.runner import SumoExecutionError, detect_sumo, run_corridor_simulation


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(3)

        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")
        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        self.detail = QLabel("")
        self.detail.setObjectName("pageSubtitle")

        layout.addWidget(label_widget)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_metric(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.detail.setText(detail)


class CorridorPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(260)
        self.scenario = CorridorScenario()

    def set_scenario(self, scenario: CorridorScenario) -> None:
        self.scenario = scenario
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(45, 55, -45, -65)
        painter.setPen(QPen(QColor("#5F6368"), 2))
        painter.setBrush(QColor("#F1F3F4"))
        painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(QColor("#202124"))
        painter.drawText(rect.left(), rect.top() - 18, "A")
        painter.drawText(rect.right() - 10, rect.top() - 18, "B")

        painter.setPen(QPen(QColor("#30343B"), 3))
        y1 = rect.center().y() - 28
        y2 = rect.center().y() + 28
        painter.drawLine(rect.left() + 30, y1, rect.right() - 30, y1)
        painter.drawLine(rect.right() - 30, y2, rect.left() + 30, y2)

        painter.setPen(QColor("#202124"))
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            f"{self.scenario.length_m:.0f} m × {self.scenario.width_m:.2f} m",
        )
        painter.drawText(
            rect.left() + 18,
            rect.top() + 30,
            f"A → B    {self.scenario.flow_ab_pph:.0f} peat/h",
        )
        painter.drawText(
            rect.left() + 18,
            rect.bottom() - 20,
            f"B ← A    {self.scenario.flow_ba_pph:.0f} peat/h",
        )


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.last_output_dir: Path | None = None

        self.setWindowTitle(f"WalkSim Mobility {__version__}")
        self.setMinimumSize(1050, 700)
        self.resize(1280, 820)

        self._create_actions()
        self._create_menu()
        self._build_ui()
        self._refresh_sumo_status()
        self._update_preview()

    def _create_actions(self) -> None:
        self.simulate_action = QAction("Simular corredor", self)
        self.simulate_action.setShortcut("F5")
        self.simulate_action.triggered.connect(self.simulate)

        self.repository_action = QAction("Abrir repositorio", self)
        self.repository_action.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/VanLinux/walksim-mobility")
            )
        )

        self.about_action = QAction("Acerca de WalkSim Mobility", self)
        self.about_action.triggered.connect(self.show_about)

        self.quit_action = QAction("Salir", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Archivo")
        file_menu.addAction(self.quit_action)

        simulation_menu = self.menuBar().addMenu("Simulación")
        simulation_menu.addAction(self.simulate_action)

        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addActions([self.repository_action, self.about_action])

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 12)
        root.setSpacing(12)

        header = QHBoxLayout()
        titles = QVBoxLayout()

        title = QLabel("WalkSim Mobility")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Simulación y análisis de movilidad peatonal · motor Eclipse SUMO")
        subtitle.setObjectName("pageSubtitle")

        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()

        version = QLabel(f"VERSIÓN {__version__}")
        version.setStyleSheet(
            "background: #30343B; color: white; border-radius: 5px; "
            "padding: 6px 10px; font-weight: 700;"
        )
        header.addWidget(version, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.scope_tab = self._build_scope_tab()
        self.project_tab = self._build_project_tab()
        self.corridor_tab = self._build_corridor_tab()
        self.results_tab = self._build_results_tab()

        self.tabs.addTab(self.scope_tab, "1  Inicio y alcance")
        self.tabs.addTab(self.project_tab, "2  Proyecto")
        self.tabs.addTab(self.corridor_tab, "3  Corredor peatonal")
        self.tabs.addTab(self.results_tab, "4  Resultados")
        root.addWidget(self.tabs, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("WalkSim Mobility listo")

    def _build_scope_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(
            f"""
            <style>
              body {{ font-family: sans-serif; color: #202124; margin: 22px; }}
              h1 {{ color: #202124; font-size: 26px; margin-bottom: 2px; }}
              h2 {{ color: #30343b; }}
              .lead {{ color: #5f6368; font-size: 14px; margin-bottom: 18px; }}
              .panel {{ background: #f1f3f4; border-left: 4px solid #5f6368;
                        padding: 12px; margin: 14px 0; }}
              table {{ border-collapse: collapse; margin: 10px 0 18px 0; width: 100%; }}
              th, td {{ border-bottom: 1px solid #dadce0; padding: 7px; text-align: left; }}
              th {{ color: #30343b; width: 180px; }}
              li {{ margin: 5px 0; }}
              a {{ color: #3f444b; }}
            </style>
            <h1>WalkSim Mobility</h1>
            <p class="lead"><b>Simulación y análisis de movilidad peatonal</b><br>
            Interfaz ligera que utiliza Eclipse SUMO como motor de microsimulación
            sin exponer XML, NetEdit ni SUMO-GUI al usuario.</p>

            <table>
              <tr><th>Versión</th><td>{__version__}</td></tr>
              <tr><th>Desarrollador</th><td>Héctor Alonso Benítez García</td></tr>
              <tr><th>Licencia</th><td>GNU General Public License v3.0</td></tr>
              <tr><th>Motor</th><td>Eclipse SUMO</td></tr>
              <tr><th>Repositorio</th><td>
                <a href="https://github.com/VanLinux/walksim-mobility">
                github.com/VanLinux/walksim-mobility</a></td></tr>
            </table>

            <div class="panel">
              <b>Alcance de la versión 1.0</b><br>
              Corredor peatonal recto y bidireccional con demanda A → B y B → A.
              WalkSim genera el escenario, ejecuta SUMO con el modelo
              <i>striping</i> y transforma la salida en indicadores de ingeniería.
            </div>

            <h2>Flujo de trabajo</h2>
            <ol>
              <li>Identifique el proyecto.</li>
              <li>Defina geometría, demanda y velocidad peatonal.</li>
              <li>Pulse <b>Simular corredor</b>.</li>
              <li>Revise los resultados totales y por sentido.</li>
            </ol>

            <h2>Fuera del alcance actual</h2>
            <ul>
              <li>Cruces peatonales e intersecciones.</li>
              <li>Interacción vehículo-peatón y control semafórico.</li>
              <li>Edición libre de redes.</li>
              <li>Calibración y optimización automática.</li>
            </ul>
            """
        )
        layout.addWidget(browser)
        return page

    def _build_project_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)

        banner = QLabel(
            "Los datos de identificación documentan el estudio; no modifican el modelo SUMO."
        )
        banner.setObjectName("infoBanner")
        banner.setWordWrap(True)
        layout.addWidget(banner)

        box = QGroupBox("Identificación del estudio")
        form = QFormLayout(box)

        self.project_name = QLineEdit("Corredor peatonal")
        self.project_location = QLineEdit()
        self.project_analyst = QLineEdit()
        self.project_notes = QPlainTextEdit()
        self.project_notes.setMaximumHeight(150)
        self.project_notes.setPlaceholderText(
            "Origen de aforos, horario, supuestos, condiciones observadas…"
        )

        form.addRow("Proyecto:", self.project_name)
        form.addRow("Ubicación:", self.project_location)
        form.addRow("Analista:", self.project_analyst)
        form.addRow("Notas:", self.project_notes)
        layout.addWidget(box)
        layout.addStretch()
        return page

    def _build_corridor_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)

        self.sumo_status_frame = QFrame()
        status_layout = QHBoxLayout(self.sumo_status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)

        self.sumo_status_label = QLabel()
        self.sumo_status_label.setWordWrap(True)
        refresh_button = QPushButton("Verificar SUMO")
        refresh_button.clicked.connect(self._refresh_sumo_status)

        status_layout.addWidget(self.sumo_status_label, 1)
        status_layout.addWidget(refresh_button)
        layout.addWidget(self.sumo_status_frame)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        parameters = QGroupBox("Parámetros del corredor")
        form = QFormLayout(parameters)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(5.0, 2000.0)
        self.length_spin.setDecimals(1)
        self.length_spin.setValue(100.0)
        self.length_spin.setSuffix(" m")

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 20.0)
        self.width_spin.setDecimals(2)
        self.width_spin.setValue(2.5)
        self.width_spin.setSuffix(" m")

        self.flow_ab_spin = QDoubleSpinBox()
        self.flow_ab_spin.setRange(0.0, 20000.0)
        self.flow_ab_spin.setDecimals(0)
        self.flow_ab_spin.setValue(600.0)
        self.flow_ab_spin.setSuffix(" peat/h")

        self.flow_ba_spin = QDoubleSpinBox()
        self.flow_ba_spin.setRange(0.0, 20000.0)
        self.flow_ba_spin.setDecimals(0)
        self.flow_ba_spin.setValue(400.0)
        self.flow_ba_spin.setSuffix(" peat/h")

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.2, 3.0)
        self.speed_spin.setDecimals(2)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setValue(1.34)
        self.speed_spin.setSuffix(" m/s")

        self.period_spin = QDoubleSpinBox()
        self.period_spin.setRange(1.0, 480.0)
        self.period_spin.setDecimals(0)
        self.period_spin.setValue(60.0)
        self.period_spin.setSuffix(" min")

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2147483647)
        self.seed_spin.setValue(42)

        form.addRow("Longitud:", self.length_spin)
        form.addRow("Ancho útil:", self.width_spin)
        form.addRow("Flujo A → B:", self.flow_ab_spin)
        form.addRow("Flujo B → A:", self.flow_ba_spin)
        form.addRow("Velocidad de referencia:", self.speed_spin)
        form.addRow("Periodo de análisis:", self.period_spin)
        form.addRow("Semilla:", self.seed_spin)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.addWidget(parameters)

        model_note = QLabel(
            "Modelo peatonal interno: SUMO striping. La versión 1.0 utiliza un "
            "corredor recto de ancho uniforme."
        )
        model_note.setObjectName("pageSubtitle")
        model_note.setWordWrap(True)
        left_layout.addWidget(model_note)

        simulate_button = QPushButton("Simular corredor")
        simulate_button.setObjectName("primaryButton")
        simulate_button.clicked.connect(self.simulate)
        left_layout.addWidget(simulate_button)
        left_layout.addStretch()

        preview_box = QGroupBox("Esquema del escenario")
        preview_layout = QVBoxLayout(preview_box)
        self.preview = CorridorPreview()
        preview_layout.addWidget(self.preview)

        preview_note = QLabel(
            "Esquema orientativo. El ancho se utiliza como ancho de la superficie "
            "peatonal generada para SUMO."
        )
        preview_note.setObjectName("pageSubtitle")
        preview_note.setWordWrap(True)
        preview_layout.addWidget(preview_note)

        splitter.addWidget(left)
        splitter.addWidget(preview_box)
        splitter.setSizes([470, 650])
        layout.addWidget(splitter, 1)

        for spin in (
            self.length_spin,
            self.width_spin,
            self.flow_ab_spin,
            self.flow_ba_spin,
            self.speed_spin,
            self.period_spin,
        ):
            spin.valueChanged.connect(self._update_preview)

        return page

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)

        top = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("Resultados del corredor")
        title.setObjectName("sectionTitle")
        self.result_status = QLabel("Aún no se ha ejecutado una simulación.")
        self.result_status.setObjectName("pageSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(self.result_status)
        top.addLayout(title_box)
        top.addStretch()

        rerun = QPushButton("Simular nuevamente")
        rerun.setObjectName("primaryButton")
        rerun.clicked.connect(self.simulate)
        top.addWidget(rerun)
        layout.addLayout(top)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)

        self.completed_card = MetricCard("RECORRIDOS COMPLETADOS")
        self.duration_card = MetricCard("TIEMPO MEDIO")
        self.speed_card = MetricCard("VELOCIDAD EFECTIVA")
        self.loss_card = MetricCard("TIEMPO PERDIDO")

        cards.addWidget(self.completed_card, 0, 0)
        cards.addWidget(self.duration_card, 0, 1)
        cards.addWidget(self.speed_card, 0, 2)
        cards.addWidget(self.loss_card, 0, 3)
        layout.addLayout(cards)

        self.results_table = QTableWidget(3, 6)
        self.results_table.setHorizontalHeaderLabels(
            [
                "Sentido",
                "Completados",
                "Tiempo medio (s)",
                "Velocidad (m/s)",
                "Tiempo perdido (s)",
                "Distancia media (m)",
            ]
        )
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.results_table, 1)

        self.output_label = QLabel("")
        self.output_label.setObjectName("pageSubtitle")
        self.output_label.setWordWrap(True)
        layout.addWidget(self.output_label)

        return page

    def _scenario_from_ui(self) -> CorridorScenario:
        return CorridorScenario(
            length_m=self.length_spin.value(),
            width_m=self.width_spin.value(),
            flow_ab_pph=self.flow_ab_spin.value(),
            flow_ba_pph=self.flow_ba_spin.value(),
            walking_speed_mps=self.speed_spin.value(),
            analysis_time_s=self.period_spin.value() * 60.0,
            seed=self.seed_spin.value(),
        )

    def _update_preview(self, *_args) -> None:
        if hasattr(self, "preview"):
            self.preview.set_scenario(self._scenario_from_ui())

    def _refresh_sumo_status(self) -> None:
        installation = detect_sumo()

        if installation.available:
            self.sumo_status_frame.setObjectName("sumoStatusOk")
            self.sumo_status_label.setText(
                "SUMO disponible. Se detectaron los ejecutables sumo y netconvert."
            )
        else:
            self.sumo_status_frame.setObjectName("sumoStatusMissing")
            missing = []
            if not installation.sumo:
                missing.append("sumo")
            if not installation.netconvert:
                missing.append("netconvert")
            self.sumo_status_label.setText(
                "SUMO no está listo. Falta en PATH: " + ", ".join(missing) + "."
            )

        self.sumo_status_frame.style().unpolish(self.sumo_status_frame)
        self.sumo_status_frame.style().polish(self.sumo_status_frame)

    def simulate(self) -> None:
        scenario = self._scenario_from_ui()
        errors = scenario.validate()

        if errors:
            QMessageBox.warning(self, "Datos del escenario", "\n".join(errors))
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage("Ejecutando SUMO…")

        try:
            run = run_corridor_simulation(scenario)
        except (SumoExecutionError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "No fue posible simular", str(exc))
            self.statusBar().showMessage("Simulación no ejecutada")
            self._refresh_sumo_status()
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.last_output_dir = run.files.workdir
        result = run.result

        self.completed_card.set_metric(
            str(result.total.completed_walks),
            "ambos sentidos",
        )
        self.duration_card.set_metric(
            f"{result.total.mean_duration_s:.1f} s",
            "recorridos completados",
        )
        self.speed_card.set_metric(
            f"{result.total.mean_speed_mps:.2f} m/s",
            "velocidad efectiva",
        )
        self.loss_card.set_metric(
            f"{result.total.mean_time_loss_s:.1f} s",
            "promedio por recorrido",
        )

        self._set_result_row(0, "A → B", result.ab)
        self._set_result_row(1, "B → A", result.ba)
        self._set_result_row(2, "Total", result.total)

        self.result_status.setText(
            f"Simulación completada · modelo striping · semilla {scenario.seed}"
        )
        self.output_label.setText(
            "Archivos temporales del escenario: " + str(run.files.workdir)
        )

        self.tabs.setCurrentWidget(self.results_tab)
        self.statusBar().showMessage("Simulación completada")

    def _set_result_row(self, row: int, label: str, result: DirectionResult) -> None:
        values = [
            label,
            str(result.completed_walks),
            f"{result.mean_duration_s:.2f}",
            f"{result.mean_speed_mps:.3f}",
            f"{result.mean_time_loss_s:.2f}",
            f"{result.mean_route_length_m:.2f}",
        ]

        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column > 0:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.results_table.setItem(row, column, item)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Acerca de WalkSim Mobility",
            f"<b>WalkSim Mobility {__version__}</b><br><br>"
            "Simulación y análisis de movilidad peatonal mediante Eclipse SUMO.<br><br>"
            "Desarrollador: Héctor Alonso Benítez García<br>"
            "Licencia: GNU GPL v3.0",
        )
