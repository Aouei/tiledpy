# TiledMap

`tiledpy.TiledMap` is the main entry point. It parses a `.tmx` file and exposes
layers, tilesets, and rendering methods.

```python
from tiledpy import TiledMap

tmap = TiledMap("map.tmx")
```

---

## Constructor

```python
TiledMap(path: str)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Absolute or relative path to the `.tmx` file |

Raises `FileNotFoundError` if any referenced tileset image is missing.

---

## Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Absolute path to the `.tmx` file |
| `base_dir` | `str` | Directory containing the `.tmx` (used to resolve relative paths) |
| `orientation` | `str` | `"orthogonal"`, `"isometric"`, etc. |
| `render_order` | `str` | `"right-down"` (default), `"right-up"`, etc. |
| `width` | `int` | Map width in tiles |
| `height` | `int` | Map height in tiles |
| `tile_width` | `int` | Tile width in pixels |
| `tile_height` | `int` | Tile height in pixels |
| `infinite` | `bool` | `True` if the map uses chunk-based infinite scrolling |
| `background_color` | `str \| None` | Hex background color `"#rrggbb"` or `None` |
| `tilesets` | `list[Tileset]` | All tilesets, sorted by `firstgid` ascending |
| `layers` | `list[TileLayer \| ObjectLayer]` | All layers in draw order |
| `properties` | `dict` | Custom map-level properties |

---

## Methods

### `get_layer`

```python
get_layer(name: str) -> TileLayer | ObjectLayer | None
```

Returns the first layer whose `name` matches, or `None`.

```python
ground = tmap.get_layer("ground")
```

---

### `get_tile_layers`

```python
get_tile_layers() -> list[TileLayer]
```

Returns all `TileLayer` instances in order.

---

### `get_object_layers`

```python
get_object_layers() -> list[ObjectLayer]
```

Returns all `ObjectLayer` instances in order.

---

### `get_tileset_for_gid`

```python
get_tileset_for_gid(gid: int) -> Tileset | None
```

Binary-searches for the `Tileset` that owns the given global tile ID.

```python
ts = tmap.get_tileset_for_gid(42)
local = ts.global_to_local(42)
```

---

### `draw_layer`

```python
draw_layer(
    surface,
    layer_name: str,
    offset: tuple[int, int] = (0, 0),
    scale: int = 1,
) -> None
```

Renders one named `TileLayer` onto a `pygame.Surface`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `surface` | `pygame.Surface` | — | Render target |
| `layer_name` | `str` | — | Name of the layer to draw |
| `offset` | `(int, int)` | `(0, 0)` | Camera offset in pixels `(ox, oy)` |
| `scale` | `int` | `1` | Integer scale factor (pixel-art) |

Tiles outside the surface bounds are skipped (viewport culling).

```python
tmap.draw_layer(screen, "water", offset=(cam_x, cam_y), scale=2)
```

---

### `draw_all_layers`

```python
draw_all_layers(
    surface,
    offset: tuple[int, int] = (0, 0),
    scale: int = 1,
) -> None
```

Draws all visible `TileLayer` instances in order.

---

## Supported TMX features

| Feature | Supported |
|---------|-----------|
| Finite maps | Yes |
| Infinite maps (chunks) | Yes |
| CSV encoding | Yes |
| Base64 + zlib | Yes |
| Base64 + gzip | Yes |
| Base64 + zstd | Yes (`pip install zstandard`) |
| External `.tsx` tilesets | Yes |
| Inline tilesets | Yes |
| Tile properties | Yes |
| Tile collision objects | Yes |
| Tile animations | Yes (data stored, no auto-play) |
| Object layers | Yes |
| Flip / rotate flags | Yes |
| Group layers | No |
| Image layers | No |
