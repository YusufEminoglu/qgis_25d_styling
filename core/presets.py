# -*- coding: utf-8 -*-
"""Curated 2.5D material styles and per-floor palettes."""
from __future__ import annotations

from typing import Any, Dict


def _style(
    name: str,
    description: str,
    roof: str,
    wall: str,
    shadow: str,
    outline: str,
    angle: float = 45.0,
    spread: float = 3.5,
) -> Dict[str, Any]:
    """Build one complete style using the shared renderer contract."""
    return {
        "name": name,
        "description": description,
        "render_mode": "per_floor_bands",
        "roof_color": roof,
        "wall_color": wall,
        "outline_color": outline,
        "outline_width": 0.35,
        "roof_outline_color": outline,
        "roof_outline_width": 0.45,
        "shadow_enabled": True,
        "shadow_color": shadow,
        "shadow_alpha": 48,
        "shadow_blur": spread,
        "projection_angle": angle,
        "sun_azimuth": 315.0,
        "facade_shading": True,
        "shading_intensity": 0.45,
        "floor_bands_enabled": True,
        "floor_height_m": 3.2,
        "floor_line_color": roof,
        "floor_line_width": 0.2,
    }


# Directly adapted from zero2cartolab.core.qgis_25d_style.STYLE_25D_PRESETS.
PRESETS: Dict[str, Dict[str, Any]] = {
    "warm_civic": _style(
        "Warm Civic", "Warm stone roofs and civic terracotta facades.",
        "#f2cf96", "#b36f43", "#202833", "#6d4028", 45.0, 3.5,
    ),
    "cool_slate": _style(
        "Cool Slate", "Cool blue-grey massing for analytical urban maps.",
        "#d7e4e8", "#607d8b", "#14242b", "#324b57", 45.0, 4.0,
    ),
    "limestone_teal": _style(
        "Limestone and Teal", "Pale limestone roofs with composed teal facades.",
        "#eadfc8", "#4f8f8a", "#1f2933", "#285c58", 30.0, 3.0,
    ),
    "night_copper": _style(
        "Night Copper", "Copper roofs over muted plum walls and deep night shadows.",
        "#d89b6a", "#6f4a58", "#090d16", "#3c2630", 60.0, 5.0,
    ),
    "urban_gold": _style(
        "Urban Core Gold", "Gold roof accents on dense charcoal urban blocks.",
        "#d4af37", "#1a1a24", "#0d1b2a", "#08080d", 45.0, 4.5,
    ),
    "suburban_pastoral": _style(
        "Suburban Pastoral", "Soft rose roofs and peach facades for low-rise districts.",
        "#c06c84", "#f8b195", "#355c7d", "#8f5363", 135.0, 3.0,
    ),
    "cyberpunk_night": _style(
        "Cyberpunk Night", "Electric cyan roofs with violet walls and magenta shadows.",
        "#00f5d4", "#7b2cbf", "#ff007f", "#351252", 315.0, 6.0,
    ),
    "nordic_minimalist": _style(
        "Nordic Minimalist", "White roofs, neutral grey facades and precise dark edges.",
        "#f8f9fa", "#6c757d", "#212529", "#343a40", 45.0, 3.5,
    ),
    "emerald_metropolis": _style(
        "Emerald Metropolis", "Emerald roofs and deep forest facades for metropolitan cores.",
        "#52b788", "#1b4332", "#081c15", "#0b2b20", 60.0, 4.0,
    ),
    "terracotta_mediterranean": _style(
        "Terracotta Mediterranean", "Sunlit terracotta roofs and masonry-red facades.",
        "#f4a261", "#b34233", "#4a121a", "#70261e", 30.0, 3.5,
    ),
}


STANDARD_ANGLES = [
    ("Isometric (45 deg NE)", 45.0),
    ("Military (30 deg)", 30.0),
    ("Cavalier (60 deg)", 60.0),
    ("Plan Oblique (135 deg SE)", 135.0),
    ("Western Oblique (225 deg SW)", 225.0),
    ("Northern Oblique (315 deg NW)", 315.0),
]


# Directly adapted from zero2cartolab's 2.5D and general palette libraries.
FLOOR_BAND_PALETTES: Dict[str, Dict[str, Any]] = {
    "civic_spectrum": {"name": "Civic Spectrum", "colors": (
        "#f4d35e", "#ee964b", "#f95738", "#d7263d", "#9b5de5", "#00bbf9",
        "#00f5d4", "#80ed99", "#ffd166", "#06d6a0", "#118ab2", "#ef476f",
        "#f4a261", "#2a9d8f", "#e76f51", "#457b9d",
    )},
    "planning_bands": {"name": "Planning Bands", "colors": (
        "#f2cc8f", "#e07a5f", "#81b29a", "#3d405b", "#8ecae6", "#219ebc",
        "#ffb703", "#fb8500", "#a7c957", "#6a994e", "#bc4749", "#9d4edd",
        "#4cc9f0", "#4895ef", "#4361ee", "#3a0ca3",
    )},
    "soft_atlas": {"name": "Soft Atlas", "colors": (
        "#b8e0d2", "#95b8d1", "#809bce", "#b8b8ff", "#ffc8dd", "#ffafcc",
        "#ffd6a5", "#fdffb6", "#caffbf", "#9bf6ff", "#a0c4ff", "#bdb2ff",
        "#d8e2dc", "#ffe5d9", "#ffcad4", "#f4acb7",
    )},
    "turbo_height": {"name": "Turbo Height", "colors": (
        "#30123b", "#4662d8", "#35abf8", "#1ae4b6", "#72fe5e", "#c8ef34",
        "#faba39", "#f66c19", "#cb2a04", "#7a0403", "#5c015b", "#2a0845",
        "#00b4d8", "#0077b6", "#023e8a", "#03045e",
    )},
    "viridis_height": {"name": "Viridis Height", "colors": (
        "#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89",
        "#35b779", "#6ece58", "#b5de2b", "#fde725", "#80ed99", "#38b000",
        "#007200", "#004b23", "#132a13", "#001a00",
    )},
    "magma": {"name": "Magma", "colors": (
        "#000004", "#180f3e", "#451077", "#721f81", "#9f2f7f", "#cd4071",
        "#f1605d", "#fd9567", "#fcfdbf",
    )},
    "plasma": {"name": "Plasma", "colors": (
        "#0d0887", "#47039f", "#7301a8", "#9c179e", "#bd3786", "#d8576b",
        "#ed7953", "#fb9f3a", "#f0f921",
    )},
    "inferno": {"name": "Inferno", "colors": (
        "#000004", "#1b0c41", "#4a0c6b", "#781c6d", "#a52c60", "#cf4446",
        "#ed6925", "#fb9b06", "#fcffa4",
    )},
    "cividis": {"name": "Cividis", "colors": (
        "#00204d", "#00336f", "#39486b", "#575d6d", "#707173", "#8a8779",
        "#a69d75", "#c4b56c", "#fee838",
    )},
    "sunset": {"name": "Sunset", "colors": (
        "#0c1048", "#2b2a6d", "#583f88", "#875097", "#b85c96", "#e16e86",
        "#f78d6e", "#fdb659", "#fbe382",
    )},
    "set3": {"name": "Set3 Floors", "colors": (
        "#8dd3c7", "#ffffb3", "#bebada", "#fb8072", "#80b1d3", "#fdb462",
        "#b3de69", "#fccde5", "#d9d9d9", "#bc80bd", "#ccebc5", "#ffed6f",
    )},
    "paired": {"name": "Paired Floors", "colors": (
        "#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#e31a1c",
        "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a", "#ffff99", "#b15928",
    )},
}
