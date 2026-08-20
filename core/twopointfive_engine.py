# -*- coding: utf-8 -*-
"""2.5D Architectural Extrusion, Lighting, and Geometry Generator Engine."""
from __future__ import annotations

import contextlib
import math
from typing import Any, Dict, Optional, Union

try:
    from qgis.core import (
        Qgis,
        Qgs25DRenderer,
        QgsColorRamp,
        QgsExpression,
        QgsFeatureRenderer,
        QgsFillSymbol,
        QgsGeometryGeneratorSymbolLayer,
        QgsLineSymbol,
        QgsProperty,
        QgsSimpleFillSymbolLayer,
        QgsSimpleLineSymbolLayer,
        QgsSingleSymbolRenderer,
        QgsSymbol,
        QgsSymbolLayer,
        QgsRuleBasedRenderer,
        QgsFeatureRequest,
        QgsUnitTypes,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor
except ImportError:
    Qgis = None
    Qgs25DRenderer = None
    QgsColorRamp = None
    QgsExpression = None
    QgsFeatureRenderer = None
    QgsFillSymbol = None
    QgsGeometryGeneratorSymbolLayer = None
    QgsLineSymbol = None
    QgsProperty = None
    QgsSimpleFillSymbolLayer = None
    QgsSimpleLineSymbolLayer = None
    QgsSingleSymbolRenderer = None
    QgsRuleBasedRenderer = None
    QgsFeatureRequest = None
    QgsSymbol = None
    QgsSymbolLayer = None
    QgsUnitTypes = None
    QgsVectorLayer = None
    Qt = None
    QColor = None

from .presets import FLOOR_BAND_PALETTES, PRESETS


_BrushSolid = getattr(getattr(Qt, "BrushStyle", Qt), "SolidPattern", getattr(Qt, "SolidPattern", 1)) if Qt else 1
_PenSolid = getattr(getattr(Qt, "PenStyle", Qt), "SolidLine", getattr(Qt, "SolidLine", 1)) if Qt else 1
_PenNone = getattr(getattr(Qt, "PenStyle", Qt), "NoPen", getattr(Qt, "NoPen", 0)) if Qt else 0


def hex_to_qcolor(val: Union[str, QColor], alpha: int = 255) -> QColor:
    """Convert hex string or QColor to valid QColor with specified alpha."""
    if isinstance(val, QColor):
        c = QColor(val)
        c.setAlpha(alpha)
        return c
    s = str(val).strip()
    c = QColor(s) if s.startswith("#") else QColor(f"#{s}")
    if not c.isValid():
        c = QColor("#ffffff")
    c.setAlpha(alpha)
    return c


def build_height_expression(
    field_or_expr: str = "height",
    multiplier: float = 1.0,
    default_height: float = 9.0,
) -> str:
    """Build a robust SQL/QGIS expression that calculates building height in meters."""
    field_clean = field_or_expr.strip()
    mult_str = f" * {multiplier:.4f}" if abs(multiplier - 1.0) > 1e-4 else ""

    if field_clean in ("height", "building_levels", "min_height"):
        return (
            f'(coalesce(try("height"), try("building_levels") * 3.0, {default_height:.1f}){mult_str})'
        )
    if field_clean:
        return f'(coalesce(try("{field_clean}"), {default_height:.1f}){mult_str})'
    return f"({default_height:.1f}{mult_str})"


def apply_native_25d_renderer(
    layer: QgsVectorLayer,
    config: Dict[str, Any],
) -> bool:
    """Configure and apply QGIS native Qgs25DRenderer to a polygon vector layer."""
    if not layer or not layer.isValid():
        return False

    h_expr = build_height_expression(
        config.get("height_field", "height"),
        config.get("height_multiplier", 1.0),
        config.get("default_height", 9.0),
    )

    angle_deg = float(config.get("projection_angle", 45.0))
    sun_angle = float(config.get("sun_azimuth", 315.0))
    wall_col = hex_to_qcolor(config.get("wall_color", "#e2e8f0"))
    roof_col = hex_to_qcolor(config.get("roof_color", "#ffffff"))

    shadow_enabled = bool(config.get("shadow_enabled", True))
    shadow_alpha = int(config.get("shadow_alpha", 40) * 2.55)
    shadow_col = hex_to_qcolor(config.get("shadow_color", "#0f172a"), shadow_alpha)
    shadow_spread = float(config.get("shadow_blur", 4.0))

    shading_enabled = bool(config.get("facade_shading", True))

    # Qgs25DRenderer uses layer custom properties for expression bindings
    layer.setCustomProperty("qgis_25d_height", h_expr)
    layer.setCustomProperty("qgis_25d_angle", str(angle_deg))
    layer.setCustomProperty("qgis_25d_sun_angle", str(sun_angle))
    layer.setCustomProperty("qgis_25d_shadow_enabled", "true" if shadow_enabled else "false")

    renderer = Qgs25DRenderer()
    renderer.setRoofColor(roof_col)
    renderer.setWallColor(wall_col)
    renderer.setShadowColor(shadow_col)
    renderer.setShadowEnabled(shadow_enabled)
    renderer.setShadowSpread(shadow_spread)
    renderer.setWallShadingEnabled(shading_enabled)

    layer.setRenderer(renderer)
    layer.triggerRepaint()
    return True


def apply_geometry_generator_25d_style(
    layer: QgsVectorLayer,
    config: Dict[str, Any],
) -> bool:
    """Build an advanced multi-layer Geometry Generator symbol with floor lines and sun shading."""
    if not layer or not layer.isValid():
        return False

    h_expr = build_height_expression(
        config.get("height_field", "height"),
        config.get("height_multiplier", 1.0),
        config.get("default_height", 9.0),
    )

    angle_deg = float(config.get("projection_angle", 45.0))
    angle_rad = math.radians(angle_deg)

    # Unit displacement components along projection vector
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)

    wall_col = hex_to_qcolor(config.get("wall_color", "#e2e8f0"))
    roof_col = hex_to_qcolor(config.get("roof_color", "#ffffff"))
    outline_col = hex_to_qcolor(config.get("outline_color", "#475569"))
    outline_width = float(config.get("outline_width", 0.3))

    shadow_enabled = bool(config.get("shadow_enabled", True))
    shadow_alpha = int(config.get("shadow_alpha", 40) * 2.55)
    shadow_col = hex_to_qcolor(config.get("shadow_color", "#0f172a"), shadow_alpha)

    floor_bands = bool(config.get("floor_bands_enabled", False))
    floor_h = float(config.get("floor_height_m", 3.0))
    floor_line_col = hex_to_qcolor(config.get("floor_line_color", "#cbd5e1"))
    floor_line_width = float(config.get("floor_line_width", 0.2))

    roof_outline_col = hex_to_qcolor(config.get("roof_outline_color", outline_col.name()))
    roof_outline_width = float(config.get("roof_outline_width", outline_width))

    sun_azimuth = float(config.get("sun_azimuth", 315.0))
    shading_intensity = float(config.get("shading_intensity", 0.4))

    # If layer CRS is geographic (degrees, EPSG:4326), height in meters needs scale conversion
    scale_factor = 1.0
    if layer.crs().isValid() and layer.crs().isGeographic():
        # 1 meter ~ 0.000009 degrees at equator
        scale_factor = 1.0 / 111320.0

    eff_h = f"({h_expr}) * {scale_factor:.8f}" if scale_factor != 1.0 else f"({h_expr})"

    # Base Fill Symbol
    fill_symbol = QgsFillSymbol()
    while fill_symbol.symbolLayerCount() > 0:
        fill_symbol.deleteSymbolLayer(0)

    sym_fill_type = getattr(getattr(Qgis, "SymbolType", Qgis), "Fill", 2)
    sym_line_type = getattr(getattr(Qgis, "SymbolType", Qgis), "Line", 1)
    map_unit = getattr(QgsUnitTypes, "RenderMapUnits", getattr(QgsUnitTypes, "RenderMillimeters", 1))

    # ── 1. Ground Drop Shadow (Optional) ──
    if shadow_enabled:
        sun_rad = math.radians(sun_azimuth)
        # Shadow projects opposite to sun
        shadow_dx = -math.sin(sun_rad) * 0.6
        shadow_dy = -math.cos(sun_rad) * 0.6
        shadow_expr = (
            f"order_parts(translate($geometry, {shadow_dx:.6f} * {eff_h}, {shadow_dy:.6f} * {eff_h}), 'distance($geometry, @map_extent_center)', False)"
        )
        shadow_gen = QgsGeometryGeneratorSymbolLayer.create({
            "SymbolType": "Fill",
            "geometryModifier": shadow_expr,
            "units": "MapUnit",
        })
        shadow_gen.setSymbolType(sym_fill_type)
        shadow_gen.setGeometryExpression(shadow_expr)
        shadow_gen.setUnits(map_unit)

        shadow_fill = QgsSimpleFillSymbolLayer(shadow_col, _BrushSolid, QColor(0, 0, 0, 0))
        shadow_fill.setStrokeStyle(_PenNone)
        shadow_sub_sym = QgsFillSymbol()
        while shadow_sub_sym.symbolLayerCount() > 0:
            shadow_sub_sym.deleteSymbolLayer(0)
        shadow_sub_sym.appendSymbolLayer(shadow_fill)
        shadow_gen.setSubSymbol(shadow_sub_sym)
        fill_symbol.appendSymbolLayer(shadow_gen)

    # ── 2. Extruded Walls / Facades with Lighting ──
    # Extrude perimeter segments to form 3D vertical wall quadrilaterals
    wall_expr = (
        f"order_parts(extrude(segments_to_lines($geometry), {dx:.6f} * {eff_h}, {dy:.6f} * {eff_h}), "
        f"'distance($geometry, translate(@map_extent_center, 1000 * @map_extent_width * cos(radians({angle_deg:.1f} + 180)), "
        f"1000 * @map_extent_width * sin(radians({angle_deg:.1f} + 180))))', False)"
    )
    wall_gen = QgsGeometryGeneratorSymbolLayer.create({
        "SymbolType": "Fill",
        "geometryModifier": wall_expr,
        "units": "MapUnit",
    })
    wall_gen.setSymbolType(sym_fill_type)
    wall_gen.setGeometryExpression(wall_expr)
    wall_gen.setUnits(map_unit)

    wall_fill = QgsSimpleFillSymbolLayer(
        wall_col, _BrushSolid, outline_col, _PenSolid, outline_width
    )
    # Solar shading data-defined color modulation if shading enabled
    if config.get("facade_shading", True):
        color_expr = (
            f"darker('{wall_col.name()}', "
            f"100 + to_int({shading_intensity * 60:.1f} * (1.0 - abs(sin(radians({sun_azimuth:.1f} - {angle_deg:.1f}))))))"
        )
        wall_fill.setDataDefinedProperty(
            QgsSymbolLayer.PropertyFillColor,
            QgsProperty.fromExpression(color_expr),
        )
    wall_sub_sym = QgsFillSymbol()
    while wall_sub_sym.symbolLayerCount() > 0:
        wall_sub_sym.deleteSymbolLayer(0)
    wall_sub_sym.appendSymbolLayer(wall_fill)
    wall_gen.setSubSymbol(wall_sub_sym)
    fill_symbol.appendSymbolLayer(wall_gen)

    # ── 3. Floor Band Division Lines (Optional) ──
    if floor_bands and floor_h > 0.5:
        eff_floor_h = floor_h * scale_factor
        floor_expr = (
            f"collect_geometries(\n"
            f"  array_foreach(\n"
            f"    generate_series(1, to_int({eff_h} / {eff_floor_h:.6f})),\n"
            f"    boundary(translate($geometry, {dx:.6f} * (@element * {eff_floor_h:.6f}), {dy:.6f} * (@element * {eff_floor_h:.6f})))\n"
            f"  )\n"
            f")"
        )
        floor_gen = QgsGeometryGeneratorSymbolLayer.create({
            "SymbolType": "Line",
            "geometryModifier": floor_expr,
            "units": "MapUnit",
        })
        floor_gen.setSymbolType(sym_line_type)
        floor_gen.setGeometryExpression(floor_expr)
        floor_gen.setUnits(map_unit)

        floor_line = QgsSimpleLineSymbolLayer(
            floor_line_col, floor_line_width, _PenSolid
        )
        floor_sub_sym = QgsLineSymbol()
        while floor_sub_sym.symbolLayerCount() > 0:
            floor_sub_sym.deleteSymbolLayer(0)
        floor_sub_sym.appendSymbolLayer(floor_line)
        floor_gen.setSubSymbol(floor_sub_sym)
        fill_symbol.appendSymbolLayer(floor_gen)

    # ── 4. Roof Cap Polygon ──
    roof_expr = (
        f"translate($geometry, {dx:.6f} * {eff_h}, {dy:.6f} * {eff_h})"
    )
    roof_gen = QgsGeometryGeneratorSymbolLayer.create({
        "SymbolType": "Fill",
        "geometryModifier": roof_expr,
        "units": "MapUnit",
    })
    roof_gen.setSymbolType(sym_fill_type)
    roof_gen.setGeometryExpression(roof_expr)
    roof_gen.setUnits(map_unit)

    roof_fill = QgsSimpleFillSymbolLayer(
        roof_col, _BrushSolid, roof_outline_col, _PenSolid, roof_outline_width
    )
    roof_sub_sym = QgsFillSymbol()
    while roof_sub_sym.symbolLayerCount() > 0:
        roof_sub_sym.deleteSymbolLayer(0)
    roof_sub_sym.appendSymbolLayer(roof_fill)
    roof_gen.setSubSymbol(roof_sub_sym)
    fill_symbol.appendSymbolLayer(roof_gen)

    renderer = QgsSingleSymbolRenderer(fill_symbol)
    layer.setRenderer(renderer)
    layer.emitStyleChanged()
    layer.triggerRepaint()
    return True


def floor_band_palette_color(floor_index: int, palette_key: str, wall: bool = False) -> QColor:
    """Get color for a specific floor band from a palette."""
    palette = FLOOR_BAND_PALETTES.get(palette_key, FLOOR_BAND_PALETTES.get("civic_spectrum", {}))
    colors = palette.get("colors", ("#f4d35e", "#ee964b", "#f95738", "#d7263d", "#9b5de5", "#00bbf9"))
    color_hex = colors[(max(1, int(floor_index)) - 1) % len(colors)]
    col = hex_to_qcolor(color_hex)
    if wall:
        return col.darker(120)
    return col


def estimate_layer_max_floors(
    layer: QgsVectorLayer,
    height_field: str,
    default_floor_h: float = 3.0,
    fallback_max: int = 12,
) -> int:
    """Scan layer attributes to find the maximum building floor count."""
    if not layer or not layer.isValid():
        return fallback_max

    fields = layer.fields()
    idx = fields.lookupField(height_field) if hasattr(fields, "lookupField") else fields.indexOf(height_field)
    if idx < 0:
        return fallback_max

    is_floor_field = any(tok in height_field.lower() for tok in ("level", "floor", "kat", "story", "storey"))

    max_val = 0.0
    with contextlib.suppress(Exception):
        for feat in layer.getFeatures():
            val = feat.attribute(idx)
            if val is not None:
                num = float(val)
                if num > max_val:
                    max_val = num

    if max_val <= 0:
        return fallback_max

    if is_floor_field:
        return max(1, min(60, int(round(max_val))))
    floors = int(round(max_val / max(0.5, default_floor_h)))
    return max(1, min(60, floors))


def apply_per_floor_bands_style(
    layer: QgsVectorLayer,
    config: Dict[str, Any],
) -> bool:
    """Apply classified per-floor colored 2.5D extrusion using Geometry Generator & Rule-Based Renderer."""
    if not layer or not layer.isValid():
        return False

    h_field = config.get("height_field", "height")
    h_scale = float(config.get("height_multiplier", 1.0))
    floor_h = float(config.get("floor_height_m", 3.0))
    palette_key = config.get("floor_palette", "civic_spectrum")

    is_floor_field = any(tok in h_field.lower() for tok in ("level", "floor", "kat", "story", "storey"))

    # Determine max floors
    max_floors_cfg = int(config.get("max_floors", 0))
    if max_floors_cfg > 0:
        max_floors = max(1, min(60, max_floors_cfg))
    else:
        max_floors = estimate_layer_max_floors(layer, h_field, floor_h, fallback_max=12)

    angle_deg = float(config.get("projection_angle", 45.0))
    angle_rad = math.radians(angle_deg)
    dx = math.cos(angle_rad)
    dy = math.sin(angle_rad)

    shadow_enabled = bool(config.get("shadow_enabled", True))
    shadow_alpha = int(config.get("shadow_alpha", 40) * 2.55)
    shadow_col = hex_to_qcolor(config.get("shadow_color", "#0f172a"), shadow_alpha)

    sun_azimuth = float(config.get("sun_azimuth", 315.0))
    shading_intensity = float(config.get("shading_intensity", 0.4))

    # CRS scale factor (if EPSG:4326)
    scale_factor = 1.0
    if layer.crs().isValid() and layer.crs().isGeographic():
        scale_factor = 1.0 / 111320.0

    eff_floor_h = floor_h * scale_factor * h_scale

    if is_floor_field:
        floor_count_expr = f"coalesce(to_int(round(try(\"{h_field}\"))), 3)"
    else:
        floor_count_expr = f"coalesce(to_int(round(try(\"{h_field}\") / {floor_h:.4f})), 3)"

    sym_fill_type = getattr(getattr(Qgis, "SymbolType", Qgis), "Fill", 2)
    map_unit = getattr(QgsUnitTypes, "RenderMapUnits", getattr(QgsUnitTypes, "RenderMillimeters", 1))

    root_rule = QgsRuleBasedRenderer.Rule(None)

    for i in range(1, max_floors + 1):
        sym = QgsFillSymbol()
        while sym.symbolLayerCount() > 0:
            sym.deleteSymbolLayer(0)

        band_bottom = (i - 1) * eff_floor_h
        band_top = i * eff_floor_h

        # 1. Ground Drop Shadow (on 1st floor rule)
        if i == 1 and shadow_enabled:
            sun_rad = math.radians(sun_azimuth)
            shadow_dx = -math.sin(sun_rad) * 0.6
            shadow_dy = -math.cos(sun_rad) * 0.6
            tot_h_expr = f"({floor_count_expr}) * {eff_floor_h:.6f}"
            shadow_expr = (
                f"order_parts(translate($geometry, {shadow_dx:.6f} * {tot_h_expr}, {shadow_dy:.6f} * {tot_h_expr}), "
                f"'distance($geometry, @map_extent_center)', False)"
            )
            sh_gen = QgsGeometryGeneratorSymbolLayer.create({
                "SymbolType": "Fill",
                "geometryModifier": shadow_expr,
                "units": "MapUnit",
            })
            sh_gen.setSymbolType(sym_fill_type)
            sh_gen.setGeometryExpression(shadow_expr)
            sh_gen.setUnits(map_unit)
            sh_fill = QgsSimpleFillSymbolLayer(shadow_col, _BrushSolid, QColor(0, 0, 0, 0))
            sh_fill.setStrokeStyle(_PenNone)
            sh_sub = QgsFillSymbol()
            while sh_sub.symbolLayerCount() > 0:
                sh_sub.deleteSymbolLayer(0)
            sh_sub.appendSymbolLayer(sh_fill)
            sh_gen.setSubSymbol(sh_sub)
            sym.appendSymbolLayer(sh_gen)

        # 2. Wall Facades for this floor band
        wall_col = floor_band_palette_color(i, palette_key, wall=True)
        roof_col = floor_band_palette_color(i, palette_key, wall=False)
        outline_col = wall_col.darker(140)

        wall_expr = (
            f"CASE WHEN ({floor_count_expr}) >= {i} THEN "
            f"order_parts(extrude(segments_to_lines(translate($geometry, {dx:.6f} * {band_bottom:.6f}, {dy:.6f} * {band_bottom:.6f})), "
            f"{dx:.6f} * {eff_floor_h:.6f}, {dy:.6f} * {eff_floor_h:.6f}), "
            f"'distance($geometry, translate(@map_extent_center, 1000 * @map_extent_width * cos(radians({angle_deg:.1f} + 180)), "
            f"1000 * @map_extent_width * sin(radians({angle_deg:.1f} + 180))))', False) END"
        )
        w_gen = QgsGeometryGeneratorSymbolLayer.create({
            "SymbolType": "Fill",
            "geometryModifier": wall_expr,
            "units": "MapUnit",
        })
        w_gen.setSymbolType(sym_fill_type)
        w_gen.setGeometryExpression(wall_expr)
        w_gen.setUnits(map_unit)

        w_fill = QgsSimpleFillSymbolLayer(wall_col, _BrushSolid, outline_col, _PenSolid, 0.25)
        if config.get("facade_shading", True):
            w_color_expr = (
                f"darker('{wall_col.name()}', "
                f"100 + to_int({shading_intensity * 60:.1f} * (1.0 - abs(sin(radians({sun_azimuth:.1f} - {angle_deg:.1f}))))))"
            )
            w_fill.setDataDefinedProperty(
                QgsSymbolLayer.PropertyFillColor,
                QgsProperty.fromExpression(w_color_expr),
            )
        w_sub = QgsFillSymbol()
        while w_sub.symbolLayerCount() > 0:
            w_sub.deleteSymbolLayer(0)
        w_sub.appendSymbolLayer(w_fill)
        w_gen.setSubSymbol(w_sub)
        sym.appendSymbolLayer(w_gen)

        # 3. Roof Cap for this floor band (only on the top floor of that building)
        if i >= max_floors:
            roof_cond = f"({floor_count_expr}) >= {i}"
            legend_label = f"Floor {i}+ ({i * floor_h:.1f}m+)"
        else:
            roof_cond = f"({floor_count_expr}) = {i}"
            legend_label = f"Floor {i} ({i * floor_h:.1f}m)"

        roof_expr = (
            f"CASE WHEN {roof_cond} THEN "
            f"translate($geometry, {dx:.6f} * {band_top:.6f}, {dy:.6f} * {band_top:.6f}) END"
        )
        r_gen = QgsGeometryGeneratorSymbolLayer.create({
            "SymbolType": "Fill",
            "geometryModifier": roof_expr,
            "units": "MapUnit",
        })
        r_gen.setSymbolType(sym_fill_type)
        r_gen.setGeometryExpression(roof_expr)
        r_gen.setUnits(map_unit)

        r_fill = QgsSimpleFillSymbolLayer(roof_col, _BrushSolid, roof_col.darker(130), _PenSolid, 0.3)
        r_sub = QgsFillSymbol()
        while r_sub.symbolLayerCount() > 0:
            r_sub.deleteSymbolLayer(0)
        r_sub.appendSymbolLayer(r_fill)
        r_gen.setSubSymbol(r_sub)
        sym.appendSymbolLayer(r_gen)

        child_rule = QgsRuleBasedRenderer.Rule(sym, 0, 0, "", legend_label)
        root_rule.appendChild(child_rule)

    renderer = QgsRuleBasedRenderer(root_rule)
    renderer.setUsingSymbolLevels(True)
    renderer.setOrderByEnabled(True)
    order_by_expr = (
        f"distance($geometry, translate(@map_extent_center, "
        f"1000 * @map_extent_width * cos(radians({angle_deg:.1f} + 180)), "
        f"1000 * @map_extent_width * sin(radians({angle_deg:.1f} + 180))))"
    )
    renderer.setOrderBy(QgsFeatureRequest.OrderBy([
        QgsFeatureRequest.OrderByClause(order_by_expr, False, True)
    ]))

    layer.setRenderer(renderer)
    layer.emitStyleChanged()
    layer.triggerRepaint()
    return True


def apply_25d_style(
    layer: QgsVectorLayer,
    config: Dict[str, Any],
) -> bool:
    """Master styling dispatcher: applies either per-floor bands, geometry generator, or native 2.5D renderer."""
    if not layer or not layer.isValid():
        return False

    render_mode = config.get("render_mode", "")
    if render_mode == "per_floor_bands" or config.get("per_floor_bands", False):
        return apply_per_floor_bands_style(layer, config)

    use_geom_gen = config.get("use_geometry_generator", True)
    if use_geom_gen:
        return apply_geometry_generator_25d_style(layer, config)
    return apply_native_25d_renderer(layer, config)


def apply_preset_to_layer(
    layer: QgsVectorLayer,
    preset_key: str,
    height_field: str = "height",
    height_multiplier: float = 1.0,
    use_geom_gen: bool = True,
) -> bool:
    """Apply one of the 8 curated architectural presets by key."""
    if preset_key not in PRESETS:
        preset_key = "swiss_minimalist"
    cfg = dict(PRESETS[preset_key])
    cfg["height_field"] = height_field
    cfg["height_multiplier"] = height_multiplier
    cfg["use_geometry_generator"] = use_geom_gen
    return apply_25d_style(layer, cfg)
