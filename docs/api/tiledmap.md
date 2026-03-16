# TileMap & Parser

`Parser` loads a map file and returns a `TileMap`.
`TileMap` is a pure data model — it does not parse or render.

---

## Parser

```python
from tiledpy import Parser

tmap = Parser.load("map.tmx")   # XML
tmap = Parser.load("map.tmj")   # JSON
tmap = Parser.load("map.json")  # JSON (alternative extension)
```

`Parser.load(path)` auto-detects the format from the file extension:

| Extension | Format |
|-----------|--------|
| `.tmx` | XML (classic Tiled format) |
| `.tmj`, `.json` | JSON (modern Tiled format) |

Returns a fully constructed `TileMap` with all tilesets and layers populated.

---

## TileMap

```python
from tiledpy import TileMap
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `width` | `int` | Map width in tiles |
| `height` | `int` | Map height in tiles |
| `tile_width` | `int` | Tile width in pixels |
| `tile_height` | `int` | Tile height in pixels |
| `orientation` | `str` | Map orientation (e.g. `"orthogonal"`) |
| `infinite` | `bool` | True if the map uses chunk-based infinite scrolling |
| `background_color` | `str \| None` | Hex color `"#rrggbb"` or None |
| `properties` | `dict` | Custom map-level properties |
| `tilesets` | `list[Tileset]` | All tilesets sorted by `firstgid` |
| `layers` | `list[TileLayer \| ObjectLayer]` | All layers in draw order |

### Layer access

```python
# First layer matching the name
layer = tmap.get_layer("ground")          # → TileLayer | ObjectLayer | None

# All tile layers in draw order
tile_layers = tmap.get_tile_layers()      # → list[TileLayer]

# All object layers in draw order
object_layers = tmap.get_object_layers()  # → list[ObjectLayer]
```

### Coordinate helpers

```python
from tiledpy import OFFSET

# World pixel → tile (floor division)
tx, ty = tmap.world_to_tile(x, y, scale=2)
tx, ty = tmap.world_to_tile(x, y, scale=2, offset=OFFSET.CENTER)

# Tile → world pixel
wx, wy = tmap.tile_to_world(tx, ty, scale=2)
wx, wy = tmap.tile_to_world(tx, ty, scale=2, offset=OFFSET.CENTER)
```

### OFFSET enum

Nine anchor points for `world_to_tile` / `tile_to_world`:

```
LEFT_TOP    MIDDLE_TOP    RIGHT_TOP
LEFT_MIDDLE   CENTER    RIGHT_MIDDLE
LEFT_BOTTOM MIDDLE_BOTTOM RIGHT_BOTTOM
```

---

## Supported features

| Feature | Supported |
|---------|-----------|
| Finite maps | Yes |
| Infinite maps (chunks) | Yes |
| `.tmx` XML format | Yes |
| `.tmj` / `.json` format | Yes |
| CSV encoding | Yes |
| Base64 + zlib | Yes |
| Base64 + gzip | Yes |
| Base64 + zstd | Yes (`pip install zstandard`) |
| External `.tsx` tilesets | Yes |
| Inline tilesets | Yes |
| Tile class | Yes |
| Tile properties | Yes |
| Tile collision objects | Yes |
| Tile animations | Yes (auto-played via `get_animated_surface()`) |
| Object layers | Yes |
| Flip / rotate flags | Yes |
| Group layers | No |
| Image layers | No |
