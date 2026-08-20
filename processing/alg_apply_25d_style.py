# -*- coding: utf-8 -*-
"""Processing Algorithm: Apply 2.5D Building Symbology & Shading."""
from __future__ import annotations

from qgis.core import (
    QgsColorRamp,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterColor,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterVectorLayer,
    QgsVectorLayer,
)

from ..core.presets import PRESETS
from ..core.qml_exporter import export_layer_qml
from ..core.twopointfive_engine import apply_25d_style


class Apply25DStyleAlgorithm(QgsProcessingAlgorithm):
    """Apply 2.5D architectural extrusion, solar shading, and floor divisions to a vector layer."""

    INPUT = "INPUT"
    PRESET = "PRESET"
    HEIGHT_FIELD = "HEIGHT_FIELD"
    HEIGHT_SCALE = "HEIGHT_SCALE"
    PROJECTION_ANGLE = "PROJECTION_ANGLE"
    SUN_AZIMUTH = "SUN_AZIMUTH"
    SHADING_INTENSITY = "SHADING_INTENSITY"
    WALL_COLOR = "WALL_COLOR"
    ROOF_COLOR = "ROOF_COLOR"
    OUTLINE_COLOR = "OUTLINE_COLOR"
    FLOOR_BANDS = "FLOOR_BANDS"
    FLOOR_HEIGHT = "FLOOR_HEIGHT"
    OUTPUT_QML = "OUTPUT_QML"
    OUTPUT = "OUTPUT"

    PRESET_KEYS = ["custom"] + list(PRESETS.keys())
    PRESET_NAMES = ["Custom Parameters"] + [p["name"] for p in PRESETS.values()]

    def createInstance(self):
        return Apply25DStyleAlgorithm()

    def name(self):
        return "apply_25d_style"

    def displayName(self):
        return "Apply 2.5D Building Style"

    def group(self):
        return "2.5D Symbology"

    def groupId(self):
        return "symbology_25d"

    def shortHelpString(self):
        return (
            "Applies publication-grade 2.5D building extrusion, solar aspect lighting, "
            "and architectural floor bands to any polygon vector layer.\n\n"
            "Supports 8 curated architectural presets (Swiss Minimalist, Dark Obsidian, "
            "Warm Terracotta, Vintage Blueprint, Emerald Glass, Cyberpunk Neon, Solar Heatmap, "
            "and Monochrome Print)."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT, "Input Polygon Layer", [QgsProcessing.TypeVectorPolygon]
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PRESET,
                "Architectural Preset",
                options=self.PRESET_NAMES,
                defaultValue=1,  # Swiss Minimalist
            )
        )
        self.addParameter(
            QgsProcessingParameterField(
                self.HEIGHT_FIELD,
                "Height Attribute Field",
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Numeric,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.HEIGHT_SCALE,
                "Height Scale Multiplier",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=1.0,
                minValue=0.1,
                maxValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.PROJECTION_ANGLE,
                "Projection Angle (degrees, 0-360)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=45.0,
                minValue=0.0,
                maxValue=360.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUN_AZIMUTH,
                "Solar Azimuth (degrees, 0-360)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=315.0,
                minValue=0.0,
                maxValue=360.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SHADING_INTENSITY,
                "Solar Shading Depth (0.0 to 1.0)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.4,
                minValue=0.0,
                maxValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.WALL_COLOR, "Wall / Facade Color", defaultValue="#e2e8f0"
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.ROOF_COLOR, "Roof Cap Color", defaultValue="#ffffff"
            )
        )
        self.addParameter(
            QgsProcessingParameterColor(
                self.OUTLINE_COLOR, "Outline Color", defaultValue="#475569"
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.FLOOR_BANDS, "Enable Floor Division Lines", defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.FLOOR_HEIGHT,
                "Story / Floor Height (meters)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=3.2,
                minValue=1.0,
                maxValue=20.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_QML,
                "Optional Export QML Style File",
                fileFilter="QGIS Layer Style (*.qml)",
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT, "Styled Output Layer", QgsProcessing.TypeVectorPolygon
            )
        )

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Invalid input layer.")

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs(),
        )

        preset_idx = self.parameterAsEnum(parameters, self.PRESET, context)
        h_field = self.parameterAsString(parameters, self.HEIGHT_FIELD, context) or "height"
        h_scale = self.parameterAsDouble(parameters, self.HEIGHT_SCALE, context)

        # Copy features to output sink
        total = 100.0 / source.featureCount() if source.featureCount() else 0
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            if total > 0:
                feedback.setProgress(int(i * total))

        out_layer = context.getMapLayer(dest_id)
        if out_layer and isinstance(out_layer, QgsVectorLayer):
            if preset_idx > 0 and preset_idx < len(self.PRESET_KEYS):
                pkey = self.PRESET_KEYS[preset_idx]
                cfg = dict(PRESETS[pkey])
                cfg["height_field"] = h_field
                cfg["height_multiplier"] = h_scale
                cfg["use_geometry_generator"] = True
            else:
                cfg = {
                    "height_field": h_field,
                    "height_multiplier": h_scale,
                    "use_geometry_generator": True,
                    "projection_angle": self.parameterAsDouble(parameters, self.PROJECTION_ANGLE, context),
                    "sun_azimuth": self.parameterAsDouble(parameters, self.SUN_AZIMUTH, context),
                    "shading_intensity": self.parameterAsDouble(parameters, self.SHADING_INTENSITY, context),
                    "wall_color": self.parameterAsColor(parameters, self.WALL_COLOR, context).name(),
                    "roof_color": self.parameterAsColor(parameters, self.ROOF_COLOR, context).name(),
                    "outline_color": self.parameterAsColor(parameters, self.OUTLINE_COLOR, context).name(),
                    "outline_width": 0.3,
                    "roof_outline_color": self.parameterAsColor(parameters, self.OUTLINE_COLOR, context).name(),
                    "roof_outline_width": 0.4,
                    "shadow_enabled": True,
                    "shadow_color": "#0f172a",
                    "shadow_alpha": 40,
                    "shadow_blur": 4.0,
                    "floor_bands_enabled": self.parameterAsBoolean(parameters, self.FLOOR_BANDS, context),
                    "floor_height_m": self.parameterAsDouble(parameters, self.FLOOR_HEIGHT, context),
                    "floor_line_color": "#cbd5e1",
                    "floor_line_width": 0.2,
                }

            apply_25d_style(out_layer, cfg)

            qml_path = self.parameterAsString(parameters, self.OUTPUT_QML, context)
            if qml_path:
                export_layer_qml(out_layer, qml_path)
                feedback.pushInfo(f"Exported QML style to: {qml_path}")

        return {self.OUTPUT: dest_id}
