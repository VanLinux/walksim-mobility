"""Orden, descripciones e identificadores discretos de los espacios de trabajo."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

TAB_ORDER = (
    ("home", "Inicio"),
    ("project", "Proyecto"),
    ("walkway", "Walkway"),
    ("corridor_results", "Resultados del corredor"),
    ("corridor", "Corredor libre"),
    ("analyses", "Complementarios"),
    ("access", "Accesos y colas"),
    ("plaza", "Plaza y flujos cruzados"),
    ("shared", "Sendero compartido"),
    ("crossing", "Cruce semaforizado"),
)

LINKED_TABS = {"walkway", "corridor_results", "corridor", "analyses"}

SUMMARIES = {
    "walkway": "Calcula nivel de servicio, ancho o demanda admisible; compara escenarios "
    "y sus resultados de microsimulación.",
    "corridor_results": "Muestra los resultados y gráficas de Walkway o los tiempos y "
    "velocidades de Corredor libre, indicando su origen.",
    "corridor": "Simula un corredor recto con flujos en ambos sentidos y obtiene tiempos, "
    "velocidades y tiempo perdido.",
    "analyses": "Calcula ocupación, nivel de servicio o demora para aceras, esperas, "
    "escaleras y cruces mediante sus fórmulas específicas.",
    "access": "Calcula capacidad y demanda/capacidad; simula esperas, colas y tiempos de acceso.",
    "plaza": "Calcula geometría y demanda local; simula recorridos y obtiene tiempos "
    "y mapas de densidad.",
    "shared": "Calcula PLOS peatonal y BLOS ciclista por sentido; simula encuentros, "
    "rebases y tiempos de recorrido.",
    "crossing": "Estima el recorrido y simula un cruce semaforizado para obtener espera, "
    "colas y peatones que cruzan.",
}

RELATIONSHIPS = {
    "walkway": "Conectada: sus cálculos y simulaciones se consultan también en Resultados "
    "del corredor. Conserva sus propios escenarios.",
    "corridor_results": "Conectada: muestra resultados de Walkway o Corredor libre, "
    "sin mezclar sus datos.",
    "corridor": "Conectada: envía su simulación a Resultados del corredor. Puede recibir "
    "datos preparados desde Complementarios mediante su botón.",
    "analyses": "Conectada: algunos casos de acera y pelotones pueden preparar "
    "Corredor libre mediante su botón. Los demás cálculos son propios de esta ventana.",
}


def tab_icon(linked: bool, dark: bool = False) -> QIcon:
    pixmap = QPixmap(18, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#B9BCC1" if dark else "#737980"), 1.2))
    if linked:
        painter.drawEllipse(1, 4, 8, 8)
        painter.drawEllipse(9, 4, 8, 8)
        painter.drawLine(6, 8, 12, 8)
    else:
        painter.drawEllipse(5, 4, 8, 8)
    painter.end()
    return QIcon(pixmap)
