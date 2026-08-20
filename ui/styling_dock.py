# -*- coding: utf-8 -*-
"""Main right-docked panel for QGIS 2.5D Styling."""
from __future__ import annotations

import contextlib
import math
import os
import tempfile
from typing import Any, Dict, Optional

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMapLayer,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsRectangle,
    QgsSingleSymbolRenderer,
    QgsFillSymbol,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsDoubleSpinBox, QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.osm_downloader import (
    OsmDownloadError,
    build_overpass_building_query,
    fetch_overpass_json,
    osm_json_to_vector_layer,
)
from ..core.presets import PRESETS, STANDARD_ANGLES
from ..core.qml_exporter import export_layer_qml, load_layer_qml
from ..core.twopointfive_engine import apply_25d_style
from .color_button import ColorPickerButton
from .segmented_tabs import StylingSubTabs


def _get_icon(name: str = "icon.png") -> QIcon:
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "icons", name)
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


class StylingDockWidget(QDockWidget):
    """QGIS 2.5D Styling Dock Widget (Docked on the Right Side)."""

    def __init__(self, iface, parent: Optional[QWidget] = None):
        super().__init__("QGIS 2.5D Styling", parent or (iface.mainWindow() if iface else None))
        self.iface = iface
        _LeftDock = getattr(getattr(Qt, "DockWidgetArea", Qt), "LeftDockWidgetArea", getattr(Qt, "LeftDockWidgetArea", 1))
        _RightDock = getattr(getattr(Qt, "DockWidgetArea", Qt), "RightDockWidgetArea", getattr(Qt, "RightDockWidgetArea", 2))
        self.setAllowedAreas(_LeftDock | _RightDock)

        self._updating_controls = False

        self._build_ui()
        self._apply_style()
        self._connect_signals()

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QDockWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }
            QFrame#heroCard {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                margin-bottom: 6px;
            }
            QLabel#heroTitle {
                font-size: 15px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#heroSub {
                font-size: 11px;
                color: #64748b;
            }
            QFrame#subTabHeader {
                background: transparent;
                border-bottom: 1px solid #cbd5e1;
            }
            QPushButton#subTabBtn {
                background: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                margin-bottom: -1px;
                margin-right: 3px;
            }
            QPushButton#subTabBtn:hover:!checked {
                background: #e2e8f0;
                color: #0f172a;
            }
            QPushButton#subTabBtn:checked {
                background: #ffffff;
                color: #1d4ed8;
                font-weight: 700;
                border: 1px solid #94a3b8;
                border-bottom: 2px solid #2563eb;
            }
            QStackedWidget#subTabStack {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QGroupBox {
                font-weight: 700;
                font-size: 11px;
                color: #1e293b;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
            QPushButton.primaryBtn {
                background: #2563eb;
                color: #ffffff;
                font-weight: 700;
                padding: 8px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton.primaryBtn:hover {
                background: #1d4ed8;
            }
            QPushButton.presetCardBtn {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                text-align: left;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton.presetCardBtn:hover {
                background: #eff6ff;
                border-color: #3b82f6;
                color: #1d4ed8;
            }
        """)

    def _build_ui(self) -> None:
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Hero Header ──
        hero = QFrame()
        hero.setObjectName("heroCard")
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(10, 8, 10, 8)
        hl.setSpacing(2)

        title_lbl = QLabel("QGIS 2.5D Styling Studio")
        title_lbl.setObjectName("heroTitle")
        sub_lbl = QLabel("Architectural 2.5D Extrusions, Solar Shading & OSM Downloader")
        sub_lbl.setObjectName("heroSub")
        hl.addWidget(title_lbl)
        hl.addWidget(sub_lbl)
        root.addWidget(hero)

        # ── Layer Selector Card ──
        layer_card = QFrame()
        layer_card.setStyleSheet("background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px;")
        layer_lyt = QFormLayout(layer_card)
        layer_lyt.setContentsMargins(6, 6, 6, 6)

        self.cb_layer = QgsMapLayerComboBox()
        self.cb_layer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layer_lyt.addRow("Target Layer:", self.cb_layer)

        root.addWidget(layer_card)

        # ── Main Segmented Tabs ──
        self.tabs = StylingSubTabs()

        # Tab 1: OSM Downloader
        self.tabs.addTab(self._build_osm_tab(), "🌍 OSM Fetch")

        # Tab 2: 2.5D Extrusion & Angle
        self.tabs.addTab(self._build_extrusion_tab(), "🏢 Extrusion")

        # Tab 3: Lighting & Shadows
        self.tabs.addTab(self._build_lighting_tab(), "☀️ Lighting")

        # Tab 4: Facade & Floor Bands
        self.tabs.addTab(self._build_facade_tab(), "🎨 Facade")

        # Tab 5: Presets & QML
        self.tabs.addTab(self._build_presets_tab(), "✨ Presets")

        root.addWidget(self.tabs, 1)

        # ── Bottom Action Toolbar ──
        action_card = QFrame()
        action_lyt = QVBoxLayout(action_card)
        action_lyt.setContentsMargins(0, 4, 0, 0)
        action_lyt.setSpacing(6)

        self.chk_auto_apply = QCheckBox("⚡ Live Auto-Apply on Change")
        self.chk_auto_apply.setChecked(True)
        self.chk_auto_apply.setStyleSheet("font-weight: 600; color: #0f172a;")
        action_lyt.addWidget(self.chk_auto_apply)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_apply = QPushButton("🚀 Apply 2.5D Style")
        self.btn_apply.setProperty("class", "primaryBtn")
        self.btn_apply.setStyleSheet("background: #2563eb; color: white; font-weight: 700; padding: 7px; border-radius: 5px;")
        self.btn_apply.clicked.connect(self.apply_current_style)

        self.btn_reset = QPushButton("↺ Reset 2D")
        self.btn_reset.setToolTip("Reset to standard flat 2D single symbol")
        self.btn_reset.clicked.connect(self.reset_to_2d)

        self.btn_export_qml = QPushButton("💾 Export QML")
        self.btn_export_qml.clicked.connect(self.export_qml)

        btn_row.addWidget(self.btn_apply, 2)
        btn_row.addWidget(self.btn_reset, 1)
        btn_row.addWidget(self.btn_export_qml, 1)

        action_lyt.addLayout(btn_row)
        root.addWidget(action_card)

        self.setWidget(container)

    # -----------------------------------------------------------------
    # Tab 1: OSM Acquisition Panel
    # -----------------------------------------------------------------
    def _build_osm_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(8)

        gb_bbox = QGroupBox("Acquisition Scope")
        fl_bbox = QFormLayout(gb_bbox)

        self.cb_extent_mode = QComboBox()
        self.cb_extent_mode.addItems([
            "Current Map Canvas Extent",
            "Active Layer Extent",
            "Custom Bounding Box",
        ])
        fl_bbox.addRow("Extent Source:", self.cb_extent_mode)

        self.sp_default_height = QgsDoubleSpinBox()
        self.sp_default_height.setRange(1.0, 200.0)
        self.sp_default_height.setValue(9.0)
        self.sp_default_height.setSuffix(" m")
        fl_bbox.addRow("Default Height:", self.sp_default_height)

        self.sp_floor_height = QgsDoubleSpinBox()
        self.sp_floor_height.setRange(1.0, 10.0)
        self.sp_floor_height.setValue(3.0)
        self.sp_floor_height.setSuffix(" m")
        fl_bbox.addRow("Floor Height:", self.sp_floor_height)

        lyt.addWidget(gb_bbox)

        self.lbl_osm_status = QLabel("Ready to fetch building footprints.")
        self.lbl_osm_status.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_osm_status.setWordWrap(True)
        lyt.addWidget(self.lbl_osm_status)

        self.btn_download_osm = QPushButton("🌐 Download OSM 3D Buildings")
        self.btn_download_osm.setStyleSheet("background: #065f46; color: #ffffff; font-weight: 700; padding: 8px; border-radius: 6px;")
        self.btn_download_osm.clicked.connect(self.download_osm_buildings)
        lyt.addWidget(self.btn_download_osm)

        lyt.addStretch()
        return scroll

    # -----------------------------------------------------------------
    # Tab 2: 2.5D Extrusion & Projection Angle
    # -----------------------------------------------------------------
    def _build_extrusion_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(8)

        # Height Attributes
        gb_h = QGroupBox("Building Height Calculation")
        fl_h = QFormLayout(gb_h)

        self.cb_height_field = QgsFieldComboBox()
        fl_h.addRow("Height Field:", self.cb_height_field)

        self.sp_multiplier = QgsDoubleSpinBox()
        self.sp_multiplier.setRange(0.1, 10.0)
        self.sp_multiplier.setSingleStep(0.1)
        self.sp_multiplier.setValue(1.0)
        fl_h.addRow("Height Scale:", self.sp_multiplier)

        self.cb_render_engine = QComboBox()
        self.cb_render_engine.addItems([
            "Geometry Generator (Multi-Layer & Shaded)",
            "Native QGIS 2.5D Renderer",
        ])
        fl_h.addRow("Engine:", self.cb_render_engine)
        lyt.addWidget(gb_h)

        # Projection Angle
        gb_ang = QGroupBox("Projection Angle & Perspective")
        fl_ang = QFormLayout(gb_ang)

        self.slider_angle = QSlider(Qt.Horizontal)
        self.slider_angle.setRange(0, 360)
        self.slider_angle.setValue(45)

        self.sp_angle = QSpinBox()
        self.sp_angle.setRange(0, 360)
        self.sp_angle.setValue(45)
        self.sp_angle.setSuffix("°")

        ang_row = QHBoxLayout()
        ang_row.addWidget(self.slider_angle, 2)
        ang_row.addWidget(self.sp_angle, 1)
        fl_ang.addRow("Angle:", ang_row)

        self.slider_angle.valueChanged.connect(self.sp_angle.setValue)
        self.sp_angle.valueChanged.connect(self.slider_angle.setValue)

        # Quick Angle Presets
        angle_btns_grid = QGridLayout()
        angles = [
            ("Isometric (45°)", 45),
            ("Oblique (30°)", 30),
            ("Cavalier (60°)", 60),
            ("Plan Oblique (135°)", 135),
        ]
        for i, (txt, val) in enumerate(angles):
            btn = QPushButton(txt)
            btn.setStyleSheet("font-size: 10px; padding: 3px;")
            btn.clicked.connect(lambda chk, v=val: self.sp_angle.setValue(v))
            angle_btns_grid.addWidget(btn, i // 2, i % 2)

        fl_ang.addRow("Standard Angles:", angle_btns_grid)
        lyt.addWidget(gb_ang)

        lyt.addStretch()
        return scroll

    # -----------------------------------------------------------------
    # Tab 3: Lighting & Shadows
    # -----------------------------------------------------------------
    def _build_lighting_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(8)

        # Solar Illumination
        gb_sun = QGroupBox("Solar Illumination & Facade Shading")
        fl_sun = QFormLayout(gb_sun)

        self.chk_facade_shading = QCheckBox("Enable Dynamic Solar Shading")
        self.chk_facade_shading.setChecked(True)
        fl_sun.addRow(self.chk_facade_shading)

        self.slider_sun_azimuth = QSlider(Qt.Horizontal)
        self.slider_sun_azimuth.setRange(0, 360)
        self.slider_sun_azimuth.setValue(315)
        self.sp_sun_azimuth = QSpinBox()
        self.sp_sun_azimuth.setRange(0, 360)
        self.sp_sun_azimuth.setValue(315)
        self.sp_sun_azimuth.setSuffix("° (NW)")
        sun_row = QHBoxLayout()
        sun_row.addWidget(self.slider_sun_azimuth, 2)
        sun_row.addWidget(self.sp_sun_azimuth, 1)
        fl_sun.addRow("Sun Azimuth:", sun_row)
        self.slider_sun_azimuth.valueChanged.connect(self.sp_sun_azimuth.setValue)
        self.sp_sun_azimuth.valueChanged.connect(self.slider_sun_azimuth.setValue)

        self.slider_shading_intensity = QSlider(Qt.Horizontal)
        self.slider_shading_intensity.setRange(0, 100)
        self.slider_shading_intensity.setValue(40)
        fl_sun.addRow("Shading Depth:", self.slider_shading_intensity)
        lyt.addWidget(gb_sun)

        # Ground Drop Shadow
        gb_shadow = QGroupBox("Ground Drop Shadow")
        fl_shadow = QFormLayout(gb_shadow)

        self.chk_shadow = QCheckBox("Enable Ground Drop Shadow")
        self.chk_shadow.setChecked(True)
        fl_shadow.addRow(self.chk_shadow)

        self.btn_shadow_color = ColorPickerButton("#0f172a")
        fl_shadow.addRow("Shadow Color:", self.btn_shadow_color)

        self.slider_shadow_alpha = QSlider(Qt.Horizontal)
        self.slider_shadow_alpha.setRange(0, 100)
        self.slider_shadow_alpha.setValue(40)
        fl_shadow.addRow("Shadow Opacity (%):", self.slider_shadow_alpha)

        self.sp_shadow_blur = QgsDoubleSpinBox()
        self.sp_shadow_blur.setRange(0.0, 20.0)
        self.sp_shadow_blur.setValue(4.0)
        self.sp_shadow_blur.setSuffix(" mm")
        fl_shadow.addRow("Blur Radius:", self.sp_shadow_blur)

        lyt.addWidget(gb_shadow)
        lyt.addStretch()
        return scroll

    # -----------------------------------------------------------------
    # Tab 4: Facade & Floor Bands
    # -----------------------------------------------------------------
    def _build_facade_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(8)

        # Materials & Colors
        gb_col = QGroupBox("Building Massing Materials")
        fl_col = QFormLayout(gb_col)

        self.btn_wall_color = ColorPickerButton("#e2e8f0")
        fl_col.addRow("Wall / Facade:", self.btn_wall_color)

        self.btn_roof_color = ColorPickerButton("#ffffff")
        fl_col.addRow("Roof Cap:", self.btn_roof_color)

        self.btn_outline_color = ColorPickerButton("#475569")
        fl_col.addRow("Wall Outline:", self.btn_outline_color)

        self.sp_outline_width = QgsDoubleSpinBox()
        self.sp_outline_width.setRange(0.0, 2.0)
        self.sp_outline_width.setSingleStep(0.05)
        self.sp_outline_width.setValue(0.3)
        self.sp_outline_width.setSuffix(" mm")
        fl_col.addRow("Outline Width:", self.sp_outline_width)

        self.btn_roof_outline = ColorPickerButton("#334155")
        fl_col.addRow("Roof Outline:", self.btn_roof_outline)

        self.sp_roof_outline_width = QgsDoubleSpinBox()
        self.sp_roof_outline_width.setRange(0.0, 2.0)
        self.sp_roof_outline_width.setSingleStep(0.05)
        self.sp_roof_outline_width.setValue(0.4)
        self.sp_roof_outline_width.setSuffix(" mm")
        fl_col.addRow("Roof Edge Width:", self.sp_roof_outline_width)

        lyt.addWidget(gb_col)

        # Floor Band Divisions
        gb_floors = QGroupBox("Architectural Floor Bands (Mullions)")
        fl_floors = QFormLayout(gb_floors)

        self.chk_floor_bands = QCheckBox("Enable Floor Division Lines")
        self.chk_floor_bands.setChecked(True)
        fl_floors.addRow(self.chk_floor_bands)

        self.sp_band_height = QgsDoubleSpinBox()
        self.sp_band_height.setRange(1.0, 20.0)
        self.sp_band_height.setValue(3.2)
        self.sp_band_height.setSuffix(" m")
        fl_floors.addRow("Story Height:", self.sp_band_height)

        self.btn_floor_line_col = ColorPickerButton("#cbd5e1")
        fl_floors.addRow("Floor Line Color:", self.btn_floor_line_col)

        self.sp_floor_line_w = QgsDoubleSpinBox()
        self.sp_floor_line_w.setRange(0.05, 1.5)
        self.sp_floor_line_w.setSingleStep(0.05)
        self.sp_floor_line_w.setValue(0.2)
        self.sp_floor_line_w.setSuffix(" mm")
        fl_floors.addRow("Floor Line Width:", self.sp_floor_line_w)

        lyt.addWidget(gb_floors)
        lyt.addStretch()
        return scroll

    # -----------------------------------------------------------------
    # Tab 5: Architectural Presets & QML
    # -----------------------------------------------------------------
    def _build_presets_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        lbl = QLabel("1-Click Curated Architectural Archetypes:")
        lbl.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        lyt.addWidget(lbl)

        for key, p in PRESETS.items():
            btn = QPushButton(f"{p['name']}\n{p['description']}")
            btn.setProperty("class", "presetCardBtn")
            btn.setStyleSheet(
                "QPushButton { background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; "
                "padding: 6px 10px; text-align: left; font-size: 11px; } "
                "QPushButton:hover { background: #eff6ff; border-color: #3b82f6; color: #1d4ed8; }"
            )
            btn.clicked.connect(lambda chk, k=key: self.apply_preset(k))
            lyt.addWidget(btn)

        lyt.addStretch()
        return scroll

    # -----------------------------------------------------------------
    # Signal Connections & Live Updates
    # -----------------------------------------------------------------
    def _connect_signals(self) -> None:
        self.cb_layer.layerChanged.connect(self._on_layer_changed)

        # Connect live auto-apply triggers
        controls = [
            self.sp_multiplier,
            self.cb_render_engine,
            self.sp_angle,
            self.chk_facade_shading,
            self.sp_sun_azimuth,
            self.slider_shading_intensity,
            self.chk_shadow,
            self.slider_shadow_alpha,
            self.sp_shadow_blur,
            self.sp_outline_width,
            self.sp_roof_outline_width,
            self.chk_floor_bands,
            self.sp_band_height,
            self.sp_floor_line_w,
        ]
        for c in controls:
            if hasattr(c, "valueChanged"):
                c.valueChanged.connect(self._maybe_auto_apply)
            elif hasattr(c, "currentIndexChanged"):
                c.currentIndexChanged.connect(self._maybe_auto_apply)
            elif hasattr(c, "toggled"):
                c.toggled.connect(self._maybe_auto_apply)

        color_btns = [
            self.btn_wall_color,
            self.btn_roof_color,
            self.btn_outline_color,
            self.btn_shadow_color,
            self.btn_roof_outline,
            self.btn_floor_line_col,
        ]
        for btn in color_btns:
            btn.colorChanged.connect(self._maybe_auto_apply)

    def _on_layer_changed(self, layer: Optional[QgsMapLayer]) -> None:
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            self.cb_height_field.setLayer(layer)
            # Try to auto-select 'height' or 'building_levels'
            for fname in ("height", "building_levels", "levels", "h"):
                idx = layer.fields().indexOf(fname)
                if idx >= 0:
                    self.cb_height_field.setField(fname)
                    break

    def _maybe_auto_apply(self, *args) -> None:
        if self._updating_controls:
            return
        if self.chk_auto_apply.isChecked():
            self.apply_current_style()

    def get_current_config(self) -> Dict[str, Any]:
        """Harvest current GUI parameters into a configuration dictionary."""
        return {
            "height_field": self.cb_height_field.currentField() or "height",
            "height_multiplier": self.sp_multiplier.value(),
            "use_geometry_generator": (self.cb_render_engine.currentIndex() == 0),
            "projection_angle": float(self.sp_angle.value()),
            "wall_color": self.btn_wall_color.color().name(),
            "roof_color": self.btn_roof_color.color().name(),
            "outline_color": self.btn_outline_color.color().name(),
            "outline_width": self.sp_outline_width.value(),
            "roof_outline_color": self.btn_roof_outline.color().name(),
            "roof_outline_width": self.sp_roof_outline_width.value(),
            "facade_shading": self.chk_facade_shading.isChecked(),
            "sun_azimuth": float(self.sp_sun_azimuth.value()),
            "shading_intensity": float(self.slider_shading_intensity.value()) / 100.0,
            "shadow_enabled": self.chk_shadow.isChecked(),
            "shadow_color": self.btn_shadow_color.color().name(),
            "shadow_alpha": self.slider_shadow_alpha.value(),
            "shadow_blur": self.sp_shadow_blur.value(),
            "floor_bands_enabled": self.chk_floor_bands.isChecked(),
            "floor_height_m": self.sp_band_height.value(),
            "floor_line_color": self.btn_floor_line_col.color().name(),
            "floor_line_width": self.sp_floor_line_w.value(),
        }

    def load_config_into_ui(self, cfg: Dict[str, Any]) -> None:
        """Load a configuration dictionary into UI widgets without firing auto-apply on each step."""
        self._updating_controls = True
        try:
            if "wall_color" in cfg:
                self.btn_wall_color.setColor(cfg["wall_color"])
            if "roof_color" in cfg:
                self.btn_roof_color.setColor(cfg["roof_color"])
            if "outline_color" in cfg:
                self.btn_outline_color.setColor(cfg["outline_color"])
            if "outline_width" in cfg:
                self.sp_outline_width.setValue(float(cfg["outline_width"]))
            if "roof_outline_color" in cfg:
                self.btn_roof_outline.setColor(cfg["roof_outline_color"])
            if "roof_outline_width" in cfg:
                self.sp_roof_outline_width.setValue(float(cfg["roof_outline_width"]))
            if "projection_angle" in cfg:
                self.sp_angle.setValue(int(cfg["projection_angle"]))
            if "sun_azimuth" in cfg:
                self.sp_sun_azimuth.setValue(int(cfg["sun_azimuth"]))
            if "facade_shading" in cfg:
                self.chk_facade_shading.setChecked(bool(cfg["facade_shading"]))
            if "shading_intensity" in cfg:
                self.slider_shading_intensity.setValue(int(cfg["shading_intensity"] * 100))
            if "shadow_enabled" in cfg:
                self.chk_shadow.setChecked(bool(cfg["shadow_enabled"]))
            if "shadow_color" in cfg:
                self.btn_shadow_color.setColor(cfg["shadow_color"])
            if "shadow_alpha" in cfg:
                self.slider_shadow_alpha.setValue(int(cfg["shadow_alpha"]))
            if "shadow_blur" in cfg:
                self.sp_shadow_blur.setValue(float(cfg["shadow_blur"]))
            if "floor_bands_enabled" in cfg:
                self.chk_floor_bands.setChecked(bool(cfg["floor_bands_enabled"]))
            if "floor_height_m" in cfg:
                self.sp_band_height.setValue(float(cfg["floor_height_m"]))
            if "floor_line_color" in cfg:
                self.btn_floor_line_col.setColor(cfg["floor_line_color"])
            if "floor_line_width" in cfg:
                self.sp_floor_line_w.setValue(float(cfg["floor_line_width"]))
        finally:
            self._updating_controls = False

    def apply_current_style(self) -> None:
        """Apply current configuration to the selected polygon layer."""
        layer = self.cb_layer.currentLayer()
        if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            return

        cfg = self.get_current_config()
        success = apply_25d_style(layer, cfg)
        if success and hasattr(self.iface, "messageBar"):
            pass  # quiet success for smooth live auto-apply

    def apply_preset(self, preset_key: str) -> None:
        """Load and apply preset archetype."""
        if preset_key in PRESETS:
            cfg = dict(PRESETS[preset_key])
            self.load_config_into_ui(cfg)
            self.apply_current_style()
            if hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushSuccess("2.5D Styling", f"Applied preset: {PRESETS[preset_key]['name']}")

    def reset_to_2d(self) -> None:
        """Reset the layer to standard 2D flat symbology."""
        layer = self.cb_layer.currentLayer()
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            sym = QgsFillSymbol.createSimple({
                "color": "#cbd5e1",
                "outline_color": "#334155",
                "outline_width": "0.3",
            })
            layer.setRenderer(QgsSingleSymbolRenderer(sym))
            layer.triggerRepaint()
            if hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushInfo("2.5D Styling", "Reset layer to standard 2D flat fill.")

    def export_qml(self) -> None:
        """Export current style to .qml file."""
        layer = self.cb_layer.currentLayer()
        if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
            QMessageBox.warning(self, "Export QML", "Please select a valid vector layer first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Export 2.5D QML Style", "style_25d.qml", "QGIS Layer Style (*.qml)")
        if path:
            if export_layer_qml(layer, path):
                QMessageBox.information(self, "Export QML", f"Saved style to:\n{path}")
            else:
                QMessageBox.critical(self, "Export QML", "Failed to export QML style.")

    def download_osm_buildings(self) -> None:
        """Download OSM building footprints for the current extent and apply 2.5D styling."""
        if not self.iface or not self.iface.mapCanvas():
            QMessageBox.warning(self, "OSM Fetch", "No active map canvas found.")
            return

        canvas = self.iface.mapCanvas()
        mode_idx = self.cb_extent_mode.currentIndex()

        if mode_idx == 0:
            # Map canvas extent
            rect = canvas.extent()
            src_crs = canvas.mapSettings().destinationCrs()
        elif mode_idx == 1:
            # Active layer extent
            lyr = self.cb_layer.currentLayer()
            if not lyr:
                QMessageBox.warning(self, "OSM Fetch", "No active layer selected.")
                return
            rect = lyr.extent()
            src_crs = lyr.crs()
        else:
            rect = canvas.extent()
            src_crs = canvas.mapSettings().destinationCrs()

        # Transform extent to EPSG:4326 WGS84 for Overpass query
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        trans = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
        wgs_rect = trans.transformBoundingBox(rect)

        # Bounding box safety check (limit query size)
        d_lat = abs(wgs_rect.yMaximum() - wgs_rect.yMinimum())
        d_lon = abs(wgs_rect.xMaximum() - wgs_rect.xMinimum())
        if d_lat > 0.35 or d_lon > 0.35:
            res = QMessageBox.question(
                self,
                "Large Area Warning",
                "The requested extent is quite large (>30km) and may take longer or timeout.\nDo you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        self.lbl_osm_status.setText("⏳ Querying Overpass API mirrors for building footprints...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            q = build_overpass_building_query(
                wgs_rect.yMinimum(),
                wgs_rect.xMinimum(),
                wgs_rect.yMaximum(),
                wgs_rect.xMaximum(),
            )
            osm_data = fetch_overpass_json(q)
            count = len(osm_data.get("elements", []))

            if count == 0:
                self.lbl_osm_status.setText("No building footprints found in this extent.")
                QMessageBox.information(self, "OSM Fetch", "No building footprints found in the selected extent.")
                return

            self.lbl_osm_status.setText(f"Found {count} OSM elements. Building vector layer...")
            dest_crs = canvas.mapSettings().destinationCrs()
            layer = osm_json_to_vector_layer(
                osm_data,
                target_crs=dest_crs,
                layer_name=f"OSM_Buildings_25D",
                default_height=self.sp_default_height.value(),
                floor_height_m=self.sp_floor_height.value(),
            )

            if layer and layer.featureCount() > 0:
                QgsProject.instance().addMapLayer(layer)
                self.cb_layer.setLayer(layer)
                self.apply_current_style()
                self.lbl_osm_status.setText(f"✅ Loaded {layer.featureCount()} 3D buildings successfully.")
                if hasattr(self.iface, "messageBar"):
                    self.iface.messageBar().pushSuccess("2.5D Styling", f"Acquired {layer.featureCount()} OSM 3D buildings.")
            else:
                self.lbl_osm_status.setText("Failed to construct building polygon geometries.")
        except Exception as exc:
            self.lbl_osm_status.setText(f"❌ Error: {exc}")
            QMessageBox.critical(self, "OSM Download Error", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
