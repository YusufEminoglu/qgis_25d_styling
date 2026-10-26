# -*- coding: utf-8 -*-
"""Curated 2.5D material styles and per-floor palettes."""
from __future__ import annotations

import colorsys
from typing import Any, Dict, List, Tuple


def _hex_to_unit_rgb(value: str) -> Tuple[float, float, float]:
    h = value.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _unit_rgb_to_hex(rgb: Tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02x}" for c in rgb)


def _gradient(start_hex: str, end_hex: str, steps: int = 12) -> Tuple[str, ...]:
    """Build a smooth multi-stop gradient between two colors via the shortest hue path.

    Sweeping hue (instead of a straight RGB blend) keeps every stop saturated,
    so a teal-to-peach gradient passes through vivid greens and golds rather
    than collapsing into a muddy grey midpoint.
    """
    h1, s1, v1 = colorsys.rgb_to_hsv(*_hex_to_unit_rgb(start_hex))
    h2, s2, v2 = colorsys.rgb_to_hsv(*_hex_to_unit_rgb(end_hex))
    delta_h = h2 - h1
    if delta_h > 0.5:
        delta_h -= 1.0
    elif delta_h < -0.5:
        delta_h += 1.0
    colors: List[str] = []
    for i in range(steps):
        t = i / (steps - 1) if steps > 1 else 0.0
        h = (h1 + delta_h * t) % 1.0
        s = s1 + (s2 - s1) * t
        v = v1 + (v2 - v1) * t
        colors.append(_unit_rgb_to_hex(colorsys.hsv_to_rgb(h, s, v)))
    return tuple(colors)


# Directly adapted from zero2cartolab's 2.5D and general palette libraries, plus
# the plugin's own default-color gradient below.
FLOOR_BAND_PALETTES: Dict[str, Dict[str, Any]] = {
    "teal_peach": {
        "name": "Teal to Yavru Agzi",
        "colors": _gradient("#7fb8b0", "#f7c3a1", 12),
    },
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


def _style(
    key: str,
    name: str,
    description: str,
    roof: str,
    wall: str,
    shadow: str,
    outline: str,
    angle: float = 45.0,
    spread: float = 3.5,
) -> Dict[str, Any]:
    """Build one complete style using the shared renderer contract.

    Also registers a matching per-floor gradient palette (roof-to-wall) under
    the same key, so switching themes changes the visible per-floor-band
    colors too, not just the projection angle.
    """
    palette_key = f"{key}_gradient"
    FLOOR_BAND_PALETTES[palette_key] = {
        "name": f"{name} Gradient",
        "colors": _gradient(wall, roof, 12),
    }
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
        "floor_palette": palette_key,
    }


# Directly adapted from zero2cartolab.core.qgis_25d_style.STYLE_25D_PRESETS.
_THEME_DEFS: Tuple[Tuple[str, str, str, str, str, str, str, float, float], ...] = (
    ("warm_civic", "Warm Civic", "Warm stone roofs and civic terracotta facades.",
     "#f2cf96", "#b36f43", "#202833", "#6d4028", 45.0, 3.5),
    ("cool_slate", "Cool Slate", "Cool blue-grey massing for analytical urban maps.",
     "#d7e4e8", "#607d8b", "#14242b", "#324b57", 45.0, 4.0),
    ("limestone_teal", "Limestone and Teal", "Pale limestone roofs with composed teal facades.",
     "#eadfc8", "#4f8f8a", "#1f2933", "#285c58", 30.0, 3.0),
    ("night_copper", "Night Copper", "Copper roofs over muted plum walls and deep night shadows.",
     "#d89b6a", "#6f4a58", "#090d16", "#3c2630", 60.0, 5.0),
    ("urban_gold", "Urban Core Gold", "Gold roof accents on dense charcoal urban blocks.",
     "#d4af37", "#1a1a24", "#0d1b2a", "#08080d", 45.0, 4.5),
    ("suburban_pastoral", "Suburban Pastoral", "Soft rose roofs and peach facades for low-rise districts.",
     "#c06c84", "#f8b195", "#355c7d", "#8f5363", 135.0, 3.0),
    ("cyberpunk_night", "Cyberpunk Night", "Electric cyan roofs with violet walls and magenta shadows.",
     "#00f5d4", "#7b2cbf", "#ff007f", "#351252", 315.0, 6.0),
    ("nordic_minimalist", "Nordic Minimalist", "White roofs, neutral grey facades and precise dark edges.",
     "#f8f9fa", "#6c757d", "#212529", "#343a40", 45.0, 3.5),
    ("emerald_metropolis", "Emerald Metropolis", "Emerald roofs and deep forest facades for metropolitan cores.",
     "#52b788", "#1b4332", "#081c15", "#0b2b20", 60.0, 4.0),
    ("terracotta_mediterranean", "Terracotta Mediterranean", "Sunlit terracotta roofs and masonry-red facades.",
     "#f4a261", "#b34233", "#4a121a", "#70261e", 30.0, 3.5),
)

PRESETS: Dict[str, Dict[str, Any]] = {
    key: _style(key, name, description, roof, wall, shadow, outline, angle, spread)
    for key, name, description, roof, wall, shadow, outline, angle, spread in _THEME_DEFS
}


# Direction the roofs are pushed, in QGIS's 2.5D convention: degrees
# anticlockwise from east, so 135 leans buildings to the north-west.
STANDARD_ANGLES = [
    ("NE isometric (45 deg)", 45.0),
    ("ENE (30 deg)", 30.0),
    ("NNE (60 deg)", 60.0),
    ("NW (135 deg)", 135.0),
    ("SW (225 deg)", 225.0),
    ("SE (315 deg)", 315.0),
]
