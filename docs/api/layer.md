# Layers

tiledpy has two layer types: `TileLayer` for tile data and `ObjectLayer`
for vector objects (spawn points, hitboxes, triggers, etc.).

---

## TileLayer

Stores tiles as a sparse dict `{(tx, ty): raw_gid}` — empty cells consume
no memory. Supports both finite (flat array) and infinite (chunk-based) maps.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Unique layer ID |
| `name` | `str` | Layer name |
| `visible` | `bool` | Visibility flag |
| `opacity` | `float` | Layer opacity 0.0–1.0 |
| `offset_x` | `float` | Horizontal pixel offset |
| `offset_y` | `float` | Vertical pixel offset |
| `properties` | `dict` | Custom layer properties |
| `width` | `int` | Layer width in tiles (computed from bounds) |
| `height` | `int` | Layer height in tiles (computed from bounds) |

### Iterating tiles

```python
layer = tmap.get_layer("ground")

# Iterate all non-empty tiles as TileData objects
for tile in layer.iter_tiles():
    print(tile.tx, tile.ty, tile.tile_class)
    surf = tile.get_surface(scale=2)
    surf = tile.get_animated_surface(elapsed_ms, scale=2)
```

### Getting a single tile

```python
tile = layer.get_tile(tx=4, ty=3)   # → TileData | None
raw  = layer.get_raw_gid(tx=4, ty=3)  # → int (0 if empty)
```

### Filtering

```python
# By Tiled class
spikes  = layer.get_tiles_by_class("spike")

# By custom property name (any value)
damaged = layer.get_tiles_by_property("damage")

# By custom property name and value
solid   = layer.get_tiles_by_property("collision", True)

# All animated tiles (unique by tileset + local_id)
animated = layer.get_animated_tiles()
```

---

## TileData

A tile **placed at tile coordinates `(tx, ty)`** in a layer.
Wraps the underlying `Tileset` and exposes surface helpers directly.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `tx` | `int` | Tile column |
| `ty` | `int` | Tile row |
| `local_id` | `int` | Zero-based index within `tileset` |
| `tileset` | `Tileset` | Owning tileset |
| `flip_h` | `bool` | Horizontal flip flag |
| `flip_v` | `bool` | Vertical flip flag |
| `flip_d` | `bool` | Diagonal flip (90° rotation) |
| `meta` | `TileMeta \| None` | Raw TSX metadata, or None |
| `is_animated` | `bool` | True if the tile has animation frames |
| `tile_class` | `str` | Tiled class attribute |
| `properties` | `dict` | Custom properties |
| `collision_objects` | `list[dict]` | Collision rectangles |

### Size helpers

```python
w = tile.width(scale=2)    # → int: tile_width  * scale
h = tile.height(scale=2)   # → int: tile_height * scale
```

### Surface helpers

```python
# Static surface — uses Tileset pygame cache + module _scaled_cache
surf = tile.get_surface(scale=2)

# Animated surface — resolves frame from elapsed_ms % total_duration
# Falls back to get_surface() if tile has no animation
t_ms = pygame.time.get_ticks()
surf = tile.get_animated_surface(t_ms, scale=2)
```

### Typical game-loop usage

```python
t_ms      = pygame.time.get_ticks()
scaled_tw = tmap.tile_width  * scale
scaled_th = tmap.tile_height * scale

for layer in tmap.get_tile_layers():
    if not layer.visible:
        continue
    for tile in layer.iter_tiles():
        surf = tile.get_animated_surface(t_ms, scale)
        px   = tile.tx * scaled_tw - cam_x
        py   = tile.ty * scaled_th - cam_y + scaled_th - surf.get_height()
        screen.blit(surf, (px, py))
```

---

## ObjectLayer

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Unique layer ID |
| `name` | `str` | Layer name |
| `visible` | `bool` | Visibility flag |
| `opacity` | `float` | Layer opacity |
| `color` | `str \| None` | Tiled color hint |
| `objects` | `list[TileObject]` | All objects in the layer |
| `properties` | `dict` | Custom layer properties |

### Querying objects

```python
entities = tmap.get_layer("entities")

# Single object by name
spawn = entities.get_object("player_spawn")

# All objects with a given class
for enemy in entities.get_objects_by_class("enemy"):
    print(enemy.x, enemy.y, enemy.properties)
```

---

## TileObject

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `int` | Unique object ID |
| `name` | `str` | Object name |
| `object_class` | `str` | Object class (Tiled 1.9+) |
| `x` | `float` | X position in pixels (scale 1) |
| `y` | `float` | Y position in pixels (scale 1) |
| `rotation` | `float` | Clockwise rotation in degrees |
| `visible` | `bool` | Visibility flag |
| `properties` | `dict` | Custom properties |
| `gid` | `int \| None` | Tile GID if this is a tile-object |

### Size helpers

```python
# Accepts a scale parameter — multiply _width / _height internally
w = obj.width(scale=2)    # → float
h = obj.height(scale=2)   # → float
```

### Example

```python
for obj in tmap.get_layer("triggers").objects:
    rect = pygame.Rect(
        obj.x * scale, obj.y * scale,
        obj.width(scale), obj.height(scale),
    )
    if player_rect.colliderect(rect):
        trigger_event(obj.name, obj.properties)
```
