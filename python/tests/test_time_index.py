import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.core.time_index import build_time_index, detect_gfc_files
from grace_pipeline.infra.config import load_config


class TimeIndexTest(unittest.TestCase):
    def test_gsm_directory_builds_one_time_entry_per_gfc_file(self):
        cfg = load_config(default_config=ROOT / "matlab" / "cfg" / "default.json", root_dir=ROOT)
        gfc_files = detect_gfc_files(cfg.path.GFC, cfg.time.product_type, cfg.time.file_ext)
        time_entries = build_time_index(cfg)

        self.assertGreater(len(gfc_files), 0)
        self.assertEqual(len(time_entries), len(gfc_files))
        self.assertEqual(len({entry.gfc_file for entry in time_entries}), len(gfc_files))
        self.assertEqual(len({entry.yyyymm for entry in time_entries}), len(gfc_files))


if __name__ == "__main__":
    unittest.main()
