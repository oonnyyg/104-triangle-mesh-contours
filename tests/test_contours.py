import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

from contours.extract import extract_contours
from contours.mesh import MeshError, parse_mesh
from contours.report import results_to_csv, results_to_json


def make_mesh(points, values, triangles):
    return {
        "vertices": [list(p) for p in points],
        "values": list(values),
        "triangles": [list(t) for t in triangles],
        "levels": [],
    }


def parse(points, values, triangles, levels):
    data = make_mesh(points, values, triangles)
    data["levels"] = list(levels)
    return parse_mesh(data)


class ValidationTests(unittest.TestCase):
    def test_nonfinite_value_rejected(self):
        data = make_mesh([(0, 0), (1, 0), (0, 1)], [0, 1, 2], [(0, 1, 2)])
        data["values"][1] = float("inf")
        with self.assertRaises(MeshError):
            parse_mesh(data)
        data["values"][1] = "x"
        with self.assertRaises(MeshError):
            parse_mesh(data)

    def test_bad_index_rejected(self):
        data = make_mesh([(0, 0), (1, 0), (0, 1)], [0, 1, 2], [(0, 1, 3)])
        with self.assertRaises(MeshError):
            parse_mesh(data)

    def test_zero_area_rejected(self):
        data = make_mesh([(0, 0), (1, 0), (2, 0)], [0, 1, 2], [(0, 1, 2)])
        with self.assertRaises(MeshError):
            parse_mesh(data)

    def test_duplicate_triangle_rejected(self):
        data = make_mesh(
            [(0, 0), (1, 0), (0, 1)], [0, 1, 2], [(0, 1, 2), (2, 1, 0)]
        )
        with self.assertRaises(MeshError):
            parse_mesh(data)

    def test_edge_shared_by_three_triangles_rejected(self):
        points = [(0, 0), (1, 0), (0, 1), (1, 1), (-1, 0)]
        tris = [(0, 1, 2), (0, 1, 3), (0, 1, 4)]
        data = make_mesh(points, [0, 1, 2, 3, 4], tris)
        with self.assertRaises(MeshError):
            parse_mesh(data)

    def test_level_equal_to_vertex_value_rejected(self):
        with self.assertRaises(MeshError):
            parse(
                [(0, 0), (1, 0), (0, 1)], [0.0, 1.0, 2.0], [(0, 1, 2)], [1.0]
            )


class ExtractionTests(unittest.TestCase):
    def test_single_triangle(self):
        mesh, levels = parse(
            [(0, 0), (1, 0), (0, 1)], [0.0, 1.0, 2.0], [(0, 1, 2)], [0.5]
        )
        (result,) = extract_contours(mesh, levels)
        self.assertEqual(len(result.contours), 1)
        contour = result.contours[0]
        self.assertFalse(contour.closed)
        self.assertEqual(contour.points, ((0.0, 0.25), (0.5, 0.0)))
        self.assertAlmostEqual(contour.length, math.hypot(0.5, 0.25))

    def test_out_of_range_level_empty(self):
        mesh, levels = parse(
            [(0, 0), (1, 0), (0, 1)], [0.0, 1.0, 2.0], [(0, 1, 2)], [5.0, -1.0]
        )
        for result in extract_contours(mesh, levels):
            self.assertEqual(result.contours, [])

    def test_shared_edge_stitching(self):
        points = [(0, 0), (2, 0), (0, 2), (2, 2)]
        values = [0.0, 0.0, 2.0, 2.0]
        tris = [(0, 1, 2), (1, 3, 2)]
        mesh, levels = parse(points, values, tris, [1.0])
        (result,) = extract_contours(mesh, levels)
        self.assertEqual(len(result.contours), 1)
        contour = result.contours[0]
        self.assertFalse(contour.closed)
        self.assertEqual(contour.points, ((0.0, 1.0), (1.0, 1.0), (2.0, 1.0)))
        self.assertAlmostEqual(contour.length, 2.0)

    def test_closed_loop(self):
        points = [(0, 0), (-1, -1), (1, -1), (1, 1), (-1, 1)]
        values = [10.0, 0.0, 0.0, 0.0, 0.0]
        tris = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)]
        mesh, levels = parse(points, values, tris, [5.0])
        (result,) = extract_contours(mesh, levels)
        self.assertEqual(len(result.contours), 1)
        contour = result.contours[0]
        self.assertTrue(contour.closed)
        self.assertEqual(len(contour.points), 4)
        self.assertEqual(contour.points[0], min(contour.points))
        self.assertNotEqual(contour.points[0], contour.points[-1])
        self.assertAlmostEqual(contour.length, 4.0)

    def test_triangle_order_and_orientation_invariant(self):
        points = [(0, 0), (2, 0), (0, 2), (2, 2), (4, 0)]
        values = [0.0, 1.0, 2.0, 3.0, 0.5]
        tris = [(0, 1, 2), (1, 3, 2), (1, 4, 3)]
        mesh1, levels = parse(points, values, tris, [1.5])
        out1 = extract_contours(mesh1, levels)
        shuffled = [
            tuple(reversed(tris[2])),
            tris[0],
            (tris[1][1], tris[1][2], tris[1][0]),
        ]
        mesh2, _ = parse(points, values, shuffled, [1.5])
        out2 = extract_contours(mesh2, levels)
        self.assertEqual(out1, out2)


class ReportTests(unittest.TestCase):
    def test_json_and_csv_structure(self):
        mesh, levels = parse(
            [(0, 0), (1, 0), (0, 1)], [0.0, 1.0, 2.0], [(0, 1, 2)], [0.5, 9.0]
        )
        results = extract_contours(mesh, levels)
        summary = json.loads(results_to_json(results))
        self.assertEqual(len(summary["levels"]), 2)
        self.assertEqual(len(summary["levels"][0]["contours"]), 1)
        self.assertEqual(summary["levels"][1]["contours"], [])
        csv_text = results_to_csv(results)
        lines = csv_text.strip().splitlines()
        self.assertEqual(
            lines[0], "level,contour_index,closed,length,point_index,x,y"
        )
        self.assertEqual(len(lines), 1 + 2)


class CliTests(unittest.TestCase):
    def test_cli_writes_reports(self):
        data = make_mesh([(0, 0), (1, 0), (0, 1)], [0.0, 1.0, 2.0], [(0, 1, 2)])
        data["levels"] = [0.5]
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "mesh.json")
            jout = os.path.join(tmp, "out.json")
            cout = os.path.join(tmp, "out.csv")
            with open(src, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            proc = subprocess.run(
                [sys.executable, "-m", "contours", src, "--json", jout,
                 "--csv", cout],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(jout, encoding="utf-8") as fh:
                summary = json.load(fh)
            self.assertEqual(len(summary["levels"][0]["contours"]), 1)
            with open(cout, encoding="utf-8") as fh:
                self.assertTrue(fh.read().startswith("level,"))

    def test_cli_rejects_invalid_input(self):
        data = make_mesh([(0, 0), (1, 0), (2, 0)], [0.0, 1.0, 2.0], [(0, 1, 2)])
        data["levels"] = [0.5]
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "mesh.json")
            with open(src, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            proc = subprocess.run(
                [sys.executable, "-m", "contours", src],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("zero area", proc.stderr)


if __name__ == "__main__":
    unittest.main()
