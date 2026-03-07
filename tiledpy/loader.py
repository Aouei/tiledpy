"""
loader.py — Parser for Tiled TMX map files.

Supports:

- Finite and infinite maps (chunks)
- CSV and Base64 encoding (with zlib/gzip/zstd compression)
- Inline and external tilesets (.tsx)
- Tile layers (:class:`TileLayer`) and object layers (:class:`ObjectLayer`)
- :meth:`TiledMap.draw_layer` for pygame rendering via the cached renderer
"""

from __future__ import annotations

import base64
import os
import struct
import xml.etree.ElementTree as ET
import zlib
from typing import Union

from .enums import OFFSET
from .layer import ObjectLayer, TileLayer, TileObject
from .tileset import TileData, Tileset
import gzip

LayerType = Union[TileLayer, ObjectLayer]

class TiledMap:
    """A Tiled map loaded from a ``.tmx`` file.

    Parses the TMX XML, builds :class:`~tiledpy.tileset.Tileset`,
    :class:`~tiledpy.layer.TileLayer`, and
    :class:`~tiledpy.layer.ObjectLayer` objects, and exposes rendering
    helpers for Pygame.

    Parameters
    ----------
    path : str
        Absolute or relative path to the ``.tmx`` file.

    Attributes
    ----------
    path : str
        Absolute path to the ``.tmx`` file.
    base_dir : str
        Directory containing the ``.tmx`` (used to resolve relative
        paths to images and external tilesets).
    orientation : str
        Map orientation: ``"orthogonal"``, ``"isometric"``, etc.
    render_order : str
        Tile render order, e.g. ``"right-down"`` (default).
    width : int
        Map width in tiles.
    height : int
        Map height in tiles.
    tile_width : int
        Tile width in pixels.
    tile_height : int
        Tile height in pixels.
    infinite : bool
        ``True`` if the map uses chunk-based infinite scrolling.
    background_color : str or None
        Hex background color string ``"#rrggbb"``, or ``None``.
    tilesets : list[Tileset]
        All tilesets sorted by ``firstgid`` ascending.
    layers : list[TileLayer or ObjectLayer]
        All layers in draw order.
    properties : dict
        Custom map-level properties.

    Raises
    ------
    FileNotFoundError
        If any tileset image referenced by the TMX/TSX is missing.

    Examples
    --------
    >>> tmap = TiledMap("map.tmx")
    >>> tmap.draw_layer(screen, "ground", offset=(cam_x, cam_y))
    """

    def __init__(self, path: str) -> None:
        self.path     = os.path.abspath(path)
        self.base_dir = os.path.dirname(self.path)

        # Atributos del <map>
        self.orientation: str  = "orthogonal"
        self.render_order: str = "right-down"
        self.width:        int = 0
        self.height:       int = 0
        self.tile_width:   int = 16
        self.tile_height:  int = 16
        self.infinite:     bool = False
        self.background_color: str | None = None

        self.tilesets: list[Tileset]  = []
        self.layers:   list[LayerType] = []
        self.properties: dict = {}

        self._parse(path)

    @property
    def visible_layers(self) -> list[TileLayer]:
        return [ layer for layer in self.get_tile_layers() if layer.visible ]

    # ------------------------------------------------------------------
    # Acceso a capas
    # ------------------------------------------------------------------

    def get_layer(self, name: str) -> LayerType | None:
        """Return the first layer whose name matches.

        Parameters
        ----------
        name : str
            Layer name to look up.

        Returns
        -------
        TileLayer or ObjectLayer or None
            The matching layer, or ``None`` if not found.
        """
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_tile_layers(self) -> list[TileLayer]:
        """Return all TileLayer instances in draw order.

        Returns
        -------
        list[TileLayer]
            All tile layers from the map.
        """
        return [l for l in self.layers if isinstance(l, TileLayer)]

    def get_object_layers(self) -> list[ObjectLayer]:
        """Return all ObjectLayer instances in draw order.

        Returns
        -------
        list[ObjectLayer]
            All object layers from the map.
        """
        return [l for l in self.layers if isinstance(l, ObjectLayer)]

    # ------------------------------------------------------------------
    # Conversión de coordenadas
    # ------------------------------------------------------------------

    def world_to_tile(
        self,
        x: float,
        y: float,
        scale: int = 1,
        offset : OFFSET = OFFSET.LEFT_TOP,
    ) -> tuple[int | float, int | float]:
        """Convert world pixel coordinates to tile coordinates.

        Parameters
        ----------
        x : float
            World X position in pixels.
        y : float
            World Y position in pixels.
        scale : int, optional
            Integer scale factor applied during rendering, by default ``1``.

        Returns
        -------
        tuple[int, int]
            ``(tx, ty)`` tile coordinates (integer, floor division).

        Examples
        --------
        >>> tx, ty = tmap.world_to_tile(mouse_x + cam_x, mouse_y + cam_y, scale=2)
        """
        off_x, off_y = offset.value

        tw = self.tile_width  * scale
        th = self.tile_height * scale
        return int(x // tw) + off_x, int(y // th) + off_y

    def tile_to_world(
        self,
        tx: int,
        ty: int,
        scale: int = 1,
        offset : OFFSET = OFFSET.LEFT_TOP
    ) -> tuple[int | float, int | float]:
        """Convert tile coordinates to world pixel coordinates.

        Returns the top-left pixel of the tile.

        Parameters
        ----------
        tx : int
            Tile X coordinate.
        ty : int
            Tile Y coordinate.
        scale : int, optional
            Integer scale factor applied during rendering, by default ``1``.

        Returns
        -------
        tuple[int, int]
            ``(x, y)`` world position in pixels (top-left corner of the tile).

        Examples
        --------
        >>> x, y = tmap.tile_to_world(tx, ty, scale=2)
        >>> screen.blit(marker, (x - cam_x, y - cam_y))
        """
        off_x, off_y = offset.value

        return (tx + off_x) * self.tile_width * scale, (ty + off_y) * self.tile_height * scale

    # ------------------------------------------------------------------
    # Acceso a tiles por coordenada
    # ------------------------------------------------------------------

    def get_tile_gid(
        self,
        tx: int,
        ty: int,
        layer_name: str | None = None,
    ) -> int:
        """Return the raw GID at tile coordinates ``(tx, ty)``.

        Parameters
        ----------
        tx : int
            Tile X coordinate.
        ty : int
            Tile Y coordinate.
        layer_name : str or None, optional
            Name of the layer to query. If ``None``, all
            :class:`~tiledpy.layer.TileLayer` instances are searched in
            draw order and the first non-zero GID is returned.

        Returns
        -------
        int
            Raw GID (may include flip/rotate flags). Returns ``0`` if
            the tile is empty or the layer does not exist.

        Examples
        --------
        >>> gid = tmap.get_tile_gid(3, 5, "ground")
        >>> gid = tmap.get_tile_gid(3, 5)          # first non-empty layer
        """
        if layer_name is not None:
            layer = self.get_layer(layer_name)
            if layer is None or not isinstance(layer, TileLayer):
                return 0
            return layer.get_raw_gid(tx, ty)

        for layer in self.layers:
            if not isinstance(layer, TileLayer):
                continue
            gid = layer.get_raw_gid(tx, ty)
            if gid != 0:
                return gid
        return 0

    # ------------------------------------------------------------------
    # Acceso a tilesets
    # ------------------------------------------------------------------

    def get_tileset_for_gid(self, gid: int) -> Tileset | None:
        """Return the Tileset that owns the given global tile ID.

        Uses a linear scan (tilesets are sorted by ``firstgid``),
        returning the last tileset whose ``firstgid`` is less than or
        equal to ``gid``.

        Parameters
        ----------
        gid : int
            Global tile ID (without flip flags).

        Returns
        -------
        Tileset or None
            The owning tileset, or ``None`` if no tileset covers this
            GID.

        Examples
        --------
        >>> ts = tmap.get_tileset_for_gid(42)
        >>> local = ts.global_to_local(42)
        """
        result = None
        for ts in self.tilesets:
            if ts.firstgid <= gid:
                result = ts
            else:
                break
        return result

    # ------------------------------------------------------------------
    # Renderizado con pygame
    # ------------------------------------------------------------------

    def draw_layer(
        self,
        surface,
        layer_name: str,
        offset: tuple[int, int] = (0, 0),
        scale: int = 1,
    ) -> None:
        """Render one named TileLayer onto a ``pygame.Surface``.

        Delegates to :func:`tiledpy.renderer.draw_layer`. Tiles outside
        the surface bounds are skipped (viewport culling). Does nothing
        if the layer does not exist or is not a :class:`TileLayer`.

        Parameters
        ----------
        surface : pygame.Surface
            Render target.
        layer_name : str
            Name of the layer to draw.
        offset : tuple[int, int], optional
            Camera offset ``(ox, oy)`` in pixels, by default ``(0, 0)``.
        scale : int, optional
            Integer scale factor for pixel-art rendering, by default ``1``.

        Examples
        --------
        >>> tmap.draw_layer(screen, "water", offset=(cam_x, cam_y), scale=2)
        """
        from .renderer import draw_layer as _draw_layer

        layer = self.get_layer(layer_name)
        if layer is None or not isinstance(layer, TileLayer):
            return

        _draw_layer(
            surface=surface,
            layer=layer,
            tilesets=self.tilesets,
            tile_width=self.tile_width,
            tile_height=self.tile_height,
            offset=offset,
            scale=scale,
        )

    def draw_all_layers(
        self,
        surface,
        offset: tuple[int, int] = (0, 0),
        scale: int = 1,
    ) -> None:
        """Draw all visible TileLayer instances in order.

        Parameters
        ----------
        surface : pygame.Surface
            Render target.
        offset : tuple[int, int], optional
            Camera offset ``(ox, oy)`` in pixels, by default ``(0, 0)``.
        scale : int, optional
            Integer scale factor for pixel-art rendering, by default ``1``.
        """
        for layer in self.layers:
            if isinstance(layer, TileLayer) and layer.visible:
                self.draw_layer(surface, layer.name, offset=offset, scale=scale)

    # ------------------------------------------------------------------
    # Parsing interno
    # ------------------------------------------------------------------

    def _parse(self, path: str) -> None:
        tree = ET.parse(path)
        root = tree.getroot()

        self.orientation   = root.attrib.get("orientation", "orthogonal")
        self.render_order  = root.attrib.get("renderorder", "right-down")
        self.width         = int(root.attrib.get("width", 0))
        self.height        = int(root.attrib.get("height", 0))
        self.tile_width    = int(root.attrib.get("tilewidth", 16))
        self.tile_height   = int(root.attrib.get("tileheight", 16))
        self.infinite      = root.attrib.get("infinite", "0") == "1"
        self.background_color = root.attrib.get("backgroundcolor")

        self.properties = _parse_properties(root.find("properties"))

        for child in root:
            if child.tag == "tileset":
                ts = self._parse_tileset_ref(child)
                if ts is not None:
                    self.tilesets.append(ts)
            elif child.tag == "layer":
                self.layers.append(self._parse_tile_layer(child))
            elif child.tag == "objectgroup":
                self.layers.append(self._parse_object_layer(child))

        # Ordenar tilesets por firstgid ascendente (necesario para get_tileset_for_gid)
        self.tilesets.sort(key=lambda t: t.firstgid)

        # Dar a cada TileLayer acceso directo a los tilesets
        for layer in self.layers:
            if isinstance(layer, TileLayer):
                layer._tilesets = self.tilesets

    def _parse_tileset_ref(self, elem: ET.Element) -> Tileset | None:
        firstgid = int(elem.attrib.get("firstgid", 1))

        if "source" in elem.attrib:
            tsx_path = os.path.normpath(
                os.path.join(self.base_dir, elem.attrib["source"])
            )
            return self._parse_tsx(firstgid, tsx_path)
        else:
            return self._parse_inline_tileset(firstgid, elem, self.base_dir)

    def _parse_tsx(self, firstgid: int, tsx_path: str) -> Tileset | None:
        tsx_dir = os.path.dirname(tsx_path)
        tree = ET.parse(tsx_path)
        root = tree.getroot()
        return self._parse_inline_tileset(firstgid, root, tsx_dir)

    def _parse_inline_tileset(
        self,
        firstgid: int,
        elem: ET.Element,
        base_dir: str,
    ) -> Tileset | None:
        name       = elem.attrib.get("name", "")
        tile_w     = int(elem.attrib.get("tilewidth",  self.tile_width))
        tile_h     = int(elem.attrib.get("tileheight", self.tile_height))
        tilecount  = int(elem.attrib.get("tilecount", 0))
        columns    = int(elem.attrib.get("columns", 0))
        spacing    = int(elem.attrib.get("spacing", 0))
        margin     = int(elem.attrib.get("margin", 0))

        img_elem = elem.find("image")
        if img_elem is None:
            return None

        raw_src = img_elem.attrib.get("source", "")
        raw_src = raw_src.replace("\\/", "/").replace("\\", "/")
        img_path = os.path.normpath(os.path.join(base_dir, raw_src))

        if not os.path.isfile(img_path):
            raise FileNotFoundError(
                f"Imagen de tileset no encontrada: {img_path}"
            )

        # Parsear propiedades y collision de tiles individuales
        tile_data: dict[int, TileData] = {}
        for tile_elem in elem.findall("tile"):
            local_id = int(tile_elem.attrib["id"])
            tile_class = tile_elem.attrib.get("class", tile_elem.attrib.get("type", ""))
            props = _parse_properties(tile_elem.find("properties"))
            collisions = []
            obj_group = tile_elem.find("objectgroup")
            if obj_group is not None:
                for obj in obj_group.findall("object"):
                    collisions.append({
                        "x":      float(obj.attrib.get("x", 0)),
                        "y":      float(obj.attrib.get("y", 0)),
                        "width":  float(obj.attrib.get("width", 0)),
                        "height": float(obj.attrib.get("height", 0)),
                    })
            animation = []
            anim_elem = tile_elem.find("animation")
            if anim_elem is not None:
                for frame in anim_elem.findall("frame"):
                    animation.append({
                        "tileid":   int(frame.attrib["tileid"]),
                        "duration": int(frame.attrib["duration"]),
                    })
            tile_data[local_id] = TileData(
                local_id=local_id,
                tile_class=tile_class,
                properties=props,
                collision_objects=collisions,
                animation=animation,
                width=tile_w,
                height=tile_h,
            )

        return Tileset(
            name=name,
            firstgid=firstgid,
            image_path=img_path,
            tile_width=tile_w,
            tile_height=tile_h,
            columns=columns,
            tilecount=tilecount,
            spacing=spacing,
            margin=margin,
            tile_data=tile_data,
        )

    def _parse_tile_layer(self, elem: ET.Element) -> TileLayer:
        layer = TileLayer(
            id=int(elem.attrib.get("id", 0)),
            name=elem.attrib.get("name", ""),
            visible=elem.attrib.get("visible", "1") != "0",
            opacity=float(elem.attrib.get("opacity", 1.0)),
            offset_x=float(elem.attrib.get("offsetx", 0.0)),
            offset_y=float(elem.attrib.get("offsety", 0.0)),
            properties=_parse_properties(elem.find("properties")),
        )

        data_elem = elem.find("data")
        if data_elem is None:
            return layer

        encoding    = data_elem.attrib.get("encoding", "xml")
        compression = data_elem.attrib.get("compression", "")

        if self.infinite:
            chunks = []
            for chunk_elem in data_elem.findall("chunk"):
                chunk_data = _decode_data(
                    chunk_elem.text or "",
                    encoding,
                    compression,
                )
                chunks.append({
                    "x":      int(chunk_elem.attrib["x"]),
                    "y":      int(chunk_elem.attrib["y"]),
                    "width":  int(chunk_elem.attrib["width"]),
                    "height": int(chunk_elem.attrib["height"]),
                    "data":   chunk_data,
                })
            layer.load_from_chunks(chunks)
        else:
            width  = int(elem.attrib.get("width",  self.width))
            height = int(elem.attrib.get("height", self.height))
            flat_data = _decode_data(data_elem.text or "", encoding, compression)
            layer.load_from_flat(flat_data, width, height)

        return layer

    def _parse_object_layer(self, elem: ET.Element) -> ObjectLayer:
        objects = []
        for obj_elem in elem.findall("object"):
            obj = TileObject(
                id=int(obj_elem.attrib.get("id", 0)),
                name=obj_elem.attrib.get("name", ""),
                type=obj_elem.attrib.get("type", obj_elem.attrib.get("class", "")),
                x=float(obj_elem.attrib.get("x", 0)),
                y=float(obj_elem.attrib.get("y", 0)),
                width=float(obj_elem.attrib.get("width", 0)),
                height=float(obj_elem.attrib.get("height", 0)),
                rotation=float(obj_elem.attrib.get("rotation", 0)),
                visible=obj_elem.attrib.get("visible", "1") != "0",
                properties=_parse_properties(obj_elem.find("properties")),
                gid=int(obj_elem.attrib["gid"]) if "gid" in obj_elem.attrib else None,
            )
            objects.append(obj)

        return ObjectLayer(
            id=int(elem.attrib.get("id", 0)),
            name=elem.attrib.get("name", ""),
            visible=elem.attrib.get("visible", "1") != "0",
            opacity=float(elem.attrib.get("opacity", 1.0)),
            color=elem.attrib.get("color"),
            objects=objects,
            properties=_parse_properties(elem.find("properties")),
        )

    def __repr__(self) -> str:
        return (
            f"TiledMap({os.path.basename(self.path)!r}, "
            f"{self.width}x{self.height}, "
            f"layers={[l.name for l in self.layers]})"
        )


# ------------------------------------------------------------------
# Helpers de parsing
# ------------------------------------------------------------------

def _parse_properties(elem: ET.Element | None) -> dict:
    """Parse a Tiled ``<properties>`` XML element into a plain dict.

    Parameters
    ----------
    elem : xml.etree.ElementTree.Element or None
        The ``<properties>`` element, or ``None``.

    Returns
    -------
    dict
        Mapping of property name to typed value (``int``, ``float``,
        ``bool``, or ``str``).
    """
    if elem is None:
        return {}
    result = {}
    for prop in elem.findall("property"):
        name  = prop.attrib["name"]
        ptype = prop.attrib.get("type", "string")
        value = prop.attrib.get("value", prop.text or "")
        if ptype == "int":
            result[name] = int(value)
        elif ptype == "float":
            result[name] = float(value)
        elif ptype == "bool":
            result[name] = value.lower() == "true"
        else:
            result[name] = value
    return result


def _decode_data(
    raw: str,
    encoding: str,
    compression: str,
) -> list[int]:
    """Decode the content of a Tiled ``<data>`` element into a list of GIDs.

    Parameters
    ----------
    raw : str
        Raw text content of the ``<data>`` element.
    encoding : str
        Encoding format: ``"csv"``, ``"base64"``, or ``"xml"``.
    compression : str
        Compression algorithm applied to base64 data: ``""`` (none),
        ``"zlib"``, ``"gzip"``, or ``"zstd"``.

    Returns
    -------
    list[int]
        Flat list of raw GID values (uint32, may include flip flags).

    Raises
    ------
    ValueError
        If ``encoding`` is not one of the supported values.
    ImportError
        If ``compression="zstd"`` and the ``zstandard`` package is not
        installed.
    """
    if encoding == "csv":
        return [int(v) for v in raw.strip().replace("\n", "").split(",") if v.strip()]

    if encoding == "base64":
        data = base64.b64decode(raw.strip())
        if compression == "zlib":
            data = zlib.decompress(data)
        elif compression == "gzip":
            import gzip as _gzip
            data = _gzip.decompress(data)
        elif compression == "zstd":
            try:
                import zstandard as zstd
                data = zstd.ZstdDecompressor().decompress(data)
            except ImportError:
                raise ImportError("zstandard es necesario para compresion zstd: pip install zstandard")
        # Los GIDs son uint32 little-endian
        count = len(data) // 4
        return list(struct.unpack(f"<{count}I", data))

    if encoding == "xml":
        # <tile gid="..."/> dentro del bloque de datos
        import re
        return [int(m) for m in re.findall(r'gid="(\d+)"', raw)]

    raise ValueError(f"Encoding desconocido: {encoding!r}")
