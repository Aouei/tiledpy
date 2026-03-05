# tiledpy

A Python library for loading Tiled `.tmx` maps, using **Pillow** for sprite
detection and **Pygame** for hardware-accelerated rendering with cached surfaces.

---

## Features

- Parse `.tmx` files (finite and infinite/chunked maps)
- Load external `.tsx` tilesets or inline definitions
- Encodings: CSV, Base64 + zlib / gzip / zstd
- Tile flip and rotation flags (`GID_FLIP_H/V/D`)
- Per-tile properties, collision objects, and animations
- Pillow-based sprite helpers: empty detection, dominant color
- Pygame `draw_layer()` with two-level surface cache (tile + scaled)
- Viewport culling — only draws tiles inside the screen

---

## Quick install

```bash
pip install -e ".[docs]"   # with docs extras
pip install -e .           # runtime only
```

---

## Minimal usage

```python
import pygame
from tiledpy import TiledMap

pygame.init()
screen = pygame.display.set_mode((800, 600))
clock  = pygame.time.Clock()

tmap = TiledMap("map.tmx")
cam_x, cam_y = 0, 0

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((0, 0, 0))
    tmap.draw_all_layers(screen, offset=(cam_x, cam_y))
    pygame.display.flip()
    clock.tick(60)
```

---

## High-level loading flow

```mermaid
flowchart TD
    A([TiledMap.__init__]) --> B[Parse &lt;map&gt; attributes]
    B --> C{Has tilesets?}
    C -- inline --> D[Parse inline tileset]
    C -- .tsx source --> E[Parse external TSX file]
    D --> F[Open spritesheet\nwith Pillow]
    E --> F
    F --> G[Tileset ready\nfirstgid · columns · tilecount]
    G --> H{More layers?}
    H -- tilelayer --> I[Decode data\nCSV / Base64]
    I --> J{Infinite map?}
    J -- yes --> K[load_from_chunks]
    J -- no --> L[load_from_flat]
    K --> M[TileLayer ready]
    L --> M
    H -- objectgroup --> N[Parse TileObject list]
    N --> O[ObjectLayer ready]
    M --> P{More layers?}
    O --> P
    P -- yes --> H
    P -- no --> Q([TiledMap ready])
```

---

## Package structure

```
tiledpy/
├── __init__.py      Public API exports
├── loader.py        TiledMap — parser + draw_layer()
├── tileset.py       Tileset — Pillow crop + pygame surface cache
├── layer.py         TileLayer · ObjectLayer · TileObject
└── renderer.py      draw_layer() with two-level global cache
```
