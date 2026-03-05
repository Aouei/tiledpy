# Interaction diagrams

## Loading a TMX map

Sequence from `TiledMap("map.tmx")` to the moment it's ready to render.

```mermaid
sequenceDiagram
    actor User
    participant TM as TiledMap
    participant ET as xml.etree
    participant TS as Tileset
    participant PIL as Pillow (Image)
    participant TL as TileLayer
    participant OL as ObjectLayer

    User->>TM: TiledMap("map.tmx")
    activate TM
    TM->>ET: ET.parse("map.tmx")
    ET-->>TM: root Element

    loop for each <tileset> in root
        alt source=".tsx"
            TM->>ET: ET.parse("tileset.tsx")
            ET-->>TM: tsx root Element
        end
        TM->>PIL: Image.open(image_path).convert("RGBA")
        PIL-->>TM: spritesheet Image
        TM->>TS: Tileset(name, firstgid, sheet, ...)
        TS-->>TM: Tileset instance
    end

    loop for each layer in root
        alt tag == "layer"
            TM->>TL: TileLayer(id, name, ...)
            TM->>TM: _decode_data(encoding, compression)
            alt infinite map
                TM->>TL: load_from_chunks(chunks)
            else finite map
                TM->>TL: load_from_flat(data, w, h)
            end
            TL-->>TM: TileLayer ready
        else tag == "objectgroup"
            TM->>OL: ObjectLayer(id, name, objects, ...)
            OL-->>TM: ObjectLayer ready
        end
    end

    TM-->>User: TiledMap ready
    deactivate TM
```

---

## draw_layer() — one frame

Full call chain from `tmap.draw_layer(screen, "ground")` down to `surface.blit`.

```mermaid
sequenceDiagram
    actor User
    participant TM as TiledMap
    participant R as renderer
    participant RC as _surface_cache (dict)
    participant TS as Tileset
    participant PIL as Pillow (Image)
    participant PG as pygame

    User->>TM: draw_layer(screen, "ground", offset)
    TM->>R: draw_layer(surface, layer, tilesets, ...)

    loop for each (tx, ty, raw_gid) in layer.iter_tiles()
        R->>R: culling check (viewport bounds)
        alt tile outside viewport
            R-->>R: skip
        else tile inside viewport
            R->>R: decode_gid(raw_gid) → real_gid, TileFlags
            R->>RC: lookup (firstgid, local_id, fh, fv, fd)
            alt cache hit
                RC-->>R: pygame.Surface
            else cache miss
                R->>TS: get_pygame_surface(local_id, flags)
                TS->>TS: lookup _pil_cache[local_id]
                alt PIL cache miss
                    TS->>PIL: sheet.crop(x, y, x+tw, y+th)
                    PIL-->>TS: tile Image
                    TS->>TS: store in _pil_cache
                end
                opt flags.flip_d or flip_h or flip_v
                    TS->>PIL: img.transpose(...)
                    PIL-->>TS: flipped Image
                end
                TS->>PIL: img.tobytes()
                PIL-->>TS: raw bytes
                TS->>PG: pygame.image.fromstring(...).convert_alpha()
                PG-->>TS: pygame.Surface
                TS-->>R: pygame.Surface
                R->>RC: store surface
            end
            opt scale != 1
                R->>R: _get_scaled_surface (scaled cache)
                R->>PG: pygame.transform.scale(surf, (w,h))
                PG-->>R: scaled Surface
            end
            R->>PG: surface.blit(tile_surf, (px, py))
        end
    end

    R-->>TM: done
    TM-->>User: (returns None)
```

---

## Tileset sprite detection (Pillow helpers)

```mermaid
sequenceDiagram
    actor Dev
    participant TS as Tileset
    participant PIL as Pillow (Image)

    Dev->>TS: is_empty_tile(local_id)
    TS->>TS: get_tile_image(local_id)
    TS->>PIL: sheet.crop(x, y, w, h)
    PIL-->>TS: RGBA Image
    TS->>PIL: img.split() → r,g,b,a
    TS->>PIL: a.getextrema()
    PIL-->>TS: (min_alpha, max_alpha)
    TS-->>Dev: max_alpha == 0  → True/False

    Dev->>TS: get_dominant_color(local_id)
    TS->>TS: get_tile_image(local_id)
    TS->>PIL: img.getdata()
    PIL-->>TS: pixel list [(r,g,b,a), ...]
    TS->>TS: filter alpha > 0, average RGB
    TS-->>Dev: (r, g, b)
```

---

## Cache lifecycle

```mermaid
stateDiagram-v2
    [*] --> Empty : module imported

    Empty --> TileCached : first draw_layer() call\nfor a given GID
    TileCached --> TileCached : subsequent frames\n(cache hit, no allocation)

    TileCached --> ScaleCached : scale != 1\nfirst occurrence
    ScaleCached --> ScaleCached : subsequent frames\n(scaled cache hit)

    TileCached --> Empty : clear_surface_cache()
    ScaleCached --> Empty : clear_surface_cache()

    note right of TileCached
        key: (firstgid, local_id,
              flip_h, flip_v, flip_d)
    end note

    note right of ScaleCached
        key: (id(surf), width, height)
    end note
```
