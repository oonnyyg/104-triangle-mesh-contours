"""Command line entry point: ``python -m contours input.json``."""

from __future__ import annotations

import argparse
import sys

from .contour import extract_contours
from .mesh import MeshError, read_mesh
from .report import to_csv, to_json


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract reproducible contour lines from a 2D triangle mesh."
    )
    parser.add_argument("input", help="path to the input JSON file")
    parser.add_argument(
        "--json",
        dest="json_out",
        default=None,
        help="path for the JSON summary (use '-' for stdout; default: <input>.contours.json)",
    )
    parser.add_argument(
        "--csv",
        dest="csv_out",
        default=None,
        help="path for the CSV detail (default: <input>.contours.csv; '-' disables)",
    )
    args = parser.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            mesh, levels = read_mesh(handle)
    except (OSError, MeshError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    contours_by_level = extract_contours(mesh, levels)
    json_text = to_json(contours_by_level)
    csv_text = to_csv(contours_by_level)

    json_path = args.json_out
    if json_path is None:
        json_path = args.input + ".contours.json"
    csv_path = args.csv_out
    if csv_path is None:
        csv_path = args.input + ".contours.csv"

    if json_path == "-":
        sys.stdout.write(json_text + "\n")
    else:
        with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json_text)

    if csv_path != "-":
        with open(csv_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(csv_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
