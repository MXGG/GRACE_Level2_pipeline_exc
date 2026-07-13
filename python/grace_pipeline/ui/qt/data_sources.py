"""Human-facing, official data portals exposed by the desktop UI.

Downloader endpoints live in :mod:`grace_pipeline.services.gfc_download`.
This module intentionally keeps browser links separate: users should see an
official product or catalogue page, not a JSON API or protected object URL.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OfficialDataPortal:
    product_type: str
    center: str
    label_en: str
    label_zh: str
    url: str
    requires_earthdata: bool = False

    def label(self, language: str = "en") -> str:
        return self.label_zh if str(language).lower() == "zh" else self.label_en


# These are stable, human-facing pages maintained by the data providers. They
# were live-checked on 2026-07-11. Do not replace them with CMR JSON endpoints.
OFFICIAL_DATA_PORTALS: tuple[OfficialDataPortal, ...] = (
    OfficialDataPortal(
        "GSM",
        "CSR",
        "CSR RL06.3 · PO.DAAC",
        "CSR RL06.3 · PO.DAAC",
        "https://podaac.jpl.nasa.gov/dataset/GRACEFO_L2_CSR_MONTHLY_0063",
        True,
    ),
    OfficialDataPortal(
        "GSM",
        "JPL",
        "JPL RL06.3 · PO.DAAC",
        "JPL RL06.3 · PO.DAAC",
        "https://podaac.jpl.nasa.gov/dataset/GRACEFO_L2_JPL_MONTHLY_0063",
        True,
    ),
    OfficialDataPortal(
        "GSM",
        "GFZ",
        "GFZ RL06.3 · PO.DAAC",
        "GFZ RL06.3 · PO.DAAC",
        "https://podaac.jpl.nasa.gov/dataset/GRACEFO_L2_GFZ_MONTHLY_0063",
        True,
    ),
    OfficialDataPortal(
        "GSM",
        "HUST",
        "HUST-Grace2024 · ICGEM",
        "HUST-Grace2024 · ICGEM",
        "https://icgem.gfz.de/sp/03_other/HUST/HUST-Grace2024",
    ),
    OfficialDataPortal(
        "GSM",
        "ITSG",
        "ITSG-Grace operational · ICGEM",
        "ITSG-Grace 实时序列 · ICGEM",
        "https://icgem.gfz.de/sp/03_other/ITSG/ITSG-Grace_op",
    ),
    OfficialDataPortal(
        "MASCON_NC",
        "CSR",
        "CSR RL06.3 Mascon",
        "CSR RL06.3 Mascon",
        "https://www2.csr.utexas.edu/grace/RL06_mascons.html",
    ),
    OfficialDataPortal(
        "MASCON_NC",
        "JPL",
        "JPL RL06.3 v04 Mascon · PO.DAAC",
        "JPL RL06.3 v04 Mascon · PO.DAAC",
        "https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_GRID_RL06.3_V4",
        True,
    ),
    OfficialDataPortal(
        "MASCON_NC",
        "GSFC",
        "NASA GSFC RL06 Mascon",
        "NASA GSFC RL06 Mascon",
        "https://earth.gsfc.nasa.gov/geo/data/grace-mascons",
    ),
)


def normalize_product_type(value: str | None) -> str:
    return "MASCON_NC" if "MASCON" in str(value or "").upper() else "GSM"


def portals_for_product(product_type: str | None = None) -> tuple[OfficialDataPortal, ...]:
    if product_type is None:
        return OFFICIAL_DATA_PORTALS
    normalized = normalize_product_type(product_type)
    return tuple(portal for portal in OFFICIAL_DATA_PORTALS if portal.product_type == normalized)


def official_data_portal(product_type: str | None, center: str | None) -> OfficialDataPortal:
    product = normalize_product_type(product_type)
    normalized_center = str(center or "CSR").upper().replace("JPL_CRI", "JPL")
    for portal in OFFICIAL_DATA_PORTALS:
        if portal.product_type == product and portal.center == normalized_center:
            return portal
    return next(portal for portal in OFFICIAL_DATA_PORTALS if portal.product_type == product)


def official_data_url(product_type: str | None, center: str | None) -> str:
    return official_data_portal(product_type, center).url
