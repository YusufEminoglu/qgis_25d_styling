# -*- coding: utf-8 -*-
"""2.5D building renderers: geometry-generator styles and QGIS's native 2.5D renderer.

The geometry-generator styles are rule-based renderers with two rendering
passes. The first pass draws every building's ground shadow; the second draws
the buildings one at a time from the back of the view to the front. QGIS's
rule-based renderer queues work per pass and, inside a pass, per feature, so
a later building's shadow can no longer darken a roof drawn before it, while
each building still covers whatever stands behind it.

Only facades that face the viewer are generated. Back faces are always hidden,
so drawing them costs time, and edges drawn on them (floor lines, corners)
used to show through the front facade.
"""
from __future__ import annotations

import contextlib
import math
from typing import Any, Dict, Iterable, List, Tuple, Union

try:
    from qgis.core import (
        Qgis,
        Qgs25DRenderer,
        QgsExpressionContextUtils,
        QgsFeatureRequest,
        QgsFillSymbol,
        QgsGeometryGeneratorSymbolLayer,
        QgsHashedLineSymbolLayer,
        QgsLineSymbol,
        QgsProperty,
        QgsRuleBasedRenderer,
        QgsSimpleFillSymbolLayer,
        QgsSimpleLineSymbolLayer,
        QgsSymbolLayer,
        QgsTemplatedLineSymbolLayerBase,
        QgsUnitTypes,
        QgsVectorLayer,
    )
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor
except ImportError:
    Qgis = None
    Qgs25DRenderer = None
    QgsExpressionContextUtils = None
    QgsFeatureRequest = None
    QgsFillSymbol = None
    QgsGeometryGeneratorSymbolLayer = None
    QgsHashedLineSymbolLayer = None
    QgsLineSymbol = None
    QgsProperty = None
    QgsRuleBasedRenderer = None
    QgsSimpleFillSymbolLayer = None
    QgsSimpleLineSymbolLayer = None
    QgsSymbolLayer = None
    QgsTemplatedLineSymbolLayerBase = None
    QgsUnitTypes = None
    QgsVectorLayer = None
    Qt = None
    QColor = None

from .config import normalize_config
from .heights import (
    field_kind,
    floor_count_expression,
    height_meters_expression,
    slab_count,
)
from .presets import FLOOR_BAND_PALETTES, PRESETS


_BrushSolid = getattr(getattr(Qt, "BrushStyle", Qt), "SolidPattern", getattr(Qt, "SolidPattern", 1)) if Qt else 1
_PenSolid = getattr(getattr(Qt, "PenStyle", Qt), "SolidLine", getattr(Qt, "SolidLine", 1)) if Qt else 1
_PenNone = getattr(getattr(Qt, "PenStyle", Qt), "NoPen", getattr(Qt, "NoPen", 0)) if Qt else 0

# Metres in one degree along a meridian; QGIS uses the same constant.
_METERS_PER_DEGREE = 111319.49079327357


def hex_to_qcolor(val: Union[str, "QColor"], alpha: int = 255) -> "QColor":
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


def _num(value: float) -> str:
    return f"{float(value):.10g}"


def _symbol_property(name: str):
    """QgsSymbolLayer property key, across the QGIS 3 and QGIS 4 enum spellings."""
    scoped = getattr(QgsSymbolLayer, "Property", None)
    for owner, attr in ((scoped, name), (QgsSymbolLayer, f"Property{name}"), (scoped, f"Property{name}")):
        if owner is not None and hasattr(owner, attr):
            return getattr(owner, attr)
    raise AttributeError(f"QgsSymbolLayer has no property {name}")


def _map_unit():
    render_unit = getattr(Qgis, "RenderUnit", None)
    if render_unit is not None and hasattr(render_unit, "MapUnits"):
        return render_unit.MapUnits
    return getattr(QgsUnitTypes, "RenderMapUnits", 3)


def meters_to_layer_units(layer) -> float:
    """Factor turning metres into the layer CRS's map units (degrees, feet, ...).

    Geometry generators work in the layer's own coordinates, so a 30 m
    building has to become 30 feet-equivalents or ~0.00027 degrees before it is
    added to a coordinate.
    """
    crs = layer.crs() if layer is not None else None
    if crs is None or not crs.isValid():
        return 1.0
    if crs.isGeographic():
        return 1.0 / _METERS_PER_DEGREE
    meters = getattr(getattr(Qgis, "DistanceUnit", None), "Meters", None)
    if meters is None:
        meters = getattr(QgsUnitTypes, "DistanceMeters", None)
    with contextlib.suppress(Exception):
        factor = float(QgsUnitTypes.fromUnitToUnitFactor(meters, crs.mapUnits()))
        if factor > 0 and math.isfinite(factor):
            return factor
    return 1.0


def build_height_expression(
    field_or_expr: str = "height",
    multiplier: float = 1.0,
    default_height: float = 9.0,
    floor_height: float = 3.2,
    unit: str = "auto",
    default_levels: int = 3,
) -> str:
    """Expression for a building's height in metres (kept for API compatibility)."""
    return height_meters_expression(
        field_or_expr, unit, multiplier, default_height, floor_height, default_levels
    )


def _new_symbol(symbol_class):
    symbol = symbol_class()
    while symbol.symbolLayerCount() > 0:
        symbol.deleteSymbolLayer(0)
    return symbol


def _generator(kind: str, expression: str, sub_layers: List[Any]):
    """A geometry-generator symbol layer drawing ``expression`` with ``sub_layers``."""
    is_line = kind == "Line"
    layer = QgsGeometryGeneratorSymbolLayer.create({
        "SymbolType": kind,
        "geometryModifier": expression,
    })
    symbol_type = getattr(getattr(Qgis, "SymbolType", Qgis), kind, 1 if is_line else 2)
    layer.setSymbolType(symbol_type)
    layer.setGeometryExpression(expression)
    if hasattr(layer, "setUnits"):
        layer.setUnits(_map_unit())
    sub = _new_symbol(QgsLineSymbol if is_line else QgsFillSymbol)
    for sub_layer in sub_layers:
        sub.appendSymbolLayer(sub_layer)
    layer.setSubSymbol(sub)
    return layer


def _depth_key(angle_deg: float, of_part: bool = False) -> str:
    """How far back a geometry sits along the projection direction.

    Buildings are ordered by their front-most corner and wall quads by their
    centre; larger values are further from the viewer and are drawn first.
    Only cheap bounding-box and centroid functions are used, because the key
    is evaluated for every feature and every wall on every redraw.
    """
    theta = math.radians(angle_deg)
    dx, dy = math.cos(theta), math.sin(theta)
    if of_part:
        return f"x(centroid($geometry)) * {_num(dx)} + y(centroid($geometry)) * {_num(dy)}"
    x_term = "x_min($geometry)" if dx >= 0 else "x_max($geometry)"
    y_term = "y_min($geometry)" if dy >= 0 else "y_max($geometry)"
    return f"{x_term} * {_num(dx)} + {y_term} * {_num(dy)}"


def _front_edges(angle_deg: float, nudge: float) -> str:
    """Footprint edges that face the viewer, as a multilinestring.

    Moving the footprint a hair along the extrusion direction covers every
    edge that faces away from the viewer and leaves exactly the facing ones
    outside, so one GEOS difference replaces a per-edge expression loop.
    ``force_rhr`` orients exterior rings clockwise and holes anticlockwise,
    and GEOS keeps that direction, so each edge's outward normal is its
    azimuth minus 90 degrees.
    """
    theta = math.radians(angle_deg)
    return (
        "difference(boundary(force_rhr($geometry)), "
        f"translate($geometry, {_num(math.cos(theta) * nudge)}, {_num(math.sin(theta) * nudge)}))"
    )


def _facade_shade_expression(base: Union["QColor", str], cfg: Dict[str, Any]) -> str:
    """Per-facade colour: Lambert-style darkening by how far a face turns from the sun.

    Evaluated for each wall quad (``@geometry_part_num``). A quad's first
    edge is the footprint edge it was extruded from, whose outward normal is
    its azimuth minus 90 degrees. A face looking straight at the sun keeps the
    base colour; a face turned fully away is darkened by the shading depth.
    ``base`` is a colour or an expression returning one.
    """
    depth = 110.0 * float(cfg["shading_intensity"])
    turn = math.radians(float(cfg["sun_azimuth"])) + math.pi / 2
    part = "geometry_n($geometry, @geometry_part_num)"
    color = f"'{base.name()}'" if isinstance(base, QColor) else base
    return (
        f"darker({color}, 100 + to_int({_num(depth / 2)} * (1 - cos("
        f"azimuth(point_n({part}, 1), point_n({part}, 2)) - {_num(turn)}))))"
    )


def _wall_fill(base: "QColor", cfg: Dict[str, Any], color_expr: str = ""):
    """Facade fill without an outline.

    Visible edges come from the corner, floor and ground lines, which also
    cover the anti-aliasing seam where two walls meet. A data-defined stroke
    colour would hide those seams too, but it doubles the per-wall expression
    work on every redraw.
    """
    fill = QgsSimpleFillSymbolLayer(base, _BrushSolid, base, _PenNone, 0.0)
    if not color_expr and cfg["facade_shading"] and cfg["shading_intensity"] > 0:
        color_expr = _facade_shade_expression(base, cfg)
    if color_expr:
        fill.setDataDefinedProperty(_symbol_property("FillColor"), QgsProperty.fromExpression(color_expr))
    return fill


def _line(color: "QColor", width: float):
    line = QgsSimpleLineSymbolLayer(color, max(0.0, float(width)), _PenSolid)
    with contextlib.suppress(Exception):
        line.setPenCapStyle(getattr(getattr(Qt, "PenCapStyle", Qt), "RoundCap", getattr(Qt, "RoundCap", 0x20)))
    return line


def _corner_ticks(color: "QColor", width: float, angle_deg: float, length_expr: str):
    """Vertical facade edges: one tick per vertex, pointing up the extrusion.

    A hashed line placed on every vertex, at a fixed angle and with a
    map-unit length, draws all corner edges in C++ instead of an expression
    loop over vertices. The line it decorates runs through the middle of the
    facade, so each centred tick spans it exactly. ``length_expr`` is in
    layer units. When the map is drawn in another CRS the tick is measured and
    aimed through that transformation; the canvas and print layouts provide
    ``@map_crs``, a bare render job may not.
    """
    theta = math.radians(angle_deg)
    cos_t, sin_t = _num(math.cos(theta)), _num(math.sin(theta))
    ticks = QgsHashedLineSymbolLayer(False, 0.0)
    placement = getattr(getattr(Qgis, "MarkerLinePlacement", None), "Vertex", None)
    if placement is not None and hasattr(ticks, "setPlacements"):
        ticks.setPlacements(placement)
    else:
        ticks.setPlacement(QgsTemplatedLineSymbolLayerBase.Vertex)
    # Hash angles run clockwise from north; projection angles anticlockwise from east.
    hash_angle = (90.0 - angle_deg) % 360.0
    ticks.setHashAngle(hash_angle)
    ticks.setHashLengthUnit(_map_unit())
    same_crs = "@map_crs IS NULL OR @layer_crs = @map_crs"
    in_map_crs = (
        "transform(make_line(start_point($geometry), translate(start_point($geometry), "
        f"{cos_t} * @h25_len, {sin_t} * @h25_len)), @layer_crs, @map_crs)"
    )
    length = (
        f"with_variable('h25_len', {length_expr}, CASE WHEN {same_crs} THEN @h25_len "
        f"ELSE length({in_map_crs}) END)"
    )
    angle = (
        f"CASE WHEN {same_crs} THEN {_num(hash_angle)} "
        f"ELSE with_variable('h25_len', 1, with_variable('h25_t', {in_map_crs}, "
        "degrees(azimuth(start_point(@h25_t), end_point(@h25_t))))) END"
    )
    ticks.setDataDefinedProperty(_symbol_property("LineDistance"), QgsProperty.fromExpression(length))
    ticks.setDataDefinedProperty(_symbol_property("LineAngle"), QgsProperty.fromExpression(angle))
    sub = _new_symbol(QgsLineSymbol)
    sub.appendSymbolLayer(_line(color, width))
    ticks.setSubSymbol(sub)
    return ticks


def _set_pass(symbol, rendering_pass: int) -> None:
    for index in range(symbol.symbolLayerCount()):
        symbol.symbolLayer(index).setRenderingPass(rendering_pass)


class _Geometry:
    """Expression snippets shared by every layer of one style."""

    def __init__(self, cfg: Dict[str, Any], height_expr: str, nudge: float):
        self.angle = float(cfg["projection_angle"])
        theta = math.radians(self.angle)
        self.dx, self.dy = math.cos(theta), math.sin(theta)
        self.height = height_expr
        self.front = _front_edges(self.angle, nudge)
        self.part_order = _depth_key(self.angle, of_part=True)

    def at(self, geometry: str, z: str) -> str:
        """``geometry`` lifted to height ``z`` (an expression in layer units)."""
        return f"translate({geometry}, {_num(self.dx)} * ({z}), {_num(self.dy)} * ({z}))"

    def with_height(self, body: str) -> str:
        return f"with_variable('h25_hu', {self.height}, {body})"

    @property
    def sorted_edges(self) -> str:
        """Front edges split into single segments, back to front.

        Every wall extruded from this list (and every band of it) comes out
        in painting order, so one sort per building is enough.
        """
        return f"order_parts(segments_to_lines({self.front}), '{self.part_order}', False)"

    def walls(self, z0: str, z1: str, when: str = "") -> str:
        body = (
            f"extrude({self.at(self.sorted_edges, z0)}, "
            f"{_num(self.dx)} * (({z1}) - ({z0})), {_num(self.dy)} * (({z1}) - ({z0})))"
        )
        return self.with_height(f"CASE WHEN {when} THEN {body} END" if when else body)

    def line_at(self, z: str, when: str = "") -> str:
        body = self.at(self.front, z)
        return self.with_height(f"CASE WHEN {when} THEN {body} END" if when else body)

    def floor_lines(self, floor: float) -> str:
        """Every floor line below the roof, as one multilinestring."""
        return self.with_height(
            f"CASE WHEN @h25_hu > {_num(floor * 1.000001)} THEN with_variable('h25_f', {self.front}, "
            "collect_geometries(array_foreach("
            f"generate_series(1, to_int(ceil(@h25_hu / {_num(floor)} - 0.000001)) - 1), "
            f"translate(@h25_f, {_num(self.dx * floor)} * @element, {_num(self.dy * floor)} * @element)))) END"
        )

    def roof(self) -> str:
        return self.with_height(self.at("$geometry", "@h25_hu"))


def _roof_fill(color: "QColor", edge: "QColor", edge_width: float, color_expr: str = ""):
    fill = QgsSimpleFillSymbolLayer(color, _BrushSolid, edge, _PenSolid, max(0.0, edge_width))
    if edge_width <= 0:
        fill.setStrokeStyle(_PenNone)
    if color_expr:
        fill.setDataDefinedProperty(_symbol_property("FillColor"), QgsProperty.fromExpression(color_expr))
    return fill


def _shadow_rule(cfg: Dict[str, Any], height_expr: str):
    """Ground shadow: the footprint swept away from the sun by a share of the height.

    For a convex footprint that sweep is the convex hull of the footprint and
    its displaced copy, which is cheap. Courtyards and L or U shapes need the
    real union of the footprint, its copy and every swept edge, so they are
    not shaded where the sun reaches.
    """
    sun = math.radians(float(cfg["sun_azimuth"]))
    length = float(cfg["shadow_length"])
    # Azimuths are clockwise from north; the shadow falls away from the sun.
    sx, sy = -math.sin(sun) * length, -math.cos(sun) * length
    shift = f"{_num(sx)} * @h25_hu, {_num(sy)} * @h25_hu"
    expression = (
        f"with_variable('h25_hu', {height_expr}, "
        "CASE WHEN area(convex_hull($geometry)) > area($geometry) * 1.02 "
        f"THEN buffer(collect_geometries($geometry, translate($geometry, {shift}), "
        f"extrude(segments_to_lines($geometry), {shift})), 0) "
        f"ELSE convex_hull(collect_geometries($geometry, translate($geometry, {shift}))) END)"
    )
    color = hex_to_qcolor(cfg["shadow_color"], int(round(cfg["shadow_alpha"] * 2.55)))
    fill = QgsSimpleFillSymbolLayer(color, _BrushSolid, QColor(0, 0, 0, 0))
    fill.setStrokeStyle(_PenNone)
    symbol = _new_symbol(QgsFillSymbol)
    symbol.appendSymbolLayer(_generator("Fill", expression, [fill]))
    _set_pass(symbol, 0)
    return QgsRuleBasedRenderer.Rule(symbol, 0, 0, "", "Ground shadow")


def _install(layer, cfg: Dict[str, Any], height_expr: str, rules: List[Any]) -> bool:
    root = QgsRuleBasedRenderer.Rule(None)
    if cfg["shadow_enabled"]:
        root.appendChild(_shadow_rule(cfg, height_expr))
    for rule in rules:
        if rule.symbol() is not None:
            _set_pass(rule.symbol(), 1)
        root.appendChild(rule)
    renderer = QgsRuleBasedRenderer(root)
    # Rule-based symbol levels queue work per rendering pass and, inside a
    # pass, feature by feature in the request order below.
    renderer.setUsingSymbolLevels(True)
    order = _depth_key(float(cfg["projection_angle"]))
    renderer.setOrderBy(QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause(order, False, True)]))
    renderer.setOrderByEnabled(True)
    layer.setRenderer(renderer)
    layer.emitStyleChanged()
    layer.triggerRepaint()
    return True


def _layer_height_values(layer, field: str) -> Iterable[Any]:
    """Raw values of ``field`` (one ``None`` per feature when there is no field)."""
    fields = layer.fields()
    idx = fields.lookupField(field) if field else -1
    request = QgsFeatureRequest()
    no_geometry = getattr(getattr(QgsFeatureRequest, "Flag", None), "NoGeometry", None)
    if no_geometry is None:
        no_geometry = getattr(QgsFeatureRequest, "NoGeometry", None)
    if no_geometry is not None:
        request.setFlags(no_geometry)
    request.setSubsetOfAttributes([idx] if idx >= 0 else [])
    values: List[Any] = []
    with contextlib.suppress(Exception):
        for feature in layer.getFeatures(request):
            values.append(feature.attribute(idx) if idx >= 0 else None)
    return values


def _resolve_field(layer, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Drop a configured height field the layer does not have."""
    field = cfg.get("height_field", "")
    if field and layer.fields().lookupField(field) < 0:
        cfg = dict(cfg)
        cfg["height_field"] = ""
    return cfg


def _field_is_numeric(layer, field: str) -> bool:
    idx = layer.fields().lookupField(field) if field else -1
    return idx >= 0 and layer.fields().at(idx).isNumeric()


def layer_slab_count(layer, cfg: Dict[str, Any], per_floor: bool = True) -> int:
    """Floors needed for ``layer``: the explicit maximum, else its tallest building."""
    cfg = _resolve_field(layer, normalize_config(cfg))
    if int(cfg.get("max_floors", 0) or 0) > 0:
        return slab_count((), cfg, per_floor)
    return slab_count(_layer_height_values(layer, cfg["height_field"]), cfg, per_floor)


def apply_geometry_generator_25d_style(layer, config: Dict[str, Any]) -> bool:
    """Solid 2.5D extrusion in the configured facade and roof materials."""
    if not layer or not layer.isValid():
        return False
    cfg = _resolve_field(layer, normalize_config(config))
    k = meters_to_layer_units(layer)
    height_m = height_meters_expression(
        cfg["height_field"], cfg["height_unit"], cfg["height_multiplier"],
        cfg["default_height"], cfg["floor_height_m"], cfg["default_levels"],
        _field_is_numeric(layer, cfg["height_field"]),
    )
    height = f"(({height_m}) * {_num(k)})"
    geo = _Geometry(cfg, height, 0.01 * k)
    floor = cfg["floor_height_m"] * cfg["height_multiplier"] * k

    symbol = _new_symbol(QgsFillSymbol)
    walls = _wall_fill(hex_to_qcolor(cfg["wall_color"]), cfg)
    symbol.appendSymbolLayer(_generator("Fill", geo.walls("0", "@h25_hu"), [walls]))
    if cfg["floor_bands_enabled"] and cfg["floor_line_width"] > 0:
        floor_line = _line(hex_to_qcolor(cfg["floor_line_color"]), cfg["floor_line_width"])
        symbol.appendSymbolLayer(_generator("Line", geo.floor_lines(floor), [floor_line]))
    edge = hex_to_qcolor(cfg["outline_color"])
    if cfg["outline_width"] > 0:
        ticks = _corner_ticks(edge, cfg["outline_width"], geo.angle, height)
        symbol.appendSymbolLayer(_generator("Line", geo.line_at("@h25_hu / 2"), [ticks]))
        symbol.appendSymbolLayer(_generator("Line", geo.line_at("0"), [_line(edge, cfg["outline_width"])]))
    roof = _roof_fill(
        hex_to_qcolor(cfg["roof_color"]), hex_to_qcolor(cfg["roof_outline_color"]), cfg["roof_outline_width"]
    )
    symbol.appendSymbolLayer(_generator("Fill", geo.roof(), [roof]))
    return _install(layer, cfg, height, [QgsRuleBasedRenderer.Rule(symbol, 0, 0, "", "Buildings")])


def floor_band_palette_color(floor_index: int, palette_key: str, wall: bool = False) -> "QColor":
    """Get color for a specific floor band from a palette."""
    palette = FLOOR_BAND_PALETTES.get(palette_key, FLOOR_BAND_PALETTES.get("teal_peach", {}))
    colors = palette.get("colors", ("#f4d35e", "#ee964b", "#f95738", "#d7263d", "#9b5de5", "#00bbf9"))
    color_hex = colors[(max(1, int(floor_index)) - 1) % len(colors)]
    col = hex_to_qcolor(color_hex)
    if wall:
        return col.darker(120)
    return col


# Floors listed in a per-floor legend; taller buildings share the last entry.
LEGEND_FLOORS = 20

# Edges in per-floor mode darken whichever band colour they cross.
_BAND_EDGE = (0, 0, 0, 96)


def _palette_array(colors) -> str:
    return "array(" + ", ".join(f"'{QColor(c).name()}'" for c in colors) + ")"


def apply_per_floor_bands_style(layer, config: Dict[str, Any]) -> bool:
    """2.5D extrusion with every floor coloured from the selected per-floor palette.

    All floors of a building come from one generator: band ``b`` contributes
    one wall per front edge, in band order, so a wall's band is its part
    number divided by the walls per band, and its colour is read from the
    palette. The geometry work per building is the same as for the solid
    style, however many floors it has.
    """
    if not layer or not layer.isValid():
        return False
    cfg = _resolve_field(layer, normalize_config(config))
    k = meters_to_layer_units(layer)
    floor = cfg["floor_height_m"] * cfg["height_multiplier"] * k
    floors = floor_count_expression(
        cfg["height_field"], cfg["height_unit"], cfg["floor_height_m"], cfg["default_levels"],
        _field_is_numeric(layer, cfg["height_field"]),
    )
    height = f"(({floors}) * {_num(floor)})"
    geo = _Geometry(cfg, height, 0.01 * k)
    tallest = layer_slab_count(layer, cfg, per_floor=True)
    palette = cfg["floor_palette"]
    colors = list(FLOOR_BAND_PALETTES.get(palette, FLOOR_BAND_PALETTES["teal_peach"])["colors"])
    wall_colors = [floor_band_palette_color(i + 1, palette, wall=True).name() for i in range(len(colors))]
    edge = QColor(*_BAND_EDGE)

    # Bands drawn for a building: its floors, the last band running to the
    # roof of anything taller than the tallest floor count styled.
    bands = f"min({floors}, {tallest})"
    # Each band reaches 2 % into the next one, which is drawn over it, so no
    # anti-aliasing seam shows between floors.
    rise = (
        f"CASE WHEN @element = @h25_n THEN @h25_hu - (@element - 1) * {_num(floor)} "
        f"ELSE {_num(floor * 1.02)} END"
    )
    walls = geo.with_height(
        f"with_variable('h25_f', {geo.sorted_edges}, with_variable('h25_n', {bands}, "
        "collect_geometries(array_foreach(generate_series(1, @h25_n), "
        f"extrude({geo.at('@h25_f', f'(@element - 1) * {_num(floor)}')}, "
        f"{_num(geo.dx)} * {rise}, {_num(geo.dy)} * {rise})))))"
    )
    band_index = (
        f"to_int(floor((@geometry_part_num - 1) / (@geometry_part_count / ({bands})))) % {len(colors)}"
    )
    band_color = f"array_get({_palette_array(wall_colors)}, {band_index})"
    shaded = cfg["facade_shading"] and cfg["shading_intensity"] > 0
    fill = _wall_fill(QColor(wall_colors[0]), cfg, _facade_shade_expression(band_color, cfg) if shaded else band_color)

    symbol = _new_symbol(QgsFillSymbol)
    symbol.appendSymbolLayer(_generator("Fill", walls, [fill]))
    if cfg["floor_bands_enabled"]:
        symbol.appendSymbolLayer(_generator("Line", geo.floor_lines(floor), [_line(edge, 0.2)]))
    ticks = _corner_ticks(edge, 0.2, geo.angle, height)
    symbol.appendSymbolLayer(_generator("Line", geo.line_at("@h25_hu / 2"), [ticks]))
    symbol.appendSymbolLayer(_generator("Line", geo.line_at("0"), [_line(edge, 0.2)]))
    roof_expr = f"array_get({_palette_array(colors)}, ({bands} - 1) % {len(colors)})"
    roof = _roof_fill(QColor(colors[0]), QColor(0, 0, 0, 70), 0.3, roof_expr)
    symbol.appendSymbolLayer(_generator("Fill", geo.roof(), [roof]))
    rules = [QgsRuleBasedRenderer.Rule(symbol, 0, 0, "", "Buildings")]

    # Legend key: one swatch per floor colour. These rules never match a
    # feature, so they cost a constant test and draw nothing.
    shown = min(tallest, LEGEND_FLOORS)
    for i in range(1, shown + 1):
        swatch = _new_symbol(QgsFillSymbol)
        color = floor_band_palette_color(i, palette)
        swatch.appendSymbolLayer(QgsSimpleFillSymbolLayer(color, _BrushSolid, color.darker(130), _PenSolid, 0.2))
        label = f"Floor {i}+" if i == shown and tallest > shown else f"Floor {i}"
        rules.append(QgsRuleBasedRenderer.Rule(swatch, 0, 0, "FALSE", label))
    return _install(layer, cfg, height, rules)


def apply_native_25d_renderer(layer, config: Dict[str, Any]) -> bool:
    """Configure and apply QGIS's native Qgs25DRenderer to a polygon layer."""
    if not layer or not layer.isValid():
        return False
    cfg = _resolve_field(layer, normalize_config(config))
    height_m = height_meters_expression(
        cfg["height_field"], cfg["height_unit"], cfg["height_multiplier"],
        cfg["default_height"], cfg["floor_height_m"], cfg["default_levels"],
        _field_is_numeric(layer, cfg["height_field"]),
    )
    k = meters_to_layer_units(layer)
    h_expr = height_m if abs(k - 1.0) < 1e-12 else f"({height_m} * {_num(k)})"

    # Qgs25DRenderer evaluates only these two layer-scoped expression variables;
    # sun azimuth and shading depth have no native-renderer equivalent.
    QgsExpressionContextUtils.setLayerVariable(layer, "qgis_25d_height", h_expr)
    QgsExpressionContextUtils.setLayerVariable(layer, "qgis_25d_angle", float(cfg["projection_angle"]))

    renderer = Qgs25DRenderer()
    renderer.setRoofColor(hex_to_qcolor(cfg["roof_color"]))
    renderer.setWallColor(hex_to_qcolor(cfg["wall_color"]))
    renderer.setShadowColor(hex_to_qcolor(cfg["shadow_color"], int(round(cfg["shadow_alpha"] * 2.55))))
    renderer.setShadowEnabled(cfg["shadow_enabled"])
    renderer.setShadowSpread(float(cfg["shadow_blur"]))
    renderer.setWallShadingEnabled(cfg["facade_shading"])

    layer.setRenderer(renderer)
    layer.emitStyleChanged()
    layer.triggerRepaint()
    return True


def apply_25d_style(layer, config: Dict[str, Any]) -> bool:
    """Master styling dispatcher: per-floor bands, solid geometry generator, or native 2.5D renderer."""
    if not layer or not layer.isValid():
        return False
    cfg = normalize_config(config)
    if cfg["render_mode"] == "per_floor_bands":
        return apply_per_floor_bands_style(layer, cfg)
    if cfg["render_mode"] == "geometry_generator":
        return apply_geometry_generator_25d_style(layer, cfg)
    return apply_native_25d_renderer(layer, cfg)


def apply_preset_to_layer(
    layer,
    preset_key: str,
    height_field: str = "height",
    height_multiplier: float = 1.0,
    use_geom_gen: bool = True,
) -> bool:
    """Apply one of the curated themes by key."""
    if preset_key not in PRESETS:
        preset_key = "warm_civic"
    cfg = dict(PRESETS[preset_key])
    cfg["height_field"] = height_field
    cfg["height_multiplier"] = height_multiplier
    if not use_geom_gen:
        cfg["render_mode"] = "native"
    return apply_25d_style(layer, cfg)


def describe_layer_heights(layer, config: Dict[str, Any]) -> Tuple[int, int, float, str]:
    """``(features, using_fallback, tallest_m, kind)`` for the dock's diagnostics line."""
    from .heights import height_meters_value

    cfg = _resolve_field(layer, normalize_config(config))
    kind = field_kind(cfg["height_field"], cfg["height_unit"])
    values = list(_layer_height_values(layer, cfg["height_field"]))
    fallback = 0
    tallest = 0.0
    for value in values:
        try:
            ok = kind != "none" and value is not None and float(value) > 0
        except (TypeError, ValueError):
            ok = False
        if not ok:
            fallback += 1
        tallest = max(tallest, height_meters_value(value, kind, cfg))
    return len(values), fallback, tallest * cfg["height_multiplier"], kind
