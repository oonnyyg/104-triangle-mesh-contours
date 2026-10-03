"""JSON summary and CSV detail output for contour results."""

from __future__ import annotations

import csv
import io
import json


def build_summary(contours_by_level):
    """Build the canonical JSON-serialisable summary structure."""
    levels = []
    for level in sorted(contours_by_level):
        contours = contours_by_level[level]
        levels.append(
            {
                "level": level,
                "contour_count": len(contours),
                "total_length": sum(c["length"] for c in contours),
                "contours": contours,
            }
        )
    return {"level_count": len(levels), "levels": levels}


def to_json(contours_by_level, indent=2):
    return json.dumps(
        build_summary(contours_by_level), indent=indent, ensure_ascii=False
    )


def _format_number(value):
    return format(float(value), ".12g")


def to_csv_rows(contours_by_level):
    rows = [["level", "contour_index", "closed", "point_index", "x", "y", "segment_length", "total_length"]]
    for level in sorted(contours_by_level):
        for contour_index, contour in enumerate(contours_by_level[level]):
            points = contour["points"]
            count = len(points)
            for point_index, (x, y) in enumerate(points):
                if point_index + 1 < count:
                    nx, ny = points[point_index + 1]
                elif contour["closed"] and count > 1:
                    nx, ny = points[0]
                else:
                    nx = ny = ""
                if nx == "":
                    segment_length = ""
                else:
                    segment_length = _format_number(
                        ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5
                    )
                rows.append(
                    [
                        _format_number(level),
                        contour_index,
                        str(bool(contour["closed"])).lower(),
                        point_index,
                        _format_number(x),
                        _format_number(y),
                        segment_length,
                        _format_number(contour["length"]),
                    ]
                )
    return rows


def to_csv(contours_by_level):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(to_csv_rows(contours_by_level))
    return buffer.getvalue()
