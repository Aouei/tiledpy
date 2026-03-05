"""
tileset.py
Carga y cachea tiles de un spritesheet usando Pillow.
Convierte tiles a pygame.Surface bajo demanda con cache integrado.
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
    flip_h: bool = False
    flip_v: bool = False
    flip_d: bool = False


def decode_gid(raw_gid: int) -> tuple[int, TileFlags]:
    """Separa el GID real de sus flags de transformacion."""
    flags = TileFlags(
        flip_h=bool(raw_gid & GID_FLIP_H),
        flip_v=bool(raw_gid & GID_FLIP_V),
        flip_d=bool(raw_gid & GID_FLIP_D),
    )
    return raw_gid & GID_MASK, flags


@dataclass
class TileData:
    """Propiedades opcionales de un tile individual (del TSX)."""
    local_id: int
    properties: dict = field(default_factory=dict)
    collision_objects: list[dict] = field(default_factory=list)
    animation: list[dict] = field(default_factory=list)


class Tileset:
    """
    Representa un tileset cargado desde un spritesheet.

    Usa Pillow internamente para recortar los sprites y los convierte
    a pygame.Surface de forma lazy con cache por (local_id, flags).
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
        """Devuelve la imagen PIL del tile (recortada del spritesheet)."""
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
        """Devuelve True si el tile es completamente transparente (alpha=0 en todos los px)."""
        img = self.get_tile_image(local_id)
        r, g, b, a = img.split()
        return a.getextrema()[1] == 0

    def get_dominant_color(self, local_id: int) -> tuple[int, int, int]:
        """Devuelve el color dominante del tile (ignora pixels transparentes)."""
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
        """
        Devuelve un pygame.Surface para el tile dado.
        La superficie se cachea por (local_id, flip_h, flip_v, flip_d).
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
        self._pygame_cache.clear()

    def contains_gid(self, gid: int) -> bool:
        return self.firstgid <= gid < self.firstgid + self.tilecount

    def global_to_local(self, gid: int) -> int:
        return gid - self.firstgid

    def __repr__(self) -> str:
        return (
            f"Tileset(name={self.name!r}, firstgid={self.firstgid}, "
            f"tilecount={self.tilecount}, size={self.tile_width}x{self.tile_height})"
        )
