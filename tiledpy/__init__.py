"""
tiledpy — TMX map loader for Pygame.

A lightweight library that parses Tiled ``.tmx`` map files, loads
tilesets with Pillow, and renders tile layers with Pygame.

Classes
-------
TiledMap
    Main entry point: parses a ``.tmx`` file and exposes layers,
    tilesets, and rendering helpers.
TileLayer
    Sparse tile layer with GID storage and iteration.
ObjectLayer
    Object layer containing a list of :class:`TileObject` items.
TileObject
    A single object (spawn point, zone, trigger, etc.) from an
    ``ObjectLayer``.
Tileset
    Spritesheet-backed tileset with PIL and pygame surface caches.

Examples
--------
>>> from tiledpy import TiledMap
>>> tmap = TiledMap("map.tmx")
>>> tmap.draw_layer(screen, "ground", offset=(cam_x, cam_y))
"""

from .loader import TiledMap
from .layer import TileLayer, ObjectLayer, TileObject
from .tileset import Tileset

__all__ = ["TiledMap", "TileLayer", "ObjectLayer", "TileObject", "Tileset"]
__version__ = "0.1.0"
