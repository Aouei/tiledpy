# Tileset

`Tileset` loads a spritesheet image with Pillow, crops individual tile sprites,
and converts them to `pygame.Surface` objects with a two-level cache (PIL + pygame).

You rarely construct a `Tileset` manually — `Parser.load()` builds them from
the `.tmx` / `.tmj` / `.tsx` file automatically.

---

## Tileset

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Tileset name |
| `firstgid` | `int` | First global tile ID |
| `tile_width` | `int` | Width of each tile in pixels |
| `tile_height` | `int` | Height of each tile in pixels |
| `columns` | `int` | Number of tile columns in the spritesheet |
| `tilecount` | `int` | Total number of tiles |
| `spacing` | `int` | Pixels between adjacent tiles |
| `margin` | `int` | Pixels around the sheet edge |
| `tile_data` | `dict[int, TileMeta]` | Per-tile metadata keyed by local ID |

### Pygame surface

```python
from tiledpy.layer.tileset import TileFlags

flags = TileFlags(flip_h=True, flip_v=False, flip_d=False)

# Returns a cached pygame.Surface with flip/rotation applied
surf = tileset.get_pygame_surface(local_id=3, flags=flags)

# Clear pygame surface cache (call after scale changes)
tileset.clear_pygame_cache()
```

### PIL helpers

```python
# RGBA crop of the tile (cached)
img = tileset.get_tile_image(local_id=3)

# True if every pixel is fully transparent
empty = tileset.is_empty_tile(local_id=3)

# Average RGB of non-transparent pixels
r, g, b = tileset.get_dominant_color(local_id=3)
```

### GID utilities

```python
tileset.contains_gid(gid=42)      # → bool: firstgid <= gid < firstgid + tilecount
tileset.global_to_local(gid=42)   # → int: gid - firstgid
```

---

## TileMeta

Per-tile metadata parsed from a TSX `<tile>` element.
Accessed via `TileData.meta`.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `local_id` | `int` | Zero-based local tile ID |
| `tile_class` | `str` | Tiled `class` attribute |
| `properties` | `dict` | Custom properties |
| `collision_objects` | `list[dict]` | Collision rects: `[{x, y, width, height}, ...]` |
| `animation` | `list[dict]` | Animation frames: `[{tileid, duration}, ...]` (duration in ms) |
| `width` | `int \| None` | Override tile width (None = use tileset default) |
| `height` | `int \| None` | Override tile height (None = use tileset default) |

### Example

```python
tile = tmap.get_layer("ground").get_tile(tx=2, ty=3)
if tile and tile.meta:
    print(tile.meta.tile_class)         # e.g. "ground_wet"
    print(tile.meta.properties)         # custom props dict
    print(tile.meta.collision_objects)  # list of rects
    for frame in tile.meta.animation:
        print(frame["tileid"], frame["duration"])
```

---

## TileFlags

Flip and rotation flags decoded from the upper 3 bits of a raw Tiled GID.

| Field | Bit | Description |
|-------|-----|-------------|
| `flip_h` | `0x80000000` | Horizontal flip |
| `flip_v` | `0x40000000` | Vertical flip |
| `flip_d` | `0x20000000` | Diagonal flip (used for 90° rotation) |

```python
from tiledpy.layer.tileset import TileFlags

flags = TileFlags(flip_h=True, flip_v=False, flip_d=False)
```

---

## decode_gid

Separates the real GID from Tiled's flip/rotation flag bits.

```python
from tiledpy.layer.tileset import decode_gid

real_gid, flags = decode_gid(raw_gid)
# real_gid = raw_gid & 0x1FFFFFFF
# flags.flip_h, flags.flip_v, flags.flip_d = upper 3 bits
```

### GID encoding constants

```python
from tiledpy.layer.tileset import GID_FLIP_H, GID_FLIP_V, GID_FLIP_D, GID_MASK
# GID_FLIP_H = 0x80000000
# GID_FLIP_V = 0x40000000
# GID_FLIP_D = 0x20000000
# GID_MASK   = 0x1FFFFFFF
```
