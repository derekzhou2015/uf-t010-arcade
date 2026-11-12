.. _hex_map_tutorial:

Working with Hexagonal Tilemaps
===============================

This tutorial covers how to load and display hexagonal tilemaps in Arcade using
the `Tiled`_ map editor and Arcade's ``arcade.hexagon`` module.

You don't need to understand all the math behind hexagonal grids to follow this
tutorial, but if you're building something with hexes,
`Red Blob Games' guide to hexagonal grids <https://www.redblobgames.com/grids/hexagons/>`_
is an invaluable resource for understanding the coordinate systems, algorithms, and
geometry involved.

.. _Tiled: https://www.mapeditor.org/

Hexagonal Coordinate Systems
-----------------------------

Hexagonal grids use a different coordinate system than square grids. Arcade's
:class:`~arcade.hexagon.HexTile` class uses **cube coordinates** (q, r, s) where
``q + r + s = 0`` always holds true. This constraint means you only need two of the
three values to uniquely identify a hex, but keeping all three makes the math simpler.

.. code-block:: python

    from arcade.hexagon import HexTile

    # Create a hex tile at the origin
    origin = HexTile(0, 0, 0)

    # A neighbor one step in the q direction
    neighbor = HexTile(1, -1, 0)

    # Distance between two hexes
    dist = origin.distance_to(neighbor)  # 1

Cube coordinates are great for math, but map editors like Tiled use **offset
coordinates** (column, row). Arcade handles the conversion automatically when
loading maps, but you can also convert manually:

.. code-block:: python

    from arcade.hexagon import HexTile, OffsetCoord

    # Convert from offset to cube
    offset = OffsetCoord(col=3, row=2)
    cube = offset.to_cube("even-r")

    # Convert back
    offset_again = cube.to_offset("even-r")

The offset system must match your map's configuration. Arcade picks the
matching system automatically from the map's ``staggeraxis`` and
``staggerindex`` values: ``y``/``odd`` is ``odd-r``, ``y``/``even`` is
``even-r``, ``x``/``odd`` is ``odd-q`` and ``x``/``even`` is ``even-q``.

Hex Layout
----------

A :class:`~arcade.hexagon.Layout` defines how hex coordinates map to pixel positions
on screen. It contains three pieces of information:

1. **Orientation** -- pointy-top or flat-top hexagons
2. **Size** -- the size of each hexagon in pixels
3. **Origin** -- the pixel position of hex (0, 0, 0)

.. code-block:: python

    from pyglet.math import Vec2
    from arcade.hexagon import Layout, pointy_orientation, flat_orientation

    # Pointy-top hexagons (what Tiled uses)
    layout = Layout(
        orientation=pointy_orientation,
        size=Vec2(40.0, 40.0),
        origin=Vec2(0.0, 0.0),
    )

.. note::

    Tiled uses pointy-top hexagons when the stagger axis is ``y`` and
    flat-top hexagons when it is ``x``. When loading a map through
    :func:`arcade.load_tilemap` you do not need to construct a
    :class:`~arcade.hexagon.Layout` at all; the orientation is derived from
    the map metadata.

Computing the Hex Size from Tiled
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``size`` in a Layout is **not** the same as the tile width/height in Tiled.
For pointy-top hexagons, the conversion is:

.. code-block:: python

    import math

    # From your Tiled map properties
    tile_width = 120   # tilewidth in the .tmj file
    tile_height = 140  # tileheight in the .tmj file

    hex_size_x = tile_width / math.sqrt(3)
    hex_size_y = tile_height / 2

    layout = Layout(
        orientation=pointy_orientation,
        size=Vec2(hex_size_x, hex_size_y),
        origin=Vec2(0, 0),
    )

These values come from the relationship between a hexagon's size and its bounding
rectangle. See the `Red Blob Games size reference
<https://www.redblobgames.com/grids/hexagons/#size-and-spacing>`_ for the full
derivation.

Loading a Hex Map from Tiled
-----------------------------

Hexagonal tilemaps load exactly like regular tilemaps. Arcade reads the
``orientation``, ``staggeraxis``, ``staggerindex`` and ``hexsidelength``
values saved in the Tiled file and positions every tile with Tiled's own
pixel formulas, so the four stagger combinations (two axes times odd/even)
all render the same way they do in the editor:

.. code-block:: python

    import arcade

    class GameView(arcade.View):

        def reset(self):
            # No extra layout argument is required: everything is derived
            # from the map metadata.
            self.tile_map = arcade.load_tilemap("my_hex_map.tmj")
            self.scene = arcade.Scene.from_tilemap(self.tile_map)
            self.background_color = arcade.color.BLACK

The ``scaling`` argument scales both the tile images *and* the hexagonal
spacing, so a map loaded with ``scaling=2.0`` keeps its tiles edge-to-edge
on high-resolution displays instead of overlapping.

For programmatic use outside of map loading, the geometry is exposed on the
loaded map and as a standalone class:

.. code-block:: python

    tile_map = arcade.load_tilemap("my_hex_map.tmj")
    geometry = tile_map.hex_geometry            # arcade.HexMapGeometry
    center_x, center_y = geometry.tile_center(column=3, row=2)

Everything else -- creating a Scene, drawing, using layers -- works the same as
with square tilemaps. See :ref:`platformer_part_twelve` for the general tilemap
loading tutorial.

Migrating from the old ``hex_layout`` argument
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Older Arcade versions ignored the map's stagger metadata and required a
manually constructed :class:`~arcade.hexagon.Layout` passed as
``hex_layout``. That parameter still works (it takes precedence and emits a
``DeprecationWarning``), but new code should omit it:

.. code-block:: python

    # Old (still works, deprecated):
    import math
    from pyglet.math import Vec2
    from arcade import hexagon

    hex_layout = hexagon.Layout(
        orientation=hexagon.pointy_orientation,
        size=Vec2(120 / math.sqrt(3), 140 / 2),
        origin=Vec2(0, 0),
    )
    tile_map = arcade.load_tilemap("my_hex_map.tmj", hex_layout=hex_layout)

    # New: the layout is derived from staggeraxis/staggerindex/hexsidelength.
    tile_map = arcade.load_tilemap("my_hex_map.tmj")

Because the old manual layout did not honor the map's stagger settings, an
existing project can look different after the switch. That means the new
rendering now matches Tiled; if you deliberately tuned assets to the old
positions, force the previous behavior while migrating:

.. code-block:: python

    tile_map = arcade.load_tilemap("my_hex_map.tmj", hex_map_mode="square")

``hex_map_mode`` accepts:

- ``"auto"`` (default): hexagonal maps use the metadata-driven Tiled
  formulas; other orientations keep their square grid.
- ``"square"``: hexagonal tiles are placed on a plain square grid, exactly
  like loading without ``hex_layout`` did previously.
- ``"hex"``: force hexagonal positioning; raises ``ValueError`` if the map
  is not hexagonal.

Rectangular (square-grid) maps and their tutorials are unaffected by any of
these settings.

Working with Hex Tiles in Code
-------------------------------

The :class:`~arcade.hexagon.HexTile` class provides several useful operations:

**Neighbors and Distance**

.. code-block:: python

    tile = HexTile(2, -1, -1)

    # Get all 6 neighbors
    neighbors = tile.neighbors()

    # Get a specific neighbor by direction (0-5)
    north = tile.neighbor(0)

    # Distance between two hexes
    dist = tile.distance_to(HexTile(0, 0, 0))  # 2

**Rotation**

.. code-block:: python

    tile = HexTile(1, -3, 2)

    rotated_right = tile.rotate_right()  # HexTile(3, -2, -1)
    rotated_left = tile.rotate_left()    # HexTile(-2, -1, 3)

**Line Drawing**

.. code-block:: python

    from arcade.hexagon import line

    # Get all hexes on a line between two points
    path = line(HexTile(0, 0, 0), HexTile(3, -3, 0))

**Pixel Conversion**

.. code-block:: python

    from arcade.hexagon import hextile_to_pixel, pixel_to_hextile

    # Convert a hex to pixel coordinates
    pixel_pos = hextile_to_pixel(tile, layout)

    # Convert a mouse click back to hex coordinates
    hex_tile = pixel_to_hextile(Vec2(mouse_x, mouse_y), layout)
    snapped = round(hex_tile)  # Round to nearest hex

Creating a Hex Map in Tiled
-----------------------------

To create your own hexagonal map in Tiled:

1. Open Tiled and select **File > New > New Map**
2. Set **Map Orientation** to ``Hexagonal``
3. Set **Tile Render Order** to ``Right Down``
4. Set **Stagger Axis** (``y`` for pointy-top rows, ``x`` for flat-top
   columns) and **Stagger Index** (``Odd`` or ``Even``). Arcade honors all
   four combinations, so pick whichever your art requires.
5. Set your desired **Tile Width** and **Tile Height**
6. Set the **Hex Side Length** (this controls how "tall" the flat edges are)
7. Create your tileset and start painting

Arcade reads all of these settings when the map is loaded, so unlike older
versions there is no manual layout math to keep in sync with the file.

Full Example
------------

For a complete working example with camera controls (panning and zooming), see
the built-in hex map example:

.. code-block:: bash

    python -m arcade.examples.hex_map

Source: ``arcade/examples/hex_map.py``
