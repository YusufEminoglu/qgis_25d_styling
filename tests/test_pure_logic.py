# -*- coding: utf-8 -*-
"""Unit tests for the 2.5D configuration and preset contract."""
import pytest

from qgis_25d_styling.core.config import (
    DEFAULT_CONFIG,
    choose_height_field,
    compass_direction,
    extrusion_compass,
    normalize_config,
)
from qgis_25d_styling.core.heights import (
    MAX_SLABS,
    field_kind,
    floor_count_expression,
    floor_count_value,
    height_meters_expression,
    height_meters_value,
    slab_count,
)
from qgis_25d_styling.core.osm_downloader import parse_numeric_height, parse_numeric_levels, stitch_rings
from qgis_25d_styling.core.presets import FLOOR_BAND_PALETTES, PRESETS, STANDARD_ANGLES
from qgis_25d_styling.core.twopointfive_engine import build_height_expression


def test_normalize_config_provides_complete_bounded_contract():
    cfg = normalize_config({
        "render_mode": "invalid",
        "height_multiplier": -3,
        "projection_angle": 800,
        "shadow_alpha": 999,
        "shading_intensity": "invalid",
        "default_levels": 500,
    })
    assert set(DEFAULT_CONFIG).issubset(cfg)
    assert cfg["render_mode"] == "geometry_generator"
    assert cfg["height_multiplier"] == pytest.approx(0.05)
    assert cfg["projection_angle"] == pytest.approx(359.0)
    assert cfg["shadow_alpha"] == 100
    assert cfg["shading_intensity"] == pytest.approx(0.4)
    assert cfg["default_levels"] == 100


@pytest.mark.parametrize(
    ("mode", "use_geometry", "per_floor"),
    [
        ("geometry_generator", True, False),
        ("per_floor_bands", False, True),
        ("native", False, False),
    ],
)
def test_render_modes_have_one_source_of_truth(mode, use_geometry, per_floor):
    cfg = normalize_config({"render_mode": mode})
    assert cfg["use_geometry_generator"] is use_geometry
    assert cfg["per_floor_bands"] is per_floor


def test_height_field_detection_is_case_insensitive_and_prioritized():
    assert choose_height_field(["id", "BUILDING_LEVELS", "Height"]) == "Height"
    assert choose_height_field(["id", "BUILDING_LEVELS"]) == "BUILDING_LEVELS"
    assert choose_height_field(["id", "name"]) == ""


@pytest.mark.parametrize(
    ("angle", "label"),
    [(0, "N"), (44, "NE"), (90, "E"), (181, "S"), (270, "W"), (359, "N")],
)
def test_compass_direction(angle, label):
    assert compass_direction(angle) == label


def test_presets_match_the_normalized_schema():
    assert len(PRESETS) == 10
    for key, preset in PRESETS.items():
        cfg = normalize_config(preset)
        assert cfg["wall_color"].startswith("#"), key
        assert cfg["roof_color"].startswith("#"), key
        assert 0 <= cfg["projection_angle"] < 360, key
        assert 0 <= cfg["sun_azimuth"] < 360, key


def test_angles_and_floor_palettes_are_release_ready():
    assert len(STANDARD_ANGLES) == 6
    assert {int(value) for _name, value in STANDARD_ANGLES} == {30, 45, 60, 135, 225, 315}
    assert len(FLOOR_BAND_PALETTES) >= 10
    assert all(len(value["colors"]) >= 8 for value in FLOOR_BAND_PALETTES.values())


def test_height_expressions_follow_the_field_kind():
    height = build_height_expression("height", multiplier=1.0, default_height=9.0)
    levels = build_height_expression("building_levels", multiplier=1.5, default_height=12.0, floor_height=3.0)
    constant = build_height_expression("", multiplier=2.0, default_height=7.0)
    # A metre field never borrows another column that may not exist.
    assert '"height"' in height and "building_levels" not in height
    assert '"building_levels"' in levels and "@h25_v * 3" in levels and "* 1.5" in levels
    assert constant == "((7) * 2)"


def test_height_expression_quotes_awkward_field_names():
    expr = height_meters_expression('my "tall" field', "meters")
    assert '"my ""tall"" field"' in expr


def test_numeric_fields_are_read_without_text_conversion():
    expr = floor_count_expression("kat_sayisi", numeric=True)
    assert "to_real" not in expr and '"kat_sayisi" > 0' in expr
    assert "to_real" in floor_count_expression("kat_sayisi", numeric=False)


@pytest.mark.parametrize(
    ("field", "unit", "kind"),
    [
        ("building_levels", "auto", "floors"),
        ("KAT_SAYISI", "auto", "floors"),
        ("height", "auto", "meters"),
        ("yukseklik", "auto", "meters"),
        ("height", "floors", "floors"),
        ("levels", "meters", "meters"),
        ("", "floors", "none"),
    ],
)
def test_field_kind(field, unit, kind):
    assert field_kind(field, unit) == kind


def test_turkish_height_fields_are_detected():
    assert choose_height_field(["id", "Kat_Sayisi"]) == "Kat_Sayisi"
    assert choose_height_field(["id", "yukseklik", "kat_sayisi"]) == "yukseklik"


def test_values_mirror_the_expressions():
    cfg = {"floor_height_m": 3.0, "default_levels": 3, "default_height": 9.0}
    assert height_meters_value(4, "floors", cfg) == pytest.approx(12.0)
    assert height_meters_value(None, "floors", cfg) == pytest.approx(9.0)
    assert height_meters_value("tall", "meters", cfg) == pytest.approx(9.0)
    assert height_meters_value(-5, "meters", cfg) == pytest.approx(9.0)
    # QGIS rounds halves away from zero.
    assert floor_count_value(2.5, "floors", cfg) == 3
    assert floor_count_value(7.4, "meters", cfg) == 2
    assert floor_count_value(0.2, "floors", cfg) == 1
    assert floor_count_value(None, "meters", cfg) == 3


def test_slab_count_reaches_the_tallest_building():
    cfg = {"height_field": "building_levels", "floor_height_m": 3.2, "default_levels": 3}
    assert slab_count([2, None, 7, "x"], cfg, per_floor=True) == 7
    assert slab_count([250], cfg, per_floor=True) == MAX_SLABS
    assert slab_count([], cfg, per_floor=True) == 3
    assert slab_count([2, 9], dict(cfg, max_floors=4), per_floor=True) == 4
    metres = {"height_field": "height", "floor_height_m": 3.0, "default_height": 9.0}
    assert slab_count([10.0, 2.0], metres, per_floor=False) == 4


@pytest.mark.parametrize(
    ("angle", "label"),
    [(0, "E"), (45, "NE"), (90, "N"), (135, "NW"), (225, "SW"), (315, "SE")],
)
def test_extrusion_compass_uses_the_qgis_angle_convention(angle, label):
    assert extrusion_compass(angle) == label


def test_quick_angle_labels_name_the_real_direction():
    for name, value in STANDARD_ANGLES:
        assert extrusion_compass(value) in name.split("(")[0], name


def test_normalize_config_bounds_new_keys():
    cfg = normalize_config({"height_unit": "furlongs", "shadow_length": 99})
    assert cfg["height_unit"] == "auto"
    assert cfg["shadow_length"] == pytest.approx(3.0)


def test_osm_numbers_accept_decimal_commas_and_feet():
    assert parse_numeric_height("12,5 m") == pytest.approx(12.5)
    assert parse_numeric_height("40 ft") == pytest.approx(12.192)
    assert parse_numeric_levels("4,5") == pytest.approx(4.5)
    assert parse_numeric_height("roof") is None


def test_stitch_rings_joins_split_and_reversed_ways():
    a = [(0, 0), (1, 0), (1, 1)]
    b = [(0, 1), (1, 1)]          # reversed relative to the ring
    c = [(0, 1), (0, 0)]
    rings = stitch_rings([a, b, c])
    assert len(rings) == 1
    ring = rings[0]
    assert ring[0] == ring[-1] and len(ring) == 5
    assert set(ring) == {(0, 0), (1, 0), (1, 1), (0, 1)}


def test_stitch_rings_drops_open_lines():
    assert stitch_rings([[(0, 0), (1, 0), (2, 0)]]) == []
