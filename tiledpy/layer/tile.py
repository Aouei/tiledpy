"""
layer/tile.py — TileData and TileLayer.

TileData represents a single tile **placed at (tx, ty)** in a layer.
It holds its position, local ID, owning tileset, and flip flags, and
exposes ``get_surface()`` / ``get_animated_surface()`` for rendering.

TileLayer stores tiles in a sparse dict and iterates them as TileData.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from .tileset import TileFlags, Tileset, TileMeta, decode_gid

if TYPE_CHECKING:
    import pygame

# Sentinel for optional value parameter in get_tiles_by_property
_MISSING: Any = object()

# Module-level scaled-surface cache shared by all TileData instances
# Key: (tileset.firstgid, local_id, flip_h, flip_v, flip_d, scale_2x)
# where scale_2x = round(scale * 100) to avoid float key issues
_scaled_cache: dict[tuple, "pygame.Surface"] = {}


def _get_scaled(surf: "pygame.Surface", w: int, h: int) -> "pygame.Surface":
    key = (id(surf), w, h)
    if key not in _scaled_cache:
        import pygame
        _scaled_cache[key] = pygame.transform.scale(surf, (w, h))
    return _scaled_cache[key]


def clear_tile_cache() -> None:
    """Clear the module-level scaled-surface cache."""
    _scaled_cache.clear()


# ---------------------------------------------------------------------------
# TileData
# ---------------------------------------------------------------------------

@dataclass
class TileData:
    """A tile placed at tile coordinates ``(tx, ty)`` within a layer.

    Attributes
    ----------
    tx : int
        Tile column (x in tile units).
    ty : int
        Tile row (y in tile units).
    local_id : int
        Zero-based tile index within ``tileset``.
    tileset : Tileset
        The tileset that owns this tile.
    flip_h : bool
        Horizontal flip flag.
    flip_v : bool
        Vertical flip flag.
    flip_d : bool
        Diagonal flip flag (used for 90° rotation).

    Properties (delegated to TileMeta)
    ------------------------------------
    meta          — raw TileMeta or None
    is_animated   — True if the tile has animation frames
    tile_class    — Tiled class attribute string
    properties    — custom properties dict
    collision_objects — list of collision rects

    Methods
    -------
    width(scale=1.0)  -> int
    height(scale=1.0) -> int
    get_surface(scale=1.0) -> pygame.Surface
    get_animated_surface(elapsed_ms, scale=1.0) -> pygame.Surface
    """

    tx: int
    ty: int
    local_id: int
    tileset: Tileset
    flip_h: bool = False
    flip_v: bool = False
    flip_d: bool = False

    # ------------------------------------------------------------------
    # TileMeta delegation
    # ------------------------------------------------------------------

    @property
    def meta(self) -> TileMeta | None:
        """Raw TileMeta for this tile, or None if not defined in TSX."""
        return self.tileset.tile_data.get(self.local_id)

    @property
    def is_animated(self) -> bool:
        """True if this tile has animation frames."""
        m = self.meta
        return bool(m and m.animation)

    @property
    def tile_class(self) -> str:
        """Tiled class attribute, empty string if not set."""
        m = self.meta
        return m.tile_class if m else ""

    @property
    def properties(self) -> dict:
        """Custom properties dict (empty if tile has no metadata)."""
        m = self.meta
        return m.properties if m else {}

    @property
    def collision_objects(self) -> list[dict]:
        """Collision rectangles list (empty if tile has no metadata)."""
        m = self.meta
        return m.collision_objects if m else []

    # ------------------------------------------------------------------
    # Size helpers
    # ------------------------------------------------------------------

    def width(self, scale: float = 1.0) -> int:
        """Tile width in pixels at the given scale."""
        return int(self.tileset.tile_width * scale)

    def height(self, scale: float = 1.0) -> int:
        """Tile height in pixels at the given scale."""
        return int(self.tileset.tile_height * scale)

    # ------------------------------------------------------------------
    # Surface helpers
    # ------------------------------------------------------------------

    def _flags(self) -> TileFlags:
        return TileFlags(self.flip_h, self.flip_v, self.flip_d)

    def get_surface(self, scale: float = 1.0) -> "pygame.Surface":
        """Return the pygame.Surface for this tile at the given scale.

        Uses the Tileset's pygame cache for the base (unscaled) surface,
        then applies scaling via a module-level cache.

        Parameters
        ----------
        scale : float, optional
            Render scale factor, by default 1.0.

        Returns
        -------
        pygame.Surface
        """
        surf = self.tileset.get_pygame_surface(self.local_id, self._flags())
        if scale == 1.0:
            return surf
        return _get_scaled(surf, self.width(scale), self.height(scale))

    def get_animated_surface(
        self,
        elapsed_ms: float,
        scale: float = 1.0,
    ) -> "pygame.Surface":
        """Return the current animation frame surface.

        If the tile has no animation, delegates to ``get_surface()``.

        Parameters
        ----------
        elapsed_ms : float
            Total elapsed time in milliseconds (e.g. ``pygame.time.get_ticks()``).
        scale : float, optional
            Render scale factor, by default 1.0.

        Returns
        -------
        pygame.Surface
        """
        if not self.is_animated:
            return self.get_surface(scale)

        frame_local_id = self._resolve_frame(elapsed_ms)
        surf = self.tileset.get_pygame_surface(frame_local_id, self._flags())
        if scale == 1.0:
            return surf
        return _get_scaled(surf, self.width(scale), self.height(scale))

    def _resolve_frame(self, elapsed_ms: float) -> int:
        animation = self.meta.animation  # type: ignore[union-attr]
        total = sum(f["duration"] for f in animation)
        t = int(elapsed_ms) % total
        acc = 0
        for frame in animation:
            acc += frame["duration"]
            if t < acc:
                return frame["tileid"]
        return animation[-1]["tileid"]

    def __repr__(self) -> str:
        return (
            f"TileData(tx={self.tx}, ty={self.ty}, "
            f"local_id={self.local_id}, tileset={self.tileset.name!r})"
        )


# ---------------------------------------------------------------------------
# TileLayer
# ---------------------------------------------------------------------------

class TileLayer:
    """A tile layer from a Tiled map.

    Stores raw GIDs in a sparse dict ``{(tx, ty): raw_gid}`` — empty
    tiles consume no memory. Supports finite maps (flat array) and
    infinite maps (chunks).

    Iterating via ``iter_tiles()`` yields fully constructed
    :class:`TileData` objects ready for rendering or game logic.

    Parameters
    ----------
    id : int
    name : str
    visible : bool
    opacity : float
    offset_x : float
    offset_y : float
    properties : dict or None
    """

    def __init__(
        self,
        id: int,
        name: str,
        visible: bool,
        opacity: float,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        properties: dict | None = None,
    ) -> None:
        self.id         = id
        self.name       = name
        self.visible    = visible
        self.opacity    = opacity
        self.offset_x   = offset_x
        self.offset_y   = offset_y
        self.properties = properties or {}

        self._data: dict[tuple[int, int], int] = {}
        self._tilesets: list[Tileset] = []

        self.min_x: int = 0
        self.min_y: int = 0
        self.max_x: int = 0
        self.max_y: int = 0

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_from_flat(self, data: list[int], width: int, height: int) -> None:
        """Load from a flat row-major list of raw GIDs (finite maps)."""
        xs, ys = [], []
        for i, raw_gid in enumerate(data):
            if raw_gid == 0:
                continue
            tx = i % width
            ty = i // width
            self._data[(tx, ty)] = raw_gid
            xs.append(tx)
            ys.append(ty)
        self._update_bounds(xs, ys)

    def load_from_chunks(self, chunks: list[dict]) -> None:
        """Load from chunk dicts (infinite maps).

        Each chunk dict must have: ``x``, ``y``, ``width``, ``height``, ``data``.
        """
        xs, ys = [], []
        for chunk in chunks:
            cx, cy, cw = chunk["x"], chunk["y"], chunk["width"]
            for i, raw_gid in enumerate(chunk["data"]):
                tx = cx + (i % cw)
                ty = cy + (i // cw)
                if raw_gid != 0:
                    self._data[(tx, ty)] = raw_gid
                xs.append(tx)
                ys.append(ty)
        self._update_bounds(xs, ys)

    def _update_bounds(self, xs: list[int], ys: list[int]) -> None:
        if xs:
            self.min_x = min(xs)
            self.max_x = max(xs)
        if ys:
            self.min_y = min(ys)
            self.max_y = max(ys)

    # ------------------------------------------------------------------
    # Size
    # ------------------------------------------------------------------

    @property
    def width(self) -> int:
        """Layer width in tiles."""
        return self.max_x - self.min_x + 1 if self._data else 0

    @property
    def height(self) -> int:
        """Layer height in tiles."""
        return self.max_y - self.min_y + 1 if self._data else 0

    # ------------------------------------------------------------------
    # Tile access
    # ------------------------------------------------------------------

    def get_raw_gid(self, tx: int, ty: int) -> int:
        """Return the raw GID (with flip flags) at (tx, ty), or 0 if empty."""
        return self._data.get((tx, ty), 0)

    def get_tile(self, tx: int, ty: int) -> TileData | None:
        """Return the TileData at (tx, ty), or None if the cell is empty."""
        raw_gid = self._data.get((tx, ty), 0)
        if raw_gid == 0:
            return None
        gid, flags = decode_gid(raw_gid)
        tileset = self._find_tileset(gid)
        if tileset is None:
            return None
        return TileData(
            tx=tx, ty=ty,
            local_id=tileset.global_to_local(gid),
            tileset=tileset,
            flip_h=flags.flip_h,
            flip_v=flags.flip_v,
            flip_d=flags.flip_d,
        )

    def iter_tiles(self) -> Iterator[TileData]:
        """Iterate over all non-empty tiles as TileData objects."""
        for (tx, ty), raw_gid in self._data.items():
            tile = self._make_tile(tx, ty, raw_gid)
            if tile is not None:
                yield tile

    def _make_tile(self, tx: int, ty: int, raw_gid: int) -> TileData | None:
        gid, flags = decode_gid(raw_gid)
        if gid == 0:
            return None
        tileset = self._find_tileset(gid)
        if tileset is None:
            return None
        return TileData(
            tx=tx, ty=ty,
            local_id=tileset.global_to_local(gid),
            tileset=tileset,
            flip_h=flags.flip_h,
            flip_v=flags.flip_v,
            flip_d=flags.flip_d,
        )

    # ------------------------------------------------------------------
    # Filtered access
    # ------------------------------------------------------------------

    def get_tiles_by_class(self, tile_class: str) -> list[TileData]:
        """Return all tiles whose Tiled class matches ``tile_class``."""
        return [t for t in self.iter_tiles() if t.tile_class == tile_class]

    def get_tiles_by_property(
        self,
        prop: str,
        value: Any = _MISSING,
    ) -> list[TileData]:
        """Return tiles that have a custom property, optionally matching a value.

        Parameters
        ----------
        prop : str
            Property name (use ``"Class"`` to match the Tiled class attribute).
        value : Any, optional
            If given, only tiles whose property equals this value are returned.
        """
        result: list[TileData] = []
        match_class = prop == "Class"
        for tile in self.iter_tiles():
            if match_class:
                candidate = tile.tile_class
                if not candidate:
                    continue
                if value is not _MISSING and candidate != value:
                    continue
            else:
                props = tile.properties
                if prop not in props:
                    continue
                if value is not _MISSING and props[prop] != value:
                    continue
            result.append(tile)
        return result

    def get_animated_tiles(self) -> list[TileData]:
        """Return all tiles that have animation frames (unique by local_id)."""
        seen: set[tuple[int, int]] = set()
        result: list[TileData] = []
        for tile in self.iter_tiles():
            if not tile.is_animated:
                continue
            key = (tile.tileset.firstgid, tile.local_id)
            if key not in seen:
                seen.add(key)
                result.append(tile)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_tileset(self, gid: int) -> Tileset | None:
        result = None
        for ts in self._tilesets:
            if ts.firstgid <= gid:
                result = ts
            else:
                break
        return result

    def __repr__(self) -> str:
        return (
            f"TileLayer(name={self.name!r}, tiles={len(self._data)}, "
            f"bounds=({self.min_x},{self.min_y})-({self.max_x},{self.max_y}))"
        )
