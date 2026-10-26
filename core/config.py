# -*- coding: utf-8 -*-
"""Configuration contract for the dedicated 2.5D styling workflow."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


DEFAULT_CONFIG: Dict[str, Any] = {
    "render_mode": "per_floor_bands",
    "height_field": "",
    "height_unit": "auto",
    "height_multiplier": 1.0,
    "default_height": 9.0,
    "default_levels": 3,
    "projection_angle": 45.0,
    "wall_color": "#7fb8b0",
    "roof_color": "#f7c3a1",
    "outline_color": "#3f6d66",
    "outline_width": 0.3,
    "roof_outline_color": "#b97350",
    "roof_outline_width": 0.4,
    "facade_shading": True,
    "sun_azimuth": 315.0,
    "shading_intensity": 0.4,
    "shadow_enabled": True,
    "shadow_color": "#0f172a",
    "shadow_alpha": 40,
    "shadow_blur": 4.0,
    "shadow_length": 0.6,
    "floor_bands_enabled": True,
    "floor_height_m": 3.2,
    "floor_line_color": "#cbd5e1",
    "floor_line_width": 0.2,
    "floor_palette": "teal_peach",
    "max_floors": 0,
}

HEIGHT_FIELD_CANDIDATES = (
    "height",
    "building_height",
    "building:height",
    "building_levels",
    "building:levels",
    "levels",
    "floors",
    "storeys",
    "stories",
    "yukseklik",
    "bina_yuksekligi",
    "kat_sayisi",
    "kat_adedi",
    "kat",
    "h",
)

HEIGHT_UNITS = ("auto", "meters", "floors")


def _clamp(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    return min(high, max(low, number))


def normalize_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a complete, bounded configuration accepted by every renderer."""
    result = dict(DEFAULT_CONFIG)
    if config:
        result.update(config)

    mode = str(result.get("render_mode", "geometry_generator"))
    if mode not in {"geometry_generator", "per_floor_bands", "native"}:
        mode = "geometry_generator"
    result["render_mode"] = mode
    result["use_geometry_generator"] = mode == "geometry_generator"
    result["per_floor_bands"] = mode == "per_floor_bands"

    result["height_field"] = str(result.get("height_field") or "").strip()
    unit = str(result.get("height_unit") or "auto").strip().lower()
    result["height_unit"] = unit if unit in HEIGHT_UNITS else "auto"
    result["height_multiplier"] = _clamp(result.get("height_multiplier"), 0.05, 20.0, 1.0)
    result["default_height"] = _clamp(result.get("default_height"), 0.5, 1000.0, 9.0)
    result["default_levels"] = int(_clamp(result.get("default_levels"), 1, 100, 3))
    result["projection_angle"] = _clamp(result.get("projection_angle"), 0.0, 359.0, 45.0)
    result["sun_azimuth"] = _clamp(result.get("sun_azimuth"), 0.0, 359.0, 315.0)
    result["shading_intensity"] = _clamp(result.get("shading_intensity"), 0.0, 1.0, 0.4)
    result["shadow_alpha"] = int(_clamp(result.get("shadow_alpha"), 0, 100, 40))
    result["shadow_blur"] = _clamp(result.get("shadow_blur"), 0.0, 50.0, 4.0)
    result["shadow_length"] = _clamp(result.get("shadow_length"), 0.05, 3.0, 0.6)
    result["outline_width"] = _clamp(result.get("outline_width"), 0.0, 5.0, 0.3)
    result["roof_outline_width"] = _clamp(result.get("roof_outline_width"), 0.0, 5.0, 0.4)
    result["floor_height_m"] = _clamp(result.get("floor_height_m"), 0.5, 20.0, 3.2)
    result["floor_line_width"] = _clamp(result.get("floor_line_width"), 0.0, 5.0, 0.2)
    result["max_floors"] = int(_clamp(result.get("max_floors"), 0, 100, 0))

    for key in ("facade_shading", "shadow_enabled", "floor_bands_enabled"):
        result[key] = bool(result.get(key))
    for key in (
        "wall_color", "roof_color", "outline_color", "roof_outline_color",
        "shadow_color", "floor_line_color",
    ):
        value = str(result.get(key) or DEFAULT_CONFIG[key]).strip()
        result[key] = value if value.startswith("#") else f"#{value}"
    return result


def choose_height_field(field_names: Iterable[str]) -> str:
    """Choose the most conventional height or level field, case-insensitively."""
    names = [str(name) for name in field_names]
    lookup = {name.casefold(): name for name in names}
    for candidate in HEIGHT_FIELD_CANDIDATES:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return ""


def compass_direction(angle: Any) -> str:
    """Return the nearest eight-point compass label for an azimuth (clockwise from north)."""
    value = _clamp(angle, 0.0, 359.999, 0.0)
    labels = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return labels[int((value + 22.5) // 45.0) % 8]


def extrusion_compass(angle: Any) -> str:
    """Compass label of the direction roofs are pushed by a projection angle.

    Projection angles follow QGIS's own 2.5D renderer: degrees counter-clockwise
    from east (0 = E, 90 = N), so 45 leans roofs to the NE and 135 to the NW.
    """
    value = _clamp(angle, 0.0, 359.999, 0.0)
    return compass_direction((90.0 - value) % 360.0)
