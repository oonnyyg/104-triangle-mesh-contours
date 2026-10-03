"""JSON summary and CSV detail export for contour results."""

from __future__ import annotations

import csv
import io
import json

from .extract import LevelResult


def results_to_dict(results: list[LevelResult]) -> dict:
    levels = []
    for result in results:
        contours = []
        for contour in result.contours:
            contours.append(
                {
                    "closed": contour.closed,
                    "length": contour.length,
                    "points": [[x, y] for x, y in contour.points],
                }
            )
        levels.append({"level": result.level, "contours": contours})
    return {"levels": levels}


def results_to_json(results: list[LevelResult]) -> str:
    return json.dumps(results_to_dict(results), indent=2) + "\n"


def results_to_csv(results: list[LevelResult]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["level", "contour_index", "closed", "length", "point_index", "x", "y"]
    )
    for result in results:
        for ci, contour in enumerate(result.contours):
            for pi, (x, y) in enumerate(contour.points):
                writer.writerow(
                    [result.level, ci, contour.closed, contour.length, pi, x, y]
                )
    return buffer.getvalue()
