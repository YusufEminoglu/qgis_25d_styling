<p align="center">
  <strong>QGIS 2.5D Styling</strong>
</p>

<h1 align="center">QGIS 2.5D Styling</h1>

<p align="center">
  <strong>One focused tool for turning flat building polygons into clear, publication-ready 2.5D maps.</strong>
</p>

<p align="center">
  <a href="metadata.txt"><img alt="QGIS" src="https://img.shields.io/badge/QGIS-3.28%2B-5da85d?style=for-the-badge"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPL--2.0--or--later-111827?style=for-the-badge"></a>
  <a href="https://geophilo.com/qgis_25d_styling/"><img alt="Documentation" src="https://img.shields.io/badge/%F0%9F%93%96_Reference_Manual-13a0a0?style=for-the-badge"></a>
  <img alt="OpenStreetMap native" src="https://img.shields.io/badge/data-OpenStreetMap_native-8f6f5b?style=for-the-badge">
  <img alt="Processing" src="https://img.shields.io/badge/workflow-Processing_algorithm-2f4858?style=for-the-badge">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> |
  <a href="#the-workflow">Workflow</a> |
  <a href="#three-renderers">Renderers</a> |
  <a href="#processing">Processing</a> |
  <a href="#acknowledgements">Acknowledgements</a> |
  <a href="docs/index.html">Web Documentation</a>
</p>

---

## &#128214; Documentation

**[Full reference manual](https://geophilo.com/qgis_25d_styling/)** — a polished single-page guide to every renderer, theme, palette, and workflow. Hosted on Web Documentation.

---

## The Product Promise

QGIS 2.5D Styling does one thing and does it well: it turns any polygon layer — your own building footprints, or bounded OpenStreetMap footprints downloaded on demand — into layered 2.5D building symbology. No 3D dataset preparation, no external dependencies, no browser viewer to learn. Just a compact right-side dock and one Processing algorithm.

It is built for urban planners, cartographers, educators, students, and anyone who needs a fast, legible spatial story from building data.

The workflow stays deliberately simple:

1. Pick a polygon layer, or download buildings for the current map view from OSM.
2. Choose a renderer — Geometry Generator, Per-Floor Color Bands, or Native QGIS 2.5D.
3. Set the projection direction, facade and roof materials, shading, shadow, and floor divisions.
4. Apply one of 10 curated themes, or tune the controls directly.
5. Export the renderer as a QML style, or restore the layer's previous renderer.

## Quick Start

### Install from the QGIS Plugin Manager

Open QGIS &rarr; **Plugins &rarr; Manage and Install Plugins &rarr; All**, search for **QGIS 2.5D Styling**, and click **Install Plugin**.

### Install from a release ZIP

Download `qgis_25d_styling.zip` from [Releases](https://github.com/YusufEminoglu/qgis_25d_styling/releases), then **Plugins &rarr; Manage and Install Plugins &rarr; Install from ZIP**.

### Install for development

```powershell
$env:QGIS_PLUGINPATH = "C:\Users\YE\PyCharmMiscProject\qgis_plugins"
```

Restart QGIS, enable **QGIS 2.5D Styling**, and open it from the toolbar or plugin menu.

## The Workflow

The dock is organized into five stages — OSM, Form, Light, Floors, and Themes — so each step is clearly separated:

| Step | What you do |
| --- | --- |
| **1. Select a layer or download OSM** | Pick any polygon layer, or fetch OSM footprints for the current view. `building:levels` and `height` tags are extracted automatically. |
| **2. Choose a renderer** | Geometry Generator for full control, Per-Floor Color Bands for floor-level gradients, or Native QGIS 2.5D. |
| **3. Configure projection, materials &amp; lighting** | Set projection angle (0&ndash;359&deg;), facade/roof colors, outline, shading depth, shadow opacity, and story height. |
| **4. Apply a theme or tune floor palettes** | Pick one of 10 themes, or any of 23 per-floor palettes with a live ten-floor swatch preview. |
| **5. Apply, export QML, or restore** | Commit the renderer, export a QML style file for reuse, or restore the previous renderer non-destructively. |

## Three Renderers

| Renderer | What it gives you |
| --- | --- |
| **Geometry Generator** | Full facade, roof, drop-shadow and floor-division control built entirely from QGIS geometry expressions. Feature draw ordering paints taller buildings above shorter neighbours. |
| **Per-Floor Color Bands** | A rule-based renderer that assigns a distinct colour to each floor level. 23 palettes, a live ten-floor swatch preview, and automatic or explicit floor limits. The default for OSM downloads. |
| **Native QGIS 2.5D** | Delegates to QGIS's built-in `Qgs25DRenderer` through layer-scoped expression variables. Integrates with QGIS 3D views and respects global rendering settings. |

## 10 Material Themes

Every theme coordinates facade colour, roof accent, outline, shading depth, shadow opacity, and projection angle into one visual identity — and each ships its own matching per-floor gradient, so switching themes recolours per-floor-band mode too, not just the angle.

| Theme | Mood |
| --- | --- |
| **Warm Civic** | Warm stone roofs and civic terracotta facades. |
| **Cool Slate** | Cool blue-grey massing for analytical urban maps. |
| **Limestone and Teal** | Pale limestone roofs with composed teal facades. |
| **Night Copper** | Copper roofs over muted plum walls and deep night shadows. |
| **Urban Core Gold** | Gold roof accents on dense charcoal urban blocks. |
| **Suburban Pastoral** | Soft rose roofs and peach facades for low-rise districts. |
| **Cyberpunk Night** | Electric cyan roofs with violet walls and magenta shadows. |
| **Nordic Minimalist** | White roofs, neutral grey facades, precise dark edges. |
| **Emerald Metropolis** | Emerald roofs and deep forest facades for metropolitan cores. |
| **Terracotta Mediterranean** | Sunlit terracotta roofs and masonry-red facades. |

The default building material is a soft teal facade (`#7fb8b0`) with a yavru a&#287;z&#305; (peach) roof accent (`#f7c3a1`), matched by a default "Teal to Yavru A&#287;z&#305;" floor gradient.

## Why It Matters

| Need | How the plugin helps |
| --- | --- |
| Fast building context | Styles any polygon layer, or acquires bounded OSM footprints, without preparing a 3D dataset. |
| Planning communication | Turns a flat parcel map into layered 2.5D facades with solar shading for clear stakeholder visuals. |
| Floor-level reading | `building:levels` drives floor counts; missing values use a visible, configurable three-floor default. |
| Reproducible styling | QML import/export lets you share and reuse a look across projects and machines. |
| Automation | One headless Processing algorithm applies the full renderer stack from scripts or Model Builder. |
| No install friction | Pure QGIS API &mdash; qgis.core, qgis.gui, Processing. No pip packages; network only on explicit OSM download. |

## OSM Building Acquisition

The OSM download is asynchronous, bounded to the current view or selected-layer extent, cached locally, and falls back between Overpass mirrors when a service is unavailable. It reprojects to a metric CRS automatically and records the floor source (`building:levels`, an estimated floor count from `height`, or the fallback default) in an auditable `levels_source` attribute.

## Processing

`qgis_25d_styling:apply_25d_style` copies an input polygon layer to an output layer and applies the selected 2.5D renderer — no dock required.

```python
import processing

result = processing.run(
    "qgis_25d_styling:apply_25d_style",
    {
        "INPUT": buildings_layer,
        "RENDERER_MODE": "geometry_generator",   # geometry_generator | per_floor_bands | native_25d
        "THEME": "Night Copper",
        "PROJECTION_ANGLE": 315,
        "FACADE_COLOR": "#7fb8b0",
        "ROOF_COLOR": "#f7c3a1",
        "FALLBACK_HEIGHT": 3,
        "OUTPUT": "memory:",
    },
)
```

## Compatibility

| Runtime | Status |
| --- | --- |
| QGIS 3.28+ | Minimum requirement. Full feature support across 3.x. |
| QGIS 3.44 LTR | Primary release target &mdash; every version is verified on LTR before publishing. |
| QGIS 4.2 | Qt6 / QGIS 4 verified. No deprecated API usage in the plugin codebase. |
| Dependencies | Zero pip dependencies &mdash; pure QGIS API only. |
| Network | Optional &mdash; used only when the user starts an OSM download. |

## Repository Map

| Path | Role |
| --- | --- |
| `main_plugin.py` | QGIS plugin lifecycle, action and dock wiring. |
| `ui/styling_dock.py` | The compact right-dock studio: OSM, Form, Light, Floors, Themes. |
| `core/twopointfive_engine.py` | The shared renderer contract: geometry-generator, per-floor-band, and native 2.5D styling. |
| `core/presets.py` | The 10 themes, 23 per-floor palettes, and six projection shortcuts. |
| `core/osm_downloader.py` | Bounded Overpass download with cache, mirror fallback, and tag parsing. |
| `core/config.py` | The normalized, bounded configuration shared by every renderer. |
| `core/qml_exporter.py` | QML import/export and renderer restoration. |
| `processing/` | The headless `apply_25d_style` algorithm and provider. |
| `docs/` | Web Documentation landing page. |

## Web Documentation

This repository includes a polished static landing page at [`docs/index.html`](docs/index.html). To publish it:

1. Open the repository **Settings**.
2. Go to **Pages**.
3. Set **Source** to the main branch and the `/docs` folder.
4. Save.

No plugin version bump is required for documentation-only updates.

## &#129513; Part of the PlanX ecosystem

This plugin is one of a family of open-source QGIS plugins for urban planning by the same author:

| Planning &amp; analysis | CAD &amp; production | 3D &amp; visualization |
|---|---|---|
| [PlanX](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; spatial-planning suite | [PlanX CAD Toolset](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; drafting-grade CAD | [PlanX 3D City](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; Three.js city viewer |
| [GeoStats Lab](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; spatial statistics | [EasyFillet](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; tangent-arc fillet | [3D OSM Model](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; OSM &rarr; 3D city in browser |
| [Suitability Lab](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; raster MCDA | [Settlement Toolset](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; settlement plans | [OSM Quick 3D](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; OSM &rarr; native QGIS 3D |
| [DataCube Lab](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; spatiotemporal cubes | [UIP Toolset](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; master-plan automation | [CartoLab](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; publication cartography |
| [Urban Resilience](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; resilience tools | [ParcelFlux](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; parcel subdivision | [Urban Procedural 3D](https://github.com/YusufEminoglu/qgis_25d_styling) &mdash; parametric zoning |

## Acknowledgements &amp; Inspiration

The per-floor building classification concept and workflow in this plugin are directly inspired by a tutorial from **Narcélio de Sá** (Geocast Brasil) — *"QGIS - visualiza&ccedil;&atilde;o de vetor em 2.5D (Classificando os andares dos pr&eacute;dios)"* — [Watch on YouTube](https://www.youtube.com/watch?v=03XlpABs9vE) &middot; [narceliodesa.com](https://narceliodesa.com/).

Further thanks to **Klas Karlsson** and the wider QGIS cartography community for shared geometry-generator 2.5D extrusion and solar-shadow techniques. Full notices are collected in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Data, Credits, and License

QGIS 2.5D Styling is developed by **Yusuf Emino&#287;lu** at Dokuz Eyl&uuml;l University, Department of City and Regional Planning.

Map data is provided by OpenStreetMap contributors under the ODbL. Keep the OSM attribution visible when sharing downloads, screenshots, or exports.

The plugin code is released under the [GPL-2.0-or-later License](LICENSE).
