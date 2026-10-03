"""Marching-triangles contour extraction and polyline assembly."""

from __future__ import annotations

from .mesh import Mesh, _edge_key


def _edge_point(mesh, a_id, b_id, level):
    """Linearly interpolate the crossing of ``level`` on one mesh edge."""
    a = mesh.vertices[a_id]
    b = mesh.vertices[b_id]
    t = (level - a.value) / (b.value - a.value)
    return (a.x + t * (b.x - a.x), a.y + t * (b.y - a.y))


def _triangle_segments(mesh, tri, level):
    ids = tri
    vals = [mesh.vertices[i].value for i in ids]
    crossing_edges = []
    for i in range(3):
        j = (i + 1) % 3
        low, high = (vals[i], vals[j]) if vals[i] < vals[j] else (vals[j], vals[i])
        if low < level < high:
            crossing_edges.append((ids[i], ids[j]))
    return [
        (
            _edge_key(*edge),
            _edge_point(mesh, edge[0], edge[1], level),
        )
        for edge in crossing_edges
    ]


def _build_chains(nodes, adjacency):
    chains = []
    remaining = {n: list(ns) for n, ns in adjacency.items()}

    starts = [n for n in remaining if len(remaining[n]) == 1]
    for start in starts:
        if start not in remaining:
            continue
        chain = [start]
        prev = None
        current = start
        while True:
            neighbours = [n for n in remaining[current] if n != prev]
            if not neighbours:
                remaining.pop(current, None)
                break
            nxt = neighbours[0]
            remaining.pop(current, None)
            prev, current = current, nxt
            chain.append(current)
        chains.append((chain, False))

    for start in list(remaining):
        if start not in remaining:
            continue
        chain = [start]
        prev = start
        current = next(iter(remaining[start]))
        while current != start:
            chain.append(current)
            options = [n for n in remaining[current] if n != prev]
            prev, current = current, options[0]
        chains.append((chain, True))
        for node in chain:
            remaining.pop(node, None)

    return [([nodes[n] for n in chain], closed) for chain, closed in chains]


def _length(points, closed):
    total = 0.0
    count = len(points)
    limit = count if closed else count - 1
    for i in range(limit):
        ax, ay = points[i]
        bx, by = points[(i + 1) % count]
        total += ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    return total


def _orient_open(points):
    return list(reversed(points)) if points[-1] < points[0] else points


def _orient_closed(points):
    n = len(points)
    min_index = min(range(n), key=lambda i: points[i])
    forward = [points[(min_index + k) % n] for k in range(n)]
    backward = [points[(min_index - k) % n] for k in range(n)]
    return forward if forward <= backward else backward


def extract_contours(mesh: Mesh, levels):
    """Return ``{level: [contour, ...]}`` for the requested levels."""
    vmin = min(v.value for v in mesh.vertices.values())
    vmax = max(v.value for v in mesh.vertices.values())
    result = {}
    for level in levels:
        if any(v.value == level for v in mesh.vertices.values()) or not (
            vmin < level < vmax
        ):
            result[level] = []
            continue

        nodes = {}
        adjacency = {}

        for tri in mesh.triangles:
            segments = _triangle_segments(mesh, tri, level)
            for edge, point in segments:
                nodes[edge] = point
                adjacency.setdefault(edge, [])
            if len(segments) == 2:
                e1, e2 = segments[0][0], segments[1][0]
                adjacency[e1].append(e2)
                adjacency[e2].append(e1)

        contours = []
        for chain, closed in _build_chains(nodes, adjacency):
            if closed:
                points = _orient_closed(chain)
            else:
                points = _orient_open(chain)
            contours.append(
                {
                    "closed": closed,
                    "points": [[x, y] for x, y in points],
                    "length": _length(points, closed),
                }
            )
        contours.sort(key=lambda c: c["points"])
        result[level] = contours
    return result
