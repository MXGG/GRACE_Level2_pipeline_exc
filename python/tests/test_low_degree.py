import sys
import unittest
from pathlib import Path
from datetime import datetime

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.core.config import load_config
from grace_pipeline.core.time_index import TimeEntry
from grace_pipeline.inversion.gfc_reader import SHCoefficients
from grace_pipeline.inversion.low_degree import infer_mission_from_time_entry, parse_tn14_slr, replace_low_degree, select_tn14_slr_entry


class LowDegreeReplacementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_config(ROOT / "matlab" / "cfg" / "default.json")
        cls.slr_path = ROOT / "data" / "GRACE" / "LowDegree" / "TN-14_C30_C20_GSFC_SLR.txt"

    def test_parse_tn14_slr_exposes_c20_and_c30_columns(self):
        slr = parse_tn14_slr(str(self.slr_path))
        self.assertIn("2002-04", slr)
        self.assertTrue(np.isfinite(slr["2002-04"]["C20"]))
        self.assertTrue(any(np.isfinite(values.get("C30", np.nan)) for ym, values in slr.items() if ym >= "2018-01"))

    def test_replace_low_degree_only_applies_c30_to_grace_fo(self):
        slr = parse_tn14_slr(str(self.slr_path))
        grace_fo_ym = next(ym for ym, values in sorted(slr.items()) if ym >= "2018-01" and np.isfinite(values.get("C30", np.nan)))

        sh_grace = SHCoefficients(
            C=np.zeros((5, 5), dtype=float),
            S=np.zeros((5, 5), dtype=float),
            Lmax=4,
        )
        grace_entry = TimeEntry.from_ym("2002-04", gfc_file="GSM-2_2002095-2002120_GRAC_UTCSR_BA01_0600.gfc")
        sh_grace = replace_low_degree(self.cfg, sh_grace, grace_entry)
        self.assertTrue(sh_grace.replaced.get("C20", False))
        self.assertTrue(sh_grace.replaced.get("Degree1", False))
        self.assertFalse(sh_grace.replaced.get("C30", False))
        self.assertEqual(infer_mission_from_time_entry(grace_entry), "GRACE")

        sh_grfo = SHCoefficients(
            C=np.zeros((5, 5), dtype=float),
            S=np.zeros((5, 5), dtype=float),
            Lmax=4,
        )
        grfo_entry = TimeEntry.from_ym(grace_fo_ym, gfc_file=f"GSM-2_{grace_fo_ym.replace('-', '')}_GRFO_UTCSR_BA01_0600.gfc")
        sh_grfo = replace_low_degree(self.cfg, sh_grfo, grfo_entry)
        self.assertTrue(sh_grfo.replaced.get("C20", False))
        self.assertTrue(sh_grfo.replaced.get("C30", False))
        self.assertTrue(sh_grfo.replaced.get("Degree1", False))
        self.assertEqual(infer_mission_from_time_entry(grfo_entry), "GRACE-FO")

    def test_replace_low_degree_keeps_c30_grace_fo_only_for_grace_months(self):
        sh = SHCoefficients(
            C=np.zeros((5, 5), dtype=float),
            S=np.zeros((5, 5), dtype=float),
            Lmax=4,
        )
        entry = TimeEntry.from_ym("2017-01", gfc_file="GSM-2_2017001-2017031_GRAC_UTCSR_BA01_0600.gfc")
        sh = replace_low_degree(self.cfg, sh, entry)
        self.assertFalse(sh.replaced.get("C30", False))

    def test_tn14_month_named_hust_files_use_month_key_not_neighbor_overlap(self):
        entry = TimeEntry.from_ym(
            "2011-12",
            gfc_file="HUST-Grace2024-n60-201112.gfc",
            start_dt=datetime(2011, 12, 1),
            end_dt=datetime(2011, 12, 31),
        )
        selected = select_tn14_slr_entry(str(self.slr_path), entry)

        self.assertEqual(selected, {})

    def test_tn14_day_arc_gsm_files_still_use_overlap(self):
        entry = TimeEntry.from_ym(
            "2011-12",
            gfc_file="GSM-2_2011335-2011365_GRAC_UTCSR_BA01_0600.gfc",
            start_dt=datetime(2011, 12, 1),
            end_dt=datetime(2011, 12, 31),
        )
        selected = select_tn14_slr_entry(str(self.slr_path), entry)

        self.assertEqual(selected.get("match_method"), "mjd_overlap")
        self.assertTrue(np.isfinite(selected.get("C20", np.nan)))


if __name__ == "__main__":
    unittest.main()
