"""Descripción y contacto del autor, sin envíos automáticos de información."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from walksim import __version__

CONTACT_EMAIL = "prof.benitezgh@gmail.com"


def contact_url():
    return QUrl(
        "mailto:"
        + CONTACT_EMAIL
        + "?subject=Sugerencias%20o%20problemas%20con%20WalkSim%20Mobility"
    )


class ContactDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Contacto")
        layout = QVBoxLayout(self)
        text = QLabel("Héctor Alonso Benítez García\nSugerencias o problemas con WalkSim Mobility:")
        text.setWordWrap(True)
        layout.addWidget(text)
        email = QLabel(CONTACT_EMAIL)
        email.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(email)
        write = QPushButton("Escribir sugerencia…")
        write.clicked.connect(lambda: QDesktopServices.openUrl(contact_url()))
        layout.addWidget(write)
        copy = QPushButton("Copiar correo")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(CONTACT_EMAIL))
        layout.addWidget(copy)
        note = QLabel("Se abrirá su aplicación de correo. Revise el mensaje antes de enviarlo.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acerca de WalkSim Mobility")
        self.resize(520, 360)
        layout = QVBoxLayout(self)
        description = QLabel(
            f"WalkSim Mobility {__version__}\n\n"
            "Herramienta de análisis y microsimulación de movilidad peatonal y ciclista. "
            "Permite estudiar corredores, accesos y colas, plazas, senderos compartidos "
            "y cruces semaforizados, y comparar alternativas.\n\n"
            "Autor: Héctor Alonso Benítez García\n"
            "Software libre · GPL-3.0-only\nCopyright © 2026 Héctor Alonso Benítez García"
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        contact = QPushButton("Contacto")
        contact.clicked.connect(self._contact)
        layout.addWidget(contact)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _contact(self):
        dialog = ContactDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
