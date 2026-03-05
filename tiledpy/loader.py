"""
loader.py
Parser de archivos TMX de Tiled.

Soporta:
- Mapas finitos e infinitos (chunks)
- Encoding CSV y base64 (con compresion zlib/gzip)
- Tilesets inline y externos (.tsx)
- Capas de tiles (TileLayer) y de objetos (ObjectLayer)
- draw_layer() para renderizar con pygame usando el renderer cacheado
"""

from __future__ import annotations

import base64
import os
import struct
import xml.etree.ElementTree as ET
import zlib
from typing import Union

from .layer import ObjectLayer, TileLayer, TileObject
from .tileset import TileData, Tileset

try:
    import gzip
except ImportError:
    gzip = None  # type: ignore


LayerType = Union[TileLayer, ObjectLayer]


class TiledMap:
    """
    Representa un mapa de Tiled cargado desde un archivo .tmx.

    Uso basico:
        tmap = TiledMap("mapa.tmx")
        tmap.draw_layer(screen, "agua", offset=(0, 0))
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

    # ------------------------------------------------------------------
    # Acceso a capas
    # ------------------------------------------------------------------

    def get_layer(self, name: str) -> LayerType | None:
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def get_tile_layers(self) -> list[TileLayer]:
        return [l for l in self.layers if isinstance(l, TileLayer)]

    def get_object_layers(self) -> list[ObjectLayer]:
        return [l for l in self.layers if isinstance(l, ObjectLayer)]

    # ------------------------------------------------------------------
    # Acceso a tilesets
    # ------------------------------------------------------------------

    def get_tileset_for_gid(self, gid: int) -> Tileset | None:
        """Devuelve el Tileset al que pertenece el GID global dado."""
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
        """
        Dibuja una TileLayer sobre un pygame.Surface.

        Args:
            surface:     pygame.Surface destino.
            layer_name:  Nombre de la capa a dibujar.
            offset:      Desplazamiento de camara (px) como (x, y).
            scale:       Factor de escala entero (para pixel-art).
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
        """Dibuja todas las TileLayers visibles en orden."""
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
                properties=props,
                collision_objects=collisions,
                animation=animation,
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
    """Decodifica el contenido de <data> a una lista de GIDs enteros."""
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
