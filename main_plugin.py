# -*- coding: utf-8 -*-
"""Main plugin entry point for QGIS 2.5D Styling."""
from __future__ import annotations

import os
from contextlib import suppress

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .processing.provider import Qgis25DStylingProvider
from .ui.styling_dock import StylingDockWidget


class Qgis25DStylingPlugin:
    """Top-level QGIS plugin: toolbar action + menu + right-docked studio panel + Processing provider."""

    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None
        self.provider = None

    def initProcessing(self) -> None:
        if self.provider is not None:
            return
        self.provider = Qgis25DStylingProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self) -> None:
        self.initProcessing()
        if not self.iface:
            return

        icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, "QGIS 2.5D Styling", self.iface.mainWindow())
        self.action.setToolTip("Open QGIS 2.5D Styling Studio (Right Dock Panel)")
        self.action.triggered.connect(self.toggle_dock)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu("QGIS 2.5D Styling", self.action)

        # Create Right-Docked Panel
        self.dock = StylingDockWidget(self.iface, self.iface.mainWindow())
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.hide()

    def toggle_dock(self) -> None:
        if not self.dock:
            self.dock = StylingDockWidget(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.show()
            self.dock.raise_()
            self.dock.activateWindow()

    def unload(self) -> None:
        if self.provider:
            with suppress(Exception):
                QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

        if self.iface:
            if self.action:
                self.iface.removePluginVectorMenu("QGIS 2.5D Styling", self.action)
                self.iface.removeToolBarIcon(self.action)
                self.action = None

            if self.dock:
                self.iface.removeDockWidget(self.dock)
                self.dock.deleteLater()
                self.dock = None
