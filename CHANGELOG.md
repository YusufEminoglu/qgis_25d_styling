# Changelog

## [1.1.1] - 2026-10-27

- Hub listing text rewritten; author Geophilo; university affiliation removed; documentation links use the standard geophilo.com pages (manual.html, guide/); manual HTML no longer ships in the plugin package.

## [1.1.0] - 2026-10-26

### Fixed

- **Shadows darkened neighbouring roofs.** Each building drew its own shadow
  just before itself, so a building drawn later laid its shadow over roofs and
  walls already on the map. Shadows now have their own first rendering pass;
  buildings follow, back to front.
- **Facade shading was one colour for every wall.** The shading term did not
  depend on the wall, so the sun azimuth only shifted the colour of the whole
  layer. Each facade is now shaded by its own orientation to the sun (lit
  faces keep the material colour, faces turned away are darkened by the
  shading depth).
- **Floor lines showed through the front facade.** Whole footprint rings were
  drawn at every floor, including the hidden back edges, which crossed the
  visible walls of tall or narrow buildings. Floor lines, corner edges and
  walls are now generated only for the edges that face the viewer.
- **Native renderer on a geographic layer extruded in degrees.** A 9 m
  building was pushed 9 degrees across the map. Heights are now converted to
  the layer's units (degrees, feet or metres) in every renderer.
- **Tall buildings detached from their shadow** and per-floor styles cut
  buildings off at 60 floors; the shadow is now the footprint swept away from
  the sun (exact for courtyards and L or U shapes) and the top floor band runs
  to the real roof.
- **OSM buildings mapped as multipolygon relations were dropped.** Courtyard
  blocks, malls and stations are now assembled from their member ways, holes
  included. Heights written with a decimal comma ("12,5") are read correctly.
- A configured height field the layer does not have, or a field name with
  quotes, broke the style; text fields with values such as "12 m" now fall
  back to the missing-height value instead of failing.
- The quick-angle buttons were mislabelled: 135 degrees was called SE but
  leans buildings north-west. They now name the real direction, and the angle
  control shows it as a compass point.
- The dock left the tab pages short with an empty strip below them on tall
  screens.
- The Processing algorithm used the fallback height for every building when no
  field was chosen, even when the layer had a `height` field.

### Added

- Height field unit: Auto (from the field name), Metres or Floors. Turkish
  field names (`yukseklik`, `kat_sayisi`, `kat_adedi`, `bina_yuksekligi`) are
  detected.
- Shadow length control (as a share of building height).
- Per-floor legend: one swatch per floor colour.
- Diagnostics after every apply: how the height field was read, how many
  buildings used the fallback, and the tallest building.
- Processing parameters `HEIGHT_UNIT` and `FLOOR_PALETTE`.

### Changed

- Choosing a theme keeps the renderer you picked and, with live preview on,
  applies at once.
- Both geometry-generator styles are rule-based renderers with a "Ground
  shadow" and a "Buildings" rule. Redrawing 20,000 synthetic buildings at full
  extent on the release test machine: 6 s for the solid style and 17 s for
  per-floor colours, against 61 s for QGIS's own 2.5D renderer. The solid
  style is about 2.5 times slower than in 1.0.2, which drew no per-facade
  shading or corner edges and ordered shadows wrongly.
- OSM layers are MultiPolygon and `osm_id` reads `way/123` or `relation/456`.

## [1.0.2] - 2026-09-29

### Fixed

- **The Processing algorithm never styled its output.** Vector destinations are
  written to disk even as temporary outputs, so the layer it tried to style did
  not exist during the run: every run logged "Could not resolve the output
  layer", the result arrived unstyled, and the optional QML was never written.
  The 2.5D style is now applied to the layer QGIS loads, and the QML is written
  from a template styled with the same settings. Per-floor bands take the
  maximum floor count from the input data during the run. The e2e suite now
  runs the algorithm as temporary and GeoPackage output.

### Changed

- Repository, tracker and release links point at the `geophilo1` GitLab namespace.

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
