# -*- coding: utf-8 -*-
"""How a height or floor attribute becomes a building height.

Pure Python on purpose: the QGIS expressions the renderers draw with and the
values the dock and the Processing algorithm scan are built from the same
rules here, so a building can never be one height on the map and another in
the slab count, the legend or the diagnostics.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Optional

FLOOR_TOKENS = ("level", "floor", "storey", "story", "kat")

# Hard ceiling on drawn slabs. Taller buildings are not cut off: the last slab
# absorbs every floor above it.
MAX_SLABS = 100


def quote_field(name: str) -> str:
    """Quote a field name for a QGIS expression (same rule as QgsExpression.quotedColumnRef)."""
    return '"' + str(name).replace('"', '""') + '"'


def field_kind(field: str, unit: str = "auto") -> str:
    """Return ``"floors"``, ``"meters"`` or ``"none"`` for a height attribute.

    ``unit`` is the user's explicit choice; ``"auto"`` reads the field name,
    so ``building_levels`` or ``kat_sayisi`` count floors and ``height`` or
    ``yukseklik`` hold metres.
    """
    name = str(field or "").strip()
    if not name:
        return "none"
    if unit in ("meters", "floors"):
        return unit
    lowered = name.casefold()
    return "floors" if any(token in lowered for token in FLOOR_TOKENS) else "meters"


def _num(value: float) -> str:
    return f"{float(value):.6g}"


def _positive_value_expr(field: str, positive: str, fallback: str, numeric: bool = False) -> str:
    """``positive`` (written with ``{v}`` for the value) when the field holds a
    positive number, else ``fallback``.

    A numeric field is read directly. Any other field goes through
    ``try(to_real())``, which turns text such as "12 m" or "" into NULL
    instead of an evaluation error; a NULL comparison falls through to the
    fallback either way.
    """
    if numeric:
        value = quote_field(field)
        return f"CASE WHEN {value} > 0 THEN {positive.format(v=value)} ELSE {fallback} END"
    return (
        f"with_variable('h25_v', try(to_real({quote_field(field)})), "
        f"CASE WHEN @h25_v > 0 THEN {positive.format(v='@h25_v')} ELSE {fallback} END)"
    )


def height_meters_expression(
    field: str,
    unit: str = "auto",
    multiplier: float = 1.0,
    default_height: float = 9.0,
    floor_height: float = 3.2,
    default_levels: int = 3,
    numeric: bool = False,
) -> str:
    """Expression for a building's drawn height in metres, multiplier included."""
    kind = field_kind(field, unit)
    if kind == "floors":
        base = _positive_value_expr(
            field, f"{{v}} * {_num(floor_height)}", _num(default_levels * floor_height), numeric
        )
    elif kind == "meters":
        base = _positive_value_expr(field, "{v}", _num(default_height), numeric)
    else:
        base = _num(default_height)
    if abs(float(multiplier) - 1.0) > 1e-9:
        return f"(({base}) * {_num(multiplier)})"
    return f"({base})"


def floor_count_expression(
    field: str,
    unit: str = "auto",
    floor_height: float = 3.2,
    default_levels: int = 3,
    numeric: bool = False,
) -> str:
    """Expression for a building's whole number of floors (at least one)."""
    kind = field_kind(field, unit)
    fallback = str(max(1, int(default_levels)))
    if kind == "floors":
        return _positive_value_expr(field, "max(1, to_int(round({v})))", fallback, numeric)
    if kind == "meters":
        return _positive_value_expr(
            field, f"max(1, to_int(round({{v}} / {_num(floor_height)})))", fallback, numeric
        )
    return fallback


def _positive(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number <= 0 or math.isinf(number):
        return None
    return number


def height_meters_value(value: Any, kind: str, cfg: dict) -> float:
    """Python twin of :func:`height_meters_expression` without the multiplier."""
    floor_h = float(cfg.get("floor_height_m", 3.2))
    number = _positive(value) if kind != "none" else None
    if kind == "floors":
        return (number if number is not None else int(cfg.get("default_levels", 3))) * floor_h
    if kind == "meters" and number is not None:
        return number
    return float(cfg.get("default_height", 9.0))


def floor_count_value(value: Any, kind: str, cfg: dict) -> int:
    """Python twin of :func:`floor_count_expression`."""
    number = _positive(value) if kind != "none" else None
    if number is None:
        return max(1, int(cfg.get("default_levels", 3)))
    if kind == "meters":
        number = number / float(cfg.get("floor_height_m", 3.2))
    # QGIS round() rounds halves away from zero; Python's round() does not.
    return max(1, int(math.floor(number + 0.5)))


def slab_count(values: Iterable[Any], cfg: dict, per_floor: bool) -> int:
    """Number of floor slabs needed to draw the tallest building.

    A positive ``cfg["max_floors"]`` caps it explicitly; otherwise the values
    of the height field decide, and the result never exceeds :data:`MAX_SLABS`.
    """
    explicit = int(cfg.get("max_floors", 0) or 0)
    if explicit > 0:
        return max(1, min(MAX_SLABS, explicit))
    kind = field_kind(cfg.get("height_field", ""), cfg.get("height_unit", "auto"))
    floor_h = max(0.5, float(cfg.get("floor_height_m", 3.2)))
    tallest = 1
    seen = False
    for value in values:
        seen = True
        if per_floor:
            floors = floor_count_value(value, kind, cfg)
        else:
            floors = int(math.ceil(height_meters_value(value, kind, cfg) / floor_h - 1e-9))
        tallest = max(tallest, floors)
    if not seen:
        if per_floor:
            tallest = max(1, int(cfg.get("default_levels", 3)))
        else:
            tallest = int(math.ceil(float(cfg.get("default_height", 9.0)) / floor_h - 1e-9))
    return max(1, min(MAX_SLABS, tallest))
