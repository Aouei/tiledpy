# Tileset

`tiledpy.Tileset` loads a spritesheet image with Pillow, crops individual tile
sprites, and converts them to `pygame.Surface` objects with a two-level cache.

---

## Constructor

```python
Tileset(
    name: str,
    firstgid: int,
    image_path: str,
    tile_width: int,
    tile_height: int,
    columns: int,
    tilecount: int,
    spacing: int = 0,
    margin: int = 0,
    tile_data: dict[int, TileData] | None = None,
)
```

You rarely need to construct a `Tileset` manually — `TiledMap` builds them
automatically from the `.tmx` / `.tsx` file.

---

## Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Tileset name from the TMX/TSX |
| `firstgid` | `int` | First global tile ID of this tileset |
| `tile_width` | `int` | Width of each tile in pixels |
| `tile_height` | `int` | Height of each tile in pixels |
| `columns` | `int` | Number of columns in the spritesheet |
| `tilecount` | `int` | Total number of tiles |
| `spacing` | `int` | Pixels between tiles |
| `margin` | `int` | Pixels around the edges of the sheet |
| `tile_data` | `dict[int, TileData]` | Per-tile metadata keyed by local ID |

---

## Pillow methods

### `get_tile_image`

```python
get_tile_image(local_id: int) -> PIL.Image.Image
```

Returns the RGBA crop of the tile at `local_id` (0-based).
Result is cached in `_pil_cache` — subsequent calls are free.

```python
img = ts.get_tile_image(3)
img.save("tile_3.png")
```

---

### `is_empty_tile`

```python
is_empty_tile(local_id: int) -> bool
```

Returns `True` if every pixel in the tile is fully transparent (alpha = 0).
Useful for skipping decoration layers that use transparency as "no tile".

```python
if ts.is_empty_tile(local_id):
    continue
```

---

### `get_dominant_color`

```python
get_dominant_color(local_id: int) -> tuple[int, int, int]
```

Computes the average RGB of all non-transparent pixels.
Returns `(0, 0, 0)` if the tile is empty.

```python
r, g, b = ts.get_dominant_color(5)
print(f"Dominant: rgb({r},{g},{b})")
```

---

## Pygame methods

### `get_pygame_surface`

```python
get_pygame_surface(
    local_id: int,
    flags: TileFlags | None = None,
) -> pygame.Surface
```

Returns a `pygame.Surface` with `convert_alpha()` applied.
Applies flip / rotation from `flags` (derived from `decode_gid`).
Result is cached in `_pygame_cache` — subsequent calls are instant.

```python
surf = ts.get_pygame_surface(local_id, flags)
screen.blit(surf, (x, y))
```

---

### `clear_pygame_cache`

```python
clear_pygame_cache() -> None
```

Clears the per-instance pygame surface cache. Call when you resize the window
or change the scale factor.

---

## Utility methods

### `contains_gid`

```python
contains_gid(gid: int) -> bool
```

Returns `True` if `firstgid <= gid < firstgid + tilecount`.

---

### `global_to_local`

```python
global_to_local(gid: int) -> int
```

Converts a global GID to a local (0-based) tile ID: `gid - firstgid`.

---

## TileFlags

```python
from tiledpy.tileset import TileFlags, decode_gid

real_gid, flags = decode_gid(raw_gid)
# flags.flip_h  → bool
# flags.flip_v  → bool
# flags.flip_d  → bool (diagonal = 90° rotation)
```

| Flag | Hex mask | Description |
|------|----------|-------------|
| `flip_h` | `0x80000000` | Horizontal flip |
| `flip_v` | `0x40000000` | Vertical flip |
| `flip_d` | `0x20000000` | Diagonal (transpose + flip for 90° rotation) |

---

## TileData

Per-tile metadata parsed from TSX `<tile>` elements.

```python
td = ts.tile_data.get(local_id)
if td:
    print(td.properties)          # {"collision": True, ...}
    print(td.collision_objects)   # [{"x":1,"y":3,"width":14,"height":12}]
    print(td.animation)           # [{"tileid":0,"duration":200}, ...]
```
