# -*- coding: utf-8 -*-
"""OSM Overpass building footprint and height acquisition engine."""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsFeature,
        QgsField,
        QgsFields,
        QgsGeometry,
        QgsPointXY,
        QgsProject,
        QgsRectangle,
        QgsVectorLayer,
        QgsWkbTypes,
    )
    from qgis.PyQt.QtCore import QVariant
except ImportError:
    QgsCoordinateReferenceSystem = None
    QgsCoordinateTransform = None
    QgsFeature = None
    QgsField = None
    QgsFields = None
    QgsGeometry = None
    QgsPointXY = None
    QgsProject = None
    QgsRectangle = None
    QgsVectorLayer = None
    QgsWkbTypes = None
    QVariant = None

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
USER_AGENT = "QGIS-2.5D-Styling-Plugin/1.0.1 (https://github.com/YusufEminoglu/qgis_25d_styling)"
DEFAULT_TIMEOUT_S = 60
CACHE_TTL_S = 7 * 24 * 3600  # 1 week cache


class OsmDownloadError(RuntimeError):
    """Raised when OSM Overpass download or parsing fails."""
    pass


def _cache_dir() -> str:
    path = os.path.join(tempfile.gettempdir(), "qgis_25d_styling_cache")
    with contextlib.suppress(OSError):
        os.makedirs(path, exist_ok=True)
    return path


def _cache_path(query: str) -> str:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:40]
    return os.path.join(_cache_dir(), f"osm_{digest}.json")


def _read_cache(query: str) -> Optional[dict]:
    path = _cache_path(query)
    try:
        if not os.path.isfile(path):
            return None
        if time.time() - os.path.getmtime(path) > CACHE_TTL_S:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _write_cache(query: str, payload: dict) -> None:
    with contextlib.suppress(OSError, TypeError, ValueError):
        with open(_cache_path(query), "w", encoding="utf-8") as handle:
            json.dump(payload, handle)


def build_overpass_building_query(
    south: float, west: float, north: float, east: float, timeout_s: int = 50
) -> str:
    """Construct an optimized Overpass QL query to fetch buildings and geometries."""
    bbox_str = f"{south:.6f},{west:.6f},{north:.6f},{east:.6f}"
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f"(\n"
        f'  way["building"]({bbox_str});\n'
        f'  relation["building"]({bbox_str});\n'
        f");\n"
        f"out body geom qt;\n"
    )


def parse_numeric_height(val: Any) -> Optional[float]:
    """Parse raw OSM height string (e.g. '12.5 m', '14', '15.2m') into float meters."""
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s:
        return None
    # match float prefix
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", s)
    if match:
        with contextlib.suppress(ValueError):
            meters = float(match.group(1))
            # handle feet if specified
            if "ft" in s or "'" in s:
                meters = meters * 0.3048
            return meters
    return None


def parse_numeric_levels(val: Any) -> Optional[float]:
    """Parse building:levels value to float."""
    if val is None:
        return None
    s = str(val).strip()
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", s)
    if match:
        with contextlib.suppress(ValueError):
            return float(match.group(1))
    return None


def fetch_overpass_json(
    query: str, feedback=None, timeout_s: int = DEFAULT_TIMEOUT_S
) -> dict:
    """Fetch Overpass JSON with automatic endpoint fallback and caching."""
    cached = _read_cache(query)
    if cached is not None and isinstance(cached, dict) and "elements" in cached:
        if feedback:
            feedback.setProgressText("Loaded OSM data from local disk cache.")
        return cached

    encoded = urllib.parse.urlencode({"data": query}).encode("utf-8")
    for endpoint in OVERPASS_ENDPOINTS:
        if feedback and feedback.isCanceled():
            raise OsmDownloadError("Download canceled by user.")

        try:
            if not endpoint.startswith(("http://", "https://")):
                continue

            if feedback:
                feedback.setProgressText(f"Querying Overpass mirror: {endpoint} ...")

            req = urllib.request.Request(
                endpoint,
                data=encoded,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310
                if resp.status != 200:
                    last_error = f"HTTP {resp.status} from {endpoint}"
                    continue
                raw = resp.read()
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict) and "elements" in data:
                    _write_cache(query, data)
                    return data
                last_error = f"Invalid response JSON structure from {endpoint}"
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code} from {endpoint}: {exc.reason}"
        except urllib.error.URLError as exc:
            last_error = f"Network error connecting to {endpoint}: {exc.reason}"
        except Exception as exc:
            last_error = f"Error with {endpoint}: {exc}"

    raise OsmDownloadError(f"All Overpass mirrors failed. Last error: {last_error}")


def utm_crs_for_lon_lat(lon: float, lat: float) -> QgsCoordinateReferenceSystem:
    """Return appropriate metric UTM CRS (EPSG:326xx or EPSG:327xx) for a coordinate."""
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = max(1, min(60, zone))
    epsg = (32600 + zone) if lat >= 0 else (32700 + zone)
    crs = QgsCoordinateReferenceSystem(f"EPSG:{epsg}")
    if crs.isValid():
        return crs
    return QgsCoordinateReferenceSystem("EPSG:3857")


def osm_json_to_vector_layer(
    osm_data: dict,
    target_crs: Optional[QgsCoordinateReferenceSystem] = None,
    layer_name: str = "OSM_25D_Buildings",
    default_levels: int = 3,
    floor_height_m: float = 3.0,
) -> QgsVectorLayer:
    """Convert OSM Overpass elements into a clean QgsVectorLayer with calculated 2.5D attributes."""
    elements = osm_data.get("elements", [])
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    # If no target CRS is given, auto-detect UTM zone from first element or use EPSG:3857
    if target_crs is None or not target_crs.isValid():
        # find centroid lon/lat
        sample_lon, sample_lat = 0.0, 0.0
        for el in elements:
            geom = el.get("geometry", [])
            if geom and len(geom) > 0:
                sample_lon = geom[0].get("lon", 0.0)
                sample_lat = geom[0].get("lat", 0.0)
                break
        if sample_lon != 0.0 or sample_lat != 0.0:
            target_crs = utm_crs_for_lon_lat(sample_lon, sample_lat)
        else:
            target_crs = QgsCoordinateReferenceSystem("EPSG:3857")

    transform = QgsCoordinateTransform(wgs84, target_crs, QgsProject.instance())

    # Create Memory Layer
    fields = QgsFields()
    fields.append(QgsField("osm_id", QVariant.String))
    fields.append(QgsField("name", QVariant.String))
    fields.append(QgsField("building", QVariant.String))
    fields.append(QgsField("building_levels", QVariant.Double))
    fields.append(QgsField("levels_source", QVariant.String))
    fields.append(QgsField("height", QVariant.Double))
    fields.append(QgsField("min_height", QVariant.Double))
    fields.append(QgsField("roof_shape", QVariant.String))
    fields.append(QgsField("roof_colour", QVariant.String))
    fields.append(QgsField("building_colour", QVariant.String))
    fields.append(QgsField("amenity", QVariant.String))

    layer = QgsVectorLayer(
        f"Polygon?crs={target_crs.authid()}", layer_name, "memory"
    )
    pr = layer.dataProvider()
    pr.addAttributes(list(fields))
    layer.updateFields()

    features_to_add = []

    for el in elements:
        el_type = el.get("type")
        tags = el.get("tags", {})
        if not tags or "building" not in tags:
            continue

        raw_geom = el.get("geometry", [])
        if not raw_geom or len(raw_geom) < 3:
            continue

        # Build Polygon Ring in WGS84
        pts = [QgsPointXY(pt["lon"], pt["lat"]) for pt in raw_geom]
        # ensure closed
        if pts[0] != pts[-1]:
            pts.append(pts[0])

        qgs_geom = QgsGeometry.fromPolygonXY([pts])
        if not qgs_geom or qgs_geom.isEmpty():
            continue

        # Transform to metric CRS
        with contextlib.suppress(Exception):
            qgs_geom.transform(transform)

        # Attribute Parsing & Height Estimation
        osm_id = str(el.get("id", ""))
        name = str(tags.get("name", ""))
        b_type = str(tags.get("building", "yes"))
        raw_levels = tags.get("building:levels")
        raw_h = tags.get("height")
        raw_min_h = tags.get("min_height")
        roof_shape = str(tags.get("roof:shape", "flat"))
        roof_colour = str(tags.get("roof:colour", ""))
        b_colour = str(tags.get("building:colour", ""))
        amenity = str(tags.get("amenity", ""))

        num_levels = parse_numeric_levels(raw_levels)
        num_height = parse_numeric_height(raw_h)
        num_min_h = parse_numeric_height(raw_min_h) or 0.0
        if num_levels is not None and num_levels > 0:
            levels_source = "osm"
        elif num_height is not None and num_height > 0:
            num_levels = float(max(1, min(100, round(num_height / max(0.5, float(floor_height_m))))))
            levels_source = "estimated"
        else:
            num_levels = float(max(1, min(100, int(default_levels))))
            levels_source = "default"
        if num_height is None or num_height <= 0:
            num_height = num_levels * max(0.5, float(floor_height_m))

        feat = QgsFeature(layer.fields())
        feat.setGeometry(qgs_geom)
        feat.setAttribute("osm_id", osm_id)
        feat.setAttribute("name", name)
        feat.setAttribute("building", b_type)
        feat.setAttribute("building_levels", float(num_levels) if num_levels else 1.0)
        feat.setAttribute("levels_source", levels_source)
        feat.setAttribute("height", float(num_height))
        feat.setAttribute("min_height", float(num_min_h))
        feat.setAttribute("roof_shape", roof_shape)
        feat.setAttribute("roof_colour", roof_colour)
        feat.setAttribute("building_colour", b_colour)
        feat.setAttribute("amenity", amenity)

        features_to_add.append(feat)

    if features_to_add:
        pr.addFeatures(features_to_add)
        layer.updateExtents()

    return layer
