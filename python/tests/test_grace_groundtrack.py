import struct
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from grace_pipeline.app.grace_groundtrack import (
    GNV_RECORD_DTYPE,
    _sample_days_for_month,
    build_bundle_order_scores,
    build_bundle_phase_unit,
    build_bundle_template_from_density,
    parse_gnv1b_bytes,
)


def _header_line(text: str) -> bytes:
    return text.ljust(80).encode("ascii") + b"\n"


def _synthetic_gnv_blob() -> bytes:
    header = b"".join(
        [
            _header_line("PRODUCER AGENCY               : NASA"),
            _header_line("NUMBER OF HEADER RECORDS      : 2"),
            _header_line("END OF HEADER"),
        ]
    )
    rec = struct.Struct(">i1s1s12dB")
    payload = b"".join(
        [
            rec.pack(71150340, b"A", b"E", 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 4.0, 5.0, 6.0, 0.0, 0.0, 0.0, 0),
            rec.pack(71150345, b"A", b"E", 7.0, 8.0, 9.0, 0.0, 0.0, 0.0, 1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0),
        ]
    )
    return header + payload


class GraceGroundtrackTest(unittest.TestCase):
    def test_gnv_record_dtype_size(self):
        self.assertEqual(GNV_RECORD_DTYPE.itemsize, 103)

    def test_parse_gnv1b_bytes(self):
        arr = parse_gnv1b_bytes(_synthetic_gnv_blob())
        self.assertEqual(arr.size, 2)
        self.assertEqual(arr["gps_time"][0], 71150340)
        self.assertEqual(arr["coord_ref"][0], b"E")
        self.assertAlmostEqual(float(arr["xvel"][1]), 1.0)

    def test_build_bundle_template_from_density(self):
        nlon, nlat = 72, 18
        x = np.arange(nlon, dtype=float)
        density = np.zeros((nlon, nlat), dtype=float)
        for j in range(nlat):
            density[:, j] = 3.0 + np.sin(2.0 * np.pi * 10.0 * x / nlon + 0.1 * j)
        template = build_bundle_template_from_density(density, center=10.0 / nlon, width=0.03)
        self.assertEqual(template.shape, density.shape)
        self.assertTrue(np.isfinite(template).all())
        self.assertGreater(float(np.nanstd(template)), 0.0)

    def test_build_bundle_phase_unit(self):
        nlon, nlat = 72, 6
        x = np.arange(nlon, dtype=float)
        template = np.column_stack(
            [np.sin(2.0 * np.pi * 8.0 * x / nlon + 0.15 * j) for j in range(nlat)]
        )
        unit = build_bundle_phase_unit(template)
        self.assertEqual(unit.shape, template.shape)
        self.assertTrue(np.isfinite(unit).all())
        self.assertAlmostEqual(float(np.nanmean(np.abs(unit))), 1.0, places=4)

    def test_build_bundle_order_scores(self):
        nlon, nlat = 72, 8
        x = np.arange(nlon, dtype=float)
        template = np.column_stack(
            [np.sin(2.0 * np.pi * 12.0 * x / nlon + 0.12 * j) for j in range(nlat)]
        )
        scores = build_bundle_order_scores(template, lmax=24, smooth_window=3, m_start=6)
        self.assertEqual(scores.shape, (25,))
        self.assertTrue(np.isfinite(scores).all())
        self.assertGreaterEqual(float(np.nanmax(scores)), 0.9)
        self.assertLess(np.argmax(scores), 20)

    def test_sample_days_for_month(self):
        self.assertEqual(_sample_days_for_month("2015-09", 1), ["2015-09-16"])
        self.assertEqual(_sample_days_for_month("2017-03", 2), ["2017-03-01", "2017-03-31"])


if __name__ == "__main__":
    unittest.main()
