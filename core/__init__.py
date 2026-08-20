# -*- coding: utf-8 -*-
"""Core computation, acquisition and styling modules for QGIS 2.5D Styling."""
from .osm_downloader import (
    OsmDownloadError,
    build_overpass_building_query,
    fetch_overpass_json,
    osm_json_to_vector_layer,
    parse_numeric_height,
    parse_numeric_levels,
)
from .presets import PRESETS, STANDARD_ANGLES
from .qml_exporter import export_layer_qml, load_layer_qml
from .twopointfive_engine import (
    apply_25d_style,
    apply_geometry_generator_25d_style,
    apply_native_25d_renderer,
    apply_preset_to_layer,
    build_height_expression,
    hex_to_qcolor,
)

__all__ = [
    "OsmDownloadError",
    "build_overpass_building_query",
    "fetch_overpass_json",
    "osm_json_to_vector_layer",
    "parse_numeric_height",
    "parse_numeric_levels",
    "PRESETS",
    "STANDARD_ANGLES",
    "export_layer_qml",
    "load_layer_qml",
    "apply_25d_style",
    "apply_geometry_generator_25d_style",
    "apply_native_25d_renderer",
    "apply_preset_to_layer",
    "build_height_expression",
    "hex_to_qcolor",
]
