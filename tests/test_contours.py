import json
import subprocess
import sys
import unittest
from pathlib import Path

from contours.contour import extract_contours
from contours.mesh import MeshError, read_mesh
from contours.report import build_summary, to_csv, to_json

ROOT = Path(__file__).resolve().parents[1]


class SingleTriangleTests(unittest.TestCase):
    def test_open_segment_interpolation(self):
        data = {
            "vertices": [[0, 0, 0], [2, 0, 2], [0, 2, 2]],
            "triangles": [[0, 1, 2]],
            "levels": [1],
        }
        mesh, levels = read_mesh(json.dumps(data))
        (contour,) = extract_contours(mesh, levels)[1.0]
        self.assertFalse(contour["closed"])
        self.assertEqual(contour["points"], [[0.0, 1.0], [1.0, 0.0]])
        self.assertAlmostEqual(contour["length"], 2 ** 0.5)

    def test_out_of_range_and_vertex_equal_levels_are_empty(self):
        data = {
            "vertices": [[0, 0, 0], [2, 0, 2], [0, 2, 2]],
            "triangles": [[0, 1, 2]],
            "levels": [2, 3, -1],
        }
        mesh, levels = read_mesh(json.dumps(data))
        result = extract_contours(mesh, levels)
        self.assertEqual({lvl: c for lvl, c in result.items()}, {2.0: [], 3.0: [], -1.0: []})


class SharedEdgeTests(unittest.TestCase):
    def setUp(self):
        # Two triangles sharing edge (1,2); values peak at vertex 3.
        # 0:(0,0)=0  1:(2,0)=0  2:(2,2)=0  3:(0,2)=4
        self.data = {
            "vertices": [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 4]],
            "triangles": [[0, 1, 2], [0, 2, 3]],
            "levels": [2],
        }

    def test_segments_stitch_across_shared_edge(self):
        mesh, levels = read_mesh(json.dumps(self.data))
        (contour,) = extract_contours(mesh, levels)[2.0]
        self.assertFalse(contour["closed"])
        # crossings on edges (0,3)->midpoint (0,1); (2,3)->midpoint (1,2)
        self.assertEqual(contour["points"], [[0.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(contour["length"], 2 ** 0.5)

    def test_invariant_under_triangle_reorder_and_winding(self):
        mesh_a, levels_a = read_mesh(json.dumps(self.data))
        flipped = {
            **self.data,
            "triangles": [[3, 2, 0], [2, 1, 0]],
        }
        mesh_b, levels_b = read_mesh(json.dumps(flipped))
        self.assertEqual(
            extract_contours(mesh_a, levels_a),
            extract_contours(mesh_b, levels_b),
        )

    def test_shared_node_not_duplicated(self):
        mesh, levels = read_mesh(json.dumps(self.data))
        points = extract_contours(mesh, levels)[2.0][0]["points"]
        self.assertEqual(len(points), len({tuple(p) for p in points}))


class ClosedLoopTests(unittest.TestCase):
    def test_peak_triangle_forms_closed_loop(self):
        # Central high vertex surrounded by a ring; level cuts every spoke.
        data = {
            "vertices": [
                [0.0, 0.0, 4],
                [2.0, 0.0, 0],
                [1.0, 2.0, 0],
                [-1.0, 1.0, 0],
                [-1.0, -1.0, 0],
                [1.0, -1.0, 0],
            ],
            "triangles": [
                [0, 1, 2],
                [0, 2, 3],
                [0, 3, 4],
                [0, 4, 5],
                [0, 5, 1],
            ],
            "levels": [2],
        }
        mesh, levels = read_mesh(json.dumps(data))
        (contour,) = extract_contours(mesh, levels)[2.0]
        self.assertTrue(contour["closed"])
        # loop does not repeat the first point and starts at its minimum point
        self.assertEqual(len(contour["points"]), 5)
        self.assertEqual(contour["points"][0], min(contour["points"]))
        first = contour["points"][0]
        self.assertNotIn(first, contour["points"][1:])
        # closing segment is included in the length
        self.assertGreater(contour["length"], 0.0)

    def test_loop_orientation_prefers_lexicographically_smaller_direction(self):
        data = {
            "vertices": [
                [1.0, 1.0, 4],
                [0.0, 0.0, 0],
                [2.0, 0.0, 0],
                [2.0, 2.0, 0],
                [0.0, 2.0, 0],
            ],
            "triangles": [[0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 1]],
            "levels": [2],
        }
        mesh, levels = read_mesh(json.dumps(data))
        points = extract_contours(mesh, levels)[2.0][0]["points"]
        midpoints = {
            ((1.0, 1.0), (0.0, 0.0)): (0.5, 0.5),
            ((1.0, 1.0), (2.0, 0.0)): (1.5, 0.5),
            ((1.0, 1.0), (2.0, 2.0)): (1.5, 1.5),
            ((1.0, 1.0), (0.0, 2.0)): (0.5, 1.5),
        }
        self.assertIn(tuple(points[0]), midpoints.values())
        self.assertEqual(points[0], min(points))


class MultipleBranchTests(unittest.TestCase):
    def test_disjoint_components_and_result_sorting(self):
        data = {
            "vertices": [
                [0, 0, 0], [1, 0, 2], [0, 1, 2],
                [5, 5, 0], [6, 5, 2], [5, 6, 2],
            ],
            "triangles": [[0, 1, 2], [3, 4, 5]],
            "levels": [1],
        }
        mesh, levels = read_mesh(json.dumps(data))
        contours = extract_contours(mesh, levels)[1.0]
        self.assertEqual(len(contours), 2)
        self.assertEqual(
            contours,
            sorted(contours, key=lambda c: c["points"]),
        )


class ValidationTests(unittest.TestCase):
    def reject(self, data, fragment):
        with self.assertRaises(MeshError) as ctx:
            read_mesh(json.dumps(data))
        self.assertIn(fragment, str(ctx.exception))

    def test_unknown_reference(self):
        self.reject(
            {"vertices": [[0, 0, 0], [1, 0, 1], [0, 1, 1]],
             "triangles": [[0, 1, 9]]},
            "unknown vertex",
        )

    def test_non_finite_values(self):
        data = {
            "vertices": [[0, 0, 0], [1, 0, 1], [0, 1, float("nan")]],
            "triangles": [[0, 1, 2]],
        }
        with self.assertRaises(MeshError) as ctx:
            read_mesh(json.dumps(data))
        self.assertIn("finite number", str(ctx.exception))

    def test_zero_area_triangle(self):
        self.reject(
            {"vertices": [[0, 0, 0], [1, 0, 1], [2, 0, 2]],
             "triangles": [[0, 1, 2]]},
            "zero area",
        )

    def test_duplicate_triangle(self):
        self.reject(
            {"vertices": [[0, 0, 0], [1, 0, 1], [0, 1, 1], [1, 1, 0]],
             "triangles": [[0, 1, 2], [2, 1, 0]]},
            "duplicate triangle",
        )

    def test_edge_shared_by_three_triangles(self):
        self.reject(
            {
                "vertices": [
                    [0, 0, 0], [1, 0, 1],
                    [0.5, 1, 1], [0.5, -1, 1], [0.5, 2, 1],
                ],
                "triangles": [[0, 1, 2], [1, 0, 3], [0, 1, 4]],
            },
            "more than two triangles",
        )


class ReportTests(unittest.TestCase):
    def test_empty_result_keeps_structure(self):
        summary = build_summary({})
        self.assertEqual(summary, {"level_count": 0, "levels": []})
        self.assertEqual(
            to_csv({}).splitlines(),
            ["level,contour_index,closed,point_index,x,y,segment_length,total_length"],
        )

    def test_json_roundtrip(self):
        data = {
            "vertices": [[0, 0, 0], [2, 0, 2], [0, 2, 2]],
            "triangles": [[0, 1, 2]],
            "levels": [1],
        }
        mesh, levels = read_mesh(json.dumps(data))
        parsed = json.loads(to_json(extract_contours(mesh, levels)))
        self.assertEqual(parsed["level_count"], 1)
        self.assertEqual(parsed["levels"][0]["contour_count"], 1)


class CliTests(unittest.TestCase):
    def test_cli_writes_outputs(self):
        input_path = ROOT / "sample_input.json"
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "contours",
                str(input_path),
                "--json",
                str(ROOT / "out.json"),
                "--csv",
                str(ROOT / "out.csv"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads((ROOT / "out.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["level_count"], 1)
        (ROOT / "out.json").unlink()
        (ROOT / "out.csv").unlink()


if __name__ == "__main__":
    unittest.main()
