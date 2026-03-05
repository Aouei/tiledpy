"""
Tileset loading and tile sprite extraction using Pillow.

Loads a spritesheet image, crops individual tiles on demand, and
converts them to ``pygame.Surface`` objects with a two-level cache:
one Pillow cache (PIL crop) and one pygame cache (Surface per flags).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    import pygame

# Flags de flip/rotate codificados en los GIDs de Tiled
GID_FLIP_H   = 0x80000000
GID_FLIP_V   = 0x40000000
GID_FLIP_D   = 0x20000000  # diagonal (rotacion 90)
GID_MASK     = 0x1FFFFFFF  # mascara para obtener el GID real


@dataclass
class TileFlags:
    """Flip and rotation flags decoded from a raw Tiled GID.

    Attributes
    ----------
    flip_h : bool
        Horizontal flip flag (GID bit ``0x80000000``).
    flip_v : bool
        Vertical flip flag (GID bit ``0x40000000``).
    flip_d : bool
        Diagonal flip flag (GID bit ``0x20000000``); used for 90°
        rotation when combined with ``flip_h`` or ``flip_v``.
    """

    flip_h: bool = False
    flip_v: bool = False
    flip_d: bool = False


def decode_gid(raw_gid: int) -> tuple[int, TileFlags]:
    """Separate the real GID from Tiled's flip/rotation flags.

    Tiled encodes flip and rotation by setting the three highest bits
    of the 32-bit GID. This function extracts those flags and returns
    the clean GID.

    Parameters
    ----------
    raw_gid : int
        Raw 32-bit GID as stored in a TileLayer (may include flag bits).

    Returns
    -------
    tuple[int, TileFlags]
        ``(real_gid, flags)`` where ``real_gid`` has the flag bits
        cleared and ``flags`` is a :class:`TileFlags` instance.

    Examples
    --------
    >>> real_gid, flags = decode_gid(0x80000005)
    >>> real_gid
    5
    >>> flags.flip_h
    True
    """
    flags = TileFlags(
        flip_h=bool(raw_gid & GID_FLIP_H),
        flip_v=bool(raw_gid & GID_FLIP_V),
        flip_d=bool(raw_gid & GID_FLIP_D),
    )
    return raw_gid & GID_MASK, flags


@dataclass
class TileData:
    """Per-tile metadata parsed from a TSX ``<tile>`` element.

    Attributes
    ----------
    local_id : int
        Zero-based local tile ID within the tileset.
    properties : dict
        Custom properties defined in Tiled for this tile.
    collision_objects : list[dict]
        Collision rectangles, each with keys ``x``, ``y``,
        ``width``, and ``height`` (in pixels).
    animation : list[dict]
        Animation frames, each with keys ``tileid`` (int) and
        ``duration`` (int, milliseconds).
    """

    local_id: int
    properties: dict = field(default_factory=dict)
    collision_objects: list[dict] = field(default_factory=list)
    animation: list[dict] = field(default_factory=list)


class Tileset:
    """A tileset backed by a spritesheet image.

    Uses Pillow to crop individual tile images from the sheet and
    converts them to ``pygame.Surface`` objects on demand. Results are
    cached at both the Pillow level (raw crop) and the pygame level
    (surface per flip/rotation flags).

    Parameters
    ----------
    name : str
        Tileset name as declared in the TMX/TSX.
    firstgid : int
        First global tile ID assigned to this tileset.
    image_path : str
        Absolute path to the spritesheet image file.
    tile_width : int
        Width of each tile in pixels.
    tile_height : int
        Height of each tile in pixels.
    columns : int
        Number of tile columns in the spritesheet.
    tilecount : int
        Total number of tiles in the tileset.
    spacing : int, optional
        Pixels between adjacent tiles, by default ``0``.
    margin : int, optional
        Pixels around the outer edge of the sheet, by default ``0``.
    tile_data : dict[int, TileData] or None, optional
        Per-tile metadata keyed by local ID, by default ``None``.
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
        tile_data: dict[int, TileData] | None = None,
    ) -> None:
        self.name        = name
        self.firstgid    = firstgid
        self.tile_width  = tile_width
        self.tile_height = tile_height
        self.columns     = columns
        self.tilecount   = tilecount
        self.spacing     = spacing
        self.margin      = margin
        self.tile_data   = tile_data or {}

        # Imagen completa del spritesheet cargada con Pillow
        self._sheet: Image.Image = Image.open(image_path).convert("RGBA")

        # Cache: local_id -> PIL.Image (recorte sin transformar)
        self._pil_cache: dict[int, Image.Image] = {}

        # Cache: (local_id, flip_h, flip_v, flip_d) -> pygame.Surface
        self._pygame_cache: dict[tuple, "pygame.Surface"] = {}

    # ------------------------------------------------------------------
    # Pillow: deteccion y recorte de sprites
    # ------------------------------------------------------------------

    def get_tile_image(self, local_id: int) -> Image.Image:
        """Return the RGBA PIL crop of the tile at ``local_id``.

        The result is cached in an internal PIL cache — subsequent
        calls for the same ``local_id`` are free.

        Parameters
        ----------
        local_id : int
            Zero-based local tile index within the tileset.

        Returns
        -------
        PIL.Image.Image
            RGBA image of the tile.
        """
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
        """Return ``True`` if the tile is fully transparent.

        Checks whether the maximum alpha value across all pixels is 0.

        Parameters
        ----------
        local_id : int
            Zero-based local tile index.

        Returns
        -------
        bool
            ``True`` if every pixel has alpha = 0.
        """
        img = self.get_tile_image(local_id)
        r, g, b, a = img.split()
        return a.getextrema()[1] == 0

    def get_dominant_color(self, local_id: int) -> tuple[int, int, int]:
        """Return the average RGB color of all non-transparent pixels.

        Parameters
        ----------
        local_id : int
            Zero-based local tile index.

        Returns
        -------
        tuple[int, int, int]
            ``(r, g, b)`` average color. Returns ``(0, 0, 0)`` if the
            tile has no non-transparent pixels.
        """
        img = self.get_tile_image(local_id).convert("RGBA")
        pixels = [
            px[:3]
            for px in img.getdata()
            if px[3] > 0
        ]
        if not pixels:
            return (0, 0, 0)
        r = sum(p[0] for p in pixels) // len(pixels)
        g = sum(p[1] for p in pixels) // len(pixels)
        b = sum(p[2] for p in pixels) // len(pixels)
        return (r, g, b)

    # ------------------------------------------------------------------
    # Pygame: conversion con cache
    # ------------------------------------------------------------------

    def get_pygame_surface(
        self,
        local_id: int,
        flags: TileFlags | None = None,
    ) -> "pygame.Surface":
        """Return a pygame.Surface for the given tile with flip/rotation applied.

        The surface is cached by ``(local_id, flip_h, flip_v, flip_d)``
        — subsequent calls for the same combination are instant dict
        lookups.

        Parameters
        ----------
        local_id : int
            Zero-based local tile index.
        flags : TileFlags or None, optional
            Flip/rotation flags to apply, by default no transforms.

        Returns
        -------
        pygame.Surface
            Tile surface with ``convert_alpha()`` applied and the
            requested transformations.
        """
        import pygame  # import tardio para no requerir pygame en contextos solo-Pillow

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

        # Aplicar transformaciones de flip/rotacion
        if flags.flip_d:
            img = img.transpose(Image.TRANSPOSE)
        if flags.flip_h:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if flags.flip_v:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

        raw = img.tobytes()
        surface = pygame_module.image.fromstring(raw, img.size, "RGBA").convert_alpha()
        return surface

    def clear_pygame_cache(self) -> None:
        """Clear the per-instance pygame surface cache.

        Call this after resizing the window or changing the scale
        factor to force surfaces to be rebuilt at the new resolution.
        """
        self._pygame_cache.clear()

    def contains_gid(self, gid: int) -> bool:
        """Return ``True`` if the global GID belongs to this tileset.

        Parameters
        ----------
        gid : int
            Global tile ID to test.

        Returns
        -------
        bool
            ``True`` if ``firstgid <= gid < firstgid + tilecount``.
        """
        return self.firstgid <= gid < self.firstgid + self.tilecount

    def global_to_local(self, gid: int) -> int:
        """Convert a global GID to a local (0-based) tile ID.

        Parameters
        ----------
        gid : int
            Global tile ID.

        Returns
        -------
        int
            Local tile index: ``gid - firstgid``.
        """
        return gid - self.firstgid

    def __repr__(self) -> str:
        return (
            f"Tileset(name={self.name!r}, firstgid={self.firstgid}, "
            f"tilecount={self.tilecount}, size={self.tile_width}x{self.tile_height})"
        )
