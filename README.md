# QGIS 2.5D Styling

[![QGIS Hub](https://img.shields.io/badge/QGIS-Plugin_Hub-brightgreen.svg)](https://plugins.qgis.org/plugins/qgis_25d_styling/)
[![License: GPL-2.0-or-later](https://img.shields.io/badge/License-GPL_2.0+-blue.svg)](LICENSE)

**Dedicated architectural 2.5D building extrusion, solar aspect lighting, and symbology studio dock with built-in OpenStreetMap Overpass downloader for QGIS.**

---

## Highlights

- **Built-in OSM Overpass Downloader**:
  - 1-Click acquisition of building footprint polygons and height/level tags for any map extent.
  - Multi-endpoint fallback (`overpass-api.de`, `kumi.systems`, `private.coffee`) and local response caching.
  - Automatic UTM metric projection and smart height estimation (`building:levels` × 3.0m, `height`, typology fallbacks).

- **Architectural 2.5D Extrusion Engine**:
  - **Native `Qgs25DRenderer` Mode**: Built-in fast QGIS 2.5D renderer configuration.
  - **Advanced Multi-Layer Geometry Generator Mode**: True isometric projections, solar aspect facade illumination, horizontal floor division lines (mullions), and directional ground drop shadows.
  - **Projection Angle Controls**: 0° to 360° continuous angle dial with standard presets: Isometric (45° NE), Oblique Military (30°), Cavalier (60°), and Plan Oblique (135° SE).

- **Dynamic Solar Lighting & Shadows**:
  - Solar azimuth & elevation simulation with real-time facade angle modulation.
  - Ground drop shadow with customizable color, opacity, and blur radius.

- **8 Curated Architectural Design Presets**:
  - **Swiss Minimalist**: Crisp porcelain white massing, graphite soft shadows, and clean hairline outlines.
  - **Dark Obsidian**: Deep navy massing with neon cyan illuminated roof outlines.
  - **Warm Terracotta**: Mediterranean terracotta roof tiles with warm limestone facades.
  - **Vintage Blueprint**: Technical cyan isometric projection with white CAD wireframes.
  - **Emerald Glass**: Commercial high-rise aesthetic with turquoise-tinted glazing.
  - **Cyberpunk Neon**: Futuristic purple shadow massing with electric magenta roof edges.
  - **Solar Heatmap**: Aspect-based solar insolation color mapping.
  - **Monochrome Print**: Neutral grayscale tones optimized for journal publications.

- **Live Auto-Apply & QML Export**:
  - Live preview on canvas while moving sliders and picking colors.
  - Save and load standard QGIS `.qml` style files.

- **Headless Processing Provider**:
  - `Apply 2.5D Building Style` (`qgis_25d_styling:apply_25d_style`)
  - `Download OSM 3D Buildings` (`qgis_25d_styling:download_osm_25d`)

---

## Installation

### Method 1: QGIS Plugin Manager (Recommended)
1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins...**
3. Search for **QGIS 2.5D Styling** and click **Install Plugin**.

### Method 2: Manual Installation from ZIP
1. Download `qgis_25d_styling.zip` from [Releases](https://github.com/YusufEminoglu/qgis_25d_styling/releases).
2. In QGIS, go to **Plugins → Install from ZIP** and select the zip archive.

---

## Usage

1. Click the **QGIS 2.5D Styling** icon in the toolbar or menu to toggle the right dock panel.
2. Select your building polygon layer in the **Target Layer** dropdown.
   *(Or switch to the **🌍 OSM Fetch** tab and click **Download OSM 3D Buildings** to acquire footprints automatically).*
3. Adjust height scales, projection angles, and solar lighting parameters.
4. Pick from the **✨ Presets** tab for instant 1-click architectural styling.

---

## Acknowledgements & Inspiration

- **Geocast Brasil**: Inspired by the 2.5D building floor classification concept and tutorial (*"QGIS - visualização de vetor em 2.5D (Classificando os andares dos prédios)"* — [Watch on YouTube](https://www.youtube.com/watch?v=03XlpABs9vE)).
- **OpenStreetMap & Overpass API**: For open geospatial building footprint data and public API services.

---

## License

This project is licensed under the **GNU General Public License v2.0 or later** ([GPL-2.0-or-later](LICENSE)).

Author: **Yusuf Eminoğlu** (<yusuf.eminoglu@deu.edu.tr>)
