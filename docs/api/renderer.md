# Renderer

`tiledpy.map.render` is a module-level rendering system for Pygame.
It maintains two global caches that persist across frames:

| Cache | Key | Value |
|-------|-----|-------|
| `_surface_cache` | `(firstgid, local_id, flip_h, flip_v, flip_d)` | `pygame.Surface` |
| `_scaled_cache` | `(id(surf), scale)` | `pygame.Surface` (scaled) |

Import the module directly — it is not a class:

```python
import tiledpy.map.render as render
```

---

## draw_all_layers

Render all visible `TileLayer` instances in draw order.

```python
render.draw_all_layers(screen, tmap, offset=(cam_x, cam_y), scale=2)
```

Parameters:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `surface` | `pygame.Surface` | — | Render target |
| `tilemap` | `TileMap` | — | The map to draw |
| `offset` | `tuple[int, int]` | `(0, 0)` | Camera offset in pixels |
| `scale` | `float` | `1.0` | Render scale factor |

---

## draw_layer

Render a single `TileLayer` with viewport culling.

```python
render.draw_layer(screen, layer,
                  tmap.tile_width, tmap.tile_height,
                  offset=(cam_x, cam_y), scale=2)
```

Parameters:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `surface` | `pygame.Surface` | — | Render target |
| `layer` | `TileLayer` | — | The tile layer to draw |
| `tile_width` | `int` | — | Base tile width in pixels |
| `tile_height` | `int` | — | Base tile height in pixels |
| `offset` | `tuple[int, int]` | `(0, 0)` | Camera offset |
| `scale` | `float` | `1.0` | Render scale factor |

### Tile anchor

Tiles are drawn **bottom-aligned** within their cell:

```
py = ty * scaled_th - oy + scaled_th - actual_h
```

This matches Tiled's behaviour for tall sprites (sprites taller than one tile
extend upward from the cell's bottom edge).

### Opacity

If `layer.opacity < 1.0`, a per-blit surface copy is made for each visible
tile (one allocation per tile per frame). Keep opacity at `1.0` for
performance-critical layers.

---

## clear_cache

Clear both global caches. Call this when the scale changes or a new map is
loaded.

```python
render.clear_cache()
```

---

## cache_stats

Return current cache entry counts for debugging.

```python
stats = render.cache_stats()
# → {"tile_surfaces": int, "scaled_surfaces": int}

print(f"Tile surfaces cached: {stats['tile_surfaces']}")
print(f"Scaled surfaces cached: {stats['scaled_surfaces']}")
```

---

## Performance tips

```mermaid
flowchart LR
    A[First frame] --> B[Cache miss\nPillow crop + pygame convert]
    B --> C[Stored in _surface_cache]
    C --> D[Subsequent frames]
    D --> E[Cache hit\nO(1) dict lookup]
    E --> F[surface.blit]
```

- Keep `scale` constant across frames — changing it requires `clear_cache()`
  to free stale scaled entries.
- Use `layer.visible = False` instead of conditional `draw_layer()` calls
  — the layer is simply skipped in the iteration.
- For very large maps, the number of cache entries equals the number of
  **unique** `(tileset, local_id, flip flags)` combinations — not the total
  tile count.
- For animated tiles, use `TileData.get_animated_surface()` in a custom loop
  instead of `draw_all_layers()`, which only draws the static tile.

---

## Mixing render module and TileData

You can combine both approaches in the same game loop:

```python
t_ms = pygame.time.get_ticks()

# Use render module for static background layers (fast, cached)
render.draw_layer(screen, ground_layer,
                  tmap.tile_width, tmap.tile_height,
                  offset=camera.offset, scale=scale)

# Draw player here

# Use TileData.get_animated_surface for animated foreground
for tile in animated_layer.iter_tiles():
    surf = tile.get_animated_surface(t_ms, scale)
    px   = tile.tx * tmap.tile_width  * scale - camera.x
    py   = tile.ty * tmap.tile_height * scale - camera.y
    screen.blit(surf, (px, py))
```
