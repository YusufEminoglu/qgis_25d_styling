# -*- coding: utf-8 -*-
"""Processing Algorithm: Download OSM 3D Buildings & Apply 2.5D Style."""
from __future__ import annotations

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExtent,
    QgsProcessingParameterNumber,
    QgsProcessingParameterVectorDestination,
    QgsProject,
    QgsVectorLayer,
)

from ..core.osm_downloader import (
    build_overpass_building_query,
    fetch_overpass_json,
    osm_json_to_vector_layer,
)
from ..core.presets import PRESETS
from ..core.twopointfive_engine import apply_25d_style


class DownloadOsm25DAlgorithm(QgsProcessingAlgorithm):
    """Download OpenStreetMap building footprints for an extent and apply 2.5D architectural styling."""

    EXTENT = "EXTENT"
    PRESET = "PRESET"
    DEFAULT_HEIGHT = "DEFAULT_HEIGHT"
    FLOOR_HEIGHT = "FLOOR_HEIGHT"
    OUTPUT = "OUTPUT"

    PRESET_KEYS = list(PRESETS.keys())
    PRESET_NAMES = [p["name"] for p in PRESETS.values()]

    def createInstance(self):
        return DownloadOsm25DAlgorithm()

    def name(self):
        return "download_osm_25d"

    def displayName(self):
        return "Download OSM 3D Buildings (2.5D Styled)"

    def group(self):
        return "OSM 3D Buildings"

    def groupId(self):
        return "osm_25d"

    def shortHelpString(self):
        return (
            "Fetches building footprints and height/level tags from the public Overpass API "
            "for the specified geographic bounding box, transforms geometries to metric UTM CRS, "
            "and automatically styles them with 2.5D architectural extrusion."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT, "Geographic Bounding Box Extent"
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PRESET,
                "Architectural Preset",
                options=self.PRESET_NAMES,
                defaultValue=0,  # Swiss Minimalist
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.DEFAULT_HEIGHT,
                "Default Height for un-tagged buildings (meters)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=9.0,
                minValue=1.0,
                maxValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.FLOOR_HEIGHT,
                "Estimated Floor Height (meters/level)",
                type=QgsProcessingParameterNumber.Double,
                defaultValue=3.0,
                minValue=1.0,
                maxValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterVectorDestination(
                self.OUTPUT, "Downloaded 2.5D Buildings", QgsProcessing.TypeVectorPolygon
            )
        )

    def processAlgorithm(self, parameters, context: QgsProcessingContext, feedback: QgsProcessingFeedback):
        rect = self.parameterAsExtent(parameters, self.EXTENT, context)
        rect_crs = self.parameterAsExtentCrs(parameters, self.EXTENT, context)
        if not rect or rect.isEmpty():
            raise QgsProcessingException("Please provide a valid non-empty bounding box extent.")

        # Transform extent to WGS 84 (EPSG:4326)
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        trans = QgsCoordinateTransform(rect_crs, wgs84, context.transformContext())
        wgs_rect = trans.transformBoundingBox(rect)

        feedback.setProgressText("Constructing Overpass query...")
        q = build_overpass_building_query(
            wgs_rect.yMinimum(),
            wgs_rect.xMinimum(),
            wgs_rect.yMaximum(),
            wgs_rect.xMaximum(),
        )

        feedback.setProgressText("Fetching OSM data from Overpass API mirrors...")
        osm_data = fetch_overpass_json(q, feedback=feedback)

        elements = osm_data.get("elements", [])
        if not elements:
            feedback.pushInfo("No building elements found in this extent.")

        dest_crs = rect_crs if rect_crs.isValid() and not rect_crs.isGeographic() else None
        mem_layer = osm_json_to_vector_layer(
            osm_data,
            target_crs=dest_crs,
            layer_name="OSM_Buildings_25D",
            default_height=self.parameterAsDouble(parameters, self.DEFAULT_HEIGHT, context),
            floor_height_m=self.parameterAsDouble(parameters, self.FLOOR_HEIGHT, context),
        )

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            mem_layer.fields(),
            mem_layer.wkbType(),
            mem_layer.crs(),
        )

        for feat in mem_layer.getFeatures():
            if feedback.isCanceled():
                break
            sink.addFeature(feat, QgsFeatureSink.FastInsert)

        out_layer = context.getMapLayer(dest_id)
        if out_layer and isinstance(out_layer, QgsVectorLayer):
            preset_idx = self.parameterAsEnum(parameters, self.PRESET, context)
            pkey = self.PRESET_KEYS[preset_idx] if preset_idx < len(self.PRESET_KEYS) else "swiss_minimalist"
            cfg = dict(PRESETS[pkey])
            cfg["height_field"] = "height"
            cfg["use_geometry_generator"] = True
            apply_25d_style(out_layer, cfg)

        return {self.OUTPUT: dest_id}
