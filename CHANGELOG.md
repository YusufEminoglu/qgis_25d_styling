# Changelog

All notable changes to **QGIS 2.5D Styling** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-20

### Added
- **Initial Release of QGIS 2.5D Styling**.
- **Integrated OSM Overpass Downloader**:
  - Bounding box extraction from map canvas or layer extent.
  - Multi-endpoint fallback mirrors (`overpass-api.de`, `kumi.systems`, `private.coffee`).
  - Automatic UTM metric projection and height attribute parsing (`building:levels`, `height`, typologies).
- **Architectural 2.5D Extrusion Engine**:
  - Native `Qgs25DRenderer` mode and Advanced Geometry Generator mode.
  - Solar aspect facade shading with azimuth and elevation illumination.
  - Architectural horizontal floor divisions (mullions).
  - Ground drop shadow with custom opacity, color, and blur.
  - 8 Curated Architectural Presets (Swiss Minimalist, Dark Obsidian, Warm Terracotta, Vintage Blueprint, Emerald Glass, Cyberpunk Neon, Solar Heatmap, Monochrome Print).
- **Right-Docked Studio Panel**:
  - High-DPI immune segmented sub-tabs with zero Windows clipping.
  - Live auto-apply toggle for instant canvas refresh.
  - QML style file import and export.
- **Headless Processing Provider**:
  - `Apply 2.5D Building Style` (`qgis_25d_styling:apply_25d_style`)
  - `Download OSM 3D Buildings` (`qgis_25d_styling:download_osm_25d`)
