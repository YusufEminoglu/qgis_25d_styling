# -*- coding: utf-8 -*-
"""Focused, dockable workflow for applying 2.5D polygon symbology."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFieldProxyModel,
    QgsMapLayer,
    QgsMapLayerProxyModel,
    QgsProject,
    QgsTask,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsDoubleSpinBox, QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import QSettings, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QPixmap
from qgis.PyQt.QtWidgets import (
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
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.config import choose_height_field, compass_direction, normalize_config
from ..core.osm_downloader import build_overpass_building_query, fetch_overpass_json, osm_json_to_vector_layer
from ..core.presets import FLOOR_BAND_PALETTES, PRESETS, STANDARD_ANGLES
from ..core.qml_exporter import export_layer_qml, load_layer_qml
from ..core.twopointfive_engine import apply_25d_style
from .color_button import ColorPickerButton


def _horizontal() -> Any:
    return getattr(getattr(Qt, "Orientation", Qt), "Horizontal", getattr(Qt, "Horizontal", 1))


def _no_frame() -> Any:
    return getattr(getattr(QFrame, "Shape", QFrame), "NoFrame", getattr(QFrame, "NoFrame", 0))


def _form_growth_policy() -> Any:
    return getattr(
        getattr(QFormLayout, "FieldGrowthPolicy", QFormLayout),
        "AllNonFixedFieldsGrow",
        getattr(QFormLayout, "AllNonFixedFieldsGrow", 1),
    )


def _standard_icon(widget: QWidget, name: str):
    enum = getattr(getattr(QStyle, "StandardPixmap", QStyle), name, getattr(QStyle, name, None))
    return widget.style().standardIcon(enum) if enum is not None else widget.windowIcon()


class StylingDockWidget(QDockWidget):
    """Right/left dock dedicated to polygon-to-2.5D styling."""

    SETTINGS_GROUP = "qgis_25d_styling/dock"

    def __init__(self, iface, parent: Optional[QWidget] = None):
        super().__init__("QGIS 2.5D Styling", parent or (iface.mainWindow() if iface else None))
        self.iface = iface
        right = getattr(getattr(Qt, "DockWidgetArea", Qt), "RightDockWidgetArea", getattr(Qt, "RightDockWidgetArea", 2))
        self.setAllowedAreas(right)
        self.setMinimumWidth(340)
        self.setMaximumWidth(480)
        self.setMaximumHeight(790)
        self.setObjectName("Qgis25DStylingDock")

        self._updating_controls = False
        self._original_renderers: Dict[str, Any] = {}
        self._osm_task = None
        self._osm_cancel_requested = False
        self._osm_floor_height = 3.2
        self._osm_default_levels = 3
        self._settings = QSettings("PlanX", "QGIS25DStyling")
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.timeout.connect(lambda: self.apply_current_style(automatic=True))

        self._build_ui()
        self._connect_signals()
        self._restore_settings()

        active = self.iface.activeLayer() if self.iface and hasattr(self.iface, "activeLayer") else None
        if isinstance(active, QgsVectorLayer):
            self.cb_layer.setLayer(active)
        self._on_layer_changed(self.cb_layer.currentLayer())

    def _scroll_page(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(_no_frame())
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(8)
        scroll.setWidget(body)
        return scroll, layout

    def _build_ui(self) -> None:
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(7)

        hero = QFrame()
        hero.setObjectName("heroPanel")
        hero.setStyleSheet("QFrame#heroPanel { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 6px; }")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(10, 7, 10, 7)
        hero_layout.setSpacing(9)
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "icon.png")
        pixmap = QPixmap(icon_path)
        icon_label.setPixmap(pixmap.scaled(56, 56, getattr(getattr(Qt, "AspectRatioMode", Qt), "KeepAspectRatio", getattr(Qt, "KeepAspectRatio", 1)), getattr(getattr(Qt, "TransformationMode", Qt), "SmoothTransformation", getattr(Qt, "SmoothTransformation", 1))))
        icon_label.setFixedSize(58, 58)
        hero_layout.addWidget(icon_label)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(0)
        eyebrow = QLabel("2.5D BUILDING STYLER")
        eyebrow.setStyleSheet("font-size: 9px; font-weight: 700; color: palette(text); letter-spacing: 0px;")
        title = QLabel("QGIS 2.5D")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        subtitle = QLabel("OSM buildings and floor-by-floor colour")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 10px; color: palette(text);")
        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)
        badge = QLabel("OSM\n2.5D")
        badge.setAlignment(getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignCenter", getattr(Qt, "AlignCenter", 132)))
        badge.setStyleSheet("font-size: 9px; font-weight: 700; border: 1px solid palette(highlight); border-radius: 4px; padding: 3px;")
        hero_layout.addWidget(badge)
        root.addWidget(hero)

        heading = QHBoxLayout()
        self.lbl_state = QLabel("Select a polygon layer")
        self.lbl_state.setAlignment(getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignRight", getattr(Qt, "AlignRight", 2)))
        self.lbl_state.setWordWrap(True)
        heading.addWidget(QLabel("Target"))
        heading.addWidget(self.lbl_state, 1)
        root.addLayout(heading)

        source = QGroupBox("Source")
        source_form = QFormLayout(source)
        source_form.setFieldGrowthPolicy(_form_growth_policy())
        self.cb_layer = QgsMapLayerComboBox()
        self.cb_layer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.cb_layer.setAccessibleName("Target polygon layer")
        source_form.addRow("Layer", self.cb_layer)

        self.cb_height_field = QgsFieldComboBox()
        self.cb_height_field.setFilters(QgsFieldProxyModel.Numeric)
        self.cb_height_field.setAllowEmptyFieldName(True)
        self.cb_height_field.setAccessibleName("Building height field")
        source_form.addRow("Height / floors", self.cb_height_field)

        self.sp_default_levels = QSpinBox()
        self.sp_default_levels.setRange(1, 100)
        self.sp_default_levels.setValue(3)
        self.sp_default_levels.setSuffix(" floors")
        self.sp_default_levels.setToolTip("Used when building:levels or the selected floor field is missing")
        source_form.addRow("Missing levels", self.sp_default_levels)

        height_row = QHBoxLayout()
        self.sp_default_height = QgsDoubleSpinBox()
        self.sp_default_height.setRange(0.5, 1000.0)
        self.sp_default_height.setValue(9.0)
        self.sp_default_height.setSuffix(" m")
        self.sp_default_height.setDecimals(1)
        self.sp_multiplier = QgsDoubleSpinBox()
        self.sp_multiplier.setRange(0.05, 20.0)
        self.sp_multiplier.setValue(1.0)
        self.sp_multiplier.setSingleStep(0.1)
        self.sp_multiplier.setPrefix("x ")
        height_row.addWidget(self.sp_default_height)
        height_row.addWidget(self.sp_multiplier)
        source_form.addRow("Fallback / scale", height_row)
        root.addWidget(source)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setAccessibleName("2.5D style settings")
        self.tabs.addTab(self._build_osm_tab(), "OSM")
        self.tabs.addTab(self._build_projection_tab(), "Form")
        self.tabs.addTab(self._build_lighting_tab(), "Light")
        self.tabs.addTab(self._build_surface_tab(), "Floors")
        self.tabs.addTab(self._build_presets_tab(), "Themes")
        root.addWidget(self.tabs)
        root.addStretch(1)

        self.lbl_diagnostics = QLabel()
        self.lbl_diagnostics.setWordWrap(True)
        self.lbl_diagnostics.setStyleSheet("padding: 4px;")
        root.addWidget(self.lbl_diagnostics)

        live_row = QHBoxLayout()
        self.chk_auto_apply = QCheckBox("Live preview")
        self.chk_auto_apply.setChecked(True)
        self.chk_auto_apply.setToolTip("Apply changes after a short pause")
        live_row.addWidget(self.chk_auto_apply)
        live_row.addStretch()
        self.lbl_apply_status = QLabel("Ready")
        live_row.addWidget(self.lbl_apply_status)
        root.addLayout(live_row)

        command_row = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setIcon(_standard_icon(self, "SP_DialogApplyButton"))
        self.btn_apply.setToolTip("Apply the current 2.5D style")
        self.btn_apply.setAccessibleName("Apply 2.5D style")
        self.btn_restore = QPushButton("Restore")
        self.btn_restore.setIcon(_standard_icon(self, "SP_DialogResetButton"))
        self.btn_restore.setToolTip("Restore the style that existed before the first apply")
        self.btn_import_qml = QPushButton()
        self.btn_import_qml.setIcon(_standard_icon(self, "SP_DialogOpenButton"))
        self.btn_import_qml.setToolTip("Import a QGIS layer style")
        self.btn_import_qml.setAccessibleName("Import QML style")
        self.btn_export_qml = QPushButton()
        self.btn_export_qml.setIcon(_standard_icon(self, "SP_DialogSaveButton"))
        self.btn_export_qml.setToolTip("Export the current QGIS layer style")
        self.btn_export_qml.setAccessibleName("Export QML style")
        command_row.addWidget(self.btn_apply, 2)
        command_row.addWidget(self.btn_restore)
        command_row.addStretch()
        command_row.addWidget(self.btn_import_qml)
        command_row.addWidget(self.btn_export_qml)
        root.addLayout(command_row)

        self.setWidget(container)

    def _build_osm_tab(self) -> QWidget:
        page, layout = self._scroll_page()
        acquisition = QGroupBox("Download building footprints")
        form = QFormLayout(acquisition)
        self.cb_osm_extent = QComboBox()
        self.cb_osm_extent.addItem("Current map view", "map")
        self.cb_osm_extent.addItem("Selected layer extent", "layer")
        form.addRow("Extent", self.cb_osm_extent)
        defaults = QLabel("Uses OSM building:levels. Missing values use the Missing levels setting above (default: 3 floors). Building height is floors x Story height.")
        defaults.setWordWrap(True)
        form.addRow(defaults)
        self.lbl_osm_status = QLabel("Ready to download OSM buildings.")
        self.lbl_osm_status.setWordWrap(True)
        form.addRow(self.lbl_osm_status)
        download_row = QHBoxLayout()
        self.btn_download_osm = QPushButton("Download buildings and style")
        self.btn_download_osm.setToolTip("Download OSM buildings for the chosen extent and apply the selected floor palette")
        self.btn_download_osm.setIcon(_standard_icon(self, "SP_ArrowDown"))
        self.btn_cancel_osm = QPushButton()
        self.btn_cancel_osm.setIcon(_standard_icon(self, "SP_DialogCancelButton"))
        self.btn_cancel_osm.setToolTip("Cancel the active OSM building download")
        self.btn_cancel_osm.setAccessibleName("Cancel OSM building download")
        self.btn_cancel_osm.setEnabled(False)
        download_row.addWidget(self.btn_download_osm, 1)
        download_row.addWidget(self.btn_cancel_osm)
        form.addRow(download_row)
        layout.addWidget(acquisition)
        layout.addStretch()
        return page

    def _build_projection_tab(self) -> QWidget:
        page, layout = self._scroll_page()
        engine_box = QGroupBox("Renderer")
        engine_form = QFormLayout(engine_box)
        self.cb_render_engine = QComboBox()
        self.cb_render_engine.addItem("Geometry generator", "geometry_generator")
        self.cb_render_engine.addItem("Per-floor color bands", "per_floor_bands")
        self.cb_render_engine.addItem("Native QGIS 2.5D", "native")
        self.cb_render_engine.setToolTip("Choose the 2.5D rendering method")
        engine_form.addRow("Mode", self.cb_render_engine)
        layout.addWidget(engine_box)

        angle_box = QGroupBox("Projection")
        angle_form = QFormLayout(angle_box)
        angle_row = QHBoxLayout()
        self.slider_angle = QSlider(_horizontal())
        self.slider_angle.setRange(0, 359)
        self.slider_angle.setValue(45)
        self.sp_angle = QSpinBox()
        self.sp_angle.setRange(0, 359)
        self.sp_angle.setValue(45)
        self.sp_angle.setSuffix(" deg")
        angle_row.addWidget(self.slider_angle, 2)
        angle_row.addWidget(self.sp_angle)
        angle_form.addRow("Direction", angle_row)

        quick_grid = QGridLayout()
        for index, (name, value) in enumerate(STANDARD_ANGLES):
            label = name.split("(", 1)[0].strip()
            button = QPushButton(label)
            button.setToolTip(f"Set projection to {int(value)} degrees")
            button.clicked.connect(lambda _checked=False, v=int(value): self.sp_angle.setValue(v))
            quick_grid.addWidget(button, index // 2, index % 2)
        angle_form.addRow("Quick angles", quick_grid)
        layout.addWidget(angle_box)
        layout.addStretch()
        return page

    def _build_lighting_tab(self) -> QWidget:
        page, layout = self._scroll_page()
        sun_box = QGroupBox("Facade shading")
        sun_form = QFormLayout(sun_box)
        self.chk_facade_shading = QCheckBox("Enabled")
        self.chk_facade_shading.setChecked(True)
        sun_form.addRow(self.chk_facade_shading)
        sun_row = QHBoxLayout()
        self.slider_sun_azimuth = QSlider(_horizontal())
        self.slider_sun_azimuth.setRange(0, 359)
        self.slider_sun_azimuth.setValue(315)
        self.sp_sun_azimuth = QSpinBox()
        self.sp_sun_azimuth.setRange(0, 359)
        self.sp_sun_azimuth.setValue(315)
        sun_row.addWidget(self.slider_sun_azimuth, 2)
        sun_row.addWidget(self.sp_sun_azimuth)
        azimuth_tip = "Native renderer has no directional control; only used in advanced modes"
        self.slider_sun_azimuth.setToolTip(azimuth_tip)
        self.sp_sun_azimuth.setToolTip(azimuth_tip)
        sun_form.addRow("Azimuth", sun_row)
        shade_row = QHBoxLayout()
        self.slider_shading_intensity = QSlider(_horizontal())
        self.slider_shading_intensity.setRange(0, 100)
        self.slider_shading_intensity.setValue(40)
        self.lbl_shading_value = QLabel("40%")
        self.lbl_shading_value.setMinimumWidth(38)
        shade_row.addWidget(self.slider_shading_intensity)
        shade_row.addWidget(self.lbl_shading_value)
        self.slider_shading_intensity.setToolTip(
            "Native renderer only supports on/off shading; depth only applies in advanced modes"
        )
        sun_form.addRow("Depth", shade_row)
        self._shading_controls = [self.slider_sun_azimuth, self.sp_sun_azimuth, self.slider_shading_intensity]
        layout.addWidget(sun_box)

        shadow_box = QGroupBox("Ground shadow")
        shadow_form = QFormLayout(shadow_box)
        self.chk_shadow = QCheckBox("Enabled")
        self.chk_shadow.setChecked(True)
        shadow_form.addRow(self.chk_shadow)
        self.btn_shadow_color = ColorPickerButton("#0f172a")
        shadow_form.addRow("Color", self.btn_shadow_color)
        opacity_row = QHBoxLayout()
        self.slider_shadow_alpha = QSlider(_horizontal())
        self.slider_shadow_alpha.setRange(0, 100)
        self.slider_shadow_alpha.setValue(40)
        self.lbl_shadow_alpha = QLabel("40%")
        self.lbl_shadow_alpha.setMinimumWidth(38)
        opacity_row.addWidget(self.slider_shadow_alpha)
        opacity_row.addWidget(self.lbl_shadow_alpha)
        shadow_form.addRow("Opacity", opacity_row)
        self.sp_shadow_blur = QgsDoubleSpinBox()
        self.sp_shadow_blur.setRange(0.0, 50.0)
        self.sp_shadow_blur.setValue(4.0)
        self.sp_shadow_blur.setSuffix(" map units")
        self.sp_shadow_blur.setToolTip("Native renderer shadow spread; retained as style metadata in advanced modes")
        shadow_form.addRow("Spread", self.sp_shadow_blur)
        self._shadow_controls = [self.btn_shadow_color, self.slider_shadow_alpha, self.sp_shadow_blur]
        layout.addWidget(shadow_box)
        layout.addStretch()
        return page

    def _build_surface_tab(self) -> QWidget:
        page, layout = self._scroll_page()
        material_box = QGroupBox("Materials")
        material_form = QFormLayout(material_box)
        self.btn_wall_color = ColorPickerButton("#7fb8b0")
        self.btn_roof_color = ColorPickerButton("#f7c3a1")
        self.btn_outline_color = ColorPickerButton("#3f6d66")
        self.btn_roof_outline = ColorPickerButton("#b97350")
        self.sp_outline_width = QgsDoubleSpinBox()
        self.sp_outline_width.setRange(0.0, 5.0)
        self.sp_outline_width.setValue(0.3)
        self.sp_outline_width.setSuffix(" mm")
        self.sp_roof_outline_width = QgsDoubleSpinBox()
        self.sp_roof_outline_width.setRange(0.0, 5.0)
        self.sp_roof_outline_width.setValue(0.4)
        self.sp_roof_outline_width.setSuffix(" mm")
        material_form.addRow("Facade", self.btn_wall_color)
        material_form.addRow("Roof", self.btn_roof_color)
        material_form.addRow("Facade outline", self.btn_outline_color)
        material_form.addRow("Outline width", self.sp_outline_width)
        material_form.addRow("Roof outline", self.btn_roof_outline)
        material_form.addRow("Roof line width", self.sp_roof_outline_width)
        layout.addWidget(material_box)

        floor_box = QGroupBox("Floor divisions")
        floor_form = QFormLayout(floor_box)
        self.chk_floor_bands = QCheckBox("Enabled")
        self.chk_floor_bands.setChecked(True)
        floor_form.addRow(self.chk_floor_bands)
        self.sp_band_height = QgsDoubleSpinBox()
        self.sp_band_height.setRange(0.5, 20.0)
        self.sp_band_height.setValue(3.2)
        self.sp_band_height.setSuffix(" m")
        self.btn_floor_line_col = ColorPickerButton("#cbd5e1")
        self.sp_floor_line_w = QgsDoubleSpinBox()
        self.sp_floor_line_w.setRange(0.0, 5.0)
        self.sp_floor_line_w.setValue(0.2)
        self.sp_floor_line_w.setSuffix(" mm")
        floor_form.addRow("Story height", self.sp_band_height)
        floor_form.addRow("Line color", self.btn_floor_line_col)
        floor_form.addRow("Line width", self.sp_floor_line_w)
        self._floor_controls = [self.sp_band_height, self.btn_floor_line_col, self.sp_floor_line_w]
        layout.addWidget(floor_box)

        palette_box = QGroupBox("Per-floor palette")
        palette_form = QFormLayout(palette_box)
        self.cb_floor_palette = QComboBox()
        for key, value in FLOOR_BAND_PALETTES.items():
            self.cb_floor_palette.addItem(value.get("name", key), key)
        palette_preview = QWidget()
        palette_preview_layout = QHBoxLayout(palette_preview)
        palette_preview_layout.setContentsMargins(0, 0, 0, 0)
        palette_preview_layout.setSpacing(2)
        self.floor_palette_swatches = []
        for _index in range(10):
            swatch = QFrame()
            swatch.setFixedHeight(15)
            swatch.setMinimumWidth(16)
            palette_preview_layout.addWidget(swatch, 1)
            self.floor_palette_swatches.append(swatch)
        self.sp_max_floors = QSpinBox()
        self.sp_max_floors.setRange(0, 100)
        self.sp_max_floors.setSpecialValueText("Auto")
        palette_form.addRow("Palette", self.cb_floor_palette)
        palette_form.addRow("Floors 1-10", palette_preview)
        palette_form.addRow("Maximum floors", self.sp_max_floors)
        self._palette_controls = [palette_box]
        layout.addWidget(palette_box)
        self._update_floor_palette_preview()
        layout.addStretch()
        return page

    def _build_presets_tab(self) -> QWidget:
        page, layout = self._scroll_page()
        self.cb_preset = QComboBox()
        for key, preset in PRESETS.items():
            self.cb_preset.addItem(preset["name"], key)
        layout.addWidget(self.cb_preset)
        swatch_grid = QGridLayout()
        swatch_grid.setSpacing(4)
        self.preset_swatches = []
        for column, title in enumerate(("Facade", "Roof", "Outline")):
            label = QLabel(title)
            label.setAlignment(getattr(getattr(Qt, "AlignmentFlag", Qt), "AlignCenter", getattr(Qt, "AlignCenter", 132)))
            swatch = QFrame()
            swatch.setMinimumHeight(24)
            swatch.setAccessibleName(f"Preset {title.lower()} color")
            swatch_grid.addWidget(label, 0, column)
            swatch_grid.addWidget(swatch, 1, column)
            self.preset_swatches.append(swatch)
        layout.addLayout(swatch_grid)
        self.lbl_preset_description = QLabel()
        self.lbl_preset_description.setWordWrap(True)
        layout.addWidget(self.lbl_preset_description)
        self.btn_apply_preset = QPushButton("Use preset")
        self.btn_apply_preset.setIcon(_standard_icon(self, "SP_CommandLink"))
        layout.addWidget(self.btn_apply_preset)
        layout.addStretch()
        self._update_preset_summary()
        return page

    def _connect_signals(self) -> None:
        self.cb_layer.layerChanged.connect(self._on_layer_changed)
        self.cb_height_field.fieldChanged.connect(self._schedule_auto_apply)
        self.btn_download_osm.clicked.connect(self.download_osm_buildings)
        self.btn_cancel_osm.clicked.connect(self.cancel_download)
        self.btn_apply.clicked.connect(self.apply_current_style)
        self.btn_restore.clicked.connect(self.restore_previous_style)
        self.btn_import_qml.clicked.connect(self.import_qml)
        self.btn_export_qml.clicked.connect(self.export_qml)
        self.btn_apply_preset.clicked.connect(self.apply_selected_preset)
        self.cb_preset.currentIndexChanged.connect(self._update_preset_summary)
        self.cb_floor_palette.currentIndexChanged.connect(self._update_floor_palette_preview)
        self.tabs.currentChanged.connect(self._save_settings)
        self.chk_auto_apply.toggled.connect(self._save_settings)

        self.slider_angle.valueChanged.connect(self.sp_angle.setValue)
        self.sp_angle.valueChanged.connect(self.slider_angle.setValue)
        self.slider_sun_azimuth.valueChanged.connect(self.sp_sun_azimuth.setValue)
        self.sp_sun_azimuth.valueChanged.connect(self.slider_sun_azimuth.setValue)
        self.sp_sun_azimuth.valueChanged.connect(self._update_direction_label)
        self.slider_shading_intensity.valueChanged.connect(lambda value: self.lbl_shading_value.setText(f"{value}%"))
        self.slider_shadow_alpha.valueChanged.connect(lambda value: self.lbl_shadow_alpha.setText(f"{value}%"))

        self.chk_facade_shading.toggled.connect(self._update_dependent_controls)
        self.chk_shadow.toggled.connect(self._update_dependent_controls)
        self.chk_floor_bands.toggled.connect(self._update_dependent_controls)
        self.cb_render_engine.currentIndexChanged.connect(self._update_dependent_controls)

        controls = [
            self.sp_default_height, self.sp_default_levels, self.sp_multiplier, self.cb_render_engine, self.sp_angle,
            self.chk_facade_shading, self.sp_sun_azimuth, self.slider_shading_intensity,
            self.chk_shadow, self.slider_shadow_alpha, self.sp_shadow_blur,
            self.sp_outline_width, self.sp_roof_outline_width, self.chk_floor_bands,
            self.sp_band_height, self.sp_floor_line_w, self.cb_floor_palette, self.sp_max_floors,
        ]
        for control in controls:
            if hasattr(control, "valueChanged"):
                control.valueChanged.connect(self._schedule_auto_apply)
            elif hasattr(control, "currentIndexChanged"):
                control.currentIndexChanged.connect(self._schedule_auto_apply)
            elif hasattr(control, "toggled"):
                control.toggled.connect(self._schedule_auto_apply)
        for button in (
            self.btn_wall_color, self.btn_roof_color, self.btn_outline_color,
            self.btn_roof_outline, self.btn_shadow_color, self.btn_floor_line_col,
        ):
            button.colorChanged.connect(self._schedule_auto_apply)

    def _is_polygon_layer(self, layer: Optional[QgsMapLayer]) -> bool:
        polygon = getattr(getattr(QgsWkbTypes, "GeometryType", QgsWkbTypes), "PolygonGeometry", getattr(QgsWkbTypes, "PolygonGeometry", 2))
        return isinstance(layer, QgsVectorLayer) and layer.isValid() and layer.geometryType() == polygon

    def _on_layer_changed(self, layer: Optional[QgsMapLayer]) -> None:
        valid = self._is_polygon_layer(layer)
        self._updating_controls = True
        try:
            self.cb_height_field.setLayer(layer if valid else None)
        finally:
            self._updating_controls = False
        for button in (self.btn_apply, self.btn_import_qml, self.btn_export_qml):
            button.setEnabled(valid)
        self.btn_restore.setEnabled(valid and bool(layer and layer.id() in self._original_renderers))
        if not valid:
            self.lbl_state.setText("No polygon layer")
            self.lbl_diagnostics.setText("Add or select a polygon layer to begin.")
            return

        selected = choose_height_field(field.name() for field in layer.fields())
        if selected:
            self._updating_controls = True
            try:
                self.cb_height_field.setField(selected)
            finally:
                self._updating_controls = False
        self.lbl_state.setText(f"{layer.featureCount():,} features")
        crs_label = layer.crs().authid() or "Unknown CRS"
        units = "geographic" if layer.crs().isGeographic() else "projected"
        field_label = selected or "constant fallback height"
        warning = " Reproject to a metric CRS for consistent height." if layer.crs().isGeographic() else ""
        self.lbl_diagnostics.setText(f"{crs_label} ({units}) | Height: {field_label}.{warning}")

    def _update_dependent_controls(self, *_args) -> None:
        advanced = self.cb_render_engine.currentData() != "native"
        for widget in self._shading_controls:
            widget.setEnabled(advanced and self.chk_facade_shading.isChecked())
        for widget in self._shadow_controls:
            widget.setEnabled(self.chk_shadow.isChecked())
        self.chk_floor_bands.setEnabled(advanced)
        for widget in self._floor_controls:
            widget.setEnabled(advanced and self.chk_floor_bands.isChecked())
        per_floor = self.cb_render_engine.currentData() == "per_floor_bands"
        for widget in self._palette_controls:
            widget.setEnabled(per_floor)
        self._update_direction_label()

    def _update_direction_label(self, *_args) -> None:
        self.sp_sun_azimuth.setSuffix(f" deg {compass_direction(self.sp_sun_azimuth.value())}")

    def _update_preset_summary(self, *_args) -> None:
        key = self.cb_preset.currentData() if hasattr(self, "cb_preset") else None
        preset = PRESETS.get(key, {})
        self.lbl_preset_description.setText(preset.get("description", ""))
        wall = preset.get("wall_color", "#7fb8b0")
        roof = preset.get("roof_color", "#f7c3a1")
        outline = preset.get("outline_color", "#3f6d66")
        for swatch, color in zip(self.preset_swatches, (wall, roof, outline)):
            swatch.setStyleSheet(f"background-color: {color}; border: 1px solid palette(mid); border-radius: 3px;")

    def _update_floor_palette_preview(self, *_args) -> None:
        key = self.cb_floor_palette.currentData() if hasattr(self, "cb_floor_palette") else "civic_spectrum"
        colors = FLOOR_BAND_PALETTES.get(key, FLOOR_BAND_PALETTES["civic_spectrum"])["colors"]
        for index, swatch in enumerate(self.floor_palette_swatches):
            color = colors[index % len(colors)]
            swatch.setToolTip(f"Floor {index + 1}: {color}")
            swatch.setStyleSheet(f"background-color: {color}; border: 1px solid palette(mid);")

    def _schedule_auto_apply(self, *_args) -> None:
        if self._updating_controls:
            return
        self._save_settings()
        if not self.chk_auto_apply.isChecked():
            self.lbl_apply_status.setText("Changes pending")
            return
        layer = self.cb_layer.currentLayer()
        if not self._is_polygon_layer(layer):
            return
        delay = 650 if layer.featureCount() > 10000 else 250
        if layer.featureCount() > 100000:
            self.lbl_apply_status.setText("Preview paused for large layer")
            return
        self.lbl_apply_status.setText("Preview pending")
        self._apply_timer.start(delay)

    def get_current_config(self) -> Dict[str, Any]:
        return normalize_config({
            "height_field": self.cb_height_field.currentField(),
            "height_multiplier": self.sp_multiplier.value(),
            "default_height": self.sp_default_height.value(),
            "default_levels": self.sp_default_levels.value(),
            "render_mode": self.cb_render_engine.currentData(),
            "projection_angle": self.sp_angle.value(),
            "wall_color": self.btn_wall_color.color().name(),
            "roof_color": self.btn_roof_color.color().name(),
            "outline_color": self.btn_outline_color.color().name(),
            "outline_width": self.sp_outline_width.value(),
            "roof_outline_color": self.btn_roof_outline.color().name(),
            "roof_outline_width": self.sp_roof_outline_width.value(),
            "facade_shading": self.chk_facade_shading.isChecked(),
            "sun_azimuth": self.sp_sun_azimuth.value(),
            "shading_intensity": self.slider_shading_intensity.value() / 100.0,
            "shadow_enabled": self.chk_shadow.isChecked(),
            "shadow_color": self.btn_shadow_color.color().name(),
            "shadow_alpha": self.slider_shadow_alpha.value(),
            "shadow_blur": self.sp_shadow_blur.value(),
            "floor_bands_enabled": self.chk_floor_bands.isChecked(),
            "floor_height_m": self.sp_band_height.value(),
            "floor_line_color": self.btn_floor_line_col.color().name(),
            "floor_line_width": self.sp_floor_line_w.value(),
            "floor_palette": self.cb_floor_palette.currentData(),
            "max_floors": self.sp_max_floors.value(),
        })

    def load_config_into_ui(self, config: Dict[str, Any]) -> None:
        cfg = normalize_config(config)
        self._updating_controls = True
        try:
            mode_index = self.cb_render_engine.findData(cfg["render_mode"])
            self.cb_render_engine.setCurrentIndex(max(0, mode_index))
            if cfg["height_field"]:
                self.cb_height_field.setField(cfg["height_field"])
            self.sp_multiplier.setValue(cfg["height_multiplier"])
            self.sp_default_height.setValue(cfg["default_height"])
            self.sp_default_levels.setValue(cfg["default_levels"])
            self.sp_angle.setValue(int(cfg["projection_angle"]))
            self.btn_wall_color.setColor(cfg["wall_color"])
            self.btn_roof_color.setColor(cfg["roof_color"])
            self.btn_outline_color.setColor(cfg["outline_color"])
            self.sp_outline_width.setValue(cfg["outline_width"])
            self.btn_roof_outline.setColor(cfg["roof_outline_color"])
            self.sp_roof_outline_width.setValue(cfg["roof_outline_width"])
            self.chk_facade_shading.setChecked(cfg["facade_shading"])
            self.sp_sun_azimuth.setValue(int(cfg["sun_azimuth"]))
            self.slider_shading_intensity.setValue(int(cfg["shading_intensity"] * 100))
            self.chk_shadow.setChecked(cfg["shadow_enabled"])
            self.btn_shadow_color.setColor(cfg["shadow_color"])
            self.slider_shadow_alpha.setValue(cfg["shadow_alpha"])
            self.sp_shadow_blur.setValue(cfg["shadow_blur"])
            self.chk_floor_bands.setChecked(cfg["floor_bands_enabled"])
            self.sp_band_height.setValue(cfg["floor_height_m"])
            self.btn_floor_line_col.setColor(cfg["floor_line_color"])
            self.sp_floor_line_w.setValue(cfg["floor_line_width"])
            palette_index = self.cb_floor_palette.findData(cfg["floor_palette"])
            self.cb_floor_palette.setCurrentIndex(max(0, palette_index))
            self.sp_max_floors.setValue(cfg["max_floors"])
        finally:
            self._updating_controls = False
        self._update_dependent_controls()
        self._update_floor_palette_preview()

    def download_osm_buildings(self) -> None:
        """Download OSM buildings asynchronously and apply per-floor 2.5D styling."""
        if self._osm_task is not None:
            self.lbl_osm_status.setText("A building download is already running.")
            return
        if not self.iface or not self.iface.mapCanvas():
            QMessageBox.warning(self, "OSM Buildings", "No active QGIS map canvas is available.")
            return

        canvas = self.iface.mapCanvas()
        if self.cb_osm_extent.currentData() == "layer":
            source_layer = self.cb_layer.currentLayer()
            if not source_layer:
                QMessageBox.warning(self, "OSM Buildings", "Select a layer before using its extent.")
                return
            rect = source_layer.extent()
            source_crs = source_layer.crs()
        else:
            rect = canvas.extent()
            source_crs = canvas.mapSettings().destinationCrs()

        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(source_crs, wgs84, QgsProject.instance())
        wgs_rect = transform.transformBoundingBox(rect)
        latitude_span = abs(wgs_rect.yMaximum() - wgs_rect.yMinimum())
        longitude_span = abs(wgs_rect.xMaximum() - wgs_rect.xMinimum())
        if latitude_span > 0.35 or longitude_span > 0.35:
            QMessageBox.warning(
                self,
                "OSM Buildings",
                "The selected extent is too large for a reliable building request. Zoom in to an area smaller than about 30 km.",
            )
            return

        query = build_overpass_building_query(
            wgs_rect.yMinimum(), wgs_rect.xMinimum(),
            wgs_rect.yMaximum(), wgs_rect.xMaximum(),
        )
        self._osm_default_levels = self.sp_default_levels.value()
        self._osm_floor_height = self.sp_band_height.value()
        self._osm_cancel_requested = False
        self.btn_download_osm.setEnabled(False)
        self.btn_cancel_osm.setEnabled(True)
        self.lbl_osm_status.setText("Downloading building footprints from Overpass...")

        def fetch(task):
            if task.isCanceled():
                return None
            return fetch_overpass_json(query)

        self._osm_task = QgsTask.fromFunction(
            "Download OSM buildings for 2.5D styling",
            fetch,
            on_finished=self._osm_download_finished,
        )
        QgsApplication.taskManager().addTask(self._osm_task)

    def _osm_download_finished(self, exception, osm_data) -> None:
        self.btn_download_osm.setEnabled(True)
        self.btn_cancel_osm.setEnabled(False)
        self._osm_task = None
        if self._osm_cancel_requested:
            self._osm_cancel_requested = False
            self.lbl_osm_status.setText("OSM building download canceled.")
            return
        if exception is not None:
            self.lbl_osm_status.setText(f"Download failed: {exception}")
            if self.iface and hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushCritical("2.5D Styling", str(exception))
            return
        if not osm_data or not osm_data.get("elements"):
            self.lbl_osm_status.setText("No OSM buildings were found in this extent.")
            return

        layer = osm_json_to_vector_layer(
            osm_data,
            target_crs=None,
            layer_name="OSM Buildings - 2.5D Floors",
            default_levels=self._osm_default_levels,
            floor_height_m=self._osm_floor_height,
        )
        if not layer or layer.featureCount() == 0:
            self.lbl_osm_status.setText("OSM returned data, but no valid building polygons were created.")
            return

        QgsProject.instance().addMapLayer(layer)
        self._updating_controls = True
        try:
            self.cb_layer.setLayer(layer)
            self.cb_height_field.setField("building_levels")
            self.sp_default_height.setValue(self._osm_default_levels * self._osm_floor_height)
            mode_index = self.cb_render_engine.findData("per_floor_bands")
            self.cb_render_engine.setCurrentIndex(max(0, mode_index))
        finally:
            self._updating_controls = False

        fallback_count = sum(
            1 for feature in layer.getFeatures()
            if feature["levels_source"] == "default"
        )
        self.apply_current_style()
        self.tabs.setCurrentIndex(3)
        self.lbl_osm_status.setText(
            f"Loaded {layer.featureCount():,} buildings. "
            f"OSM levels used where available; {fallback_count:,} buildings use the "
            f"{self._osm_default_levels}-floor default."
        )

    def cancel_download(self) -> None:
        if self._osm_task is not None:
            self._osm_cancel_requested = True
            self.btn_cancel_osm.setEnabled(False)
            self.lbl_osm_status.setText("Canceling OSM building download...")
            self._osm_task.cancel()

    def apply_current_style(self, _checked: bool = False, automatic: bool = False) -> None:
        layer = self.cb_layer.currentLayer()
        if not self._is_polygon_layer(layer):
            self.lbl_apply_status.setText("Select a polygon layer")
            return
        if layer.id() not in self._original_renderers and layer.renderer():
            self._original_renderers[layer.id()] = layer.renderer().clone()
            self.btn_restore.setEnabled(True)

        self.btn_apply.setEnabled(False)
        self.lbl_apply_status.setText("Applying...")
        try:
            if not apply_25d_style(layer, self.get_current_config()):
                raise RuntimeError("The renderer rejected the selected layer or configuration.")
            layer.emitStyleChanged()
            layer.triggerRepaint()
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
            self.lbl_apply_status.setText("Preview applied" if automatic else "Style applied")
            self._save_settings()
        except Exception as exc:
            self.lbl_apply_status.setText("Apply failed")
            if not automatic:
                QMessageBox.critical(self, "2.5D Styling", str(exc))
            elif self.iface and hasattr(self.iface, "messageBar"):
                self.iface.messageBar().pushWarning("2.5D Styling", str(exc))
        finally:
            self.btn_apply.setEnabled(True)

    def restore_previous_style(self) -> None:
        layer = self.cb_layer.currentLayer()
        renderer = self._original_renderers.pop(layer.id(), None) if self._is_polygon_layer(layer) else None
        if renderer is None:
            return
        layer.setRenderer(renderer)
        layer.emitStyleChanged()
        layer.triggerRepaint()
        if self.iface and self.iface.mapCanvas():
            self.iface.mapCanvas().refresh()
        self.btn_restore.setEnabled(False)
        self.lbl_apply_status.setText("Previous style restored")

    def apply_selected_preset(self) -> None:
        key = self.cb_preset.currentData()
        if key not in PRESETS:
            return
        current = self.get_current_config()
        current.update(PRESETS[key])
        current["height_field"] = self.cb_height_field.currentField()
        current["height_multiplier"] = self.sp_multiplier.value()
        current["default_height"] = self.sp_default_height.value()
        self.load_config_into_ui(current)
        self.apply_current_style()
        self.lbl_apply_status.setText(f"Preset applied: {PRESETS[key]['name']}")

    def import_qml(self) -> None:
        layer = self.cb_layer.currentLayer()
        if not self._is_polygon_layer(layer):
            return
        start = self._settings.value(f"{self.SETTINGS_GROUP}/lastDirectory", "", type=str)
        path, _filter = QFileDialog.getOpenFileName(self, "Import 2.5D QML Style", start, "QGIS Layer Style (*.qml)")
        if not path:
            return
        if layer.id() not in self._original_renderers and layer.renderer():
            self._original_renderers[layer.id()] = layer.renderer().clone()
        if load_layer_qml(layer, path):
            self._settings.setValue(f"{self.SETTINGS_GROUP}/lastDirectory", os.path.dirname(path))
            self.btn_restore.setEnabled(True)
            self.lbl_apply_status.setText("QML style imported")
        else:
            QMessageBox.critical(self, "Import QML", "The selected QML style could not be loaded.")

    def export_qml(self) -> None:
        layer = self.cb_layer.currentLayer()
        if not self._is_polygon_layer(layer):
            return
        start = self._settings.value(f"{self.SETTINGS_GROUP}/lastDirectory", "", type=str)
        default_path = os.path.join(start, "style_25d.qml") if start else "style_25d.qml"
        path, _filter = QFileDialog.getSaveFileName(self, "Export 2.5D QML Style", default_path, "QGIS Layer Style (*.qml)")
        if not path:
            return
        if not path.lower().endswith(".qml"):
            path += ".qml"
        if export_layer_qml(layer, path):
            self._settings.setValue(f"{self.SETTINGS_GROUP}/lastDirectory", os.path.dirname(path))
            self.lbl_apply_status.setText("QML style exported")
        else:
            QMessageBox.critical(self, "Export QML", "The QML style could not be saved.")

    def _save_settings(self, *_args) -> None:
        if self._updating_controls:
            return
        config_json = json.dumps(self.get_current_config())
        self._settings.setValue(f"{self.SETTINGS_GROUP}/config", config_json)
        self._settings.setValue(f"{self.SETTINGS_GROUP}/autoApply", self.chk_auto_apply.isChecked())
        self._settings.setValue(f"{self.SETTINGS_GROUP}/tab", self.tabs.currentIndex())

    def _restore_settings(self) -> None:
        raw = self._settings.value(f"{self.SETTINGS_GROUP}/config", "", type=str)
        if raw:
            try:
                self.load_config_into_ui(json.loads(raw))
            except (TypeError, ValueError, json.JSONDecodeError):
                self.load_config_into_ui({})
        else:
            self.load_config_into_ui({})
        self.chk_auto_apply.setChecked(self._settings.value(f"{self.SETTINGS_GROUP}/autoApply", True, type=bool))
        self.tabs.setCurrentIndex(self._settings.value(f"{self.SETTINGS_GROUP}/tab", 0, type=int))
