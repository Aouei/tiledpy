"""
map/render.py — Pygame rendering functions for TileMap layers.

Module-level surface caches persist across frames. Call
:func:`clear_cache` when loading a new map or changing the scale factor.

Functions
---------
draw_layer(surface, layer, tile_width, tile_height, offset, scale)
    Render a single TileLayer.
draw_all_layers(surface, tilemap, offset, scale)
    Render all visible TileLayer instances in order.
clear_cache()
    Clear both surface caches.
cache_stats() -> dict
    Return current cache entry counts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tiledpy.layer.tile import TileLayer
from tiledpy.layer.tileset import Tileset, TileFlags, decode_gid

if TYPE_CHECKING:
    import pygame
    from tiledpy.map.map import TileMap

# Cache: (firstgid, local_id, flip_h, flip_v, flip_d) -> pygame.Surface
_surface_cache: dict[tuple, "pygame.Surface"] = {}

# Cache: (id(surf), width, height) -> pygame.Surface
_scaled_cache: dict[tuple, "pygame.Surface"] = {}


def draw_layer(
    surface: "pygame.Surface",
    layer: TileLayer,
    tile_width: int,
    tile_height: int,
    offset: tuple[int, int] = (0, 0),
    scale: float = 1.0,
) -> None:
    """Render a TileLayer onto a ``pygame.Surface``.

    Applies viewport culling — tiles entirely outside the surface are
    skipped. If ``layer.opacity < 1.0`` a per-blit surface copy is
    used (one allocation per visible tile), so keep opacity at 1.0 for
    performance-critical layers.

    Parameters
    ----------
    surface : pygame.Surface
        Render target.
    layer : TileLayer
        The tile layer to draw.
    tile_width : int
        Base tile width in pixels (from the map).
    tile_height : int
        Base tile height in pixels (from the map).
    offset : tuple[int, int], optional
        Camera offset ``(ox, oy)`` in pixels, by default ``(0, 0)``.
    scale : float, optional
        Render scale factor, by default 1.0.
    """
    ox, oy    = offset
    scaled_tw = int(tile_width  * scale)
    scaled_th = int(tile_height * scale)
    surf_w    = surface.get_width()
    surf_h    = surface.get_height()

    for (tx, ty), raw_gid in layer._data.items():
        tile_surf = _get_cached_surface(raw_gid, layer._tilesets)
        if tile_surf is None:
            continue

        actual_w = int(tile_surf.get_width()  * scale)
        actual_h = int(tile_surf.get_height() * scale)

        px = tx * scaled_tw - ox + int(layer.offset_x * scale)
        # Anchor to the bottom of the cell (matches Tiled behaviour for tall sprites)
        py = ty * scaled_th - oy + int(layer.offset_y * scale) + scaled_th - actual_h

        # Viewport culling
        if px + actual_w < 0 or px > surf_w:
            continue
        if py + actual_h < 0 or py > surf_h:
            continue

        if scale != 1.0:
            tile_surf = _get_scaled(tile_surf, actual_w, actual_h)

        if layer.opacity < 1.0:
            tile_surf = tile_surf.copy()
            tile_surf.set_alpha(int(layer.opacity * 255))

        surface.blit(tile_surf, (px, py))


def draw_all_layers(
    surface: "pygame.Surface",
    tilemap: "TileMap",
    offset: tuple[int, int] = (0, 0),
    scale: float = 1.0,
) -> None:
    """Render all visible TileLayer instances in draw order.

    Parameters
    ----------
    surface : pygame.Surface
        Render target.
    tilemap : TileMap
        The map to render.
    offset : tuple[int, int], optional
        Camera offset ``(ox, oy)`` in pixels.
    scale : float, optional
        Render scale factor.
    """
    for layer in tilemap.layers:
        if isinstance(layer, TileLayer) and layer.visible:
            draw_layer(
                surface, layer,
                tilemap.tile_width, tilemap.tile_height,
                offset=offset, scale=scale,
            )


def clear_cache() -> None:
    """Clear both global pygame surface caches.

    Call after loading a new map or changing the scale factor.
    """
    _surface_cache.clear()
    _scaled_cache.clear()


def cache_stats() -> dict:
    """Return current entry counts for both surface caches.

    Returns
    -------
    dict
        ``{"tile_surfaces": int, "scaled_surfaces": int}``
    """
    return {
        "tile_surfaces":   len(_surface_cache),
        "scaled_surfaces": len(_scaled_cache),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_cached_surface(
    raw_gid: int,
    tilesets: list[Tileset],
) -> "pygame.Surface | None":
    real_gid, flags = decode_gid(raw_gid)
    if real_gid == 0:
        return None
    tileset = _find_tileset(real_gid, tilesets)
    if tileset is None:
        return None
    local_id  = tileset.global_to_local(real_gid)
    cache_key = (tileset.firstgid, local_id, flags.flip_h, flags.flip_v, flags.flip_d)
    if cache_key not in _surface_cache:
        _surface_cache[cache_key] = tileset.get_pygame_surface(local_id, flags)
    return _surface_cache[cache_key]


def _find_tileset(gid: int, tilesets: list[Tileset]) -> Tileset | None:
    """Binary search for the tileset that owns *gid*."""
    lo, hi = 0, len(tilesets) - 1
    result = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if tilesets[mid].firstgid <= gid:
            result = tilesets[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return result


def _get_scaled(
    surf: "pygame.Surface",
    w: int,
    h: int,
) -> "pygame.Surface":
    key = (id(surf), w, h)
    if key not in _scaled_cache:
        import pygame
        _scaled_cache[key] = pygame.transform.scale(surf, (w, h))
    return _scaled_cache[key]
