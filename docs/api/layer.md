# Layers

tiledpy has two layer types: `TileLayer` for tile data and `ObjectLayer` for
vector objects.

---

## TileLayer

Represents a Tiled `<layer>`. Stores tile data as a sparse dict
`{(tx, ty): raw_gid}` — empty tiles (GID 0) use no memory.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Layer ID from TMX |
| `name` | `str` | Layer name |
| `visible` | `bool` | Visibility flag |
| `opacity` | `float` | 0.0–1.0 opacity |
| `offset_x` | `float` | Horizontal pixel offset |
| `offset_y` | `float` | Vertical pixel offset |
| `properties` | `dict` | Custom layer properties |
| `min_x` | `int` | Left-most tile X coordinate |
| `min_y` | `int` | Top-most tile Y coordinate |
| `max_x` | `int` | Right-most tile X coordinate |
| `max_y` | `int` | Bottom-most tile Y coordinate |
| `width` | `int` | `max_x - min_x + 1` (computed property) |
| `height` | `int` | `max_y - min_y + 1` (computed property) |

### Methods

#### `load_from_flat`

```python
load_from_flat(data: list[int], width: int, height: int) -> None
```

Populates the layer from a flat row-major list of raw GIDs (finite maps).

#### `load_from_chunks`

```python
load_from_chunks(chunks: list[dict]) -> None
```

Populates the layer from a list of chunk dicts (infinite maps).
Each chunk dict has keys: `x`, `y`, `width`, `height`, `data`.

#### `get_raw_gid`

```python
get_raw_gid(tx: int, ty: int) -> int
```

Returns the raw GID (including flip flags) at tile coordinates `(tx, ty)`,
or `0` if empty.

```python
raw = layer.get_raw_gid(5, 3)
real_gid, flags = decode_gid(raw)
```

#### `iter_tiles`

```python
iter_tiles() -> Iterator[tuple[int, int, int]]
```

Yields `(tile_x, tile_y, raw_gid)` for every non-empty tile.

```python
for tx, ty, raw_gid in layer.iter_tiles():
    real_gid, flags = decode_gid(raw_gid)
    ts = tmap.get_tileset_for_gid(real_gid)
```

---

## ObjectLayer

Represents a Tiled `<objectgroup>`. Contains a list of `TileObject` items.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Layer ID from TMX |
| `name` | `str` | Layer name |
| `visible` | `bool` | Visibility flag |
| `opacity` | `float` | 0.0–1.0 |
| `color` | `str \| None` | Layer color hex string |
| `objects` | `list[TileObject]` | All objects in this layer |
| `properties` | `dict` | Custom layer properties |

### Methods

#### `get_object`

```python
get_object(name: str) -> TileObject | None
```

Returns the first object matching `name`.

```python
spawn = tmap.get_layer("entities").get_object("player_spawn")
player_x, player_y = spawn.x, spawn.y
```

#### `get_objects_by_type`

```python
get_objects_by_type(type_: str) -> list[TileObject]
```

Returns all objects whose `type` (or `class` in Tiled 1.9+) matches.

```python
enemies = tmap.get_layer("entities").get_objects_by_type("enemy")
```

---

## TileObject

A single object from an `ObjectLayer`.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Unique object ID |
| `name` | `str` | Object name |
| `type` | `str` | Object type / class |
| `x` | `float` | X position in pixels |
| `y` | `float` | Y position in pixels |
| `width` | `float` | Width in pixels |
| `height` | `float` | Height in pixels |
| `rotation` | `float` | Rotation in degrees |
| `visible` | `bool` | Visibility flag |
| `properties` | `dict` | Custom object properties |
| `gid` | `int \| None` | Set if the object is a tile-object |

### Example — reading a spawn zone

```python
zone = tmap.get_layer("zones").get_object("danger_zone")
if zone:
    rect = pygame.Rect(zone.x, zone.y, zone.width, zone.height)
    if player_rect.colliderect(rect):
        player.take_damage(10)
```
