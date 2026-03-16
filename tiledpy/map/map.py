"""
map/map.py — TileMap data model and OFFSET coordinate enum.

TileMap holds the parsed state of a Tiled map: dimensions, tilesets,
and layers. It does NOT parse files (see parser.py) nor render
(see render.py). Its only responsibility is the data model and
coordinate conversion helpers.
"""

from __future__ import annotations

from enum import Enum
from typing import Union

from tiledpy.layer.tile import TileLayer
from tiledpy.layer.object import ObjectLayer
from tiledpy.layer.tileset import Tileset

LayerType = Union[TileLayer, ObjectLayer]


class OFFSET(Enum):
    """Nine anchor points for coordinate conversion helpers."""
    LEFT_TOP      = (0,   0)
    MIDDLE_TOP    = (0.5, 0)
    RIGHT_TOP     = (1,   0)
    LEFT_MIDDLE   = (0,   0.5)
    CENTER        = (0.5, 0.5)
    RIGHT_MIDDLE  = (1,   0.5)
    LEFT_BOTTOM   = (0,   1)
    MIDDLE_BOTTOM = (0.5, 1)
    RIGHT_BOTTOM  = (1,   1)


class TileMap:
    """A parsed Tiled map.

    Contains all tilesets and layers. Use :class:`~tiledpy.map.parser.Parser`
    to construct an instance from a file.

    Attributes
    ----------
    width : int
        Map width in tiles.
    height : int
        Map height in tiles.
    tile_width : int
        Tile width in pixels.
    tile_height : int
        Tile height in pixels.
    orientation : str
        Map orientation (e.g. ``"orthogonal"``).
    infinite : bool
        True if the map uses chunk-based infinite scrolling.
    background_color : str or None
        Hex background color ``"#rrggbb"``, or None.
    properties : dict
        Custom map-level properties.
    tilesets : list[Tileset]
        All tilesets sorted by ``firstgid`` ascending.
    layers : list[TileLayer | ObjectLayer]
        All layers in draw order.
    """

    def __init__(self) -> None:
        self.width:            int = 0
        self.height:           int = 0
        self.tile_width:       int = 16
        self.tile_height:      int = 16
        self.orientation:      str = "orthogonal"
        self.render_order:     str = "right-down"
        self.infinite:         bool = False
        self.background_color: str | None = None
        self.properties:       dict = {}
        self.tilesets:         list[Tileset] = []
        self.layers:           list[LayerType] = []

    # ------------------------------------------------------------------
    # Layer access
    # ------------------------------------------------------------------

    def get_layer(self, name: str) -> LayerType | None:
        """Return the first layer whose name matches, or None."""
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_tile_layers(self) -> list[TileLayer]:
        """Return all TileLayer instances in draw order."""
        return [l for l in self.layers if isinstance(l, TileLayer)]

    def get_object_layers(self) -> list[ObjectLayer]:
        """Return all ObjectLayer instances in draw order."""
        return [l for l in self.layers if isinstance(l, ObjectLayer)]

    # ------------------------------------------------------------------
    # Coordinate conversion
    # ------------------------------------------------------------------

    def world_to_tile(
        self,
        x: float,
        y: float,
        scale: float = 1.0,
        offset: OFFSET = OFFSET.LEFT_TOP,
    ) -> tuple[int, int]:
        """Convert world pixel coordinates to tile coordinates.

        Parameters
        ----------
        x, y : float
            World position in pixels.
        scale : float
            Current render scale factor.
        offset : OFFSET
            Anchor point adjustment, by default LEFT_TOP.

        Returns
        -------
        tuple[int, int]
            ``(tx, ty)`` tile coordinates (floor division).
        """
        off_x, off_y = offset.value
        tw = self.tile_width  * scale
        th = self.tile_height * scale
        return int(x // tw) + int(off_x), int(y // th) + int(off_y)

    def tile_to_world(
        self,
        tx: int,
        ty: int,
        scale: float = 1.0,
        offset: OFFSET = OFFSET.LEFT_TOP,
    ) -> tuple[float, float]:
        """Convert tile coordinates to world pixel coordinates (top-left).

        Parameters
        ----------
        tx, ty : int
            Tile coordinates.
        scale : float
            Current render scale factor.
        offset : OFFSET
            Anchor point adjustment, by default LEFT_TOP.

        Returns
        -------
        tuple[float, float]
            ``(x, y)`` world position in pixels.
        """
        off_x, off_y = offset.value
        return (
            (tx + off_x) * self.tile_width  * scale,
            (ty + off_y) * self.tile_height * scale,
        )

    def __repr__(self) -> str:
        return (
            f"TileMap({self.width}x{self.height}, "
            f"layers={[l.name for l in self.layers]})"
        )
