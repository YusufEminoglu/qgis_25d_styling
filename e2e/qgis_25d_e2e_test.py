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
    QgsExpressionContextUtils,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtWidgets import QMessageBox

qgs = QgsApplication([], False)
qgs.initQgis()
QMessageBox.critical = staticmethod(lambda *_args, **_kwargs: QMessageBox.Ok)
passed_count = 0


def record_pass(test_name):
    global passed_count
    passed_count += 1
    print(f"  [PASS] {test_name}", flush=True)


try:
    print("=== QGIS 2.5D Styling E2E Harness ===", flush=True)
    from qgis_25d_styling.core.config import normalize_config
    from qgis_25d_styling.core.osm_downloader import osm_json_to_vector_layer
    from qgis_25d_styling.core.presets import PRESETS
    from qgis_25d_styling.core.qml_exporter import export_layer_qml, load_layer_qml
    from qgis_25d_styling.core.twopointfive_engine import (
        apply_25d_style,
        apply_geometry_generator_25d_style,
        apply_native_25d_renderer,
        apply_per_floor_bands_style,
        apply_preset_to_layer,
        build_height_expression,
    )
    from qgis_25d_styling.processing.provider import Qgis25DStylingProvider
    from qgis_25d_styling.ui.styling_dock import StylingDockWidget

    layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "Test Buildings", "memory")
    provider = layer.dataProvider()
    fields = QgsFields()
    fields.append(QgsField("id", QVariant.Int))
    fields.append(QgsField("height", QVariant.Double))
    fields.append(QgsField("building_levels", QVariant.Double))
    provider.addAttributes(list(fields))
    layer.updateFields()
    for feature_id, x, height, levels in ((1, 0, 24.0, 8.0), (2, 30, 12.0, 4.0)):
        feature = QgsFeature(layer.fields())
        ring = [
            QgsPointXY(x, 0), QgsPointXY(x + 20, 0), QgsPointXY(x + 20, 20),
            QgsPointXY(x, 20), QgsPointXY(x, 0),
        ]
        feature.setGeometry(QgsGeometry.fromPolygonXY([ring]))
        feature.setAttributes([feature_id, height, levels])
        provider.addFeature(feature)
    layer.updateExtents()
    assert layer.featureCount() == 2
    QgsProject.instance().addMapLayer(layer)
    record_pass("Synthetic polygon source")

    print("  [INFO] Constructing styling dock", flush=True)
    dock = StylingDockWidget(None)
    print("  [INFO] Setting dock layer", flush=True)
    dock.cb_layer.setLayer(layer)
    assert dock.tabs.count() == 5
    assert dock.btn_apply.isEnabled()
    dock.load_config_into_ui({
        "render_mode": "geometry_generator",
        "height_field": "height",
        "projection_angle": 135,
        "shadow_enabled": False,
    })
    round_trip = dock.get_current_config()
    assert round_trip["render_mode"] == "geometry_generator"
    assert round_trip["height_field"] == "height"
    assert round_trip["projection_angle"] == 135
    assert round_trip["shadow_enabled"] is False
    original_renderer_type = type(layer.renderer())
    print("  [INFO] Applying through dock", flush=True)
    dock.apply_current_style(automatic=True)
    assert dock.lbl_apply_status.text() != "Apply failed"
    assert dock.btn_restore.isEnabled()
    dock.restore_previous_style()
    assert isinstance(layer.renderer(), original_renderer_type)
    print("  [INFO] Destroying styling dock", flush=True)
    dock.close()
    dock.deleteLater()
    qgs.processEvents()
    record_pass("Dock construction, config round trip, apply and restore")

    osm_data = {
        "elements": [
            {
                "type": "way", "id": 101,
                "tags": {"building": "apartments", "building:levels": "5"},
                "geometry": [
                    {"lon": 29.0000, "lat": 41.0000},
                    {"lon": 29.0002, "lat": 41.0000},
                    {"lon": 29.0002, "lat": 41.0002},
                    {"lon": 29.0000, "lat": 41.0002},
                    {"lon": 29.0000, "lat": 41.0000},
                ],
            },
            {
                "type": "way", "id": 102,
                "tags": {"building": "yes"},
                "geometry": [
                    {"lon": 29.0003, "lat": 41.0000},
                    {"lon": 29.0005, "lat": 41.0000},
                    {"lon": 29.0005, "lat": 41.0002},
                    {"lon": 29.0003, "lat": 41.0002},
                    {"lon": 29.0003, "lat": 41.0000},
                ],
            },
            {
                "type": "way", "id": 103,
                "tags": {"building": "yes", "height": "20"},
                "geometry": [
                    {"lon": 29.0006, "lat": 41.0000},
                    {"lon": 29.0008, "lat": 41.0000},
                    {"lon": 29.0008, "lat": 41.0002},
                    {"lon": 29.0006, "lat": 41.0002},
                    {"lon": 29.0006, "lat": 41.0000},
                ],
            },
        ]
    }
    osm_layer = osm_json_to_vector_layer(osm_data, default_levels=3, floor_height_m=3.2)
    assert osm_layer.featureCount() == 3
    osm_features = {feature["osm_id"]: feature for feature in osm_layer.getFeatures()}
    assert osm_features["101"]["building_levels"] == 5.0
    assert osm_features["101"]["levels_source"] == "osm"
    assert osm_features["102"]["building_levels"] == 3.0
    assert osm_features["102"]["levels_source"] == "default"
    assert abs(osm_features["102"]["height"] - 9.6) < 0.001
    assert osm_features["103"]["building_levels"] == 6.0
    assert osm_features["103"]["levels_source"] == "estimated"
    assert abs(osm_features["103"]["height"] - 20.0) < 0.001
    record_pass("OSM building levels, height-only estimation, and explicit three-floor fallback")

    for field_name in ("height", "building_levels", ""):
        expression = QgsExpression(build_height_expression(field_name, 1.0, 9.0))
        assert not expression.hasParserError(), expression.parserErrorString()
    record_pass("Height expressions parse")

    native_cfg = normalize_config({"render_mode": "native", "height_field": "height"})
    assert apply_native_25d_renderer(layer, native_cfg)
    scope = QgsExpressionContextUtils.layerScope(layer)
    assert scope.variable("qgis_25d_height")
    assert float(scope.variable("qgis_25d_angle")) == 45.0
    record_pass("Native renderer and expression variables")

    geometry_cfg = normalize_config({
        "render_mode": "geometry_generator",
        "height_field": "height",
        "floor_bands_enabled": True,
        "projection_angle": 60.0,
    })
    assert apply_geometry_generator_25d_style(layer, geometry_cfg)
    assert isinstance(layer.renderer(), QgsSingleSymbolRenderer)
    assert layer.renderer().orderByEnabled()
    assert layer.renderer().symbol().symbolLayerCount() >= 3
    record_pass("Ordered multi-layer geometry renderer")

    floor_cfg = normalize_config({
        "render_mode": "per_floor_bands",
        "height_field": "building_levels",
        "max_floors": 8,
    })
    assert apply_per_floor_bands_style(layer, floor_cfg)
    assert isinstance(layer.renderer(), QgsRuleBasedRenderer)
    assert layer.renderer().rootRule().children()
    record_pass("Per-floor rule renderer")

    for preset_key in PRESETS:
        assert apply_preset_to_layer(layer, preset_key, height_field="height")
    record_pass(f"All {len(PRESETS)} presets")

    for mode in ("geometry_generator", "per_floor_bands", "native"):
        assert apply_25d_style(layer, {"render_mode": mode, "height_field": "height"})
    record_pass("Dispatcher mode matrix")

    qml_path = os.path.join(tempfile.gettempdir(), "qgis_25d_release_test.qml")
    assert export_layer_qml(layer, qml_path)
    assert os.path.getsize(qml_path) > 100
    assert load_layer_qml(layer, qml_path)
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
    from qgis.core import QgsGeometryGeneratorSymbolLayer

    bld = QgsVectorLayer("Polygon?crs=EPSG:32635&field=height:double&field=levels:integer",
                         "alg_buildings", "memory")
    rows = []
    for i, (h, lv) in enumerate(((9.0, 3), (18.0, 6), (27.0, 9))):
        x0 = 500000 + i * 30
        f = QgsFeature(bld.fields())
        f.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(x0, 4200000), QgsPointXY(x0 + 20, 4200000),
                                                  QgsPointXY(x0 + 20, 4200020), QgsPointXY(x0, 4200020),
                                                  QgsPointXY(x0, 4200000)]]))
        f.setAttributes([h, lv])
        rows.append(f)
    bld.dataProvider().addFeatures(rows)
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
        sym = loaded.renderer().symbol() if isinstance(loaded.renderer(), QgsSingleSymbolRenderer) else None
        layers = [sym.symbolLayer(k) for k in range(sym.symbolLayerCount())] if sym else []
        assert layers and all(isinstance(sl, QgsGeometryGeneratorSymbolLayer) for sl in layers), \
            f"loaded output is not 2.5D-styled: {[type(sl).__name__ for sl in layers]}"
        assert os.path.exists(qml) and os.path.getsize(qml) > 1000, "QML style was not written"
        with open(qml, encoding="utf-8") as fh:
            assert fh.read().count('class="GeometryGenerator"') >= 3, "QML lacks the 2.5D style"
    record_pass("Processing output is 2.5D-styled on load and QML is written (temporary + GeoPackage)")

    # per-floor bands: the tallest building (9 levels) sets the band count,
    # read from the data during the run, not from the not-yet-loaded output
    mode_keys = algorithms[0].RENDER_MODE_KEYS
    loaded = _run_loaded({"INPUT": bld, "HEIGHT_FIELD": "levels",
                          "RENDER_MODE": mode_keys.index("per_floor_bands"),
                          "OUTPUT": os.path.join(out_dir, "floors.gpkg")})
    assert isinstance(loaded.renderer(), QgsRuleBasedRenderer), type(loaded.renderer()).__name__
    labels = " ".join(r.label() or "" for r in loaded.renderer().rootRule().descendants())
    assert "9" in labels, f"band rules do not reach floor 9: {labels[:200]}"
    record_pass("Per-floor bands use the data's maximum floor count")
    QgsApplication.processingRegistry().removeProvider(processing_provider)

    QgsProject.instance().removeAllMapLayers()

    print(f"\nPASSED: {passed_count}")
finally:
    qgs.exitQgis()
