# Complete Pygame example

This guide walks through a working game loop that loads a Tiled map,
scrolls the camera, renders all layers, and plays tile animations.

---

## Prerequisites

```bash
pip install tiledpy pygame pillow
```

Project layout:

```
game/
├── main.py
├── map.tmx           (or map.tmj)
├── tileset.tsx       (optional external tileset)
└── sprites/
    └── tileset.png
```

---

## Loading a map

```python
from tiledpy import Parser

# TMX (XML) — classic Tiled format
tmap = Parser.load("map.tmx")

# TMJ / JSON — modern Tiled format
tmap = Parser.load("map.tmj")

# Inspect basic attributes
print(tmap.width, tmap.height)         # map size in tiles
print(tmap.tile_width, tmap.tile_height)  # tile size in pixels
print([l.name for l in tmap.layers])   # layer names in draw order
```

---

## Rendering all layers (static)

Use `render.draw_all_layers()` for the simplest full-map render.
It iterates all visible `TileLayer` instances in order, applies viewport
culling, and draws via a two-level surface cache.

```python
import pygame
from tiledpy import Parser
import tiledpy.map.render as render

pygame.init()
screen = pygame.display.set_mode((800, 600))
clock  = pygame.time.Clock()

tmap   = Parser.load("map.tmx")
scale  = 2
cam_x, cam_y = 0, 0

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((30, 30, 30))
    render.draw_all_layers(screen, tmap, offset=(cam_x, cam_y), scale=scale)
    pygame.display.flip()
    clock.tick(60)
```

---

## Rendering animated tiles

To play tile animations you must drive the render loop yourself using
`TileData.get_animated_surface(elapsed_ms, scale)`.
For static tiles it falls back to `get_surface()` automatically.

```python
import pygame
from tiledpy import Parser, TileLayer
from tiledpy.layer.tile import clear_tile_cache

pygame.init()
screen = pygame.display.set_mode((800, 600))
clock  = pygame.time.Clock()

tmap  = Parser.load("map.tmj")
scale = 3
cam_x, cam_y = 0, 0

scaled_tw = tmap.tile_width  * scale
scaled_th = tmap.tile_height * scale

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    t_ms = pygame.time.get_ticks()
    screen.fill((30, 30, 30))

    for layer in tmap.get_tile_layers():
        if not layer.visible:
            continue
        for tile in layer.iter_tiles():
            # Returns current animation frame, or static surface if not animated
            surf = tile.get_animated_surface(t_ms, scale)

            px = tile.tx * scaled_tw - cam_x + int(layer.offset_x * scale)
            # Bottom-anchor: aligns tall sprites to the bottom of the cell
            py = (tile.ty * scaled_th - cam_y
                  + int(layer.offset_y * scale)
                  + scaled_th - surf.get_height())

            # Viewport culling
            if px + surf.get_width() < 0 or px > screen.get_width():
                continue
            if py + surf.get_height() < 0 or py > screen.get_height():
                continue

            screen.blit(surf, (px, py))

    pygame.display.flip()
    clock.tick(60)
```

---

## Static surface for a single tile

`TileData.get_surface(scale)` returns the tile's pygame surface at the
requested scale. Flip flags are applied automatically.

```python
layer = tmap.get_layer("ground")
tile  = layer.get_tile(tx=4, ty=3)

if tile is not None:
    surf = tile.get_surface(scale=2)
    screen.blit(surf, (tile.tx * 32, tile.ty * 32))
```

---

## Zoom in / out

When the scale changes, clear the surface caches to free stale entries.

```python
from tiledpy.layer.tile import clear_tile_cache
import tiledpy.map.render as render

# Zoom in (+) or out (-)
new_scale = max(1, min(scale + 1, 6))
if new_scale != scale:
    scale = new_scale
    render.clear_cache()      # clears render module caches
    clear_tile_cache()        # clears TileData scaled cache
```

---

## Full example with camera + zoom + debug overlay

```python
"""
main.py — tiledpy full example with camera, zoom, and debug.

Controls:
    Arrow keys / WASD   Scroll camera
    + / -               Zoom in / out (scale 1–6)
    D                   Toggle debug overlay
    ESC / Q             Quit
"""

import sys
import pygame
from tiledpy import Parser, TileMap
import tiledpy.map.render as render


class Camera:
    def __init__(self, map_pixel_w: int, map_pixel_h: int,
                 screen_w: int, screen_h: int) -> None:
        self.x, self.y = 0, 0
        self.map_w, self.map_h = map_pixel_w, map_pixel_h
        self.screen_w, self.screen_h = screen_w, screen_h

    def move(self, dx: int, dy: int) -> None:
        self.x = max(0, min(self.x + dx, max(0, self.map_w - self.screen_w)))
        self.y = max(0, min(self.y + dy, max(0, self.map_h - self.screen_h)))

    @property
    def offset(self) -> tuple[int, int]:
        return self.x, self.y


def draw_debug(screen, tmap, camera, clock, scale, font):
    stats = render.cache_stats()
    lines = [
        f"FPS: {clock.get_fps():.0f}",
        f"Camera: ({camera.x}, {camera.y})",
        f"Scale: {scale}x",
        f"Map: {tmap.width}x{tmap.height} tiles",
        f"Tile size: {tmap.tile_width}x{tmap.tile_height}px",
        f"Layers: {len(tmap.layers)}",
        f"Tilesets: {len(tmap.tilesets)}",
        f"Surface cache: {stats['tile_surfaces']} entries",
        f"Scaled cache:  {stats['scaled_surfaces']} entries",
    ]
    for i, line in enumerate(lines):
        screen.blit(font.render(line, True, (0,   0,   0)),   (11, 11 + i * 18))
        screen.blit(font.render(line, True, (255, 255, 200)), (10, 10 + i * 18))


def main(map_path: str) -> None:
    pygame.init()
    pygame.display.set_caption("tiledpy demo")

    SCREEN_W, SCREEN_H = 800, 600
    SCROLL_SPEED = 4
    INITIAL_SCALE = 2

    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()
    font   = pygame.font.SysFont("monospace", 14)

    tmap  = Parser.load(map_path)
    scale = INITIAL_SCALE

    def make_camera():
        return Camera(
            tmap.width  * tmap.tile_width  * scale,
            tmap.height * tmap.tile_height * scale,
            SCREEN_W, SCREEN_H,
        )

    camera = make_camera()

    if tmap.background_color:
        hex_color = tmap.background_color.lstrip("#")
        bg_color  = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    else:
        bg_color = (30, 30, 30)

    show_debug = False

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_d:
                    show_debug = not show_debug
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    new = min(scale + 1, 6)
                    if new != scale:
                        scale = new
                        render.clear_cache()
                        camera = make_camera()
                elif event.key == pygame.K_MINUS:
                    new = max(scale - 1, 1)
                    if new != scale:
                        scale = new
                        render.clear_cache()
                        camera = make_camera()

        keys = pygame.key.get_pressed()
        dx = dy = 0
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx -= SCROLL_SPEED * scale
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += SCROLL_SPEED * scale
        if keys[pygame.K_UP]    or keys[pygame.K_w]: dy -= SCROLL_SPEED * scale
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += SCROLL_SPEED * scale
        camera.move(dx, dy)

        screen.fill(bg_color)
        render.draw_all_layers(screen, tmap, offset=camera.offset, scale=scale)

        if show_debug:
            draw_debug(screen, tmap, camera, clock, scale, font)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "map.tmx"
    main(path)
```

---

## Controls reference

| Key | Action |
|-----|--------|
| Arrow keys / WASD | Scroll camera |
| `+` / `-` | Zoom in / out (integer scale 1–6) |
| `D` | Toggle debug overlay |
| `ESC` / `Q` | Quit |

---

## Querying layers

```python
# All tile layers in draw order
tile_layers = tmap.get_tile_layers()

# All object layers
object_layers = tmap.get_object_layers()

# Layer by name (returns TileLayer or ObjectLayer)
ground = tmap.get_layer("ground")
```

---

## Reading object layers

```python
entities = tmap.get_layer("entities")

# Find the player spawn point
spawn = entities.get_object("player_spawn")
if spawn:
    player_x = spawn.x
    player_y = spawn.y

# Iterate enemies (object_class set in Tiled)
for obj in entities.get_objects_by_class("enemy"):
    enemy_list.append(Enemy(obj.x, obj.y, obj.properties))

# Width/height accept a scale parameter
w = obj.width(scale=2)
h = obj.height(scale=2)
```

---

## Collision detection using tile properties

```python
collision = tmap.get_layer("collision")

def tile_is_solid(tx: int, ty: int) -> bool:
    td = collision.get_tile(tx, ty)
    return bool(td and td.properties.get("collision", False))

# Check if the player's feet are on a solid tile
foot_x, foot_y = player_rect.midbottom
tx, ty = tmap.world_to_tile(foot_x + cam_x, foot_y + cam_y, scale=scale)
if tile_is_solid(tx, ty):
    player.on_ground = True
```

---

## Filtering tiles by class or property

```python
layer = tmap.get_layer("hazards")

# All tiles whose Tiled class is "spike"
spikes = layer.get_tiles_by_class("spike")

# All tiles with a custom bool property "lethal" = True
lethal = layer.get_tiles_by_property("lethal", True)

# All tiles that have a "damage" property (any value)
damaging = layer.get_tiles_by_property("damage")

# All animated tiles on a layer (unique by local_id)
animated = layer.get_animated_tiles()
for tile in animated:
    print(f"  ({tile.tx},{tile.ty}) frames={len(tile.meta.animation)}")
```

---

## Coordinate conversion

```python
from tiledpy import OFFSET

# World pixel → tile
tx, ty = tmap.world_to_tile(mouse_x + cam_x, mouse_y + cam_y, scale=2)

# Tile → world pixel (top-left of cell)
wx, wy = tmap.tile_to_world(tx, ty, scale=2)
screen.blit(highlight, (wx - cam_x, wy - cam_y))

# Center anchor
cx, cy = tmap.tile_to_world(tx, ty, scale=2, offset=OFFSET.CENTER)
```

Available `OFFSET` values: `LEFT_TOP`, `MIDDLE_TOP`, `RIGHT_TOP`,
`LEFT_MIDDLE`, `CENTER`, `RIGHT_MIDDLE`, `LEFT_BOTTOM`, `MIDDLE_BOTTOM`,
`RIGHT_BOTTOM`.

---

## Inspect sprite data with Pillow

```python
layer = tmap.get_layer("decorations")

seen = set()
for tile in layer.iter_tiles():
    key = (tile.tileset.firstgid, tile.local_id)
    if key in seen:
        continue
    seen.add(key)
    r, g, b = tile.tileset.get_dominant_color(tile.local_id)
    print(f"({tile.tx},{tile.ty}) local_id={tile.local_id} → rgb({r},{g},{b})")
```
