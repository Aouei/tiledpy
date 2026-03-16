# tiledpy

A Python library for loading [Tiled](https://www.mapeditor.org/) maps (`.tmx` / `.tmj`),
using **Pillow** for sprite extraction and **Pygame** for hardware-accelerated rendering
with multi-level surface caching.

---

## Features

- Parse `.tmx` (XML) and `.tmj` / `.json` (JSON) map files
- Finite and infinite/chunked maps
- Encodings: CSV, Base64 + zlib / gzip / zstd
- External `.tsx` tilesets and inline definitions
- Tile flip and rotation flags (`flip_h`, `flip_v`, `flip_d`)
- Per-tile class, properties, collision objects, and animations
- `TileData.get_surface(scale)` — static tile surface with scale cache
- `TileData.get_animated_surface(elapsed_ms, scale)` — animated tile surface
- `render.draw_all_layers()` with viewport culling and two-level global cache
- Pillow helpers: `is_empty_tile()`, `get_dominant_color()`

---

## Install

```bash
pip install -e .           # runtime only
pip install -e ".[docs]"   # with MkDocs extras
```

---

## Quick start

```python
import pygame
from tiledpy import Parser, TileMap
import tiledpy.map.render as render

pygame.init()
screen = pygame.display.set_mode((800, 600))
clock  = pygame.time.Clock()

tmap   = Parser.load("map.tmx")   # also accepts .tmj / .json
cam_x, cam_y = 0, 0

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((0, 0, 0))
    render.draw_all_layers(screen, tmap, offset=(cam_x, cam_y), scale=2)
    pygame.display.flip()
    clock.tick(60)
```

---

## Animated tiles

```python
t_ms = pygame.time.get_ticks()

for layer in tmap.get_tile_layers():
    for tile in layer.iter_tiles():
        surf = tile.get_animated_surface(t_ms, scale=2)
        px   = tile.tx * tmap.tile_width  * 2
        py   = tile.ty * tmap.tile_height * 2
        screen.blit(surf, (px, py))
```

---

## Package structure

```
tiledpy/
├── __init__.py               Public API
├── map/
│   ├── map.py                TileMap (data model) + OFFSET enum
│   ├── parser.py             Parser.load(path) → TileMap
│   └── render.py             draw_layer / draw_all_layers / clear_cache
└── layer/
    ├── tileset.py            Tileset, TileMeta, TileFlags, decode_gid
    ├── tile.py               TileData (positioned tile), TileLayer
    └── object.py             TileObject, ObjectLayer
```

---

## Documentation

Full docs in [`docs/`](docs/index.md).
