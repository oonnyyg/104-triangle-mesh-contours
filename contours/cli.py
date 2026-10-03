"""Command line interface for the contour extraction tool."""

from __future__ import annotations

import argparse
import sys

from .extract import extract_contours
from .mesh import MeshError, load_mesh
from .report import results_to_csv, results_to_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contours",
        description=(
            "Extract iso-contours from a 2D triangle mesh with scalar "
            "values and report per-contour coordinates and lengths."
        ),
    )
    parser.add_argument("input", help="path to the mesh JSON file")
    parser.add_argument(
        "--json",
        dest="json_path",
        help="write the JSON summary to this file (default: stdout)",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="write the CSV detail report to this file",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        mesh, levels = load_mesh(args.input)
    except (MeshError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = extract_contours(mesh, levels)
    json_text = results_to_json(results)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            fh.write(json_text)
    else:
        sys.stdout.write(json_text)
    if args.csv_path:
        with open(args.csv_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(results_to_csv(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
