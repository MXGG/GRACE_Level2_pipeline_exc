import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

import grace_pipeline.services.gfc_download as gfc_download
from grace_pipeline.core.time_index import extract_ym_from_gfc


class GfcDownloadServiceTest(unittest.TestCase):
    def test_icgem_index_is_filtered_by_month_for_hust_and_itsg_names(self):
        original_read = gfc_download._read_text_url
        html = """
        <a href="/getseries/03_other/HUST/HUST-Grace2016/unfiltered/HUST-Grace2016-200301.gfc">gfc</a>
        <a href="/getseries/03_other/HUST/HUST-Grace2016/unfiltered/HUST-Grace2016-200303.gfc">gfc</a>
        <a href="/getseries/03_other/ITSG/ITSG-Grace2018/monthly/120/ITSG-Grace2018_n120_2002-04.gfc">gfc</a>
        """
        try:
            gfc_download._read_text_url = lambda _url: html
            hust = gfc_download.query_icgem_gfc_granules("HUST", "2003-01", "2003-02")
            itsg = gfc_download.query_icgem_gfc_granules("ITSG", "2002-04", "2002-04")
        finally:
            gfc_download._read_text_url = original_read

        self.assertEqual([g.name for g in hust], ["HUST-Grace2016-200301.gfc"])
        self.assertEqual([g.name for g in itsg], ["ITSG-Grace2018_n120_2002-04.gfc"])

    def test_cmr_mascon_query_keeps_netcdf_download_url(self):
        original_cmr = gfc_download._cmr_json
        payload = {
            "items": [
                {
                    "umm": {
                        "GranuleUR": "GRCTellus.JPL.200204_202603.GLO.RL06.3M.MSCNv04.nc",
                        "RelatedUrls": [
                            {
                                "URL": "https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-protected/TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4/GRCTellus.JPL.200204_202603.GLO.RL06.3M.MSCNv04.nc"
                            }
                        ],
                        "TemporalExtent": {
                            "RangeDateTime": {
                                "BeginningDateTime": "2002-04-16T00:00:00.000Z",
                                "EndingDateTime": "2026-03-16T23:59:59.000Z",
                            }
                        },
                    }
                }
            ]
        }
        try:
            gfc_download._cmr_json = lambda _url: payload
            granules = gfc_download.query_mascon_granules("JPL", "2024-01", "2024-01")
        finally:
            gfc_download._cmr_json = original_cmr

        self.assertEqual(len(granules), 1)
        self.assertTrue(granules[0].name.endswith(".nc"))
        self.assertIn("podaac-ops-cumulus-protected", granules[0].url)

    def test_gsfc_mascon_query_uses_direct_half_degree_netcdf(self):
        granules = gfc_download.query_mascon_granules("GSFC", "2024-01", "2024-01", resolution="0.5")

        self.assertEqual(len(granules), 1)
        self.assertEqual(granules[0].name, "GSFC.glb.200204_202511_RL06v2.0_OBP-ICE6GD_HALFDEGREE.nc")
        self.assertIn("earth.gsfc.nasa.gov", granules[0].url)

    def test_mascon_resolution_must_match_published_netcdf(self):
        with self.assertRaisesRegex(RuntimeError, "GSFC Mascon NetCDF is available at 0.5 degree"):
            gfc_download.query_mascon_granules("GSFC", resolution="0.25")

    def test_supported_filename_dates_remain_detectable(self):
        self.assertEqual(extract_ym_from_gfc("HUST-Grace2016-200301.gfc"), "2003-01")
        self.assertEqual(extract_ym_from_gfc("ITSG-Grace2018_n120_2002-04.gfc"), "2002-04")
        self.assertEqual(extract_ym_from_gfc("GSM-2_2024001-2024031_GRFO_UTCSR_BA01_0603.gfc"), "2024-01")

    def test_clear_earthdata_credentials_preserves_other_netrc_hosts(self):
        original_home = gfc_download.Path.home
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            netrc_path = home / ".netrc"
            netrc_path.write_text(
                "\n".join(
                    [
                        "machine urs.earthdata.nasa.gov login earth password secret",
                        "machine archive.podaac.earthdata.nasa.gov login podaac password secret",
                        "machine example.com login keep password keep",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            try:
                gfc_download.Path.home = classmethod(lambda cls: home)
                gfc_download.clear_earthdata_credentials()
            finally:
                gfc_download.Path.home = original_home

            text = netrc_path.read_text(encoding="utf-8")
            self.assertNotIn("urs.earthdata.nasa.gov", text)
            self.assertNotIn("archive.podaac.earthdata.nasa.gov", text)
            self.assertIn("example.com", text)


if __name__ == "__main__":
    unittest.main()
