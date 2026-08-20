# -*- coding: utf-8 -*-
"""QGIS 2.5D Styling Plugin entry point."""
from __future__ import annotations


def classFactory(iface):
    """Load Qgis25DStylingPlugin class from main_plugin."""
    from .main_plugin import Qgis25DStylingPlugin

    return Qgis25DStylingPlugin(iface)
