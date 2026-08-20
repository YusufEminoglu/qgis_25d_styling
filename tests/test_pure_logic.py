# -*- coding: utf-8 -*-
"""Unit tests for the 2.5D configuration and preset contract."""
import pytest

from qgis_25d_styling.core.config import (
    DEFAULT_CONFIG,
    choose_height_field,
    compass_direction,
    normalize_config,
)
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


def test_build_height_expression_distinguishes_height_levels_and_constant():
    height = build_height_expression("height", multiplier=1.0, default_height=9.0)
    levels = build_height_expression("building_levels", multiplier=1.5, default_height=12.0)
    constant = build_height_expression("", multiplier=2.0, default_height=7.0)
    assert 'try("height")' in height
    assert 'try("building_levels") * 3.0' in height
    assert 'try("building_levels") * 3.0' in levels
    assert "1.5000" in levels
    assert constant == "(7.0 * 2.0000)"
