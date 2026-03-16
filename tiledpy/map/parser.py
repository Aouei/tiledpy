"""
map/parser.py — Parser for Tiled TMX/TMJ/JSON map files.

Usage
-----
>>> from tiledpy.map.parser import Parser
>>> tmap = Parser.load("map.tmx")   # or .tmj / .json

Supports
--------
- XML (.tmx) and JSON (.tmj / .json) map formats
- Finite and infinite (chunk-based) maps
- CSV and Base64 encoding (zlib / gzip / zstd compression)
- Inline and external tilesets (.tsx)
- Tile layers and object layers
"""

from __future__ import annotations

import base64
import gzip
import os
import struct
import xml.etree.ElementTree as ET
import zlib

from tiledpy.layer.object import ObjectLayer, TileObject
from tiledpy.layer.tile import TileLayer
from tiledpy.layer.tileset import TileFlags, TileMeta, Tileset, decode_gid
from tiledpy.map.map import TileMap


class Parser:
    """Static parser that reads a Tiled map file and returns a TileMap.

    All methods are static — no instance is needed.

    Examples
    --------
    >>> tmap = Parser.load("world.tmx")
    >>> tmap = Parser.load("world.tmj")
    """

    @staticmethod
    def load(path: str) -> TileMap:
        """Load a Tiled map from *path* and return a :class:`TileMap`.

        The format is detected automatically from the file extension:
        ``.tmx`` → XML, ``.tmj`` / ``.json`` → JSON.

        Parameters
        ----------
        path : str
            Absolute or relative path to the map file.

        Returns
        -------
        TileMap
        """
        ext = os.path.splitext(path)[1].lower()
        if ext in (".tmj", ".json"):
            return Parser._parse_json(path)
        return Parser._parse_xml(path)

    # ------------------------------------------------------------------
    # XML (.tmx)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_xml(path: str) -> TileMap:
        tmap = TileMap()
        base_dir = os.path.dirname(os.path.abspath(path))

        tree = ET.parse(path)
        root = tree.getroot()

        tmap.orientation      = root.attrib.get("orientation", "orthogonal")
        tmap.render_order     = root.attrib.get("renderorder", "right-down")
        tmap.width            = int(root.attrib.get("width", 0))
        tmap.height           = int(root.attrib.get("height", 0))
        tmap.tile_width       = int(root.attrib.get("tilewidth", 16))
        tmap.tile_height      = int(root.attrib.get("tileheight", 16))
        tmap.infinite         = root.attrib.get("infinite", "0") == "1"
        tmap.background_color = root.attrib.get("backgroundcolor")
        tmap.properties       = _parse_properties_xml(root.find("properties"))

        for child in root:
            if child.tag == "tileset":
                ts = _parse_tileset_ref_xml(child, base_dir, tmap)
                if ts is not None:
                    tmap.tilesets.append(ts)
            elif child.tag == "layer":
                tmap.layers.append(
                    _parse_tile_layer_xml(child, tmap, base_dir)
                )
            elif child.tag == "objectgroup":
                tmap.layers.append(
                    _parse_object_layer_xml(child, tmap)
                )

        tmap.tilesets.sort(key=lambda t: t.firstgid)
        _inject_tilesets(tmap)
        return tmap

    # ------------------------------------------------------------------
    # JSON (.tmj / .json)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json(path: str) -> TileMap:
        import json
        tmap = TileMap()
        base_dir = os.path.dirname(os.path.abspath(path))

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        tmap.orientation      = data.get("orientation", "orthogonal")
        tmap.render_order     = data.get("renderorder", "right-down")
        tmap.width            = int(data.get("width", 0))
        tmap.height           = int(data.get("height", 0))
        tmap.tile_width       = int(data.get("tilewidth", 16))
        tmap.tile_height      = int(data.get("tileheight", 16))
        tmap.infinite         = bool(data.get("infinite", False))
        tmap.background_color = data.get("backgroundcolor")
        tmap.properties       = _parse_properties_json(data.get("properties", []))

        for ts_ref in data.get("tilesets", []):
            firstgid = int(ts_ref["firstgid"])
            source   = ts_ref.get("source")
            if source:
                tsx_path = os.path.normpath(os.path.join(base_dir, source))
                ts = _parse_tsx(firstgid, tsx_path, tmap)
                if ts is not None:
                    tmap.tilesets.append(ts)

        tmap.tilesets.sort(key=lambda t: t.firstgid)

        for layer in data.get("layers", []):
            ltype = layer.get("type")
            if ltype == "tilelayer":
                tmap.layers.append(_parse_tile_layer_json(layer, tmap))
            elif ltype == "objectgroup":
                tmap.layers.append(_parse_object_layer_json(layer, tmap))

        _inject_tilesets(tmap)
        return tmap


# ---------------------------------------------------------------------------
# Internal helpers — XML
# ---------------------------------------------------------------------------

def _parse_tileset_ref_xml(
    elem: ET.Element,
    base_dir: str,
    tmap: TileMap,
) -> Tileset | None:
    firstgid = int(elem.attrib.get("firstgid", 1))
    if "source" in elem.attrib:
        tsx_path = os.path.normpath(
            os.path.join(base_dir, elem.attrib["source"])
        )
        return _parse_tsx(firstgid, tsx_path, tmap)
    return _parse_inline_tileset(firstgid, elem, base_dir, tmap)


def _parse_tsx(firstgid: int, tsx_path: str, tmap: TileMap) -> Tileset | None:
    tsx_dir = os.path.dirname(tsx_path)
    tree = ET.parse(tsx_path)
    root = tree.getroot()
    return _parse_inline_tileset(firstgid, root, tsx_dir, tmap)


def _parse_inline_tileset(
    firstgid: int,
    elem: ET.Element,
    base_dir: str,
    tmap: TileMap,
) -> Tileset | None:
    name      = elem.attrib.get("name", "")
    tile_w    = int(elem.attrib.get("tilewidth",  tmap.tile_width))
    tile_h    = int(elem.attrib.get("tileheight", tmap.tile_height))
    tilecount = int(elem.attrib.get("tilecount", 0))
    columns   = int(elem.attrib.get("columns", 0))
    spacing   = int(elem.attrib.get("spacing", 0))
    margin    = int(elem.attrib.get("margin", 0))

    img_elem = elem.find("image")
    if img_elem is None:
        return None

    raw_src  = img_elem.attrib.get("source", "").replace("\\/", "/").replace("\\", "/")
    img_path = os.path.normpath(os.path.join(base_dir, raw_src))

    if not os.path.isfile(img_path):
        raise FileNotFoundError(f"Tileset image not found: {img_path}")

    tile_data: dict[int, TileMeta] = {}
    for tile_elem in elem.findall("tile"):
        local_id   = int(tile_elem.attrib["id"])
        tile_class = tile_elem.attrib.get("class", tile_elem.attrib.get("type", ""))
        props      = _parse_properties_xml(tile_elem.find("properties"))

        collisions = []
        obj_group  = tile_elem.find("objectgroup")
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

        tile_data[local_id] = TileMeta(
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


def _parse_tile_layer_xml(
    elem: ET.Element,
    tmap: TileMap,
    base_dir: str,
) -> TileLayer:
    layer = TileLayer(
        id=int(elem.attrib.get("id", 0)),
        name=elem.attrib.get("name", ""),
        visible=elem.attrib.get("visible", "1") != "0",
        opacity=float(elem.attrib.get("opacity", 1.0)),
        offset_x=float(elem.attrib.get("offsetx", 0.0)),
        offset_y=float(elem.attrib.get("offsety", 0.0)),
        properties=_parse_properties_xml(elem.find("properties")),
    )

    data_elem = elem.find("data")
    if data_elem is None:
        return layer

    encoding    = data_elem.attrib.get("encoding", "xml")
    compression = data_elem.attrib.get("compression", "")

    if tmap.infinite:
        chunks = []
        for chunk_elem in data_elem.findall("chunk"):
            chunk_data = _decode_data(chunk_elem.text or "", encoding, compression)
            chunks.append({
                "x":      int(chunk_elem.attrib["x"]),
                "y":      int(chunk_elem.attrib["y"]),
                "width":  int(chunk_elem.attrib["width"]),
                "height": int(chunk_elem.attrib["height"]),
                "data":   chunk_data,
            })
        layer.load_from_chunks(chunks)
    else:
        w = int(elem.attrib.get("width",  tmap.width))
        h = int(elem.attrib.get("height", tmap.height))
        layer.load_from_flat(_decode_data(data_elem.text or "", encoding, compression), w, h)

    return layer


def _parse_object_layer_xml(elem: ET.Element, tmap: TileMap) -> ObjectLayer:
    objects = []
    for obj_elem in elem.findall("object"):
        raw_gid      = int(obj_elem.attrib["gid"]) if "gid" in obj_elem.attrib else None
        object_class = obj_elem.attrib.get("class", obj_elem.attrib.get("type", ""))
        if not object_class and raw_gid is not None:
            object_class = _class_from_gid(raw_gid, tmap.tilesets)
        objects.append(TileObject(
            id=int(obj_elem.attrib.get("id", 0)),
            name=obj_elem.attrib.get("name", ""),
            object_class=object_class,
            x=float(obj_elem.attrib.get("x", 0)),
            y=float(obj_elem.attrib.get("y", 0)),
            _width=float(obj_elem.attrib.get("width", 0)),
            _height=float(obj_elem.attrib.get("height", 0)),
            rotation=float(obj_elem.attrib.get("rotation", 0)),
            visible=obj_elem.attrib.get("visible", "1") != "0",
            properties=_parse_properties_xml(obj_elem.find("properties")),
            gid=raw_gid,
        ))
    return ObjectLayer(
        id=int(elem.attrib.get("id", 0)),
        name=elem.attrib.get("name", ""),
        visible=elem.attrib.get("visible", "1") != "0",
        opacity=float(elem.attrib.get("opacity", 1.0)),
        color=elem.attrib.get("color"),
        objects=objects,
        properties=_parse_properties_xml(elem.find("properties")),
    )


# ---------------------------------------------------------------------------
# Internal helpers — JSON
# ---------------------------------------------------------------------------

def _parse_tile_layer_json(data: dict, tmap: TileMap) -> TileLayer:
    layer = TileLayer(
        id=int(data.get("id", 0)),
        name=data.get("name", ""),
        visible=bool(data.get("visible", True)),
        opacity=float(data.get("opacity", 1.0)),
        offset_x=float(data.get("offsetx", 0.0)),
        offset_y=float(data.get("offsety", 0.0)),
        properties=_parse_properties_json(data.get("properties", [])),
    )
    flat = data.get("data", [])
    if flat:
        w = int(data.get("width",  tmap.width))
        h = int(data.get("height", tmap.height))
        layer.load_from_flat(flat, w, h)
    return layer


def _parse_object_layer_json(data: dict, tmap: TileMap) -> ObjectLayer:
    objects = []
    for obj in data.get("objects", []):
        raw_gid      = obj.get("gid")
        object_class = obj.get("class", obj.get("type", ""))
        if not object_class and raw_gid is not None:
            object_class = _class_from_gid(raw_gid, tmap.tilesets)
        objects.append(TileObject(
            id=int(obj.get("id", 0)),
            name=obj.get("name", ""),
            object_class=object_class,
            x=float(obj.get("x", 0)),
            y=float(obj.get("y", 0)),
            _width=float(obj.get("width", 0)),
            _height=float(obj.get("height", 0)),
            rotation=float(obj.get("rotation", 0)),
            visible=bool(obj.get("visible", True)),
            properties=_parse_properties_json(obj.get("properties", [])),
            gid=raw_gid,
        ))
    return ObjectLayer(
        id=int(data.get("id", 0)),
        name=data.get("name", ""),
        visible=bool(data.get("visible", True)),
        opacity=float(data.get("opacity", 1.0)),
        color=data.get("color"),
        objects=objects,
        properties=_parse_properties_json(data.get("properties", [])),
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _inject_tilesets(tmap: TileMap) -> None:
    """Give every TileLayer a reference to the map's tileset list."""
    for layer in tmap.layers:
        if isinstance(layer, TileLayer):
            layer._tilesets = tmap.tilesets


def _class_from_gid(raw_gid: int, tilesets: list[Tileset]) -> str:
    """Try to resolve the tile class from a raw GID via tileset metadata."""
    clean_gid, _ = decode_gid(raw_gid)
    ts = max(
        (t for t in tilesets if t.firstgid <= clean_gid),
        key=lambda t: t.firstgid,
        default=None,
    )
    if ts is not None:
        meta = ts.tile_data.get(clean_gid - ts.firstgid)
        if meta:
            return meta.tile_class
    return ""


def _parse_properties_xml(elem: ET.Element | None) -> dict:
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


def _parse_properties_json(props: list) -> dict:
    result = {}
    for p in props:
        name  = p["name"]
        ptype = p.get("type", "string")
        value = p.get("value", "")
        if ptype == "int":
            result[name] = int(value)
        elif ptype == "float":
            result[name] = float(value)
        elif ptype == "bool":
            result[name] = bool(value)
        else:
            result[name] = value
    return result


def _decode_data(raw: str, encoding: str, compression: str) -> list[int]:
    """Decode a Tiled ``<data>`` element into a flat list of raw GIDs."""
    if encoding == "csv":
        return [int(v) for v in raw.strip().replace("\n", "").split(",") if v.strip()]

    if encoding == "base64":
        data = base64.b64decode(raw.strip())
        if compression == "zlib":
            data = zlib.decompress(data)
        elif compression == "gzip":
            data = gzip.decompress(data)
        elif compression == "zstd":
            try:
                import zstandard as zstd
                data = zstd.ZstdDecompressor().decompress(data)
            except ImportError:
                raise ImportError(
                    "zstandard is required for zstd compression: pip install zstandard"
                )
        count = len(data) // 4
        return list(struct.unpack(f"<{count}I", data))

    if encoding == "xml":
        import re
        return [int(m) for m in re.findall(r'gid="(\d+)"', raw)]

    raise ValueError(f"Unknown encoding: {encoding!r}")
