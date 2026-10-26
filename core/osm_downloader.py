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
        QgsCsException,
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
    QgsCsException = Exception
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
USER_AGENT = "QGIS-2.5D-Styling-Plugin/1.1.0 (https://github.com/YusufEminoglu/qgis_25d_styling)"
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
    """Parse raw OSM height string (e.g. '12.5 m', '14', '15,2m', '40 ft') into float meters."""
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s:
        return None
    # A decimal comma ("12,5") is common in hand-entered European values.
    s = re.sub(r"^([0-9]+),([0-9]+)", r"\1.\2", s)
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
    s = re.sub(r"^([0-9]+),([0-9]+)", r"\1.\2", str(val).strip())
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
    last_error = "no Overpass mirror answered"
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


Coord = Tuple[float, float]


def stitch_rings(ways: List[List[Coord]]) -> List[List[Coord]]:
    """Join way coordinate lists that share end nodes into closed rings.

    A multipolygon relation may split one outline over several ways, in any
    direction. Lists that cannot be closed are dropped rather than guessed.
    """
    pending = [list(way) for way in ways if len(way) >= 2]
    rings: List[List[Coord]] = []
    while pending:
        ring = pending.pop(0)
        joined = True
        while ring[0] != ring[-1] and joined:
            joined = False
            for index, way in enumerate(pending):
                if way[0] == ring[-1]:
                    ring = ring + way[1:]
                elif way[-1] == ring[-1]:
                    ring = ring + way[-2::-1]
                elif way[-1] == ring[0]:
                    ring = way + ring[1:]
                elif way[0] == ring[0]:
                    ring = way[::-1] + ring[1:]
                else:
                    continue
                pending.pop(index)
                joined = True
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings.append(ring)
    return rings


def _coords(raw: List[Dict[str, Any]]) -> List[Coord]:
    return [(float(pt["lon"]), float(pt["lat"])) for pt in raw if "lon" in pt and "lat" in pt]


def _element_geometry(el: Dict[str, Any]):
    """WGS84 polygon of a building way or multipolygon relation, or None."""
    if el.get("type") == "relation":
        members = [m for m in el.get("members", []) if m.get("type") == "way" and m.get("geometry")]
        outers = stitch_rings([_coords(m["geometry"]) for m in members if m.get("role", "outer") in ("outer", "")])
        inners = stitch_rings([_coords(m["geometry"]) for m in members if m.get("role") == "inner"])
        if not outers:
            return None
        polygons = []
        for outer in outers:
            shell = QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in outer]])
            holes = [
                [QgsPointXY(x, y) for x, y in inner] for inner in inners
                if shell.contains(QgsGeometry.fromPointXY(QgsPointXY(*inner[0])))
            ]
            polygons.append([[QgsPointXY(x, y) for x, y in outer]] + holes)
        if len(polygons) == 1:
            return QgsGeometry.fromPolygonXY(polygons[0])
        return QgsGeometry.fromMultiPolygonXY(polygons)
    points = _coords(el.get("geometry", []))
    if len(points) < 3:
        return None
    if points[0] != points[-1]:
        points.append(points[0])
    return QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in points]])


def _project(geometry, transform) -> bool:
    try:
        geometry.transform(transform)
    except QgsCsException:
        return False
    return True


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
            geom = el.get("geometry") or next(
                (m.get("geometry") for m in el.get("members", []) if m.get("geometry")), None
            )
            if geom:
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
        f"MultiPolygon?crs={target_crs.authid()}", layer_name, "memory"
    )
    pr = layer.dataProvider()
    pr.addAttributes(list(fields))
    layer.updateFields()

    features_to_add = []

    for el in elements:
        tags = el.get("tags", {})
        if not tags or "building" not in tags:
            continue

        qgs_geom = _element_geometry(el)
        if qgs_geom is None or qgs_geom.isEmpty():
            continue
        # A footprint that cannot be projected would land in the wrong CRS.
        if not _project(qgs_geom, transform):
            continue
        qgs_geom.convertToMultiType()

        # Attribute Parsing & Height Estimation
        osm_id = f"{el.get('type', 'way')}/{el.get('id', '')}"
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
