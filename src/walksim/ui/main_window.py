"""Ventana principal de WalkSim Mobility."""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QBoxLayout,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from walksim.csv_io import write_template
from walksim.domain.models import CorridorScenario, DirectionResult, ProjectInfo, SimulationResult
from walksim.project import ProjectState, load_project, save_project
from walksim.report import write_report
from walksim.sumo.runner import run_corridor_simulation
from walksim.ui.access_widget import AccessWidget
from walksim.ui.analysis_widget import AnalysisWidget
from walksim.ui.crossing_widget import CrossingWidget
from walksim.ui.plaza_widget import PlazaWidget
from walksim.ui.shared_widget import SharedWidget
from walksim.ui.styles import apply_theme, theme_colors
from walksim.ui.walkway_widget import WalkwayWidget


class SimulationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, scenario: CorridorScenario, parent: QWidget) -> None:
        super().__init__(parent)
        self.scenario = scenario

    def run(self) -> None:
        try:
            self.succeeded.emit(run_corridor_simulation(self.scenario))
        except Exception as exc:
            logging.getLogger(__name__).exception("Error al simular el corredor")
            self.failed.emit(str(exc))


class MetricCard(QFrame):
    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(3)

        label_widget = QLabel(label)
        label_widget.setObjectName("metricLabel")
        label_widget.setWordWrap(True)
        self.value = QLabel(value)
        self.value.setObjectName("metricValue")
        self.detail = QLabel("")
        self.detail.setObjectName("pageSubtitle")
        self.detail.setWordWrap(True)

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
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Mid), 2))
        painter.setBrush(self.palette().color(QPalette.ColorRole.AlternateBase))
        painter.drawRoundedRect(rect, 8, 8)

        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        painter.drawText(rect.left(), rect.top() - 18, "A")
        painter.drawText(rect.right() - 10, rect.top() - 18, "B")

        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Text), 3))
        y1 = rect.center().y() - 28
        y2 = rect.center().y() + 28
        painter.drawLine(rect.left() + 30, y1, rect.right() - 30, y1)
        painter.drawLine(rect.right() - 30, y2, rect.left() + 30, y2)

        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
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
        self.current_file: Path | None = None
        self.simulation_records: list[dict] = []
        self._loading = True
        self._busy = False
        self.worker: SimulationWorker | None = None

        self.setWindowTitle(f"WalkSim Mobility {__version__}")
        self.settings = QSettings("VanLinux", "WalkSim Mobility")
        self.theme = str(self.settings.value("appearance/theme", "light"))
        if self.theme not in ("light", "dark"):
            self.theme = "light"
        apply_theme(QApplication.instance(), self.theme)
        self.setMinimumSize(480, 360)
        available = self.screen().availableGeometry()
        self.resize(min(1280, available.width()), min(820, available.height()))

        self._create_actions()
        self._create_menu()
        self._build_ui()
        self._apply_responsive_layout()
        self._update_preview()
        self._connect_project_signals()
        self._loading = False
        self._set_clean()
        self.tabs.setCurrentIndex(2)

    def _create_actions(self) -> None:
        self.new_action = QAction("Nuevo estudio", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_project)
        self.open_action = QAction("Abrir .wksim…", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_project_dialog)
        self.save_action = QAction("Guardar .wksim", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_current)
        self.save_as_action = QAction("Guardar como…", self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.triggered.connect(self.save_as)
        self.report_action = QAction("Exportar reporte .tex…", self)
        self.report_action.triggered.connect(self.export_report)

        self.simulate_action = QAction("Simular ejemplo", self)
        self.simulate_action.setToolTip(
            "Añade y ejecuta un escenario de ejemplo sin reemplazar sus alternativas."
        )

        self.simulate_action.triggered.connect(self.simulate_example)

        self.crossing_action = QAction("Simular mis datos · Cruce semaforizado", self)
        self.crossing_action.triggered.connect(lambda: self.crossing_widget.simulate())
        self.shared_action = QAction("Simular mis datos · Sendero compartido", self)
        self.shared_action.triggered.connect(lambda: self.shared_widget.simulate())
        self.plaza_action = QAction("Simular mis datos · Plaza y flujos cruzados", self)
        self.plaza_action.triggered.connect(lambda: self.plaza_widget.simulate())
        self.access_action = QAction("Simular mis datos · Accesos y colas", self)
        self.access_action.triggered.connect(lambda: self.access_widget.simulate())
        self.execute_action = QAction("Simular mis datos · Walkway", self)
        self.execute_action.setShortcut("F5")
        self.execute_action.triggered.connect(lambda: self.walkway_widget.simulate())
        self.manual_action = QAction("Guía de uso", self)
        self.manual_action.triggered.connect(self.show_guide)
        self.method_action = QAction("Metodología Walkway", self)
        self.method_action.triggered.connect(lambda: self.show_guide(methodology=True))
        self.about_action = QAction("Acerca de WalkSim Mobility", self)
        self.about_action.triggered.connect(self.show_about)

        self.theme_actions = QActionGroup(self)
        self.theme_actions.setExclusive(True)
        for label, mode in (("Modo claro", "light"), ("Modo oscuro", "dark")):
            action = QAction(label, self.theme_actions)
            action.setCheckable(True)
            action.setData(mode)
            action.setChecked(mode == self.theme)
            action.triggered.connect(lambda _checked, value=mode: self.set_theme(value))

        self.quit_action = QAction("Salir", self)
        self.quit_action.setShortcut("Ctrl+Q")
        self.quit_action.triggered.connect(self.close)

    def _create_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Archivo")
        file_menu.addActions(
            [self.new_action, self.open_action, self.save_action, self.save_as_action]
        )
        file_menu.addSeparator()
        file_menu.addAction(self.report_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)
        analysis_menu = self.menuBar().addMenu("Análisis")
        for label, index in (
            ("Walkway · operación y diseño", 2),
            ("Análisis complementarios", 3),
            ("Corredor libre", 4),
            ("Accesos y colas · capacidad y espera", 6),
            ("Plaza · flujos cruzados y OD local", 7),
            ("Sendero compartido · PLOS y BLOS", 8),
            ("Cruce semaforizado · espera y colas", 9),
        ):
            action = analysis_menu.addAction(label)
            action.triggered.connect(lambda _checked, i=index: self.tabs.setCurrentIndex(i))
        simulation_menu = self.menuBar().addMenu("Simulación")
        simulation_menu.addAction(self.execute_action)
        simulation_menu.addAction(self.access_action)
        simulation_menu.addAction(self.plaza_action)
        simulation_menu.addAction(self.shared_action)
        simulation_menu.addAction(self.crossing_action)
        simulation_menu.addAction(self.simulate_action)

        appearance_menu = self.menuBar().addMenu("Apariencia")
        appearance_menu.addActions(self.theme_actions.actions())

        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addActions([self.manual_action, self.method_action, self.about_action])

    def _build_ui(self) -> None:
        central = QWidget()
        central.setAutoFillBackground(True)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 12)
        root.setSpacing(12)

        header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.header_layout = header
        titles = QVBoxLayout()

        title = QLabel("WalkSim Mobility")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Ingeniería peatonal · operación, diseño y microsimulación")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        version = QLabel(f"VERSIÓN {__version__}")
        version.setObjectName("versionBadge")
        header.addWidget(version, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.tabBar().setExpanding(False)
        self.scope_tab = self._build_scope_tab()
        self.project_tab = self._build_project_tab()
        self.corridor_tab = self._build_corridor_tab()
        self.results_tab = self._build_results_tab()

        self.tabs.addTab(self.scope_tab, "1  Inicio y alcance")
        self.tabs.addTab(self._scrollable(self.project_tab), "2  Proyecto")
        self.tabs.addTab(self._scrollable(self.corridor_tab), "3  Corredor peatonal")
        self.tabs.addTab(self._scrollable(self.results_tab), "4  Resultados")
        self.analysis_widget = AnalysisWidget()
        self.analysis_widget.simulationImported.connect(self._import_corridor)
        self.analysis_widget.simulationRequested.connect(self.prepare_analysis_simulation)
        self.tabs.insertTab(2, self._scrollable(self.analysis_widget), "3  Análisis peatonal")
        self.tabs.setTabText(3, "4  Microsimulación")
        self.tabs.setTabText(4, "5  Resultados simulados")
        self.walkway_widget = WalkwayWidget()
        self.tabs.insertTab(2, self._scrollable(self.walkway_widget), "3  Walkway")
        self.tabs.setTabText(0, "Inicio")
        self.tabs.setTabText(1, "Proyecto")
        self.tabs.setTabText(2, "Walkway")
        self.tabs.setTabText(3, "Complementarios")
        self.tabs.setTabText(4, "Corredor libre")
        self.tabs.setTabText(5, "Resultados del corredor")
        self.walkway_widget.busyChanged.connect(self._walkway_busy)
        self.walkway_widget.set_dark(self.theme == "dark")
        self.access_widget = AccessWidget()
        self.tabs.addTab(self._scrollable(self.access_widget), "Accesos y colas")
        self.access_widget.busyChanged.connect(self._access_busy)
        self.access_widget.set_dark(self.theme == "dark")
        self.plaza_widget = PlazaWidget()
        self.tabs.addTab(self._scrollable(self.plaza_widget), "Plaza y flujos cruzados")
        self.plaza_widget.busyChanged.connect(self._plaza_busy)
        self.plaza_widget.set_dark(self.theme == "dark")
        self.shared_widget = SharedWidget()
        self.tabs.addTab(self._scrollable(self.shared_widget), "Sendero compartido")
        self.shared_widget.busyChanged.connect(self._shared_busy)
        self.shared_widget.set_dark(self.theme == "dark")
        self.crossing_widget = CrossingWidget()
        self.tabs.addTab(self._scrollable(self.crossing_widget), "Cruce semaforizado")
        self.crossing_widget.busyChanged.connect(self._crossing_busy)
        self.crossing_widget.set_dark(self.theme == "dark")
        root.addWidget(self.tabs, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        root.addWidget(self.progress)

        self.setCentralWidget(central)
        self.statusBar().showMessage("WalkSim Mobility listo")

    def _build_scope_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)

        self.scope_browser = QTextBrowser()
        self.scope_browser.setOpenExternalLinks(True)
        self._refresh_scope_text()
        layout.addWidget(self.scope_browser)
        return page

    def _refresh_scope_text(self) -> None:
        colors = theme_colors(self.theme)
        browser = self.scope_browser
        browser.setHtml(
            f"""
            <style>
              body {{ font-family: sans-serif; color: {colors["ink"]}; margin: 22px; }}
              h1 {{ color: {colors["ink"]}; font-size: 26px; margin-bottom: 2px; }}
              h2 {{ color: {colors["dark"]}; }}
              .lead {{ color: {colors["muted"]}; font-size: 14px; margin-bottom: 18px; }}
              .panel {{ background: {colors["alternate"]}; border-left: 4px solid {colors["muted"]};
                        padding: 12px; margin: 14px 0; }}
              table {{ border-collapse: collapse; margin: 10px 0 18px 0; width: 100%; }}
              th, td {{ border-bottom: 1px solid {colors["line"]};
                        padding: 7px; text-align: left; }}
              th {{ color: {colors["dark"]}; width: 180px; }}
              li {{ margin: 5px 0; }}
              a {{ color: {colors["ink"]}; }}
            </style>
            <h1>WalkSim Mobility</h1>
            <p class="lead"><b>Simulación y análisis de movilidad peatonal</b><br>
            Defina su escenario con parámetros sencillos y consulte los
            indicadores totales y por sentido.</p>

            <table>
              <tr><th>Versión</th><td>{__version__}</td></tr>
              <tr><th>Desarrollador</th><td>Héctor Alonso Benítez García</td></tr>
              <tr><th>Licencia</th><td>GNU General Public License v3.0</td></tr>
              <tr><th>Repositorio</th><td>
                <a href="https://github.com/VanLinux/walksim-mobility">
                github.com/VanLinux/walksim-mobility</a></td></tr>
            </table>

            <div class="panel">
              <b>WalkSim 3.3 · Ingeniería peatonal y ciclista</b><br>
              Evalúe un corredor o calcule el ancho y la demanda admisible para un LOS objetivo.
              Duplique el escenario Base, cambie sus datos y compare las alternativas.
              En Accesos y colas evalúe puertas, torniquetes y descargas de Metro.
              En Plaza y flujos cruzados capture la OD local y consulte mapas de densidad.
              En Sendero compartido evalúe PLOS, BLOS y convivencia peatón–bicicleta.
              Los análisis de la versión 2.1 siguen disponibles en Complementarios.
            </div>
            <h2>Flujo de trabajo</h2>
            <ol>
              <li>Identifique el proyecto y escriba el nombre del analista.</li>
              <li>Elija un análisis: capture los datos o importe su plantilla CSV.</li>
              <li>Calcule los casos que desea añadir al estudio.</li>
              <li>Ejecute la microsimulación del corredor cuando corresponda.</li>
              <li>Guarde sus avances en <b>.wksim</b> y exporte el informe <b>.tex</b>.</li>
            </ol>
            <p>Las plantillas contienen un ejemplo editable. Los datos de ejemplo no
            sustituyen las observaciones del sitio. Cada resultado indica su criterio y alcance.</p>
            <p><b>Archivo:</b> Nuevo, Abrir, Guardar, Guardar como y Exportar reporte.
            <b>Apariencia:</b> Modo claro u oscuro. Los borradores y resultados se conservan
            en el proyecto; los archivos temporales de microsimulación no son necesarios
            para abrirlo.</p>
            """
        )

    def _build_project_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)

        banner = QLabel("Los datos de identificación documentan el estudio.")
        banner.setObjectName("infoBanner")
        banner.setWordWrap(True)
        layout.addWidget(banner)

        box = QGroupBox("Identificación del estudio")
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.corridor_splitter = splitter
        splitter.setChildrenCollapsible(False)

        parameters = QGroupBox("Parámetros del corredor")
        form = QFormLayout(parameters)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(5.0, 2000.0)
        self.length_spin.setDecimals(6)
        self.length_spin.setValue(100.0)
        self.length_spin.setSuffix(" m")

        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 20.0)
        self.width_spin.setDecimals(6)
        self.width_spin.setValue(2.5)
        self.width_spin.setSuffix(" m")

        self.flow_ab_spin = QDoubleSpinBox()
        self.flow_ab_spin.setRange(0.0, 20000.0)
        self.flow_ab_spin.setDecimals(6)
        self.flow_ab_spin.setValue(600.0)
        self.flow_ab_spin.setSuffix(" peat/h")

        self.flow_ba_spin = QDoubleSpinBox()
        self.flow_ba_spin.setRange(0.0, 20000.0)
        self.flow_ba_spin.setDecimals(6)
        self.flow_ba_spin.setValue(400.0)
        self.flow_ba_spin.setSuffix(" peat/h")

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.2, 3.0)
        self.speed_spin.setDecimals(6)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setValue(1.34)
        self.speed_spin.setSuffix(" m/s")

        self.period_spin = QDoubleSpinBox()
        self.period_spin.setRange(1.0, 480.0)
        self.period_spin.setDecimals(6)
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
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(parameters)

        model_note = QLabel("Corredor recto y bidireccional de ancho uniforme.")
        model_note.setObjectName("pageSubtitle")
        model_note.setWordWrap(True)
        left_layout.addWidget(model_note)

        simulate_button = QPushButton("Simular corredor")
        simulate_button.setObjectName("primaryButton")
        simulate_button.clicked.connect(self.simulate)
        self.simulate_button = simulate_button
        left_layout.addWidget(simulate_button)
        import_csv = QPushButton("Importar escenario CSV")
        import_csv.clicked.connect(self.analysis_widget_import_csv)
        template_csv = QPushButton("Descargar plantilla del corredor")
        template_csv.clicked.connect(self.download_corridor_template)
        left_layout.addWidget(import_csv)
        left_layout.addWidget(template_csv)
        left_layout.addStretch()

        preview_box = QGroupBox("Esquema del escenario")
        preview_layout = QVBoxLayout(preview_box)
        self.preview = CorridorPreview()
        preview_layout.addWidget(self.preview)

        preview_note = QLabel(
            "Esquema orientativo de la longitud, el ancho útil y los flujos por sentido."
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

        top = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.results_header_layout = top
        title_box = QVBoxLayout()

        title = QLabel("Resultados del corredor")
        title.setObjectName("sectionTitle")
        self.result_status = QLabel("Aún no se ha ejecutado una simulación.")
        self.result_status.setObjectName("pageSubtitle")
        self.result_status.setWordWrap(True)

        title_box.addWidget(title)
        title_box.addWidget(self.result_status)
        top.addLayout(title_box)
        top.addStretch()

        rerun = QPushButton("Simular nuevamente")
        rerun.setObjectName("primaryButton")
        rerun.clicked.connect(self.simulate)
        self.rerun_button = rerun
        top.addWidget(rerun)
        layout.addLayout(top)

        cards = QGridLayout()
        self.cards_layout = cards
        cards.setHorizontalSpacing(10)

        self.completed_card = MetricCard("RECORRIDOS COMPLETADOS")
        self.duration_card = MetricCard("TIEMPO MEDIO")
        self.speed_card = MetricCard("VELOCIDAD EFECTIVA")
        self.loss_card = MetricCard("TIEMPO PERDIDO")

        cards.addWidget(self.completed_card, 0, 0)
        cards.addWidget(self.duration_card, 0, 1)
        cards.addWidget(self.speed_card, 0, 2)
        cards.addWidget(self.loss_card, 0, 3)
        self.metric_cards = (
            self.completed_card,
            self.duration_card,
            self.speed_card,
            self.loss_card,
        )
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
        self.results_table.setMinimumHeight(180)
        self.results_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table_header = self.results_table.horizontalHeader()
        table_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table_header.setMinimumSectionSize(100)
        for column, width in enumerate((110, 130, 160, 160, 175, 180)):
            self.results_table.setColumnWidth(column, width)
        layout.addWidget(self.results_table, 1)

        self.output_label = QLabel("")
        self.output_label.setObjectName("pageSubtitle")
        self.output_label.setWordWrap(True)
        layout.addWidget(self.output_label)
        self.measurement_browser = QTextBrowser()
        self.measurement_browser.setMinimumHeight(180)
        layout.addWidget(self.measurement_browser)

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

    @staticmethod
    def _scrollable(page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def set_theme(self, mode: str) -> None:
        self.theme = mode
        self.settings.setValue("appearance/theme", mode)
        apply_theme(QApplication.instance(), mode)
        for action in self.theme_actions.actions():
            action.setChecked(action.data() == mode)
        position = self.scope_browser.verticalScrollBar().value()
        self._refresh_scope_text()
        self.scope_browser.verticalScrollBar().setValue(position)
        self.preview.update()
        self.walkway_widget.set_dark(mode == "dark")
        self.access_widget.set_dark(mode == "dark")
        self.plaza_widget.set_dark(mode == "dark")
        self.shared_widget.set_dark(mode == "dark")
        self.crossing_widget.set_dark(mode == "dark")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "metric_cards"):
            self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        width = self.width()
        if hasattr(self, "walkway_widget"):
            self.walkway_widget.adapt(width)
            self.access_widget.adapt(width)
            self.plaza_widget.adapt(width)
            self.shared_widget.adapt(width)
            self.crossing_widget.adapt(width)
        compact = width < 900
        self.corridor_splitter.setOrientation(
            Qt.Orientation.Vertical if compact else Qt.Orientation.Horizontal
        )
        direction = (
            QBoxLayout.Direction.TopToBottom if width < 650 else QBoxLayout.Direction.LeftToRight
        )
        self.header_layout.setDirection(direction)
        self.results_header_layout.setDirection(direction)
        columns = 1 if width < 650 else (2 if width < 1100 else 4)
        for card in self.metric_cards:
            self.cards_layout.removeWidget(card)
        for column in range(4):
            self.cards_layout.setColumnStretch(column, 0)
        for index, card in enumerate(self.metric_cards):
            self.cards_layout.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            self.cards_layout.setColumnStretch(column, 1)

    def simulate(self) -> None:
        scenario = self._scenario_from_ui()
        errors = scenario.validate()

        if errors:
            QMessageBox.warning(self, "Datos del escenario", "\n".join(errors))
            return

        if self._busy:
            return
        self._busy = True
        self._set_busy(True)
        self.statusBar().showMessage("Simulando corredor… Puede guardar el estudio al terminar.")
        self.worker = SimulationWorker(scenario, self)
        self.worker.succeeded.connect(self._simulation_completed)
        self.worker.failed.connect(self._simulation_failed)
        self.worker.finished.connect(self._simulation_finished)
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.corridor_tab.setEnabled(not busy)
        self.walkway_widget.setEnabled(not busy)
        self.access_widget.setEnabled(not busy)
        self.plaza_widget.setEnabled(not busy)
        self.shared_widget.setEnabled(not busy)
        self.crossing_widget.setEnabled(not busy)
        self.crossing_action.setEnabled(not busy)
        self.shared_action.setEnabled(not busy)
        self.plaza_action.setEnabled(not busy)
        self.access_action.setEnabled(not busy)
        self.execute_action.setEnabled(not busy)
        self.simulate_action.setEnabled(not busy)
        self.rerun_button.setEnabled(not busy)
        for action in (
            self.new_action,
            self.open_action,
            self.save_action,
            self.save_as_action,
            self.report_action,
        ):
            action.setEnabled(not busy)

    def _simulation_failed(self, _detail: str) -> None:
        QMessageBox.critical(
            self,
            "No fue posible simular",
            "Revise los parámetros y la instalación según los requisitos del "
            "repositorio. El detalle técnico se conserva en la terminal.",
        )
        self.statusBar().showMessage("Simulación no ejecutada")

    def _simulation_finished(self) -> None:
        self._busy = False
        self._set_busy(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _simulation_completed(self, run) -> None:
        scenario = self.worker.scenario
        self.last_output_dir = run.files.workdir
        record = {
            "scenario": asdict(scenario),
            "result": asdict(run.result),
            "created_at": datetime.now(UTC).isoformat(),
            "engine_version": getattr(run, "engine_version", "No registrada"),
            "measurements": getattr(run, "measurements", {}),
            "assumptions": [
                "La ocupación se integra durante el periodo de demanda; los tiempos medios "
                "incluyen recorridos completados hasta terminar el despeje.",
                "El espacio equivalente utiliza toda la longitud y el ancho útil del corredor. "
                "El LOS es indicativo del promedio global; no mide la zona más congestionada "
                "ni constituye una validación HCM local.",
                "El tiempo perdido simulado no es la demora de control de un cruce.",
            ],
        }
        self.simulation_records.append(record)
        self._show_simulation(record)
        self._mark_dirty()

    def _show_simulation(self, record: dict) -> None:
        scenario = CorridorScenario(**record["scenario"])
        result = SimulationResult(
            **{key: DirectionResult(**value) for key, value in record["result"].items()}
        )
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

        self.result_status.setText(f"Simulación completada · semilla {scenario.seed}")
        self.output_label.setText(
            "Resultado conservado del escenario ejecutado. "
            "El reporte incluye el historial de microsimulaciones."
        )
        from html import escape

        from walksim.report import display

        rows = "".join(
            "<tr><td>" + escape(k) + "</td><td><b>" + escape(display(v)) + "</b></td></tr>"
            for k, v in record.get("measurements", {}).items()
        )
        self.measurement_browser.setHtml(
            "<table cellpadding='5'>"
            + rows
            + "</table><p>"
            + escape(record.get("assumptions", [""])[0])
            + "</p><p>"
            + escape(
                "El LOS por espacio global es indicativo; no evalúa densidades locales máximas."
            )
            + "</p>"
        )

        self.tabs.setCurrentIndex(5)
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

    def _connect_project_signals(self) -> None:
        for widget in (self.project_name, self.project_location, self.project_analyst):
            widget.textChanged.connect(self._mark_dirty)
        self.project_notes.textChanged.connect(self._mark_dirty)
        for widget in (
            self.length_spin,
            self.width_spin,
            self.flow_ab_spin,
            self.flow_ba_spin,
            self.speed_spin,
            self.period_spin,
            self.seed_spin,
        ):
            widget.valueChanged.connect(self._mark_dirty)
        self.analysis_widget.changed.connect(self._mark_dirty)
        self.walkway_widget.changed.connect(self._mark_dirty)
        self.access_widget.changed.connect(self._mark_dirty)
        self.plaza_widget.changed.connect(self._mark_dirty)
        self.shared_widget.changed.connect(self._mark_dirty)
        self.crossing_widget.changed.connect(self._mark_dirty)

    def _mark_dirty(self, *_args) -> None:
        if not self._loading:
            self.setWindowModified(True)

    def _set_clean(self) -> None:
        title = self.current_file.name if self.current_file else "Estudio sin guardar"
        self.setWindowTitle(f"WalkSim Mobility {__version__} — {title}[*]")
        self.setWindowModified(False)

    def collect_project(self) -> ProjectState:
        self.analysis_widget._store_draft()
        return ProjectState(
            ProjectInfo(
                self.project_name.text(),
                self.project_location.text(),
                self.project_analyst.text(),
                self.project_notes.toPlainText(),
            ),
            self._scenario_from_ui(),
            self.analysis_widget.method,
            self.analysis_widget.drafts,
            self.analysis_widget.names,
            self.analysis_widget.results,
            self.simulation_records,
            self.walkway_widget.export_state(),
            self.access_widget.export_state(),
            self.plaza_widget.export_state(),
            self.shared_widget.export_state(),
            self.crossing_widget.export_state(),
        )

    def save_to_path(self, path: str | Path) -> Path:
        saved = save_project(self.collect_project(), path)
        self.current_file = saved
        self._set_clean()
        self.statusBar().showMessage("Estudio guardado: " + saved.name)
        return saved

    def save_current(self, *_args) -> bool:
        if self._busy:
            return False
        if self.current_file is None:
            return self.save_as()
        try:
            self.save_to_path(self.current_file)
            return True
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "No fue posible guardar", str(exc))
            return False

    def save_as(self, *_args) -> bool:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar estudio",
            str(self.current_file or "estudio.wksim"),
            "Proyecto WalkSim (*.wksim)",
        )
        if not path:
            return False
        try:
            self.save_to_path(path)
            return True
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "No fue posible guardar", str(exc))
            return False

    def _confirm_discard(self) -> bool:
        if not self.isWindowModified():
            return True
        answer = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "¿Desea guardar sus avances?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_current() if answer == QMessageBox.StandardButton.Save else True

    def load_from_path(self, path: str | Path) -> None:
        candidate = load_project(path)
        self._apply_project(candidate)
        self.current_file = Path(path)
        self._set_clean()
        self.statusBar().showMessage("Estudio abierto: " + self.current_file.name)

    def open_project_dialog(self, *_args) -> None:
        if self._busy or not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir estudio", "", "Proyecto WalkSim (*.wksim)"
        )
        if path:
            try:
                self.load_from_path(path)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "No fue posible abrir", str(exc))

    def _apply_project(self, state: ProjectState) -> None:
        self._loading = True
        self.project_name.setText(state.project.name)
        self.project_location.setText(state.project.location)
        self.project_analyst.setText(state.project.analyst)
        self.project_notes.setPlainText(state.project.notes)
        self._import_corridor(asdict(state.corridor))
        self.analysis_widget.restore(
            state.active_method, state.drafts, state.draft_names, state.analyses
        )
        self.walkway_widget.restore(state.walkway)
        self.access_widget.restore(state.access)
        self.plaza_widget.restore(state.plaza)
        self.shared_widget.restore(state.shared)
        self.crossing_widget.restore(state.crossing)
        self.simulation_records = state.simulations
        self.last_output_dir = None
        if self.simulation_records:
            self._show_simulation(self.simulation_records[-1])
        else:
            self.results_table.clearContents()
            for card in self.metric_cards:
                card.set_metric("—")
            self.result_status.setText("Aún no se ha ejecutado una simulación.")
            self.output_label.clear()
            self.measurement_browser.clear()
        self.tabs.setCurrentIndex(
            7
            if state.plaza and any(c.get("analytical") for c in state.plaza["cases"])
            else 6
            if state.access and any(c.get("analytical") for c in state.access["cases"])
            else 2
            if state.walkway
            else 1
        )
        if state.shared and any(c.get("analytical") for c in state.shared["cases"]):
            self.tabs.setCurrentIndex(8)
        if state.crossing and any(c.get("analytical") for c in state.crossing["cases"]):
            self.tabs.setCurrentIndex(9)
        self._loading = False

    def new_project(self, *_args) -> None:
        if self._busy or not self._confirm_discard():
            return
        self._apply_project(ProjectState())
        self.current_file = None
        self._set_clean()

    def export_report(self, *_args) -> None:
        if not self.project_analyst.text().strip():
            analyst, accepted = QInputDialog.getText(
                self, "Analista del estudio", "Nombre del analista:"
            )
            if not accepted or not analyst.strip():
                return
            self.project_analyst.setText(analyst.strip())
        if (
            not self.analysis_widget.results
            and not self.simulation_records
            and not any(case.get("analytical") for case in self.walkway_widget.cases)
            and not any(case.get("analytical") for case in self.access_widget.cases)
            and not any(case.get("analytical") for case in self.plaza_widget.cases)
            and not any(case.get("analytical") for case in self.shared_widget.cases)
            and not any(case.get("analytical") for case in self.crossing_widget.cases)
        ):
            QMessageBox.information(
                self, "Reporte", "Calcule un análisis o ejecute una simulación."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar informe completo", "informe_walksim.tex", "LaTeX (*.tex)"
        )
        if path:
            try:
                write_report(
                    self.collect_project(), path if path.lower().endswith(".tex") else path + ".tex"
                )
                self.statusBar().showMessage("Reporte LaTeX exportado")
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "No fue posible exportar", str(exc))

    def analysis_widget_import_csv(self, *_args) -> None:
        self.analysis_widget.import_csv()

    def download_corridor_template(self, *_args) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Plantilla del corredor", "plantilla_simulation.csv", "CSV (*.csv)"
        )
        if path:
            try:
                write_template(
                    path if path.lower().endswith(".csv") else path + ".csv", "simulation"
                )
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, "No fue posible exportar", str(exc))

    def prepare_analysis_simulation(self, result: dict) -> None:
        if self._busy:
            return
        length, accepted = QInputDialog.getDouble(
            self,
            "Geometría del corredor",
            "Longitud a simular (m):",
            self.length_spin.value(),
            5,
            2000,
            3,
        )
        if not accepted:
            return
        share, accepted = QInputDialog.getDouble(
            self,
            "Distribución por sentido",
            "Porcentaje de la demanda que circula A → B:",
            50,
            0,
            100,
            2,
        )
        if not accepted:
            return
        x = result["inputs"]
        period = 5 if result["method"] == "platoon" else x["period_min"]
        total = x["count"] * 60 / period
        scenario = asdict(self._scenario_from_ui())
        scenario.update(
            length_m=length,
            width_m=result["metrics"]["Ancho efectivo (m)"],
            flow_ab_pph=total * share / 100,
            flow_ba_pph=total * (1 - share / 100),
            walking_speed_mps=x["speed_mps"],
            analysis_time_s=period * 60,
        )
        candidate = CorridorScenario(**scenario)
        if candidate.validate():
            QMessageBox.warning(self, "Escenario fuera de rango", "\n".join(candidate.validate()))
            return
        self._import_corridor(scenario)
        self.statusBar().showMessage("Escenario preparado; pulse Simular corredor para ejecutarlo.")

    def _import_corridor(self, values: dict) -> None:
        scenario = CorridorScenario(**values)
        pairs = (
            (self.length_spin, scenario.length_m),
            (self.width_spin, scenario.width_m),
            (self.flow_ab_spin, scenario.flow_ab_pph),
            (self.flow_ba_spin, scenario.flow_ba_pph),
            (self.speed_spin, scenario.walking_speed_mps),
            (self.period_spin, scenario.analysis_time_s / 60),
            (self.seed_spin, scenario.seed),
        )
        for widget, value in pairs:
            widget.setValue(value)
        self._update_preview()
        self.tabs.setCurrentIndex(4)
        self._mark_dirty()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._busy:
            QMessageBox.information(
                self, "Simulación en curso", "Espere a que termine la simulación antes de cerrar."
            )
            event.ignore()
            return
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def simulate_example(self, *_args) -> None:
        from walksim.domain.walkway import new_case

        panel = self.walkway_widget
        if self._busy:
            return
        if len(panel.cases) >= 30:
            QMessageBox.information(self, "Escenarios", "El estudio admite máximo 30 escenarios.")
            return
        example = new_case("Ejemplo de corredor")
        panel.cases.append(example)
        panel.selected_id = example["id"]
        panel._refresh_selector()
        panel._load_current()
        self.tabs.setCurrentIndex(2)
        self._mark_dirty()
        panel.simulate()

    def _crossing_busy(self, busy: bool) -> None:
        self._busy = busy
        self._set_busy(busy)
        self.statusBar().showMessage("Simulando cruce…" if busy else "Cruce listo para revisar")

    def _shared_busy(self, busy: bool) -> None:
        self._busy = busy
        self._set_busy(busy)
        self.statusBar().showMessage(
            "Simulando sendero compartido…" if busy else "Sendero listo para revisar"
        )

    def _plaza_busy(self, busy: bool) -> None:
        self._busy = busy
        self._set_busy(busy)
        self.statusBar().showMessage("Simulando plaza…" if busy else "Plaza lista para revisar")

    def _access_busy(self, busy: bool) -> None:
        self._busy = busy
        self._set_busy(busy)
        self.statusBar().showMessage(
            "Simulando accesos y colas…" if busy else "Acceso listo para revisar"
        )

    def _walkway_busy(self, busy: bool) -> None:
        self._busy = busy
        self._set_busy(busy)
        self.statusBar().showMessage(
            "Ejecutando escenario Walkway…" if busy else "Escenario Walkway listo para revisar"
        )

    def show_guide(self, *_args, methodology: bool = False) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Metodología" if methodology else "Guía de uso · WalkSim 3")
        dialog.resize(
            min(760, self.screen().availableGeometry().width()),
            min(640, self.screen().availableGeometry().height()),
        )
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        if methodology:
            browser.setHtml(
                "<h1>Walkway · método y mediciones</h1>"
                "<p>HCM 7, capítulo 24, tablas 24-1 y 24-2: LOS por espacio peatonal, "
                "con umbrales convertidos exactamente a SI.</p>"
                "<p>Qd = Qh / PHF para demanda horaria. Si se proporciona un conteo directo, "
                "se usa Qd = 60N/T sin volver a aplicar PHF. T es 15 min en flujo aleatorio "
                "y 5 min para pelotones. Un PHF de 15 min no sustituye el conteo de 5 min.</p>"
                "<p>q = Qd/(60 WE), D = q/(60 S), M = 1/D. El diseño inverso busca un ancho "
                "o demanda admisible con margen para cumplir un LOS objetivo o mejor. "
                "Depende de la velocidad introducida; no predice ni calibra esa velocidad.</p>"
                "<p>La ocupación se integra durante el periodo observado posterior al "
                "calentamiento. "
                "Los tiempos corresponden a la cohorte que entra en ese periodo y termina antes "
                "del fin del despeje. El LOS simulado es indicativo del promedio global.</p>"
                "<p>La pendiente ≤5 % se documenta con la velocidad introducida. Los obstáculos "
                "reducen el ancho útil uniforme; no se dibujan como obstáculos puntuales. "
                "El ancho calculado no sustituye mínimos normativos de accesibilidad.</p>"
            )
        else:
            browser.setHtml(
                "<h1>Su primer estudio Walkway</h1>"
                "<ol><li>En Proyecto, indique nombre, ubicación y analista.</li>"
                "<li>En Walkway elija evaluar operación, diseñar ancho o calcular "
                "demanda admisible.</li>"
                "<li>Introduzca la geometría y la demanda horaria con PHF, o el conteo "
                "directo.</li>"
                "<li>Pulse Calcular escenario. Revise LOS, ancho útil y demanda/capacidad.</li>"
                "<li>Use Duplicar escenario para crear alternativas y la pestaña "
                "Comparar para evaluarlas.</li>"
                "<li>Despliegue Opciones de microsimulación para ajustar "
                "calentamiento, periodo y semilla. "
                "Pulse Ejecutar microsimulación para obtener la comparación y las gráficas.</li>"
                "<li>En Archivo guarde .wksim y exporte el reporte .tex. Los archivos "
                "2.1 se pueden abrir; "
                "guarde una copia en formato 3 para conservar el original.</li></ol>"
                "<p>Los cambios de datos marcan los resultados como pendientes de actualización. "
                "Los valores predeterminados se distinguen de los introducidos u observados.</p>"
                "<h2>Sendero compartido</h2><p>Elija PLOS, BLOS o ambos; "
                "indique flujos por sentido "
                "o conteos de 15 min. Para BLOS documente la probabilidad de demora de rebases, "
                "directamente o con intentos y demorados observados. Sin esos datos BLOS es N/A. "
                "Calcule y simule para comparar tasas de eventos y tiempos por grupo.</p>"
                "<h2>Plaza y flujos cruzados</h2><p>Seleccione plantilla y accesos, introduzca las "
                "tasas OD en peat/h o importe una matriz. Calcule la geometría y ejecute Simular "
                "mis datos. En Gráficas elija el mapa; Resultados OD muestra "
                "tiempos por movimiento. "
                "La matriz guía y las plantillas de escenarios se descargan desde el módulo.</p>"
                "<h2>Accesos y colas</h2><p>Abra la pestaña Accesos y colas "
                "y elija acceso individual "
                "o Metro. Configure dispositivos, demanda, áreas y periodos. Calcular capacidad "
                "obtiene la relación demanda/capacidad; Simular mis datos ejecuta los recorridos "
                "y la atención. Duplique el caso para comparar otra cantidad de torniquetes.</p>"
                "<p>Descarga masiva pide pasajeros, duración e intervalo entre trenes. "
                "Método y datos explica la cola equivalente y sus límites. El servicio de "
                "escaleras se introduce como capacidad; la geometría vertical corresponde "
                "a una fase posterior.</p>"
            )
        layout.addWidget(browser)
        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "Acerca de WalkSim Mobility",
            f"<b>WalkSim Mobility {__version__}</b><br><br>"
            "Simulación y análisis de movilidad peatonal.<br><br>"
            "Desarrollador: Héctor Alonso Benítez García<br>"
            "Licencia: GNU GPL v3.0",
        )
