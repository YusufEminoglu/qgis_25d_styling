# Changelog

## [Unreleased]

### Fixed

- **The Processing algorithm never styled its output.** Vector destinations are
  written to disk even as temporary outputs, so the layer it tried to style did
  not exist during the run: every run logged "Could not resolve the output
  layer", the result arrived unstyled, and the optional QML was never written.
  The 2.5D style is now applied to the layer QGIS loads, and the QML is written
  from a template styled with the same settings. Per-floor bands take the
  maximum floor count from the input data during the run. The e2e suite now
  runs the algorithm as temporary and GeoPackage output.

## [1.0.1] - 2026-09-06

- Migrate repository and documentation URLs to GitLab and Cloudflare Pages.

All notable changes to QGIS 2.5D Styling are documented here. The project follows Semantic Versioning and Keep a Changelog.

## [1.0.0] - 2026-08-21

### Added

This first published release keeps the product focused on one result: 2.5D building styling, from either project polygons or bounded OSM building footprints.

1. Added asynchronous OSM building download for the current view or selected-layer extent.
2. Added `building:levels` floor-count handling with an explicit, configurable three-floor fallback.
3. Added `levels_source` attributes so inferred floors remain auditable.
4. Reorganized the compact right dock into OSM, Form, Light, Floors, and Themes stages.
5. Replaced the custom segmented tab implementation with accessible native tabs.
6. Added numeric-only height field filtering.
7. Added case-insensitive automatic height-field detection.
8. Added a configurable constant fallback height.
9. Added a dedicated height scale control.
10. Added a normalized and bounded configuration contract shared by all renderers.
11. Removed conflicting render-mode controls and established one mode selector.
12. Added complete preset-to-UI configuration round trips.
13. Added dynamic compass labels for solar azimuth.
14. Added numeric values beside opacity and shading sliders.
15. Added six projection shortcuts from the shared angle registry.
16. Added dependent-control states for shading, shadow, floor divisions, and renderer mode.
17. Added debounced live preview for responsive slider editing.
18. Added adaptive preview delay and a large-layer preview guard.
19. Added inline apply, pending, success, restore, and error states.
20. Added polygon-layer preflight and action enablement.
21. Added feature-count, CRS, height-source, and geographic-CRS diagnostics.
22. Added non-destructive restoration of the renderer that existed before styling.
23. Added QML style import alongside QML export.
24. Added last-directory persistence for QML workflows.
25. Added persistent configuration, live-preview, and tab settings.
26. Added 10 material themes adapted from the 02CartoLab 2.5D style collection.
27. Added action/dock visibility synchronization in the plugin shell.
28. Corrected height-field and floor-count expression semantics.
29. Moved native renderer inputs to QGIS layer expression variables.
30. Added feature draw ordering to the Geometry Generator renderer.
31. Expanded the Processing algorithm with renderer and fallback-height controls.
32. Added sink and renderer failure checks to Processing execution.
33. Added 13 curated per-floor color palettes with a live ten-floor swatch preview.
34. Added OSM floor-source and fallback-height coverage to both QGIS release runtimes.
35. Added a distinctive 512 px transparent plugin icon.
36. Kept Processing focused on one styling algorithm; OSM acquisition remains an explicit dock action.
37. Set the default building materials to soft teal facades with a yavru agzi (peach) roof accent, replacing the placeholder grey/white defaults everywhere they were set (config defaults, dock color pickers, preset-summary swatches, and the Processing algorithm parameters).
38. Fixed OSM buildings with an explicit `height` tag but no `building:levels` tag falling back to the constant default floor count instead of an estimate derived from height; the fallback-count status message and `levels_source` attribute now distinguish "estimated" from "default".
39. Disabled the Sun Azimuth and Shading Depth controls in Native QGIS 2.5D mode, since the native renderer has no directional-shading equivalent and previously left them interactive with no visible effect.
40. Reported a Processing-algorithm error instead of silently skipping symbology and QML export when the destination layer cannot be resolved after being written.
41. Fixed themes only changing the projection angle in Per-Floor Color Bands mode (the mode OSM downloads default to): that renderer colors floors entirely from the Floor Palette selector and never read a theme's wall/roof colors, so switching themes looked like nothing but the angle moved. Each of the 10 themes now carries its own matching per-floor gradient (derived from that theme's own roof/wall colors) and selecting a theme now switches the Floor Palette selector to it automatically. Added a default "Teal to Yavru Agzi" gradient palette matching the new default building colors, replacing the unrelated rainbow default.
