import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.core.time_index import TimeEntry, build_time_index, detect_gfc_files
from grace_pipeline.inversion.gfc_reader import find_gfc_file, read_gfc


def _write_gfc(path: Path, *, title: str, time_line: str, c20: str = "-4.841695846313e-04") -> None:
    text = f"""IGG-SLR-DORIS sample
{time_line}
begin_of_head ================================================================================
modelname              {title}
product_type           gravity_field
earth_gravity_constant 3.9860044150e+14
radius                 6.3781363000e+06
max_degree             60
norm                   fully_normalized
tide_system            zero_tide
errors                 calibrated
end_of_head ==================================================================================
gfc     0    0  1.000000000000D+00  0.000000000000D+00  0.0  0.0
gfc     1    0  2.473500000000D-10  0.000000000000D+00  0.0  0.0
gfc     2    0  {c20}  0.000000000000D+00  0.0  0.0
gfc     2    1 -2.018059207906D-10  1.291400590358D-09  0.0  0.0
gfc     2    2  2.439361000920D-06 -1.400074904812D-06  0.0  0.0
"""
    path.write_text(text, encoding="utf-8")


class GfcReaderCompatTest(unittest.TestCase):
    def test_detect_and_build_time_index_for_non_gsm_gfc_names(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_gfc(
                d / "IGG-SLR-DORIS_1984-01.gfc",
                title="IGG-SLR-DORIS_1984-01",
                time_line="Time covered in this file: January 1984",
            )
            _write_gfc(
                d / "IGG-SLR-DORIS_1984-02.gfc",
                title="IGG-SLR-DORIS_1984-02",
                time_line="Time covered in this file: February 1984",
            )

            cfg = SimpleNamespace(
                path=SimpleNamespace(GFC=str(d)),
                time=SimpleNamespace(
                    auto_detect_gfc=True,
                    start_ym="1984-01",
                    end_ym="1984-02",
                    product_type="GSM",
                    file_ext=".gfc",
                ),
            )

            gfc_files = detect_gfc_files(str(d), product_type="GSM", file_ext=".gfc")
            entries = build_time_index(cfg)

            self.assertEqual(len(gfc_files), 2)
            self.assertEqual(len(entries), 2)
            self.assertEqual([e.ym for e in entries], ["1984-01", "1984-02"])

    def test_find_gfc_file_matches_hyphenated_year_month(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            target = d / "IGG-SLR-DORIS_1984-01.gfc"
            _write_gfc(
                target,
                title="IGG-SLR-DORIS_1984-01",
                time_line="Time covered in this file: January 1984",
            )

            cfg = SimpleNamespace(path=SimpleNamespace(GFC=str(d)))
            t = TimeEntry.from_ym("1984-01")
            matched = find_gfc_file(cfg, t)
            self.assertEqual(Path(matched), target)

    def test_read_gfc_extracts_coefficients_and_time_from_header(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            gfc = d / "IGG-SLR-DORIS_monthly.gfc"
            _write_gfc(
                gfc,
                title="IGG-SLR-DORIS_1984-01",
                time_line="Time covered in this file: January 1984",
                c20="-4.841695846313D-04",
            )

            sh = read_gfc(str(gfc), Lmax=5)

            self.assertAlmostEqual(sh.C[2, 0], -4.841695846313e-04, places=18)
            self.assertAlmostEqual(sh.S[2, 2], -1.400074904812e-06, places=18)
            self.assertEqual(sh.meta.get("ym"), "1984-01")
            self.assertEqual(sh.meta.get("yyyymm"), "198401")
            self.assertGreaterEqual(int(sh.meta.get("coeff_count", 0)), 5)


if __name__ == "__main__":
    unittest.main()
