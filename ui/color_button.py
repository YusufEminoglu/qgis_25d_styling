# -*- coding: utf-8 -*-
"""Color button widget with live preview chip and QColorDialog integration."""
from __future__ import annotations

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QColorDialog, QPushButton, QWidget

class ColorPickerButton(QPushButton):
    """Reliable color picker button with color chip, hex display, and colorChanged signal."""

    colorChanged = pyqtSignal(QColor)

    def __init__(self, default_color: str = "#ffffff", parent: QWidget = None):
        super().__init__(parent)
        self._color = QColor(default_color)
        self.clicked.connect(self._choose_color)
        self._update_display()

    def color(self) -> QColor:
        return self._color

    def setColor(self, color: QColor | str) -> None:
        candidate = QColor(color)
        if not candidate.isValid():
            return
        self._color = candidate
        self._update_display()
        self.colorChanged.emit(self._color)

    def _update_display(self) -> None:
        hex_code = self._color.name()
        # Luminance calculation to choose contrasting text
        lum = 0.299 * self._color.red() + 0.587 * self._color.green() + 0.114 * self._color.blue()
        text_color = "#000000" if lum > 140 else "#ffffff"
        self.setText(hex_code.upper())
        self.setAccessibleName(f"Color {hex_code.upper()}")
        self.setStyleSheet(
            f"QPushButton {{ background-color: {hex_code}; color: {text_color}; "
            f"font-weight: bold; border: 1px solid #94a3b8; border-radius: 4px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ border: 2px solid #2563eb; }}"
        )

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(self._color, self, "Select Color")
        if chosen.isValid():
            self.setColor(chosen)
