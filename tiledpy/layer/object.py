"""
layer/object.py — TileObject and ObjectLayer.

TileObject represents a single object placed in an object layer.
width() and height() accept a scale parameter so callers never need
to multiply themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TileObject:
    """A single object within an ObjectLayer.

    Parameters
    ----------
    id : int
        Unique object ID assigned by Tiled.
    name : str
        Object name.
    object_class : str
        Object class (``class`` in Tiled 1.9+, formerly ``type``).
    x : float
        X position in pixels (at scale 1.0).
    y : float
        Y position in pixels (at scale 1.0).
    _width : float
        Base width in pixels (at scale 1.0).
    _height : float
        Base height in pixels (at scale 1.0).
    rotation : float
        Clockwise rotation in degrees.
    visible : bool
        Visibility flag.
    properties : dict
        Custom properties defined in Tiled.
    gid : int or None
        Global tile ID if this is a tile-object, otherwise None.

    Methods
    -------
    width(scale=1.0) -> float
    height(scale=1.0) -> float
    """

    id: int
    name: str
    object_class: str
    x: float
    y: float
    _width: float
    _height: float
    rotation: float = 0.0
    visible: bool = True
    properties: dict = field(default_factory=dict)
    gid: int | None = None

    def width(self, scale: float = 1.0) -> float:
        """Object width in pixels at the given scale."""
        return self._width * scale

    def height(self, scale: float = 1.0) -> float:
        """Object height in pixels at the given scale."""
        return self._height * scale

    def __repr__(self) -> str:
        return (
            f"TileObject(id={self.id}, name={self.name!r}, "
            f"class={self.object_class!r}, x={self.x}, y={self.y})"
        )


@dataclass
class ObjectLayer:
    """A Tiled object layer (``<objectgroup>`` element).

    Parameters
    ----------
    id : int
    name : str
    visible : bool
    opacity : float
    color : str or None
    objects : list[TileObject]
    properties : dict
    """

    id: int
    name: str
    visible: bool
    opacity: float
    color: str | None
    objects: list[TileObject] = field(default_factory=list)
    properties: dict = field(default_factory=dict)

    def get_object(self, name: str) -> TileObject | None:
        """Return the first object whose name matches, or None."""
        for obj in self.objects:
            if obj.name == name:
                return obj
        return None

    def get_objects_by_class(self, object_class: str) -> list[TileObject]:
        """Return all objects whose class matches."""
        return [o for o in self.objects if o.object_class == object_class]

    def __repr__(self) -> str:
        return (
            f"ObjectLayer(name={self.name!r}, objects={len(self.objects)})"
        )
