# -*- coding: utf-8 -*-
"""Processing Provider for QGIS 2.5D Styling."""
from __future__ import annotations

import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .alg_apply_25d_style import Apply25DStyleAlgorithm


class Qgis25DStylingProvider(QgsProcessingProvider):
    """Processing provider exposing the dedicated 2.5D styling algorithm."""

    def loadAlgorithms(self):
        self.addAlgorithm(Apply25DStyleAlgorithm())

    def id(self):
        return "qgis_25d_styling"

    def name(self):
        return "QGIS 2.5D Styling"

    def icon(self):
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "icons", "icon.png"
        )
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
