"""Human-facing official data landing pages.

Avoid opening CMR JSON/API endpoints from GUI buttons. Those endpoints are
machine interfaces and often look like 404/no-permission pages in browsers.
The GUI should route users to searchable landing pages or official dataset
pages; the downloader may still use CMR internally.
"""
from __future__ import annotations

from urllib.parse import quote_plus


def _earthdata_query(*terms: str) -> str:
    query = " ".join(str(term).strip() for term in terms if str(term).strip())
    return "https://search.earthdata.nasa.gov/search?q=" + quote_plus(query)


def data_url(center, product):
    center = str(center or "").upper()
    product = str(product or "GSM").upper()

    if product == "MASCON_NC":
        if center == "CSR":
            return _earthdata_query("CSR_GRACE_GRACE-FO_RL0603_Mascons")
        if center in {"JPL", "JPL_CRI"}:
            return _earthdata_query("TELLUS_GRAC-GRFO_MASCON", "RL06.3")
        if center == "GSFC":
            return "https://earth.gsfc.nasa.gov/geo/data/grace-mascons"
        return _earthdata_query("GRACE GRACE-FO mascon")

    if center == "CSR":
        return _earthdata_query("GRACE_GSM_L2_GRAV_CSR_RL06", "GRACEFO_L2_CSR_MONTHLY_0063")
    if center == "JPL":
        return _earthdata_query("GRACE_GSM_L2_GRAV_JPL_RL06", "GRACEFO_L2_JPL_MONTHLY_0063")
    if center == "GFZ":
        return _earthdata_query("GRACE_GSM_L2_GRAV_GFZ_RL06", "GRACEFO_L2_GFZ_MONTHLY_0063")
    if center in {"HUST", "ITSG"}:
        return "https://icgem.gfz.de/tom_longtime"
    if center == "GSFC":
        return _earthdata_query("GSFC GRACE GRACE-FO GSM")

    return _earthdata_query("GRACE GRACE-FO Level-2 GSM")
