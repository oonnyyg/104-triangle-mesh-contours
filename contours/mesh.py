"""Input loading and validation for a 2D triangle mesh with scalar values."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


class MeshError(ValueError):
    """Raised when the mesh description is invalid."""


def _edge_key(a, b):
    """Canonical identity of an edge, based on vertex identifiers (not coordinates)."""
    return (a, b) if a <= b else (b, a)


@dataclass(frozen=True)
class Vertex:
    id: object
    x: float
    y: float
    value: float


@dataclass
class Mesh:
    vertices: dict
    triangles: list

    def area(self, tri):
        a, b, c = (self.vertices[i] for i in tri)
        return abs(
            (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)
        ) * 0.5


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _require_finite(name, value):
    if not _is_number(value) or not math.isfinite(value):
        raise MeshError(f"{name} must be a finite number, got {value!r}")


def _load_vertices(raw):
    if not isinstance(raw, list) or not raw:
        raise MeshError("'vertices' must be a non-empty list")
    vertices = {}
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            if "id" not in item:
                raise MeshError(f"vertex at index {index} is missing 'id'")
            vid = item["id"]
            try:
                x = float(item["x"])
                y = float(item["y"])
                value = float(item["value"])
            except (KeyError, TypeError, ValueError) as exc:
                raise MeshError(f"vertex {vid!r}: {exc}") from exc
        elif (
            isinstance(item, list)
            and len(item) == 3
            and all(_is_number(n) for n in item)
        ):
            vid = index
            x, y, value = (float(n) for n in item)
        else:
            raise MeshError(
                f"vertex at index {index} must be [x, y, value] or an object "
                "with id/x/y/value"
            )
        _require_finite(f"vertex {vid!r} x", x)
        _require_finite(f"vertex {vid!r} y", y)
        _require_finite(f"vertex {vid!r} value", value)
        if vid in vertices:
            raise MeshError(f"duplicate vertex id {vid!r}")
        vertices[vid] = Vertex(vid, x, y, value)
    return vertices


def _load_triangles(raw, vertices):
    if not isinstance(raw, list) or not raw:
        raise MeshError("'triangles' must be a non-empty list")
    triangles = []
    seen = set()
    id_types = {type(vid) for vid in vertices}
    if len(id_types) > 1:
        raise MeshError(
            f"vertex ids must share one comparable type, found {id_types}"
        )
    edge_users = {}
    for index, item in enumerate(raw):
        if not isinstance(item, list) or len(item) != 3:
            raise MeshError(f"triangle at index {index} must list 3 vertex ids")
        tri = list(item)
        for vid in tri:
            if vid not in vertices:
                raise MeshError(
                    f"triangle at index {index} references unknown vertex {vid!r}"
                )
        if len(set(tri)) != 3:
            raise MeshError(
                f"triangle at index {index} repeats a vertex (zero area)"
            )
        canonical = tuple(sorted(tri))
        if canonical in seen:
            raise MeshError(f"duplicate triangle {canonical}")
        seen.add(canonical)
        mesh = Mesh(vertices, triangles + [tri])
        if mesh.area(tri) <= 0.0:
            raise MeshError(
                f"triangle at index {index} has zero area (collinear vertices)"
            )
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            key = _edge_key(a, b)
            users = edge_users.setdefault(key, [])
            users.append(index)
            if len(users) > 2:
                raise MeshError(
                    f"edge {key} is shared by more than two triangles"
                )
        triangles.append(tri)
    return triangles


def _load_levels(raw):
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise MeshError("'levels' must be a list of numbers")
    levels = []
    for item in raw:
        _require_finite("contour level", item)
        levels.append(float(item))
    return levels


def read_mesh(source):
    """Load and validate a mesh from a JSON string, path, or parsed mapping."""

    if isinstance(source, str):
        source = json.loads(source)
    elif hasattr(source, "read"):
        source = json.load(source)
    if not isinstance(source, dict):
        raise MeshError("top-level JSON value must be an object")
    vertices = _load_vertices(source.get("vertices"))
    triangles = _load_triangles(source.get("triangles"), vertices)
    levels = _load_levels(source.get("levels"))
    return Mesh(vertices, triangles), levels
