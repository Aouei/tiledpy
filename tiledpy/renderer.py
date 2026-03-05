"""
renderer.py
Funciones de renderizado para pygame con cache de superficies.

El cache de superficies es global al modulo para sobrevivir entre frames.
Se puede limpiar con clear_surface_cache() al cambiar de mapa o tileset.
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
    """
    Devuelve el pygame.Surface correspondiente al GID global.
    Busca el tileset correcto, decodifica flags y cachea el resultado.
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
    """
    Dibuja una TileLayer sobre un pygame.Surface.

    Args:
        surface:     pygame.Surface destino.
        layer:       TileLayer a renderizar.
        tilesets:    Lista de Tileset del mapa (ordenados por firstgid).
        tile_width:  Ancho de tile en pixeles del mapa.
        tile_height: Alto de tile en pixeles del mapa.
        offset:      Desplazamiento de camara (ox, oy) en pixeles.
        scale:       Factor de escala entero para pixel-art.
    """
    import pygame

    ox, oy        = offset
    scaled_tw     = tile_width  * scale
    scaled_th     = tile_height * scale
    surf_w        = surface.get_width()
    surf_h        = surface.get_height()

    for tx, ty, raw_gid in layer.iter_tiles():
        px = tx * scaled_tw - ox + int(layer.offset_x * scale)
        py = ty * scaled_th - oy + int(layer.offset_y * scale)

        # Culling: no dibujar tiles fuera de pantalla
        if px + scaled_tw < 0 or px > surf_w:
            continue
        if py + scaled_th < 0 or py > surf_h:
            continue

        tile_surf = get_cached_surface(raw_gid, tilesets)
        if tile_surf is None:
            continue

        if scale != 1:
            tile_surf = _get_scaled_surface(tile_surf, scaled_tw, scaled_th)

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
    """Cache de superficies escaladas para no re-escalar en cada frame."""
    key = (id(surf), w, h)
    if key not in _scaled_cache:
        import pygame
        _scaled_cache[key] = pygame.transform.scale(surf, (w, h))
    return _scaled_cache[key]


def _find_tileset(gid: int, tilesets: list[Tileset]) -> Tileset | None:
    """Busqueda binaria del tileset al que pertenece el GID."""
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
    """Limpia los caches globales de superficies pygame."""
    _surface_cache.clear()
    _scaled_cache.clear()


def cache_stats() -> dict:
    """Devuelve estadisticas del cache para debugging."""
    return {
        "tile_surfaces": len(_surface_cache),
        "scaled_surfaces": len(_scaled_cache),
    }
