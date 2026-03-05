# TiledMap

`tiledpy.TiledMap` is the main entry point. It parses a `.tmx` file and
exposes layers, tilesets, and rendering methods.

```python
from tiledpy import TiledMap

tmap = TiledMap("map.tmx")
```

---

::: tiledpy.loader.TiledMap

---

## Supported TMX features

| Feature | Supported |
|---------|-----------|
| Finite maps | Yes |
| Infinite maps (chunks) | Yes |
| CSV encoding | Yes |
| Base64 + zlib | Yes |
| Base64 + gzip | Yes |
| Base64 + zstd | Yes (`pip install zstandard`) |
| External `.tsx` tilesets | Yes |
| Inline tilesets | Yes |
| Tile properties | Yes |
| Tile collision objects | Yes |
| Tile animations | Yes (data stored, no auto-play) |
| Object layers | Yes |
| Flip / rotate flags | Yes |
| Group layers | No |
| Image layers | No |
