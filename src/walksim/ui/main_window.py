"""Ventana principal de WalkSim Mobility."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QBoxLayout,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
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
from walksim.domain.models import CorridorScenario, DirectionResult
from walksim.sumo.runner import SumoExecutionError, run_corridor_simulation
from walksim.ui.styles import apply_theme, theme_colors


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

    def _create_actions(self) -> None:
        self.simulate_action = QAction("Simular corredor", self)
        self.simulate_action.setShortcut("F5")
        self.simulate_action.triggered.connect(self.simulate)

        self.repository_action = QAction("Abrir repositorio", self)
        self.repository_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/VanLinux/walksim-mobility"))
        )

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
        file_menu.addAction(self.quit_action)

        simulation_menu = self.menuBar().addMenu("Simulación")
        simulation_menu.addAction(self.simulate_action)

        appearance_menu = self.menuBar().addMenu("Apariencia")
        appearance_menu.addActions(self.theme_actions.actions())

        help_menu = self.menuBar().addMenu("Ayuda")
        help_menu.addActions([self.repository_action, self.about_action])

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
        subtitle = QLabel("Simulación y análisis de movilidad peatonal")
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
        root.addWidget(self.tabs, 1)

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
              <b>Alcance de la versión 2.0</b><br>
              Corredor peatonal recto y bidireccional con demanda A → B y B → A.
              WalkSim analiza el escenario y presenta tiempos, velocidades
              y recorridos completados.
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
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(parameters)

        model_note = QLabel("Corredor recto y bidireccional de ancho uniforme.")
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

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "metric_cards"):
            self._apply_responsive_layout()

    def _apply_responsive_layout(self) -> None:
        width = self.width()
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

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage("Simulando corredor…")

        try:
            run = run_corridor_simulation(scenario)
        except (SumoExecutionError, OSError, ValueError):
            logging.getLogger(__name__).exception("Error al simular el corredor")
            QMessageBox.critical(
                self,
                "No fue posible simular",
                "No se pudo completar la simulación. Revise los parámetros y la "
                "instalación según los requisitos del repositorio.",
            )
            self.statusBar().showMessage("Simulación no ejecutada")
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

        self.result_status.setText(f"Simulación completada · semilla {scenario.seed}")
        self.output_label.setText("Archivos temporales del escenario: " + str(run.files.workdir))

        self.tabs.setCurrentIndex(3)
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
            "Simulación y análisis de movilidad peatonal.<br><br>"
            "Desarrollador: Héctor Alonso Benítez García<br>"
            "Licencia: GNU GPL v3.0",
        )
