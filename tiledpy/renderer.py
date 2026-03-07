"""
Pygame rendering functions for TileLayer with module-level surface caches.

The surface caches are global to the module and persist across frames.
Call :func:`clear_surface_cache` when loading a new map or changing
the scale factor.

Caches
------
_surface_cache
    ``(firstgid, local_id, flip_h, flip_v, flip_d) -> pygame.Surface``
_scaled_cache
    ``(id(surf), width, height) -> pygame.Surface``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .layer import TileLayer
from .tileset import Tileset, TileFlags, decode_gid

if TYPE_CHECKING:
    import pygame

# Cache global: (firstgid, local_id, flip_h, flip_v, flip_d) -> pygame.Surface
_surface_cache: dict[tuple, "pygame.Surface"] = {}


def get_cached_surface(
    gid: int,
    tilesets: list[Tileset],
) -> "pygame.Surface | None":
    """Return the ``pygame.Surface`` for the given raw global tile ID.

    Decodes flip flags from the raw GID, locates the owning tileset,
    and returns a cached surface. Creates and caches the surface on the
    first call for each unique ``(tileset, local_id, flags)``
    combination.

    Parameters
    ----------
    gid : int
        Raw GID value as stored in a TileLayer (may include flip flags).
    tilesets : list[Tileset]
        All tilesets for the map, sorted by ``firstgid`` ascending.

    Returns
    -------
    pygame.Surface or None
        The tile surface with ``convert_alpha`` applied, or ``None``
        if the GID is 0 (empty tile) or not found in any tileset.
    """
    real_gid, flags = decode_gid(gid)
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


def draw_layer(
    surface,
    layer: TileLayer,
    tilesets: list[Tileset],
    tile_width: int,
    tile_height: int,
    offset: tuple[int, int] = (0, 0),
    scale: int = 1,
) -> None:
    """Render a TileLayer onto a ``pygame.Surface``.

    Iterates non-empty tiles, applies viewport culling, fetches cached
    surfaces, and blits each tile. If ``layer.opacity < 1.0`` a surface
    copy with ``set_alpha()`` is used — one allocation per blit, so
    keep opacity at ``1.0`` for performance-critical layers.

    Parameters
    ----------
    surface : pygame.Surface
        Render target.
    layer : TileLayer
        The tile layer to draw.
    tilesets : list[Tileset]
        All tilesets of the map, sorted by ``firstgid`` ascending.
    tile_width : int
        Base tile width in pixels (from the map).
    tile_height : int
        Base tile height in pixels (from the map).
    offset : tuple[int, int], optional
        Camera offset ``(ox, oy)`` in pixels, by default ``(0, 0)``.
    scale : int, optional
        Integer scale factor for pixel-art rendering, by default ``1``.
    """

    ox, oy        = offset
    scaled_tw     = tile_width  * scale
    scaled_th     = tile_height * scale
    surf_w        = surface.get_width()
    surf_h        = surface.get_height()

    for tx, ty, raw_gid in layer.iter_tiles():
        tile_surf = get_cached_surface(raw_gid, tilesets)
        if tile_surf is None:
            continue

        actual_w = tile_surf.get_width()  * scale
        actual_h = tile_surf.get_height() * scale

        px = tx * scaled_tw - ox + int(layer.offset_x * scale)
        # Anclar por la base de la celda (igual que Tiled con tiles grandes)
        py = ty * scaled_th - oy + int(layer.offset_y * scale) + scaled_th - actual_h

        # Culling: no dibujar tiles fuera de pantalla
        if px + actual_w < 0 or px > surf_w:
            continue
        if py + actual_h < 0 or py > surf_h:
            continue

        if scale != 1:
            tile_surf = _get_scaled_surface(tile_surf, actual_w, actual_h)

        if layer.opacity < 1.0:
            tile_surf = tile_surf.copy()
            tile_surf.set_alpha(int(layer.opacity * 255))

        surface.blit(tile_surf, (px, py))


# Cache secundario para superficies escaladas
_scaled_cache: dict[tuple, "pygame.Surface"] = {}


def _get_scaled_surface(
    surf: "pygame.Surface",
    w: int,
    h: int,
) -> "pygame.Surface":
    """Return a scaled copy of a surface, creating and caching it if needed.

    Parameters
    ----------
    surf : pygame.Surface
        Source surface to scale.
    w : int
        Target width in pixels.
    h : int
        Target height in pixels.

    Returns
    -------
    pygame.Surface
        Scaled surface, cached by ``(id(surf), w, h)``.
    """
    key = (id(surf), w, h)
    if key not in _scaled_cache:
        import pygame
        _scaled_cache[key] = pygame.transform.scale(surf, (w, h))
    return _scaled_cache[key]


def _find_tileset(gid: int, tilesets: list[Tileset]) -> Tileset | None:
    """Find the tileset that owns the given GID using binary search.

    Parameters
    ----------
    gid : int
        Real GID (without flip flags).
    tilesets : list[Tileset]
        All tilesets sorted by ``firstgid`` ascending.

    Returns
    -------
    Tileset or None
        The tileset whose ``firstgid`` is the largest value ``<= gid``,
        or ``None`` if no tileset qualifies.
    """
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


def clear_surface_cache() -> None:
    """Clear both global pygame surface caches.

    Call this when:

    - Loading a completely different map.
    - Changing the scale factor at runtime.
    - Freeing memory.

    Notes
    -----
    The next call to :func:`draw_layer` will rebuild both caches from
    scratch, which may cause a brief stutter on large maps.
    """
    _surface_cache.clear()
    _scaled_cache.clear()


def cache_stats() -> dict:
    """Return current entry counts for both surface caches.

    Returns
    -------
    dict
        Dictionary with keys ``"tile_surfaces"`` and
        ``"scaled_surfaces"``, each mapping to an integer count.

    Examples
    --------
    >>> if frame % 300 == 0:
    ...     print(cache_stats())
    {'tile_surfaces': 47, 'scaled_surfaces': 0}
    """
    return {
        "tile_surfaces": len(_surface_cache),
        "scaled_surfaces": len(_scaled_cache),
    }
