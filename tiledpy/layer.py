"""
Layer data structures for Tiled maps.

Provides :class:`TileLayer` and :class:`ObjectLayer`, which represent
the two main layer types exported by the Tiled map editor, plus
:class:`TileObject` for individual objects within an object layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from tiledpy.tileset import Tileset

_MISSING: Any = object()  # Sentinel for optional value parameter


@dataclass
class TileObject:
    """A single object within an ObjectLayer.

    Parameters
    ----------
    id : int
        Unique object ID assigned by Tiled.
    name : str
        Object name.
    type : str
        Object type or class (``class`` attribute in Tiled 1.9+).
    x : float
        X position in pixels (top-left corner).
    y : float
        Y position in pixels (top-left corner).
    width : float
        Width in pixels.
    height : float
        Height in pixels.
    rotation : float, optional
        Clockwise rotation in degrees, by default ``0.0``.
    visible : bool, optional
        Whether the object is visible, by default ``True``.
    properties : dict, optional
        Custom properties defined in Tiled, by default an empty dict.
    gid : int or None, optional
        Global tile ID if this is a tile-object, otherwise ``None``.
    """

    id: int
    name: str
    type: str
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0
    visible: bool = True
    properties: dict = field(default_factory=dict)
    gid: int | None = None  # Si es un tile-object


@dataclass
class ObjectLayer:
    """A Tiled object layer (``<objectgroup>`` element).

    Parameters
    ----------
    id : int
        Layer ID from the TMX file.
    name : str
        Layer name.
    visible : bool
        Visibility flag.
    opacity : float
        Layer opacity in the range 0.0–1.0.
    color : str or None
        Layer color as a hex string (e.g. ``"#ff0000"``), or ``None``.
    objects : list[TileObject], optional
        Objects in this layer, by default an empty list.
    properties : dict, optional
        Custom layer properties, by default an empty dict.
    """

    id: int
    name: str
    visible: bool
    opacity: float
    color: str | None
    objects: list[TileObject] = field(default_factory=list)
    properties: dict = field(default_factory=dict)

    def get_object(self, name: str) -> TileObject | None:
        """Return the first object whose name matches.

        Parameters
        ----------
        name : str
            Object name to search for.

        Returns
        -------
        TileObject or None
            The matching object, or ``None`` if not found.
        """
        for obj in self.objects:
            if obj.name == name:
                return obj
        return None

    def get_objects_by_type(self, type_: str) -> list[TileObject]:
        """Return all objects whose type matches.

        Parameters
        ----------
        type_ : str
            Object type or class to filter by.

        Returns
        -------
        list[TileObject]
            List of matching objects (may be empty).
        """
        return [o for o in self.objects if o.type == type_]


class TileLayer:
    """A tile layer from a Tiled map (``<layer>`` element).

    Stores tile GIDs in a sparse dict ``{(tx, ty): raw_gid}`` so that
    empty tiles (GID 0) consume no memory. Supports both finite maps
    (flat array) and infinite maps (chunk-based).

    Parameters
    ----------
    id : int
        Layer ID from the TMX file.
    name : str
        Layer name.
    visible : bool
        Initial visibility flag.
    opacity : float
        Layer opacity in the range 0.0–1.0.
    offset_x : float, optional
        Horizontal pixel offset, by default ``0.0``.
    offset_y : float, optional
        Vertical pixel offset, by default ``0.0``.
    properties : dict or None, optional
        Custom layer properties, by default an empty dict.

    Attributes
    ----------
    _tilesets : list[Tileset]
        Reference to the map's tilesets, assigned by
        :class:`~tiledpy.loader.TiledMap` after parsing.  Used internally
        by :meth:`get_tile_by_property` to resolve tile metadata.
        Do not modify this list directly.
    min_x : int
        Left-most tile X coordinate (computed after loading data).
    min_y : int
        Top-most tile Y coordinate (computed after loading data).
    max_x : int
        Right-most tile X coordinate (computed after loading data).
    max_y : int
        Bottom-most tile Y coordinate (computed after loading data).
    width : int
        Computed property: ``max_x - min_x + 1``.
    height : int
        Computed property: ``max_y - min_y + 1``.
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
        self.id        = id
        self.name      = name
        self.visible   = visible
        self.opacity   = opacity
        self.offset_x  = offset_x
        self.offset_y  = offset_y
        self.properties = properties or {}

        # {(tile_x, tile_y): raw_gid}  — solo tiles no vacios
        self._data: dict[tuple[int, int], int] = {}

        # Referencia a los tilesets del mapa (asignada por TiledMap tras el parseo)
        self._tilesets: list[Tileset] = []

        # Bounding box en coordenadas de tile (calculado al cargar datos)
        self.min_x: int = 0
        self.min_y: int = 0
        self.max_x: int = 0
        self.max_y: int = 0

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------

    def load_from_flat(self, data: list[int], width: int, height: int) -> None:
        """Populate the layer from a flat row-major list of raw GIDs.

        Used for finite maps where tile data is stored as a single
        array. Empty tiles (GID 0) are skipped.

        Parameters
        ----------
        data : list[int]
            Raw GID values in row-major order (left-to-right,
            top-to-bottom).
        width : int
            Map width in tiles (number of columns).
        height : int
            Map height in tiles (number of rows).
        """
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
        """Populate the layer from a list of chunk dicts (infinite maps).

        Each chunk represents a fixed-size region of the infinite map.
        Empty tiles (GID 0) are skipped.

        Parameters
        ----------
        chunks : list[dict]
            Each dict must contain the keys: ``x``, ``y`` (chunk origin
            in tile coordinates), ``width``, ``height`` (chunk
            dimensions in tiles), and ``data`` (flat list of raw GIDs).
        """
        xs, ys = [], []
        for chunk in chunks:
            cx = chunk["x"]
            cy = chunk["y"]
            cw = chunk["width"]
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
    # Acceso a tiles
    # ------------------------------------------------------------------

    def get_raw_gid(self, tx: int, ty: int) -> int:
        """Return the raw GID (including flip flags) at tile coordinates.

        Parameters
        ----------
        tx : int
            Tile X coordinate.
        ty : int
            Tile Y coordinate.

        Returns
        -------
        int
            Raw GID value (may include flip/rotate flags in the upper
            bits), or ``0`` if the tile is empty.
        """
        return self._data.get((tx, ty), 0)

    def iter_tiles(self) -> Iterator[tuple[int, int, int]]:
        """Iterate over all non-empty tiles in the layer.

        Yields
        ------
        tuple[int, int, int]
            ``(tile_x, tile_y, raw_gid)`` for each non-empty tile.
            The raw GID may include flip/rotate flags — pass it to
            :func:`tiledpy.tileset.decode_gid` to separate the real
            GID from the flags.

        Examples
        --------
        >>> for tx, ty, raw_gid in layer.iter_tiles():
        ...     real_gid, flags = decode_gid(raw_gid)
        """
        for (tx, ty), raw_gid in self._data.items():
            yield tx, ty, raw_gid

    @property
    def width(self) -> int:
        """int : Computed layer width in tiles (``max_x - min_x + 1``)."""
        return self.max_x - self.min_x + 1 if self._data else 0

    @property
    def height(self) -> int:
        """int : Computed layer height in tiles (``max_y - min_y + 1``)."""
        return self.max_y - self.min_y + 1 if self._data else 0

    def get_tile_by_property(
        self,
        prop: str,
        value: Any = _MISSING,
    ) -> list[tuple[int, int]]:
        """Return tile coordinates where the tile has a given custom property.

        Iterates over all non-empty tiles in the layer, resolves their
        tileset metadata via ``self._tilesets`` (populated by
        :class:`~tiledpy.loader.TiledMap` after parsing), and returns the
        ``(tx, ty)`` positions of tiles whose custom property *prop* matches
        the requested *value*.

        The reserved name ``"Class"`` searches against the tile's Tiled
        ``class`` attribute (``type`` in older Tiled versions) stored in
        :attr:`~tiledpy.tileset.TileData.tile_class`, not the custom
        properties dict.

        Parameters
        ----------
        prop : str
            Name of the custom property to search for (as defined in Tiled),
            or ``"Class"`` to match against the tile's Tiled class attribute.
        value : Any, optional
            If provided, only tiles whose property *prop* equals this value
            are returned.  If omitted, every tile that has the property
            (regardless of its value) is returned.  When ``prop="Class"``
            and *value* is omitted, every tile with a non-empty class is
            returned.

        Returns
        -------
        list[tuple[int, int]]
            Tile coordinates ``(tx, ty)`` of all matching tiles. Returns an
            empty list if no tile matches.

        Examples
        --------
        Find all spawn-point tiles by their Tiled class:

        >>> spawns = layer.get_tile_by_property("Class", "spawn")
        >>> pixel_positions = [(tx * tmap.tile_width, ty * tmap.tile_height)
        ...                    for tx, ty in spawns]

        Find all spawn-point tiles by a custom boolean property:

        >>> spawns = layer.get_tile_by_property("player_spawn", True)

        Find every tile that has a property, regardless of its value:

        >>> blocked = layer.get_tile_by_property("collidable")
        """
        from tiledpy.tileset import decode_gid  # lazy to avoid circular import

        match_class = prop == "Class"
        result: list[tuple[int, int]] = []
        for tx, ty, raw_gid in self.iter_tiles():
            gid, _ = decode_gid(raw_gid)
            if gid == 0:
                continue

            # Búsqueda lineal sobre tilesets ordenados por firstgid
            tileset = None
            for ts in self._tilesets:
                if ts.firstgid <= gid:
                    tileset = ts
                else:
                    break
            if tileset is None:
                continue

            local_id = tileset.global_to_local(gid)
            tile_data = tileset.tile_data.get(local_id)
            if tile_data is None:
                continue

            if match_class:
                candidate = tile_data.tile_class
                if not candidate:
                    continue
                if value is not _MISSING and candidate != value:
                    continue
            else:
                if prop not in tile_data.properties:
                    continue
                if value is not _MISSING and tile_data.properties[prop] != value:
                    continue

            result.append((tx, ty))

        return result

    def __repr__(self) -> str:
        return (
            f"TileLayer(name={self.name!r}, tiles={len(self._data)}, "
            f"bounds=({self.min_x},{self.min_y})-({self.max_x},{self.max_y}))"
        )
