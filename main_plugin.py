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
        self.action.setToolTip("Open the QGIS 2.5D Styling panel")
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_dock)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu("QGIS 2.5D Styling", self.action)

    def toggle_dock(self, visible=None) -> None:
        _RightDock = getattr(getattr(Qt, "DockWidgetArea", Qt), "RightDockWidgetArea", getattr(Qt, "RightDockWidgetArea", 2))
        if not self.dock:
            self.dock = StylingDockWidget(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(_RightDock, self.dock)
            if self.action:
                self.dock.visibilityChanged.connect(self.action.setChecked)
            main_window = self.iface.mainWindow()
            horizontal = getattr(getattr(Qt, "Orientation", Qt), "Horizontal", getattr(Qt, "Horizontal", 1))
            vertical = getattr(getattr(Qt, "Orientation", Qt), "Vertical", getattr(Qt, "Vertical", 2))
            main_window.resizeDocks([self.dock], [420], horizontal)
            main_window.resizeDocks([self.dock], [720], vertical)
        should_show = (not self.dock.isVisible()) if visible is None else bool(visible)
        self.dock.setVisible(should_show)
        if should_show:
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
                self.action.setParent(None)
                self.action.deleteLater()
                self.action = None

            if self.dock:
                self.dock.cancel_download()
                self.iface.removeDockWidget(self.dock)
                self.dock.setParent(None)
                self.dock.deleteLater()
                self.dock = None
