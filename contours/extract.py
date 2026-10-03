"""Contour extraction by linear interpolation on triangle edges."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .mesh import Mesh

EdgeKey = tuple[int, int]
Point = tuple[float, float]


@dataclass(frozen=True)
class Contour:
    closed: bool
    points: tuple[Point, ...]
    length: float


@dataclass
class LevelResult:
    level: float
    contours: list[Contour] = field(default_factory=list)


def _edge_key(a: int, b: int) -> EdgeKey:
    return (a, b) if a < b else (b, a)


def _crossing(mesh: Mesh, a: int, b: int, level: float) -> Point:
    va = mesh.values[a]
    vb = mesh.values[b]
    t = (level - va) / (vb - va)
    pa = mesh.points[a]
    pb = mesh.points[b]
    return (pa[0] + t * (pb[0] - pa[0]), pa[1] + t * (pb[1] - pa[1]))


def _segments(mesh: Mesh, level: float) -> list[tuple[EdgeKey, EdgeKey]]:
    """Return segments as pairs of mesh-edge keys crossed by the level."""
    segments = []
    for tri in mesh.triangles:
        crossings: list[EdgeKey] = []
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            lo = min(mesh.values[a], mesh.values[b])
            hi = max(mesh.values[a], mesh.values[b])
            if lo < level < hi:
                crossings.append(_edge_key(a, b))
        if crossings:
            if len(crossings) != 2:
                raise AssertionError(
                    "triangle must contribute 0 or 2 crossing edges"
                )
            segments.append((crossings[0], crossings[1]))
    return segments


def _chain_segments(
    segments: list[tuple[EdgeKey, EdgeKey]],
) -> list[tuple[bool, list[EdgeKey]]]:
    """Stitch segments into polylines via shared mesh-edge keys."""
    adjacency: dict[EdgeKey, list[int]] = {}
    for i, (e0, e1) in enumerate(segments):
        adjacency.setdefault(e0, []).append(i)
        adjacency.setdefault(e1, []).append(i)

    used = [False] * len(segments)
    polylines: list[tuple[bool, list[EdgeKey]]] = []

    def walk(start_seg: int, start_node: EdgeKey) -> list[EdgeKey]:
        """Walk a chain beginning at start_node, marking segments used."""
        chain: list[EdgeKey] = [start_node]
        seg_index = start_seg
        node = start_node
        while True:
            used[seg_index] = True
            e0, e1 = segments[seg_index]
            node = e1 if e0 == node else e0
            chain.append(node)
            nxt = None
            for cand in adjacency[node]:
                if not used[cand]:
                    nxt = cand
                    break
            if nxt is None:
                return chain
            seg_index = nxt

    for i, (e0, e1) in enumerate(segments):
        if used[i]:
            continue
        if len(adjacency[e0]) == 1:
            polylines.append((False, walk(i, e0)))
        elif len(adjacency[e1]) == 1:
            polylines.append((False, walk(i, e1)))
    for i, (e0, e1) in enumerate(segments):
        if not used[i]:
            polylines.append((True, walk(i, e0)))
    return polylines


def _polyline_length(points: tuple[Point, ...], closed: bool) -> float:
    total = 0.0
    for i in range(len(points) - 1):
        total += math.dist(points[i], points[i + 1])
    if closed and len(points) > 1:
        total += math.dist(points[-1], points[0])
    return total


def _normalize_open(points: list[Point]) -> tuple[Point, ...]:
    if points[-1] < points[0]:
        points.reverse()
    return tuple(points)


def _normalize_closed(points: list[Point]) -> tuple[Point, ...]:
    """Rotate to the smallest coordinate and pick the lexicographically
    smaller direction; the first point is not repeated at the end."""
    n = len(points)
    start = min(range(n), key=lambda i: points[i])
    forward = [points[(start + k) % n] for k in range(n)]
    backward = [points[(start - k) % n] for k in range(n)]
    return tuple(min(forward, backward))


def extract_contours(mesh: Mesh, levels: list[float]) -> list[LevelResult]:
    results: list[LevelResult] = []
    lo = min(mesh.values)
    hi = max(mesh.values)
    for level in levels:
        result = LevelResult(level=level)
        if level <= lo or level >= hi:
            results.append(result)
            continue
        node_point: dict[EdgeKey, Point] = {}
        for tri in mesh.triangles:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                key = _edge_key(a, b)
                if key in node_point:
                    continue
                vlo = min(mesh.values[a], mesh.values[b])
                vhi = max(mesh.values[a], mesh.values[b])
                if vlo < level < vhi:
                    node_point[key] = _crossing(mesh, a, b, level)
        segments = _segments(mesh, level)
        contours: list[Contour] = []
        for closed, chain in _chain_segments(segments):
            if closed and len(chain) > 1 and chain[-1] == chain[0]:
                chain = chain[:-1]
            points = [node_point[key] for key in chain]
            if closed:
                normalized = _normalize_closed(points)
            else:
                normalized = _normalize_open(points)
            contours.append(
                Contour(
                    closed=closed,
                    points=normalized,
                    length=_polyline_length(normalized, closed),
                )
            )
        contours.sort(key=lambda c: c.points)
        result.contours = contours
        results.append(result)
    return results
