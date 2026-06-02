import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.app.grace_l1b_fetch import (
    build_gfz_target,
    extract_selected_members,
    list_archive_members,
)


class GraceL1BFetchTest(unittest.TestCase):
    def test_build_gfz_target_rl03(self):
        target = build_gfz_target(release="RL03", month="2002-04")
        self.assertEqual(target.archive_name, "grace_1B_2002-04_03.tar.gz")
        self.assertIn("/RL03/grace_1B_2002-04_03.tar.gz", target.url)

    def test_build_gfz_target_rl02(self):
        target = build_gfz_target(release="RL02", day="2002-04-04")
        self.assertEqual(target.archive_name, "grace_1B_2002-04-04_02.tar.gz")
        self.assertIn("/RL02/2002/grace_1B_2002-04-04_02.tar.gz", target.url)

    def test_list_and_extract_selected_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = tmp_path / "sample.tar.gz"
            (tmp_path / "GNV1B_2002-04-04_A_02.dat").write_text("gnv", encoding="utf-8")
            (tmp_path / "GPS1B_2002-04-04_A_02.dat").write_text("gps", encoding="utf-8")
            (tmp_path / "ACC1B_2002-04-04_A_02.dat").write_text("acc", encoding="utf-8")
            with tarfile.open(archive, "w:gz") as tar:
                for name in (
                    "GNV1B_2002-04-04_A_02.dat",
                    "GPS1B_2002-04-04_A_02.dat",
                    "ACC1B_2002-04-04_A_02.dat",
                ):
                    tar.add(tmp_path / name, arcname=name)
            names = list_archive_members(archive)
            self.assertEqual(len(names), 3)
            out_dir = tmp_path / "extract"
            extracted = extract_selected_members(archive, out_dir, prefixes=["GNV1B", "GPS1B"])
            extracted_names = sorted(path.name for path in extracted)
            self.assertEqual(extracted_names, ["GNV1B_2002-04-04_A_02.dat", "GPS1B_2002-04-04_A_02.dat"])


if __name__ == "__main__":
    unittest.main()
