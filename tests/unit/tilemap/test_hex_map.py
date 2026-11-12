"""Tests for hexagonal Tiled map loading.

Covers the four Tiled stagger combinations (stagger axis x/y times stagger
index odd/even), map scaling, the backwards-compatibility switches, and
regression checks for rectangular maps. The expected positions come from an
independent re-implementation of Tiled's ``HexagonalRenderer`` formulas
(``src/libtiled/hexagonalrenderer.cpp``), not from the code under test.
"""

import math
import warnings

import pytest

import arcade
from arcade import HexMapGeometry

FIXTURE = ":fixtures:tilemaps/hex_{axis}_{index}.json"

# Dimensions shared by all generated fixtures (see tests/fixtures/tilemaps).
MAP_WIDTH = 4
MAP_HEIGHT = 3
TILE_WIDTH = 64
TILE_HEIGHT = 64
HEX_SIDE_LENGTH = 32


def tiled_reference(
    column: int,
    row: int,
    stagger_axis: str,
    stagger_index: str,
    scale: float = 1.0,
) -> tuple[float, float]:
    """Independent port of Tiled 1.11 HexagonalRenderer geometry.

    Returns the tile *center* in Arcade's Y-up coordinates, mirroring the
    logic of ``HexMapGeometry.tile_center`` without sharing any code with it.
    """
    tile_w = TILE_WIDTH * scale
    tile_h = TILE_HEIGHT * scale
    side = HEX_SIDE_LENGTH * scale

    stagger_x = stagger_axis == "x"
    stagger_even = stagger_index == "even"

    side_length_x = side if stagger_x else 0.0
    side_length_y = 0.0 if stagger_x else side
    side_offset_x = (tile_w - side_length_x) / 2.0
    side_offset_y = (tile_h - side_length_y) / 2.0
    column_width = side_offset_x + side_length_x
    row_height = side_offset_y + side_length_y
    renderer_tile_w = column_width + side_offset_x
    renderer_tile_h = row_height + side_offset_y

    def do_stagger(index: int) -> bool:
        return bool((index & 1) ^ stagger_even)

    if stagger_x:
        pixel_y = row * (renderer_tile_h + side_length_y)
        if do_stagger(column):
            pixel_y += row_height
        pixel_x = column * column_width
        map_width_px = MAP_WIDTH * column_width + side_offset_x
        map_height_px = MAP_HEIGHT * (renderer_tile_h + side_length_y)
        if MAP_WIDTH > 1:
            map_height_px += row_height
    else:
        pixel_x = column * (renderer_tile_w + side_length_x)
        if do_stagger(row):
            pixel_x += column_width
        pixel_y = row * row_height
        map_width_px = MAP_WIDTH * (renderer_tile_w + side_length_x)
        map_height_px = MAP_HEIGHT * row_height + side_offset_y
        if MAP_HEIGHT > 1:
            map_width_px += column_width

    center_x = pixel_x + renderer_tile_w / 2.0
    center_y = map_height_px - (pixel_y + renderer_tile_h / 2.0)
    return center_x, center_y


@pytest.fixture
def window():
    """Headless window providing a GL context for SpriteList creation."""
    window = arcade.open_window(200, 200, "hex-test", antialiasing=False)
    yield window
    window.close()


@pytest.mark.parametrize(
    ("axis", "index"),
    [("y", "odd"), ("y", "even"), ("x", "odd"), ("x", "even")],
    ids=["stagger-y odd-r", "stagger-y even-r", "stagger-x odd-q", "stagger-x even-q"],
)
def test_geometry_matches_tiled_formulas(axis, index):
    geometry = HexMapGeometry(
        TILE_WIDTH,
        TILE_HEIGHT,
        HEX_SIDE_LENGTH,
        stagger_axis=axis,
        stagger_index=index,
        map_width=MAP_WIDTH,
        map_height=MAP_HEIGHT,
    )
    expected_system = {
        ("y", "odd"): "odd-r",
        ("y", "even"): "even-r",
        ("x", "odd"): "odd-q",
        ("x", "even"): "even-q",
    }
    assert geometry.offset_system == expected_system[(axis, index)]

    for row in range(MAP_HEIGHT):
        for column in range(MAP_WIDTH):
            assert geometry.tile_center(column, row) == pytest.approx(
                tiled_reference(column, row, axis, index)
            )


def test_invalid_stagger_values_rejected():
    with pytest.raises(ValueError):
        HexMapGeometry(64, 64, 32, "z", "odd", 4, 3)
    with pytest.raises(ValueError):
        HexMapGeometry(64, 64, 32, "y", "third", 4, 3)


@pytest.mark.parametrize(
    ("axis", "index"),
    [("y", "odd"), ("y", "even"), ("x", "odd"), ("x", "even")],
    ids=["stagger-y odd-r", "stagger-y even-r", "stagger-x odd-q", "stagger-x even-q"],
)
def test_loaded_sprites_match_tiled_positions(window, axis, index):
    tile_map = arcade.load_tilemap(FIXTURE.format(axis=axis, index=index))

    # The metadata must actually be consumed.
    assert tile_map.hex_geometry is not None
    assert tile_map.hex_geometry.stagger_axis == axis
    assert tile_map.hex_geometry.stagger_index == index
    assert tile_map._use_hex_positioning is True

    sprites = tile_map.sprite_lists["TILE"]
    assert len(sprites) == MAP_WIDTH * MAP_HEIGHT

    # The fixture is fully populated row by row, so sprite order follows the
    # layer data order (row 0 first, columns ascending within a row).
    for row in range(MAP_HEIGHT):
        for column in range(MAP_WIDTH):
            sprite = sprites[row * MAP_WIDTH + column]
            expected_x, expected_y = tiled_reference(column, row, axis, index)
            assert sprite.center_x == pytest.approx(expected_x)
            assert sprite.center_y == pytest.approx(expected_y)


def test_stagger_combos_produce_different_positions(window):
    """Changing the metadata must change the output (the reported bug)."""
    odd = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"))
    even = arcade.load_tilemap(FIXTURE.format(axis="y", index="even"))
    x_axis = arcade.load_tilemap(FIXTURE.format(axis="x", index="odd"))

    odd_positions = [(s.center_x, s.center_y) for s in odd.sprite_lists["TILE"]]
    even_positions = [(s.center_x, s.center_y) for s in even.sprite_lists["TILE"]]
    x_positions = [(s.center_x, s.center_y) for s in x_axis.sprite_lists["TILE"]]

    assert odd_positions != even_positions
    assert odd_positions != x_positions

    # Concretely, tile (0, 1) shifts by column_width between odd and even.
    tile_01_odd = odd.hex_geometry.tile_center(0, 1)
    tile_01_even = even.hex_geometry.tile_center(0, 1)
    assert tile_01_odd[0] != tile_01_even[0]


@pytest.mark.parametrize("scale", [1.0, 2.0, 0.5])
def test_scaling_grows_spacing_and_sprite_size(window, scale):
    base = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), scaling=1.0)
    scaled = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), scaling=scale)

    base_sprites = base.sprite_lists["TILE"]
    scaled_sprites = scaled.sprite_lists["TILE"]

    for base_sprite, scaled_sprite in zip(base_sprites, scaled_sprites, strict=True):
        assert scaled_sprite.width == pytest.approx(base_sprite.width * scale)
        assert scaled_sprite.height == pytest.approx(base_sprite.height * scale)
        assert scaled_sprite.center_x == pytest.approx(base_sprite.center_x * scale)
        assert scaled_sprite.center_y == pytest.approx(base_sprite.center_y * scale)

    # Geometry spacing must scale too, otherwise adjacent hexes overlap.
    assert scaled.hex_geometry.column_width == pytest.approx(base.hex_geometry.column_width * scale)
    assert scaled.hex_geometry.row_height == pytest.approx(base.hex_geometry.row_height * scale)

    def horizontal_neighbor_gap(tile_map):
        a = tile_map.hex_geometry.tile_center(0, 0)
        b = tile_map.hex_geometry.tile_center(1, 0)
        return b[0] - a[0]

    assert horizontal_neighbor_gap(scaled) == pytest.approx(horizontal_neighbor_gap(base) * scale)

    # And every sprite center must match the independently scaled reference.
    for row in range(MAP_HEIGHT):
        for column in range(MAP_WIDTH):
            sprite = scaled_sprites[row * MAP_WIDTH + column]
            expected_x, expected_y = tiled_reference(column, row, "y", "odd", scale)
            assert sprite.center_x == pytest.approx(expected_x)
            assert sprite.center_y == pytest.approx(expected_y)


def test_no_overlap_at_2x_scaling(window):
    base = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), scaling=1.0)
    tile_map = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), scaling=2.0)
    sprites = tile_map.sprite_lists["TILE"]
    base_sprites = base.sprite_lists["TILE"]

    first = sprites[0]
    right_neighbor = sprites[1]
    center_gap = right_neighbor.center_x - first.center_x
    base_gap = base_sprites[1].center_x - base_sprites[0].center_x

    # Bounding boxes of same-row neighbors may touch, but must not overlap,
    # and the gap must grow with the scaling instead of staying fixed.
    assert center_gap >= first.width
    assert center_gap == pytest.approx(base_gap * 2.0)

    # Vertically adjacent rows are staggered but still separated.
    below = sprites[MAP_WIDTH]
    assert abs(below.center_y - first.center_y) > 0.0


def test_square_compat_mode_restores_legacy_grid(window):
    tile_map = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), hex_map_mode="square")
    assert tile_map.hex_geometry is None
    assert tile_map._use_hex_positioning is False

    sprites = tile_map.sprite_lists["TILE"]
    # Legacy square-grid placement: centers at half-tile offsets on a plain
    # 64px grid, Y flipped for the 3-row map.
    first = sprites[0]
    assert first.center_x == pytest.approx(TILE_WIDTH / 2)
    assert first.center_y == pytest.approx((MAP_HEIGHT - 1) * TILE_HEIGHT + TILE_HEIGHT / 2)
    second = sprites[1]
    assert second.center_x == pytest.approx(TILE_WIDTH + TILE_WIDTH / 2)
    assert second.center_y == pytest.approx(first.center_y)


def test_hex_mode_raises_on_rectangular_map(window):
    with pytest.raises(ValueError, match="hexagonal"):
        arcade.load_tilemap(":resources:tiled_maps/test_map_1.json", hex_map_mode="hex")


def test_auto_mode_ignored_by_rectangular_map(window):
    tile_map = arcade.load_tilemap(":resources:tiled_maps/test_map_1.json", hex_map_mode="auto")
    assert tile_map.hex_geometry is None
    assert tile_map._use_hex_positioning is False
    platforms = tile_map.sprite_lists["Platforms"]
    assert platforms[0].center_x == 64
    assert platforms[0].center_y == 64


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), hex_map_mode="diagonal")


def test_legacy_hex_layout_still_works_and_warns(window):
    from arcade import hexagon
    from pyglet.math import Vec2

    layout = hexagon.Layout(
        orientation=hexagon.pointy_orientation,
        size=Vec2(TILE_WIDTH / math.sqrt(3.0), TILE_HEIGHT / 2.0),
        origin=Vec2(0.0, 0.0),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tile_map = arcade.load_tilemap(FIXTURE.format(axis="y", index="odd"), hex_layout=layout)

    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    # Explicit layout takes precedence over automatic geometry.
    assert tile_map.hex_layout is layout
    assert tile_map.hex_geometry is None
    assert tile_map._use_hex_positioning is True
    assert len(tile_map.sprite_lists["TILE"]) == MAP_WIDTH * MAP_HEIGHT


def test_layer_offset_applied_to_hex_positions(window):
    tile_map = arcade.load_tilemap(
        FIXTURE.format(axis="y", index="odd"),
        layer_options={"TILE": {"offset": (100.0, -50.0)}},
    )
    sprites = tile_map.sprite_lists["TILE"]
    geometry = tile_map.hex_geometry
    expected_x, expected_y = geometry.tile_center(0, 0)
    assert sprites[0].center_x == pytest.approx(expected_x + 100.0)
    assert sprites[0].center_y == pytest.approx(expected_y - 50.0)


def test_layer_scaling_rebuilds_geometry(window):
    tile_map = arcade.load_tilemap(
        FIXTURE.format(axis="y", index="odd"),
        scaling=1.0,
        layer_options={"TILE": {"scaling": 3.0}},
    )
    sprites = tile_map.sprite_lists["TILE"]
    expected_x, expected_y = tiled_reference(0, 0, "y", "odd", scale=3.0)
    assert sprites[0].center_x == pytest.approx(expected_x)
    assert sprites[0].center_y == pytest.approx(expected_y)
    assert sprites[0].width == pytest.approx(TILE_WIDTH * 3.0)


def test_built_in_hex_map_loads_automatically(window):
    tile_map = arcade.load_tilemap(":resources:tiled_maps/hex_map.tmj")
    assert tile_map.hex_geometry is not None
    assert tile_map.hex_geometry.stagger_axis == "y"
    assert tile_map.hex_geometry.stagger_index == "odd"
    assert len(tile_map.sprite_lists["TILE"]) > 0
