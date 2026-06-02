# Spherical Harmonic Inversion Reference Notes

This note records the theory and reference-driven corrections applied to the
Python and MATLAB GRACE Level-2 pipeline.

## 1. Equivalent Water Height (EWH) synthesis

The grid synthesis now follows the same convention as the MATLAB pipeline:

- Fully-normalized associated Legendre functions for real `C/S` synthesis.
- Explicit handling of the Condon-Shortley phase so that `scipy.special.lpmv`
  matches MATLAB `legendre(..., 'norm')`.
- Interpolated load Love numbers using the standard table already used by the
  MATLAB pipeline.
- EWH scaling with

  `a * rho_earth / (3 * rho_water) * (2n+1) / (1 + k_n)`

Primary references:

- Wahr, Molenaar, Bryan (1998), JGR.
  https://doi.org/10.1029/98JB02844
- ICGEM documentation and FAQ.
  https://icgem.gfz.de/faq

Code:

- `python/grace_pipeline/inversion/sh_synthesis.py`
- `matlab/src/inversion/inv_prepare_synthesis.m`
- `matlab/src/inversion/inv_synthesize_ewh_fast.m`

## 2. Low-degree replacement

Low-degree replacement is aligned with common RL06 practice:

- `C20` from TN-14 SLR.
- Degree-1 (`C10`, `C11`, `S11`) from TN-13 geocenter.
- `C30` from TN-14 starting from a configurable threshold month
  (`c30_start_ym`, default `2016-08`) when enabled.

Primary references:

- CSR RL06 description page.
  https://www2.csr.utexas.edu/grace/RL06.html
- CSR RL06.3 mascon notes describing degree-1, C20, and C30 replacement.
  https://www2.csr.utexas.edu/grace/RL0603_mascons.html
- TN-13 geocenter file.
  https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-13_GEOC_CSR_RL0603.txt
- TN-14 SLR file.
  https://archive.podaac.earthdata.nasa.gov/podaac-ops-cumulus-docs/gracefo/open/docs/TN-14_C30_C20_GSFC_SLR.txt

Code:

- `python/grace_pipeline/inversion/low_degree.py`
- `matlab/src/inversion/inv_replace_low_degree.m`
- `matlab/src/inversion/inv_read_lowdeg_tn13_degree1.m`
- `matlab/src/inversion/inv_read_lowdeg_tn14_c20.m`

## 3. Spectral filters

### Gaussian

Python now uses the same recursive degree-weight construction as MATLAB, rather
than a separate approximate expression.

### Fan

Python now matches the MATLAB implementation:

1. Gaussian smoothing along degree.
2. Recursive smoothing along order.

### P4M6

The destriping logic is retained, but the combined `GAUSS+P4M6` chain is now
executed in the same order as MATLAB: `P4M6 -> Gaussian`.

Primary references:

- Swenson and Wahr (2006), Geophys. Res. Lett.
  https://doi.org/10.1029/2005GL025285
- Kusche (2007), Journal of Geodesy.
  https://doi.org/10.1007/s00190-007-0143-3

Code:

- `python/grace_pipeline/filters/gaussian.py`
- `python/grace_pipeline/filters/fan.py`
- `python/grace_pipeline/filters/p4m6.py`
- `python/grace_pipeline/app/pipeline.py`
- `matlab/src/filters/apply_gaussian_filter.m`
- `matlab/src/filters/filter_sh_fan.m`
- `matlab/src/filters/filter_sh_p4m6.m`

## 4. DDK

The Python DDK block unpacking was corrected to use Fortran order when
reshaping packed block matrices, matching MATLAB `reshape(...)` behavior in
`filterSH`.

Primary references:

- GRACE-filter toolkit.
  https://github.com/strawpants/GRACE-filter

Code:

- `python/grace_pipeline/filters/ddk.py`
- `matlab/src/tools/GRACE-filter-master/src/matlab/filterSH.m`
- `matlab/src/tools/GRACE-filter-master/src/matlab/read_BIN.m`
