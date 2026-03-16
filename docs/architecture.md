# Architecture

## Package overview

```
tiledpy/
├── __init__.py               Public API — re-exports everything below
├── map/
│   ├── map.py                TileMap (pure data model) + OFFSET enum
│   ├── parser.py             Parser — file → TileMap (XML and JSON)
│   └── render.py             Pygame rendering + global surface caches
└── layer/
    ├── tileset.py            Tileset, TileMeta, TileFlags, decode_gid
    ├── tile.py               TileData (positioned tile), TileLayer
    └── object.py             TileObject, ObjectLayer
```

Each module has a single responsibility:

| Module | Responsibility |
|--------|---------------|
| `map/parser.py` | Parse `.tmx` / `.tmj` files into data structures |
| `map/map.py` | Data model: dimensions, layers, tilesets, coordinate helpers |
| `map/render.py` | Pygame rendering with viewport culling and surface caches |
| `layer/tileset.py` | Spritesheet cropping (Pillow) + pygame surface cache |
| `layer/tile.py` | Positioned tile with `get_surface()` / `get_animated_surface()` |
| `layer/object.py` | Tiled objects (spawn points, triggers, hitboxes) |

---

## Class diagram

```mermaid
classDiagram
    class Parser {
        <<static>>
        +load(path) TileMap
        -_parse_xml(path) TileMap
        -_parse_json(path) TileMap
        -_parse_tsx(firstgid, path) Tileset
        -_parse_tile_layer(data) TileLayer
        -_parse_object_layer(data) ObjectLayer
    }

    class TileMap {
        +int width
        +int height
        +int tile_width
        +int tile_height
        +str orientation
        +bool infinite
        +str background_color
        +dict properties
        +list~Tileset~ tilesets
        +list layers
        +get_layer(name) LayerType
        +get_tile_layers() list~TileLayer~
        +get_object_layers() list~ObjectLayer~
        +world_to_tile(x, y, scale, offset) tuple
        +tile_to_world(tx, ty, scale, offset) tuple
    }

    class OFFSET {
        <<enum>>
        LEFT_TOP
        MIDDLE_TOP
        RIGHT_TOP
        LEFT_MIDDLE
        CENTER
        RIGHT_MIDDLE
        LEFT_BOTTOM
        MIDDLE_BOTTOM
        RIGHT_BOTTOM
    }

    class render {
        <<module>>
        -dict _surface_cache
        -dict _scaled_cache
        +draw_layer(surface, layer, tw, th, offset, scale)
        +draw_all_layers(surface, tilemap, offset, scale)
        +clear_cache()
        +cache_stats() dict
    }

    class Tileset {
        +str name
        +int firstgid
        +int tile_width
        +int tile_height
        +int columns
        +int tilecount
        +int spacing
        +int margin
        +dict~int,TileMeta~ tile_data
        -Image _sheet
        -dict _pil_cache
        -dict _pygame_cache
        +get_tile_image(local_id) Image
        +get_pygame_surface(local_id, flags) Surface
        +is_empty_tile(local_id) bool
        +get_dominant_color(local_id) tuple
        +contains_gid(gid) bool
        +global_to_local(gid) int
        +clear_pygame_cache()
    }

    class TileMeta {
        +int local_id
        +str tile_class
        +dict properties
        +list collision_objects
        +list animation
        +int width
        +int height
    }

    class TileFlags {
        +bool flip_h
        +bool flip_v
        +bool flip_d
    }

    class TileData {
        +int tx
        +int ty
        +int local_id
        +Tileset tileset
        +bool flip_h
        +bool flip_v
        +bool flip_d
        +meta TileMeta
        +is_animated bool
        +tile_class str
        +properties dict
        +collision_objects list
        +width(scale) int
        +height(scale) int
        +get_surface(scale) Surface
        +get_animated_surface(elapsed_ms, scale) Surface
    }

    class TileLayer {
        +int id
        +str name
        +bool visible
        +float opacity
        +float offset_x
        +float offset_y
        +dict properties
        -dict _data
        +load_from_flat(data, w, h)
        +load_from_chunks(chunks)
        +get_raw_gid(tx, ty) int
        +get_tile(tx, ty) TileData
        +iter_tiles() Iterator~TileData~
        +get_tiles_by_class(cls) list
        +get_tiles_by_property(prop, value) list
        +get_animated_tiles() list
    }

    class ObjectLayer {
        +int id
        +str name
        +bool visible
        +float opacity
        +str color
        +list~TileObject~ objects
        +dict properties
        +get_object(name) TileObject
        +get_objects_by_class(cls) list
    }

    class TileObject {
        +int id
        +str name
        +str object_class
        +float x
        +float y
        +float rotation
        +bool visible
        +dict properties
        +int gid
        +width(scale) float
        +height(scale) float
    }

    Parser ..> TileMap : creates
    Parser ..> Tileset : creates
    Parser ..> TileLayer : creates
    Parser ..> ObjectLayer : creates
    TileMap "1" --> "0..*" Tileset : tilesets
    TileMap "1" --> "0..*" TileLayer : layers
    TileMap "1" --> "0..*" ObjectLayer : layers
    TileMap ..> OFFSET : world_to_tile / tile_to_world
    render ..> TileLayer : reads _data
    render ..> Tileset : get_pygame_surface
    TileLayer "0..*" --> "0..*" Tileset : _tilesets
    TileLayer ..> TileData : iter_tiles / get_tile
    Tileset "1" --> "0..*" TileMeta : tile_data
    TileData --> Tileset : tileset
    TileData ..> TileMeta : meta (delegated)
    TileData ..> TileFlags : _flags()
    ObjectLayer "1" --> "0..*" TileObject : objects
```

---

## GID decoding

```mermaid
flowchart LR
    A[raw GID\n32-bit int] --> B[decode_gid]
    B --> C[real_gid\nbits 0–28]
    B --> D[TileFlags\nflip_h · flip_v · flip_d]

    C --> E{Cache hit?}
    E -- yes --> F[pygame.Surface]
    E -- no --> G[_find_tileset\nbinary search]
    G --> H[global_to_local\ngid - firstgid]
    H --> I[Tileset._crop_tile\nPillow crop]
    I --> J{Flags?}
    J -- flip/rotate --> K[PIL.Image.transpose]
    J -- none --> L[PIL.tobytes]
    K --> L
    L --> M[pygame.image.fromstring\n.convert_alpha]
    M --> N[store in _surface_cache]
    N --> F
```

---

## Cache architecture

Four cache levels from slowest (miss) to fastest (hit):

```mermaid
flowchart TD
    subgraph "render.py — global, shared across all layers"
        SC["_surface_cache\n(firstgid, local_id, fh, fv, fd)\n→ pygame.Surface"]
        KC["_scaled_cache\n(id surf, scale)\n→ pygame.Surface (scaled)"]
    end

    subgraph "tile.py — module-level, used by TileData"
        DC["_scaled_cache\n(id surf, scale)\n→ pygame.Surface (scaled)"]
    end

    subgraph "Tileset._pygame_cache — per instance"
        TC["(local_id, fh, fv, fd)\n→ pygame.Surface"]
    end

    subgraph "Tileset._pil_cache — per instance"
        PC["local_id\n→ PIL.Image"]
    end

    R1[render.draw_layer] --> SC
    SC -- miss --> TC
    TC -- miss --> PC
    PC -- miss --> CROP[Pillow crop\nfrom spritesheet]
    CROP --> PC
    SC -- scale != 1 --> KC

    R2[TileData.get_surface\nor get_animated_surface] --> TC
    TC -- miss --> PC
    R2 -- scale != 1 --> DC
```

| Cache | Cleared by |
|-------|-----------|
| `render._surface_cache` | `render.clear_cache()` |
| `render._scaled_cache` | `render.clear_cache()` |
| `tile._scaled_cache` | `clear_tile_cache()` |
| `Tileset._pil_cache` | persists for life of the Tileset |
| `Tileset._pygame_cache` | `tileset.clear_pygame_cache()` |
