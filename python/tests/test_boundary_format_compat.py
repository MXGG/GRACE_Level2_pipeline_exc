import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.basin.boundary import read_boundary


class BoundaryFormatCompatibilityTest(unittest.TestCase):
    def test_bln_header_preserves_a_quoted_multiword_name_after_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "named_basin.bln"
            path.write_text(
                '4,1,"Amazon Basin"\n'
                "-70,-10\n"
                "-60,-10\n"
                "-60,0\n"
                "-70,-10\n",
                encoding="utf-8",
            )

            boundaries = read_boundary(str(path))

        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0].name, "Amazon Basin")
        self.assertEqual(boundaries[0].lon.size, 4)


if __name__ == "__main__":
    unittest.main()
