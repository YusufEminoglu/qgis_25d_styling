# -*- coding: utf-8 -*-
"""QML Style Exporter & Importer for 2.5D Building Symbology."""
from __future__ import annotations

import os
try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = None


def export_layer_qml(layer: QgsVectorLayer, output_path: str) -> bool:
    """Save the layer's current 2.5D renderer / symbology to a standard QGIS .qml style file."""
    if not layer or not layer.isValid():
        return False
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    msg, success = layer.saveNamedStyle(output_path)
    return success


def load_layer_qml(layer: QgsVectorLayer, qml_path: str) -> bool:
    """Load a .qml style file onto a target vector layer."""
    if not layer or not layer.isValid() or not os.path.isfile(qml_path):
        return False
    msg, success = layer.loadNamedStyle(qml_path)
    if success:
        layer.triggerRepaint()
    return success
