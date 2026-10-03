"""Mesh loading and validation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


class MeshError(ValueError):
    """Raised when the input mesh or levels are invalid."""


@dataclass(frozen=True)
class Mesh:
    points: tuple[tuple[float, float], ...]
    values: tuple[float, ...]
    triangles: tuple[tuple[int, int, int], ...]


def _finite_number(obj, what: str) -> float:
    if isinstance(obj, bool) or not isinstance(obj, (int, float)):
        raise MeshError(f"{what} must be a number, got {obj!r}")
    value = float(obj)
    if not math.isfinite(value):
        raise MeshError(f"{what} must be finite, got {obj!r}")
    return value


def _triangle_area2(p0, p1, p2) -> float:
    return (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])


def load_mesh(path: str) -> tuple[Mesh, list[float]]:
    """Load and validate a mesh JSON file, returning (mesh, levels)."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return parse_mesh(data)


def parse_mesh(data) -> tuple[Mesh, list[float]]:
    if not isinstance(data, dict):
        raise MeshError("top-level JSON value must be an object")
    for key in ("vertices", "values", "triangles", "levels"):
        if key not in data:
            raise MeshError(f"missing required key {key!r}")

    raw_vertices = data["vertices"]
    raw_values = data["values"]
    raw_triangles = data["triangles"]
    raw_levels = data["levels"]
    if not isinstance(raw_vertices, list) or not raw_vertices:
        raise MeshError("'vertices' must be a non-empty list")
    if not isinstance(raw_values, list) or len(raw_values) != len(raw_vertices):
        raise MeshError("'values' must be a list with one entry per vertex")
    if not isinstance(raw_triangles, list) or not raw_triangles:
        raise MeshError("'triangles' must be a non-empty list")
    if not isinstance(raw_levels, list):
        raise MeshError("'levels' must be a list")

    points = []
    for i, vertex in enumerate(raw_vertices):
        if not isinstance(vertex, (list, tuple)) or len(vertex) != 2:
            raise MeshError(f"vertex {i} must be a [x, y] pair")
        x = _finite_number(vertex[0], f"vertex {i} x")
        y = _finite_number(vertex[1], f"vertex {i} y")
        points.append((x, y))
    values = tuple(
        _finite_number(v, f"value {i}") for i, v in enumerate(raw_values)
    )
    levels = [_finite_number(v, f"level {i}") for i, v in enumerate(raw_levels)]

    n = len(points)
    triangles = []
    seen_triangles: set[frozenset[int]] = set()
    edge_count: dict[tuple[int, int], int] = {}
    for i, tri in enumerate(raw_triangles):
        if not isinstance(tri, (list, tuple)) or len(tri) != 3:
            raise MeshError(f"triangle {i} must have exactly 3 vertex indices")
        indices = []
        for idx in tri:
            if isinstance(idx, bool) or not isinstance(idx, int):
                raise MeshError(f"triangle {i} index {idx!r} is not an integer")
            if idx < 0 or idx >= n:
                raise MeshError(f"triangle {i} references unknown vertex {idx}")
            indices.append(idx)
        if len(set(indices)) != 3:
            raise MeshError(f"triangle {i} repeats a vertex index")
        key = frozenset(indices)
        if key in seen_triangles:
            raise MeshError(f"triangle {i} duplicates an earlier triangle")
        seen_triangles.add(key)
        a, b, c = indices
        if _triangle_area2(points[a], points[b], points[c]) == 0.0:
            raise MeshError(f"triangle {i} has zero area")
        for edge in ((a, b), (b, c), (c, a)):
            ekey = (min(edge), max(edge))
            edge_count[ekey] = edge_count.get(ekey, 0) + 1
            if edge_count[ekey] > 2:
                raise MeshError(
                    f"edge {ekey} is shared by more than two triangles"
                )
        triangles.append((a, b, c))

    mesh = Mesh(tuple(points), values, tuple(triangles))
    _validate_levels(mesh, levels)
    return mesh, levels


def _validate_levels(mesh: Mesh, levels: list[float]) -> None:
    value_set = set(mesh.values)
    for level in levels:
        if level in value_set:
            raise MeshError(
                f"level {level} equals a vertex scalar value; "
                "such levels are rejected for unambiguous topology"
            )
