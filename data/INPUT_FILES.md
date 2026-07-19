# Input data sources and restoration guide

The repository intentionally tracks code, configuration, directory placeholders, and this guide only. Large scientific input data are downloaded on demand and remain ignored by Git.

Source links were checked on 2026-07-19. Prefer the current release shown by the provider instead of copying an old local file solely because its name appears in an older config.

## NASA Earthdata setup

NASA PO.DAAC and GES DISC downloads are free, but many files require an Earthdata Login:

1. Create an account: <https://urs.earthdata.nasa.gov/users/new>
2. Create a user token: <https://urs.earthdata.nasa.gov/documentation/for_users/user_token>
3. Authorize the PO.DAAC and GES DISC applications when prompted.

The desktop GUI can download GRACE/GRACE-FO GSM, low-degree technical notes, and Mascon NetCDF data from the Data page. The implementation queries NASA CMR and writes into the selected `data/` directory; it does not require the files to be committed to Git.

## GRACE and GRACE-FO monthly spherical harmonics

Canonical destination directories:

- `data/GRACE/GSM/CSR_RL06_RL063/`
- `data/GRACE/GSM/JPL_RL06_RL063/`
- `data/GRACE/GSM/GFZ_RL06_RL063/`

NASA collection short names used by the project:

| Centre | GRACE collection | GRACE-FO RL06.3 collection | Download/search address |
| --- | --- | --- | --- |
| CSR | `GRACE_GSM_L2_GRAV_CSR_RL06` | `GRACEFO_L2_CSR_MONTHLY_0063` | <https://search.earthdata.nasa.gov/search?q=GRACE_GSM_L2_GRAV_CSR_RL06%20GRACEFO_L2_CSR_MONTHLY_0063> |
| JPL | `GRACE_GSM_L2_GRAV_JPL_RL06` | `GRACEFO_L2_JPL_MONTHLY_0063` | <https://search.earthdata.nasa.gov/search?q=GRACE_GSM_L2_GRAV_JPL_RL06%20GRACEFO_L2_JPL_MONTHLY_0063> |
| GFZ | `GRACE_GSM_L2_GRAV_GFZ_RL06` | `GRACEFO_L2_GFZ_MONTHLY_0063` | <https://search.earthdata.nasa.gov/search?q=GRACE_GSM_L2_GRAV_GFZ_RL06%20GRACEFO_L2_GFZ_MONTHLY_0063> |

NASA CMR API used by the built-in downloader: <https://cmr.earthdata.nasa.gov/search/granules.umm_json>

The mixed files previously stored directly in `data/GRACE/GSM/`, `data/GRACE/backup/`, and `data/GRACE/GSM/CSR_D/` were duplicate or working copies. Restore only one canonical centre directory unless a comparison explicitly needs more.

### HUST-Grace2024

- Product page and individual files: <https://icgem.gfz.de/sp/03_other/HUST/HUST-Grace2024>
- Degree/order 60 ZIP: <https://icgem.gfz.de/getseries/03_other/HUST/HUST-Grace2024/n60>
- Degree/order 96 ZIP: <https://icgem.gfz.de/getseries/03_other/HUST/HUST-Grace2024/n96>
- Destinations: `data/GRACE/GSM/HUST/` and `data/GRACE/GSM/HUST_n96/`
- DOI: <https://doi.org/10.5880/ICGEM.2024.001>

## Low-degree replacement coefficients

Place the files in `data/GRACE/LowDegree/`. These are direct official NASA files:

- CSR degree 1, RL06.3: <https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_CSR_RL0603.txt>
- JPL degree 1, RL06.3: <https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_JPL_RL0603.txt>
- GFZ degree 1, RL06.3: <https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_GFZ_RL0603.txt>
- GSFC SLR C20/C30, TN-14: <https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-14_C30_C20_GSFC_SLR.txt>
- Technical-note index and descriptions: <https://podaac-www.jpl.nasa.gov/gravity/gracefo-documentation>

Do not substitute an RL06.0 degree-1 file for an RL06.3 run. Select the centre-specific TN-13 file matching the GSM centre.

## Mascon reference and correction components

Destination: `data/Reference/Mascon/`

- CSR RL06.3 product page: <https://www2.csr.utexas.edu/grace/RL06_mascons.html>
- CSR download directory: <https://download.csr.utexas.edu/outgoing/grace/RL0603_mascons/>
- Corrected RL06.3 grid: <https://download.csr.utexas.edu/outgoing/grace/RL0603_mascons/CSR_GRACE_GRACE-FO_RL0603_Mascons_all-corrections.nc>
- GAD component: <https://download.csr.utexas.edu/outgoing/grace/RL0603_mascons/CSR_GRACE_GRACE-FO_RL0603_Mascons_GAD-component.nc>
- GIA component: <https://download.csr.utexas.edu/outgoing/grace/RL0603_mascons/CSR_GRACE_GRACE-FO_RL0603_Mascons_GIA-component.nc>
- DOI: <https://doi.org/10.15781/cgq9-nh24>

The old local file `CSR_GRACE_GRACE-FO_RL06_Mascons_all-corrections_v02.nc` was an earlier RL06 product. New restorations should use the current RL06.3 file and select that file in the GUI/config.

## DDK filter matrices

Destination: `data/DDK/`

Required names used by the MATLAB/Python filters include:

`Wbd_2-120.a_1d10p_4`, `Wbd_2-120.a_1d11p_4`, `Wbd_2-120.a_1d12p_4`, `Wbd_2-120.a_1d13p_4`, `Wbd_2-120.a_1d14p_4`, `Wbd_2-120.a_5d9p_4`, `Wbd_2-120.a_5d10p_4`, and `Wbd_2-120.a_5d11p_4`.

- GFZ/ISDC download portal: <https://isdc.gfz-potsdam.de/grace-isdc/downloads>
- ICGEM DDK note: <https://icgem.gfz.de/docs/Note_on_the_DDK_filters.pdf>
- Method reference: <https://doi.org/10.1029/2008GL034976>

The ISDC portal may require registration. Download the degree/order-120 binary filter bundle and retain the filenames exactly.

## SLR/DORIS monthly gravity fields

Destination: `data/GRACE/SLR/IGG-SLR-DORR/`

- ICGEM product page and individual files: <https://icgem.gfz.de/sp/04_SLR_/IGG_SLR_DORIS>
- Complete ZIP: <https://icgem.gfz.de/getseries/04_SLR_/IGG_SLR_DORIS>
- DOI: <https://doi.org/10.5880/ICGEM.2025.001>

The former `data/GRACE/IGG-SLR-DORR.zip` was only a local archive of this collection and is not needed after extraction.

## GLDAS Noah monthly hydrology

Destination: `data/Hydro/GLDAS/`

- Dataset: `GLDAS_NOAH10_M.2.1`
- File pattern: `GLDAS_NOAH10_M.AYYYYMM.021.nc4`
- GES DISC dataset page: <https://disc.gsfc.nasa.gov/datasets/GLDAS_NOAH10_M_2.1/summary>
- HTTPS archive: <https://hydro1.gesdisc.eosdis.nasa.gov/data/GLDAS/GLDAS_NOAH10_M.2.1/>
- OPeNDAP archive: <https://hydro1.gesdisc.eosdis.nasa.gov/opendap/GLDAS/GLDAS_NOAH10_M.2.1/>

Earthdata Login and GES DISC authorization are required for bulk HTTPS downloads.

## TRMM 3B43 monthly precipitation

Destination: `data/Hydro/TRMM/3B43/`

- Dataset: `TRMM_3B43_7`
- File pattern used by the analysis: `3B43.YYYYMM01.7A.HDF` for older months and `3B43.YYYYMM01.7.HDF` for later months
- GES DISC dataset page: <https://disc.gsfc.nasa.gov/datasets/TRMM_3B43_7/summary>
- HTTPS archive: <https://disc2.gesdisc.eosdis.nasa.gov/data/TRMM_L3/TRMM_3B43.7/>
- OPeNDAP archive: <https://disc2.gesdisc.eosdis.nasa.gov/opendap/TRMM_L3/TRMM_3B43.7/>
- Earthdata granule search: <https://search.earthdata.nasa.gov/search/granules?p=C1282032631-GES_DISC>

TRMM 3B43 ended in December 2019. Keep this legacy product for reproducing the existing analysis; NASA recommends IMERG for new studies.

## Coastline and country boundaries

Destination: `data/Boundary/ne_admin_0/`

- Natural Earth 1:50m Admin-0 Countries page and ZIP download: <https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/>

Extract the shapefile components and either keep their release filenames or update the configured coastline path.

## GIA model

Destination: `data/GRACE/GIA/`

- University of Toronto ICE-6G data page: <https://www.atmosp.physics.utoronto.ca/~peltier/data.php>
- ICE-6G_D (VM5a) Stokes coefficients and supporting data: <https://doi.org/10.1002/2016JB013844>

The project used `GIA_Stokes_ICE-6G_D.txt` and `Stokes_trend_O256_orig.txt.gz`. Check the model header after download and do not silently mix ICE-6G_C, ICE-6G_D, or ANU-derived coefficients.

## Project-derived inputs retained locally

The following are not deleted because no public address reproduces the exact local files:

- `data/Boundary/boundary_cache/LargeBasin.*`: a locally processed ArcGIS layer derived from the BGR/UNESCO WHYMAP River and Groundwater Basins product. Source overview: <https://www.bgr.bund.de/whymap/EN/Maps_Data/Rgwb/whymap_ed2012_map.html>
- `data/Boundary/boundary_cache/20260131.txt`: local boundary-cache metadata.
- `data/Validation/TWSC_monthly/val_twsc_YYYYMM.txt`: project-specific observed/predicted validation grids. The repository contains an analysis reader but no downloader or deterministic generator for these exact files.
- `data/splash.png`: application artwork, not a scientific input.

Before removing these retained files, archive them in a durable project data release and add its URL here.

## Minimal restoration checklist

For a standard CSR RL06.3 run, restore only:

1. CSR GSM files for the requested months.
2. CSR TN-13 RL06.3 and GSFC TN-14.
3. DDK matrices if a DDK filter is enabled.
4. ICE-6G_D coefficients only if GIA correction is enabled.
5. Mascon, GLDAS, TRMM, boundaries, or validation grids only when the corresponding optional comparison/module is enabled.

This avoids recreating the previous multi-gigabyte collection of duplicate centre products and backup copies.
