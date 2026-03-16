"""
layer/tileset.py — Tileset loading and tile sprite extraction.

Classes
-------
TileFlags
    Flip/rotation flags decoded from a raw Tiled GID.
TileMeta
    Per-tile metadata parsed from a TSX <tile> element
    (class, properties, collision objects, animation frames).
Tileset
    Spritesheet-backed tileset with PIL and pygame surface caches.

Functions
---------
decode_gid(raw_gid) -> (int, TileFlags)
    Separate the real GID from Tiled's flip/rotation flag bits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    import pygame

# Flip/rotation flags encoded in the upper 3 bits of a Tiled GID
GID_FLIP_H = 0x80000000
GID_FLIP_V = 0x40000000
GID_FLIP_D = 0x20000000   # diagonal — used for 90° rotation
GID_MASK   = 0x1FFFFFFF   # mask for the real GID


@dataclass
class TileFlags:
    """Flip and rotation flags decoded from a raw Tiled GID."""

    flip_h: bool = False
    flip_v: bool = False
    flip_d: bool = False


def decode_gid(raw_gid: int) -> tuple[int, TileFlags]:
    """Separate the real GID from Tiled's flip/rotation flags.

    Parameters
    ----------
    raw_gid : int
        Raw 32-bit GID as stored in a TileLayer.

    Returns
    -------
    tuple[int, TileFlags]
        ``(real_gid, flags)`` with flag bits cleared from real_gid.
    """
    flags = TileFlags(
        flip_h=bool(raw_gid & GID_FLIP_H),
        flip_v=bool(raw_gid & GID_FLIP_V),
        flip_d=bool(raw_gid & GID_FLIP_D),
    )
    return raw_gid & GID_MASK, flags


@dataclass
class TileMeta:
    """Per-tile metadata from a TSX ``<tile>`` element.

    Attributes
    ----------
    local_id : int
        Zero-based local tile ID within the tileset.
    tile_class : str
        Tiled ``class`` attribute (``type`` in older versions).
    properties : dict
        Custom properties defined in Tiled.
    collision_objects : list[dict]
        Collision rectangles: ``[{x, y, width, height}, ...]``.
    animation : list[dict]
        Animation frames: ``[{tileid, duration}, ...]`` (duration in ms).
    width : int or None
        Tile width in pixels (None = use tileset default).
    height : int or None
        Tile height in pixels (None = use tileset default).
    """

    local_id: int
    tile_class: str = ""
    properties: dict = field(default_factory=dict)
    collision_objects: list[dict] = field(default_factory=list)
    animation: list[dict] = field(default_factory=list)
    width: int | None = None
    height: int | None = None


class Tileset:
    """A tileset backed by a spritesheet image.

    Crops individual tiles from the sheet using Pillow and converts them
    to ``pygame.Surface`` objects on demand. Results are cached at both
    the PIL level (raw crop) and the pygame level (surface per flags).

    Parameters
    ----------
    name : str
        Tileset name as declared in TMX/TSX.
    firstgid : int
        First global tile ID assigned to this tileset.
    image_path : str
        Absolute path to the spritesheet image.
    tile_width : int
        Width of each tile in pixels.
    tile_height : int
        Height of each tile in pixels.
    columns : int
        Number of tile columns in the spritesheet.
    tilecount : int
        Total number of tiles.
    spacing : int, optional
        Pixels between adjacent tiles, by default 0.
    margin : int, optional
        Pixels around the outer edge of the sheet, by default 0.
    tile_data : dict[int, TileMeta] or None, optional
        Per-tile metadata keyed by local ID.
    """

    def __init__(
        self,
        name: str,
        firstgid: int,
        image_path: str,
        tile_width: int,
        tile_height: int,
        columns: int,
        tilecount: int,
        spacing: int = 0,
        margin: int = 0,
        tile_data: dict[int, TileMeta] | None = None,
    ) -> None:
        self.name        = name
        self.firstgid    = firstgid
        self.tile_width  = tile_width
        self.tile_height = tile_height
        self.columns     = columns
        self.tilecount   = tilecount
        self.spacing     = spacing
        self.margin      = margin
        self.tile_data: dict[int, TileMeta] = tile_data or {}

        self._sheet: Image.Image = Image.open(image_path).convert("RGBA")
        self._pil_cache:    dict[int, Image.Image]       = {}
        self._pygame_cache: dict[tuple, "pygame.Surface"] = {}

    # ------------------------------------------------------------------
    # PIL: crop and analysis
    # ------------------------------------------------------------------

    def get_tile_image(self, local_id: int) -> Image.Image:
        """Return the RGBA PIL crop of the tile. Result is cached."""
        if local_id not in self._pil_cache:
            self._pil_cache[local_id] = self._crop_tile(local_id)
        return self._pil_cache[local_id]

    def _crop_tile(self, local_id: int) -> Image.Image:
        col = local_id % self.columns
        row = local_id // self.columns
        x = self.margin + col * (self.tile_width  + self.spacing)
        y = self.margin + row * (self.tile_height + self.spacing)
        return self._sheet.crop((x, y, x + self.tile_width, y + self.tile_height))

    def is_empty_tile(self, local_id: int) -> bool:
        """Return ``True`` if every pixel of the tile is fully transparent."""
        img = self.get_tile_image(local_id)
        _, _, _, a = img.split()
        return a.getextrema()[1] == 0

    def get_dominant_color(self, local_id: int) -> tuple[int, int, int]:
        """Return the average RGB of all non-transparent pixels."""
        img = self.get_tile_image(local_id).convert("RGBA")
        pixels = [px[:3] for px in img.getdata() if px[3] > 0]
        if not pixels:
            return (0, 0, 0)
        r = sum(p[0] for p in pixels) // len(pixels)
        g = sum(p[1] for p in pixels) // len(pixels)
        b = sum(p[2] for p in pixels) // len(pixels)
        return (r, g, b)

    # ------------------------------------------------------------------
    # Pygame: surface with caching
    # ------------------------------------------------------------------

    def get_pygame_surface(
        self,
        local_id: int,
        flags: TileFlags | None = None,
    ) -> "pygame.Surface":
        """Return a ``pygame.Surface`` for the tile with flip/rotation applied.

        Cached by ``(local_id, flip_h, flip_v, flip_d)``.
        """
        import pygame

        if flags is None:
            flags = TileFlags()

        cache_key = (local_id, flags.flip_h, flags.flip_v, flags.flip_d)
        if cache_key not in self._pygame_cache:
            self._pygame_cache[cache_key] = self._build_surface(local_id, flags, pygame)
        return self._pygame_cache[cache_key]

    def _build_surface(
        self,
        local_id: int,
        flags: TileFlags,
        pygame_module,
    ) -> "pygame.Surface":
        img = self.get_tile_image(local_id)
        if flags.flip_d:
            img = img.transpose(Image.TRANSPOSE)
        if flags.flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if flags.flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        raw = img.tobytes()
        return pygame_module.image.fromstring(raw, img.size, "RGBA").convert_alpha()

    def clear_pygame_cache(self) -> None:
        """Clear the pygame surface cache (call after scale changes)."""
        self._pygame_cache.clear()

    # ------------------------------------------------------------------
    # GID helpers
    # ------------------------------------------------------------------

    def contains_gid(self, gid: int) -> bool:
        """Return ``True`` if the global GID belongs to this tileset."""
        return self.firstgid <= gid < self.firstgid + self.tilecount

    def global_to_local(self, gid: int) -> int:
        """Convert a global GID to a local (0-based) tile ID."""
        return gid - self.firstgid

    def __repr__(self) -> str:
        return (
            f"Tileset(name={self.name!r}, firstgid={self.firstgid}, "
            f"tilecount={self.tilecount}, size={self.tile_width}x{self.tile_height})"
        )
