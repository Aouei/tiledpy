"""
layer.py
Estructuras de datos para capas de Tiled: TileLayer y ObjectLayer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class TileObject:
    """Un objeto dentro de un ObjectLayer."""
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
    """Capa de objetos de Tiled (<objectgroup>)."""
    id: int
    name: str
    visible: bool
    opacity: float
    color: str | None
    objects: list[TileObject] = field(default_factory=list)
    properties: dict = field(default_factory=dict)

    def get_object(self, name: str) -> TileObject | None:
        for obj in self.objects:
            if obj.name == name:
                return obj
        return None

    def get_objects_by_type(self, type_: str) -> list[TileObject]:
        return [o for o in self.objects if o.type == type_]


class TileLayer:
    """
    Capa de tiles de Tiled (<layer>).

    Soporta mapas finitos y mapas infinitos (con chunks).
    Los GIDs se almacenan en un dict {(tx, ty): raw_gid} para
    no desperdiciar memoria en tiles vacios (gid=0).
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

        # Bounding box en coordenadas de tile (calculado al cargar datos)
        self.min_x: int = 0
        self.min_y: int = 0
        self.max_x: int = 0
        self.max_y: int = 0

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------

    def load_from_flat(self, data: list[int], width: int, height: int) -> None:
        """Carga datos de un mapa finito (array plano row-major)."""
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
        """Carga datos de un mapa infinito (lista de chunks)."""
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
        """Devuelve el GID crudo (con flags) en la posicion de tile (tx, ty)."""
        return self._data.get((tx, ty), 0)

    def iter_tiles(self) -> Iterator[tuple[int, int, int]]:
        """Itera sobre (tile_x, tile_y, raw_gid) para todos los tiles no vacios."""
        for (tx, ty), raw_gid in self._data.items():
            yield tx, ty, raw_gid

    @property
    def width(self) -> int:
        return self.max_x - self.min_x + 1 if self._data else 0

    @property
    def height(self) -> int:
        return self.max_y - self.min_y + 1 if self._data else 0

    def __repr__(self) -> str:
        return (
            f"TileLayer(name={self.name!r}, tiles={len(self._data)}, "
            f"bounds=({self.min_x},{self.min_y})-({self.max_x},{self.max_y}))"
        )
