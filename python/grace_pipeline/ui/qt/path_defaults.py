from __future__ import annotations

from pathlib import Path

from grace_pipeline.infra.config import get_data_dir, get_output_dir, get_root_dir


ROOT_DIR = get_root_dir().resolve()
DATA_DIR = get_data_dir(ROOT_DIR).resolve()
OUTPUT_DIR = get_output_dir(ROOT_DIR).resolve()


def _first_existing(*candidates: Path) -> Path:
    fallback = candidates[0]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return fallback


DEFAULT_DATA_PATHS: dict[str, Path] = {
    "GFC": DATA_DIR / "GRACE" / "GSM",
    "OUTPUT": OUTPUT_DIR,
    "LOGS": OUTPUT_DIR / "logs",
    "AUX": DATA_DIR / "Aux",
    "DDK": _first_existing(
        DATA_DIR / "DDK",
        DATA_DIR / "Aux" / "DDK",
    ),
    "BOUNDARY": DATA_DIR / "Boundary" / "boundary_cache",
    "BOUNDARY_SHP": _first_existing(
        DATA_DIR / "Boundary" / "boundary_cache" / "LargeBasin.shp",
        DATA_DIR / "Boundary" / "ne_admin_0" / "ne_50m_admin_0_countries.shp",
    ),
    "COASTLINE_SHP": _first_existing(
        DATA_DIR / "Boundary" / "ne_admin_0" / "ne_50m_admin_0_countries.shp",
        DATA_DIR / "Boundary" / "boundary_cache" / "ne_50m_admin_0_countries.shp",
    ),
    "LOW_DEGREE_C20": _first_existing(
        DATA_DIR / "GRACE" / "LowDegree" / "TN-14_C30_C20_GSFC_SLR.txt",
        DATA_DIR / "GRACE" / "LowDegree" / "TN-14_C20_SLR.txt",
    ),
    "LOW_DEGREE_DEGREE1": _first_existing(
        DATA_DIR / "GRACE" / "LowDegree" / "TN-13_GEOC_CSR_RL0603.txt",
        DATA_DIR / "GRACE" / "LowDegree" / "TN-13_GEOC_CSR_RL06.txt",
        DATA_DIR / "GRACE" / "LowDegree" / "TN-13_GEOC.txt",
    ),
    "GIA": DATA_DIR / "GRACE" / "GIA" / "GIA_Stokes_ICE-6G_D.txt",
    "MASCON_DIR": DATA_DIR / "Reference" / "Mascon",
    "MASCON_REFERENCE_FILE": _first_existing(
        DATA_DIR / "Reference" / "Mascon" / "CSR_GRACE_GRACE-FO_RL06_Mascons_all-corrections_v02.nc",
        DATA_DIR / "Reference" / "Mascon" / "Mascon_{YYYYMM}.mat",
    ),
}

DEFAULT_DATA_PATHS["MASCON_GAD"] = DEFAULT_DATA_PATHS["MASCON_DIR"] / "CSR_GRACE_GRACE-FO_RL0603_Mascons_GAD-component.nc"
DEFAULT_DATA_PATHS["MASCON_GIA"] = DEFAULT_DATA_PATHS["MASCON_DIR"] / "CSR_GRACE_GRACE-FO_RL0603_Mascons_GIA-component.nc"
