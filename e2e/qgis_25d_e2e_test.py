# -*- coding: utf-8 -*-
"""Headless QGIS 3/4 release harness for the dedicated 2.5D workflow."""
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from qgis.core import (
    QgsApplication,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsMapRendererSequentialJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
    QgsRuleBasedRenderer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QSize, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox

qgs = QgsApplication([], False)
qgs.initQgis()
QMessageBox.critical = staticmethod(lambda *_args, **_kwargs: QMessageBox.Ok)
passed_count = 0


def record_pass(test_name):
    global passed_count
    passed_count += 1
    print(f"  [PASS] {test_name}", flush=True)


def evaluate(expression_text, layer, feature):
    context = QgsExpressionContext(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
    context.setFeature(feature)
    expression = QgsExpression(expression_text)
    assert not expression.hasParserError(), expression.parserErrorString()
    value = expression.evaluate(context)
    assert not expression.hasEvalError(), expression.evalErrorString()
    return value


def render(layer, extent, size=400):
    """Render like the map canvas does, including its map-settings variables."""
    settings = QgsMapSettings()
    settings.setLayers([layer])
    settings.setDestinationCrs(layer.crs())
    settings.setExtent(extent)
    settings.setOutputSize(QSize(size, size))
    settings.setBackgroundColor(QColor("#ffffff"))
    settings.setExpressionContext(QgsExpressionContext([
        QgsExpressionContextUtils.globalScope(),
        QgsExpressionContextUtils.projectScope(QgsProject.instance()),
        QgsExpressionContextUtils.mapSettingsScope(settings),
    ]))
    job = QgsMapRendererSequentialJob(settings)
    job.start()
    job.waitForFinished()
    assert not job.errors(), [e.message for e in job.errors()]
    return job.renderedImage(), settings


def pixel(image, settings, x, y):
    point = settings.mapToPixel().transform(x, y)
    return QColor(image.pixel(int(round(point.x())), int(round(point.y()))))


def building_layer(crs, rows, fields=(("height", QVariant.Double), ("building_levels", QVariant.Double))):
    lyr = QgsVectorLayer(f"Polygon?crs={crs}", "buildings", "memory")
    schema = QgsFields()
    for name, kind in fields:
        schema.append(QgsField(name, kind))
    lyr.dataProvider().addAttributes(list(schema))
    lyr.updateFields()
    features = []
    for (x0, y0, x1, y1), values in rows:
        feature = QgsFeature(lyr.fields())
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(x0, y0, x1, y1)))
        feature.setAttributes(list(values))
        features.append(feature)
    lyr.dataProvider().addFeatures(features)
    lyr.updateExtents()
    return lyr


try:
    print("=== QGIS 2.5D Styling E2E Harness ===", flush=True)
    from qgis_25d_styling.core.config import normalize_config
    from qgis_25d_styling.core.heights import (
        field_kind,
        floor_count_expression,
        floor_count_value,
        height_meters_expression,
        height_meters_value,
    )
    from qgis_25d_styling.core.osm_downloader import osm_json_to_vector_layer
    from qgis_25d_styling.core.presets import PRESETS
    from qgis_25d_styling.core.qml_exporter import export_layer_qml, load_layer_qml
    from qgis_25d_styling.core.twopointfive_engine import (
        apply_25d_style,
        apply_geometry_generator_25d_style,
        apply_native_25d_renderer,
        apply_per_floor_bands_style,
        apply_preset_to_layer,
    )
    from qgis_25d_styling.processing.provider import Qgis25DStylingProvider
    from qgis_25d_styling.ui.styling_dock import StylingDockWidget

    layer = building_layer(
        "EPSG:3857", [((0, 0, 20, 20), (24.0, 8.0)), ((30, 0, 50, 20), (12.0, 4.0))]
    )
    assert layer.featureCount() == 2
    QgsProject.instance().addMapLayer(layer)
    record_pass("Synthetic polygon source")

    print("  [INFO] Constructing styling dock", flush=True)
    dock = StylingDockWidget(None)
    dock.cb_layer.setLayer(layer)
    assert dock.tabs.count() == 5
    assert dock.btn_apply.isEnabled()
    dock.load_config_into_ui({
        "render_mode": "geometry_generator",
        "height_field": "height",
        "height_unit": "meters",
        "projection_angle": 135,
        "shadow_enabled": False,
        "shadow_length": 0.9,
    })
    round_trip = dock.get_current_config()
    assert round_trip["render_mode"] == "geometry_generator"
    assert round_trip["height_field"] == "height"
    assert round_trip["height_unit"] == "meters"
    assert round_trip["projection_angle"] == 135
    assert round_trip["shadow_enabled"] is False
    assert abs(round_trip["shadow_length"] - 0.9) < 1e-9
    # 135 degrees leans roofs to the north-west, and the control says so.
    assert dock.sp_angle.suffix().strip().endswith("NW"), dock.sp_angle.suffix()
    original_renderer_type = type(layer.renderer())
    dock.apply_current_style(automatic=True)
    assert dock.lbl_apply_status.text() != "Apply failed"
    assert "read as metres" in dock.lbl_diagnostics.text(), dock.lbl_diagnostics.text()
    assert dock.btn_restore.isEnabled()
    # A theme changes materials, not the renderer the user picked.
    dock.cb_preset.setCurrentIndex(dock.cb_preset.findData("night_copper"))
    dock.apply_selected_preset()
    assert dock.get_current_config()["render_mode"] == "geometry_generator"
    assert dock.get_current_config()["wall_color"] == PRESETS["night_copper"]["wall_color"]
    dock.restore_previous_style()
    assert isinstance(layer.renderer(), original_renderer_type)
    dock.close()
    dock.deleteLater()
    qgs.processEvents()
    record_pass("Dock: config round trip, compass label, diagnostics, theme keeps renderer, restore")

    def ring(x, y, w=0.0002, h=0.0002):
        return [{"lon": x, "lat": y}, {"lon": x + w, "lat": y}, {"lon": x + w, "lat": y + h},
                {"lon": x, "lat": y + h}, {"lon": x, "lat": y}]

    outer = ring(29.0010, 41.0000, 0.0004, 0.0004)
    osm_data = {
        "elements": [
            {"type": "way", "id": 101, "tags": {"building": "apartments", "building:levels": "5"},
             "geometry": ring(29.0000, 41.0000)},
            {"type": "way", "id": 102, "tags": {"building": "yes"}, "geometry": ring(29.0003, 41.0000)},
            {"type": "way", "id": 103, "tags": {"building": "yes", "height": "20,5"},
             "geometry": ring(29.0006, 41.0000)},
            # A courtyard building mapped as a relation, its outline split in two ways.
            {"type": "relation", "id": 104, "tags": {"building": "yes", "type": "multipolygon"},
             "members": [
                 {"type": "way", "role": "outer", "geometry": outer[:3]},
                 {"type": "way", "role": "outer", "geometry": outer[2:][::-1]},
                 {"type": "way", "role": "inner", "geometry": ring(29.0011, 41.0001)},
             ]},
        ]
    }
    osm_layer = osm_json_to_vector_layer(osm_data, default_levels=3, floor_height_m=3.2)
    assert osm_layer.featureCount() == 4, osm_layer.featureCount()
    osm_features = {feature["osm_id"]: feature for feature in osm_layer.getFeatures()}
    assert osm_features["way/101"]["building_levels"] == 5.0
    assert osm_features["way/101"]["levels_source"] == "osm"
    assert osm_features["way/102"]["building_levels"] == 3.0
    assert osm_features["way/102"]["levels_source"] == "default"
    assert abs(osm_features["way/102"]["height"] - 9.6) < 0.001
    assert osm_features["way/103"]["building_levels"] == 6.0
    assert osm_features["way/103"]["levels_source"] == "estimated"
    assert abs(osm_features["way/103"]["height"] - 20.5) < 0.001
    courtyard = osm_features["relation/104"].geometry()
    assert courtyard.constGet().numInteriorRings() == 1 if not courtyard.isMultipart() else \
        courtyard.constGet().geometryN(0).numInteriorRings() == 1
    record_pass("OSM: levels, height-only estimate, fallback, decimal comma, multipolygon relation with hole")

    # The expressions the renderers draw with and the Python rules the dock,
    # legend and Processing count with must agree value for value.
    probe = QgsVectorLayer(
        "Polygon?crs=EPSG:3857&field=num:double&field=txt:string(20)", "probe", "memory"
    )
    cfg = {"floor_height_m": 3.2, "default_levels": 3, "default_height": 9.0}
    for raw in (12.0, 2.5, 0.0, -4.0, None, 7.4):
        feature = QgsFeature(probe.fields())
        feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(0, 0, 1, 1)))
        feature.setAttributes([raw, None if raw is None else str(raw)])
        for field, numeric in (("num", True), ("txt", False)):
            for unit in ("meters", "floors"):
                kind = field_kind(field, unit)
                got = evaluate(height_meters_expression(field, unit, 1.0, 9.0, 3.2, 3, numeric), probe, feature)
                assert abs(float(got) - height_meters_value(raw, kind, cfg)) < 1e-9, (field, unit, raw, got)
                got = evaluate(floor_count_expression(field, unit, 3.2, 3, numeric), probe, feature)
                assert int(got) == floor_count_value(raw, kind, cfg), (field, unit, raw, got)
    record_pass("Height and floor expressions match their Python twins (numeric and text fields)")

    native_cfg = normalize_config({"render_mode": "native", "height_field": "height"})
    assert apply_native_25d_renderer(layer, native_cfg)
    scope = QgsExpressionContextUtils.layerScope(layer)
    assert float(scope.variable("qgis_25d_angle")) == 45.0
    first = next(layer.getFeatures())
    assert abs(float(evaluate(scope.variable("qgis_25d_height"), layer, first)) - 24.0) < 1e-9
    geo = building_layer("EPSG:4326", [((29.0, 41.0, 29.0002, 41.0002), (30.0, 10.0))])
    assert apply_native_25d_renderer(geo, native_cfg)
    geo_height = QgsExpressionContextUtils.layerScope(geo).variable("qgis_25d_height")
    degrees = float(evaluate(geo_height, geo, next(geo.getFeatures())))
    # 30 m must become ~0.00027 degrees, not 30 degrees.
    assert abs(degrees - 30.0 / 111319.49079327357) < 1e-9, degrees
    record_pass("Native renderer: height variable in metres, and in degrees on a geographic layer")

    geometry_cfg = normalize_config({"render_mode": "geometry_generator", "height_field": "height"})
    assert apply_geometry_generator_25d_style(layer, geometry_cfg)
    renderer = layer.renderer()
    assert isinstance(renderer, QgsRuleBasedRenderer)
    assert renderer.usingSymbolLevels() and renderer.orderByEnabled()
    rules = renderer.rootRule().children()
    assert [r.label() for r in rules] == ["Ground shadow", "Buildings"], [r.label() for r in rules]
    passes = [{rules[i].symbol().symbolLayer(k).renderingPass() for k in range(rules[i].symbol().symbolLayerCount())}
              for i in range(2)]
    assert passes == [{0}, {1}], passes
    record_pass("Solid renderer: shadow pass before building pass, back-to-front order")

    # Behaviour, not structure: a tall building's shadow falls across a low
    # neighbour that is drawn before it. The old per-building drawing order
    # darkened that neighbour's roof.
    scene = building_layer("EPSG:32635", [
        ((500000, 4200000, 500010, 4200010), (30.0, 0.0)),     # tall tower
        ((500013, 4199988, 500022, 4199997), (3.0, 0.0)),      # low roof in its shadow
    ])
    apply_25d_style(scene, {"render_mode": "geometry_generator", "height_field": "height",
                            "floor_bands_enabled": False, "shadow_alpha": 60})
    image, settings = render(scene, QgsRectangle(499995, 4199980, 500035, 4200035))
    roof = pixel(image, settings, 500019.6, 4199994.6)
    assert roof.name() == "#f7c3a1", roof.name()
    record_pass("A neighbour's shadow no longer darkens a roof drawn before it")

    # Facades shade by orientation: with the sun in the north-west, the
    # west face is lit and the south face is in shade.
    single = building_layer("EPSG:32635", [((500000, 4200000, 500020, 4200020), (12.0, 0.0))])
    apply_25d_style(single, {"render_mode": "geometry_generator", "height_field": "height",
                             "floor_bands_enabled": False, "shadow_enabled": False, "outline_width": 0})
    image, settings = render(single, QgsRectangle(499995, 4199995, 500035, 4200035))
    west = pixel(image, settings, 500002, 4200012)    # on the west wall, above its foot
    south = pixel(image, settings, 500010, 4200002)   # on the south wall
    assert west.lightness() - south.lightness() > 15, (west.name(), south.name())
    record_pass("Facade shading follows each wall's orientation to the sun")

    floor_cfg = normalize_config({"render_mode": "per_floor_bands", "height_field": "building_levels", "max_floors": 8})
    assert apply_per_floor_bands_style(layer, floor_cfg)
    rules = layer.renderer().rootRule().children()
    labels = [r.label() for r in rules]
    assert labels[:2] == ["Ground shadow", "Buildings"] and labels[-1] == "Floor 8", labels
    assert all(r.filterExpression() == "FALSE" for r in rules[2:])
    record_pass("Per-floor renderer with a legend key per floor colour")

    # Each floor band takes its own palette colour.
    banded = building_layer("EPSG:32635", [((500000, 4200000, 500020, 4200020), (0.0, 3.0))])
    apply_25d_style(banded, {"render_mode": "per_floor_bands", "height_field": "building_levels",
                             "floor_palette": "paired", "facade_shading": False, "shadow_enabled": False,
                             "floor_bands_enabled": False, "floor_height_m": 4.0})
    image, settings = render(banded, QgsRectangle(499995, 4199995, 500035, 4200035))
    low = pixel(image, settings, 500001, 4200008)      # west wall, floor 1
    high = pixel(image, settings, 500007, 4200015)     # west wall, floor 3
    expected_low = QColor("#a6cee3").darker(120)
    expected_high = QColor("#b2df8a").darker(120)
    assert abs(low.red() - expected_low.red()) < 6 and abs(low.green() - expected_low.green()) < 6, low.name()
    assert abs(high.red() - expected_high.red()) < 6 and abs(high.green() - expected_high.green()) < 6, high.name()
    record_pass("Per-floor walls take the palette colour of their floor")

    for preset_key in PRESETS:
        assert apply_preset_to_layer(layer, preset_key, height_field="height")
    record_pass(f"All {len(PRESETS)} presets")

    for mode in ("geometry_generator", "per_floor_bands", "native"):
        assert apply_25d_style(layer, {"render_mode": mode, "height_field": "height"})
        render(layer, QgsRectangle(-20, -20, 80, 80), 120)
    record_pass("Dispatcher mode matrix renders without errors")

    qml_path = os.path.join(tempfile.gettempdir(), "qgis_25d_release_test.qml")
    apply_25d_style(layer, {"render_mode": "per_floor_bands", "height_field": "building_levels"})
    assert export_layer_qml(layer, qml_path)
    assert os.path.getsize(qml_path) > 100
    assert load_layer_qml(layer, qml_path)
    assert isinstance(layer.renderer(), QgsRuleBasedRenderer)
    os.remove(qml_path)
    record_pass("QML round trip")

    processing_provider = Qgis25DStylingProvider()
    QgsApplication.processingRegistry().addProvider(processing_provider)
    algorithms = processing_provider.algorithms()
    assert len(algorithms) == 1
    assert algorithms[0].name() == "apply_25d_style"
    record_pass("Single-purpose Processing inventory")

    # Run the algorithm the way the Processing GUI does. Vector destinations
    # are written to disk even as "temporary" outputs, so a style set on the
    # context's layer during the run never reached the loaded layer, and the
    # optional QML was never written.
    import qgis as _qgis_pkg
    _plugins_dir = os.path.join(os.path.dirname(os.path.dirname(_qgis_pkg.__file__)), "plugins")
    if _plugins_dir not in sys.path:
        sys.path.insert(0, _plugins_dir)
    import processing
    from processing.core.Processing import Processing
    Processing.initialize()

    bld = building_layer("EPSG:32635", [
        ((500000 + i * 30, 4200000, 500020 + i * 30, 4200020), (h, lv))
        for i, (h, lv) in enumerate(((9.0, 3), (18.0, 6), (27.0, 9)))
    ], fields=(("height", QVariant.Double), ("levels", QVariant.Int)))
    QgsProject.instance().addMapLayer(bld)
    out_dir = tempfile.mkdtemp(prefix="q25d_alg_")

    def _run_loaded(params):
        before = set(QgsProject.instance().mapLayers())
        processing.runAndLoadResults("qgis_25d_styling:apply_25d_style", params)
        new = [QgsProject.instance().mapLayer(i) for i in set(QgsProject.instance().mapLayers()) - before]
        assert len(new) == 1, f"expected one loaded layer, got {len(new)}"
        return new[0]

    for kind in ("TEMPORARY_OUTPUT", os.path.join(out_dir, "styled.gpkg")):
        qml = os.path.join(out_dir, f"style_{len(os.listdir(out_dir))}.qml")
        loaded = _run_loaded({"INPUT": bld, "HEIGHT_FIELD": "height", "OUTPUT": kind, "OUTPUT_QML": qml})
        assert isinstance(loaded.renderer(), QgsRuleBasedRenderer), type(loaded.renderer()).__name__
        labels = [r.label() for r in loaded.renderer().rootRule().children()]
        assert "Buildings" in labels, f"loaded output is not 2.5D-styled: {labels}"
        assert os.path.exists(qml) and os.path.getsize(qml) > 1000, "QML style was not written"
        with open(qml, encoding="utf-8") as fh:
            assert fh.read().count('class="GeometryGenerator"') >= 3, "QML lacks the 2.5D style"
    record_pass("Processing output is 2.5D-styled on load and QML is written (temporary + GeoPackage)")

    # No field given: the algorithm picks the conventional "height" field
    # instead of drawing every building at the fallback height.
    loaded = _run_loaded({"INPUT": bld, "OUTPUT": "TEMPORARY_OUTPUT"})
    walls = loaded.renderer().rootRule().children()[1].symbol().symbolLayer(0).geometryExpression()
    assert '"height"' in walls, walls[:200]
    record_pass("Processing picks the height field when none is given")

    # per-floor bands: the tallest building (9 levels) sets the floor count,
    # read from the data during the run, not from the not-yet-loaded output
    mode_keys = algorithms[0].RENDER_MODE_KEYS
    loaded = _run_loaded({"INPUT": bld, "HEIGHT_FIELD": "levels",
                          "RENDER_MODE": mode_keys.index("per_floor_bands"),
                          "OUTPUT": os.path.join(out_dir, "floors.gpkg")})
    assert isinstance(loaded.renderer(), QgsRuleBasedRenderer), type(loaded.renderer()).__name__
    labels = [r.label() for r in loaded.renderer().rootRule().children()]
    assert labels[-1] == "Floor 9", f"legend does not reach floor 9: {labels}"
    record_pass("Per-floor style uses the data's maximum floor count")
    QgsApplication.processingRegistry().removeProvider(processing_provider)

    QgsProject.instance().removeAllMapLayers()

    print(f"\nPASSED: {passed_count}")
finally:
    qgs.exitQgis()
