"""
tiledpy — Tiled map loader for Pygame.

Quick start
-----------
>>> from tiledpy import Parser
>>> import tiledpy.map.render as render
>>>
>>> tmap = Parser.load("map.tmx")          # or .tmj / .json
>>>
>>> # In the game loop:
>>> render.draw_all_layers(screen, tmap, offset=(cam_x, cam_y), scale=2)
>>>
>>> # Access tiles in a layer:
>>> for tile in tmap.get_layer("ground").iter_tiles():
...     surf = tile.get_surface(scale=2)
...     surf = tile.get_animated_surface(elapsed_ms, scale=2)
>>>
>>> # Access objects:
>>> for enemy in tmap.get_layer("entities").get_objects_by_class("enemy"):
...     w = enemy.width(scale=2)
...     h = enemy.height(scale=2)

Public API
----------
Parser          Load a map file → TileMap
TileMap         Parsed map: tilesets + layers
TileLayer       Tile layer — iterate as TileData
TileData        Single placed tile with get_surface() / get_animated_surface()
ObjectLayer     Object layer — list of TileObject
TileObject      Single object with width(scale) / height(scale)
Tileset         Spritesheet manager
OFFSET          Nine-point anchor enum for coordinate conversion
"""

from .map.map    import TileMap, OFFSET
from .map.parser import Parser
from .map        import render

from .layer.tile    import TileData, TileLayer
from .layer.object  import TileObject, ObjectLayer
from .layer.tileset import Tileset, TileMeta, TileFlags, decode_gid

__all__ = [
    # Map
    "TileMap", "OFFSET", "Parser", "render",
    # Layer
    "TileData", "TileLayer",
    "TileObject", "ObjectLayer",
    # Tileset
    "Tileset", "TileMeta", "TileFlags", "decode_gid",
]

__version__ = "0.2.0"
