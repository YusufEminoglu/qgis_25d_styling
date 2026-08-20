# QGIS 2.5D Styling

[![QGIS Plugin](https://img.shields.io/badge/QGIS-Plugin-brightgreen.svg)](https://plugins.qgis.org/plugins/qgis_25d_styling/)
[![License: GPL-2.0-or-later](https://img.shields.io/badge/License-GPL_2.0+-blue.svg)](LICENSE)

A focused QGIS studio for turning polygon layers or bounded OSM building footprints into clear 2.5D maps. Every workflow ends in the same result: styled 2.5D buildings.

## 2.5D Workflow

1. Select a polygon layer, or download buildings for the current map view from OSM.
2. Choose Geometry Generator, Per-floor Color Bands, or Native QGIS 2.5D.
3. Set projection direction, facade and roof materials, shading, shadow, and floor divisions.
4. Apply a curated preset or tune the controls directly.
5. Export the renderer as a QML style, or restore the layer's previous renderer.

The compact right-side dock filters non-polygon layers, detects common height fields, supplies configurable fallbacks, warns about geographic CRS use, and pauses live preview for very large layers. OSM buildings use `building:levels`; missing values visibly fall back to a user-selectable three floors. Live changes are debounced to avoid rebuilding the renderer on every slider step.

## Styling Features

- Geometry Generator renderer with facade, roof, optional shadow, floor divisions, and feature draw ordering.
- Per-floor rule renderer with 12 palettes, a ten-floor live swatch preview, and automatic or explicit floor limits.
- Native `Qgs25DRenderer` mode using layer-scoped QGIS expression variables.
- Projection directions from 0 to 359 degrees plus six standard projection shortcuts.
- Configurable facade/roof colors, outlines, shading depth, shadow opacity, and story height.
- Ten material themes adapted directly from the proven 02CartoLab 2.5D style collection.
- Asynchronous, bounded OSM building download with local cache, mirror fallback, automatic metric CRS, and explicit floor-source attributes.
- QML import/export and non-destructive restoration of the pre-apply renderer.
- Persistent dock settings and a single headless Processing algorithm.

## Processing

`qgis_25d_styling:apply_25d_style` copies an input polygon layer to an output layer and applies the selected 2.5D renderer. Custom controls and complete presets are supported.

## Compatibility

- QGIS 3.28 through QGIS 4.x
- QGIS 3.44 LTR and QGIS 4.2 are used by the release verification harness
- No pip dependencies; network access is used only when the user starts an OSM building download

## Installation

Install **QGIS 2.5D Styling** from the QGIS Plugin Manager, or install the release ZIP through **Plugins > Manage and Install Plugins > Install from ZIP**.

## License

GPL-2.0-or-later. Copyright Yusuf Eminoglu.
