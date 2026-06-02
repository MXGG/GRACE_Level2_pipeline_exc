# GRACE Filter Methods and Program Algorithm

This note records the filter vocabulary used by this repository and the
recommended product graph for GRACE/GRACE-FO Level-2 spherical-harmonic runs.

## Source Basis

The official GRACE Tellus Level-3 land grids are generated from RL06 spherical
harmonics from CSR, JPL, and GFZ, truncated at degree/order 60. Tellus applies
low-degree replacement, GIA correction, a destriping filter for north-south
stripe errors, and a 300 km Gaussian smoother for land grids. Ocean grids use a
de-correlation filter plus a 500 km Gaussian smoother, with special leakage
treatment near land. JPL also notes that unconstrained spherical-harmonic
solutions normally need empirical smoothing and/or destriping, while mascon
solutions generally do not require empirical stripe filters because constraints
are applied during inversion.

For this repository, the authoritative Level-2 workflow is:

1. Read monthly GSM spherical harmonics.
2. Apply low-degree replacement and optional GIA in the harmonic domain.
3. Remove the configured mean field.
4. Generate multiple filter products from the same corrected monthly
   coefficients.
5. Synthesize grids as `[nLon x nLat x Nt]`.
6. Save monthly products and stacks with safe-save behavior.

## Filter Definitions

### RAW

`RAW` is the corrected, mean-removed Level-2 field synthesized to EWH without
post-processing smoothing. It is mainly a diagnostic and an input for controlled
experiments; it should not be the default interpreted mass-change product.

### GAUSS

`GAUSS` is isotropic degree-domain smoothing. Each degree `l` receives a
Gaussian weight controlled by `cfg.filter.gaussian.radius_km`.

Default for land-like products: `300 km`.

Use when a simple official-style low-pass product is needed. It suppresses
short-wavelength noise but does not explicitly decorrelate north-south stripes.

### P4M6

`P4M6` is polynomial de-striping in the harmonic domain:

1. For every order `m >= 6`, split coefficients by even and odd degree.
2. Fit a degree-4 polynomial to each `C(l,m)` and `S(l,m)` sequence.
3. Subtract the fitted polynomial from the corresponding coefficients.

This is the repository's explicit implementation of the common
Swenson/Wahr-style polynomial de-correlation family using the Chen-style P4M6
parameterization. It targets correlated errors visible as north-south stripes.

### P4M6_GAUSS

`P4M6_GAUSS` is the official-style land product analogue for this program:

```text
corrected SH -> P4M6 -> 300 km Gaussian -> EWH grid
```

This should remain the baseline conservative Level-2 SH product for land and
basin comparisons because it combines stripe suppression with spatial
low-pass smoothing.

### FAN

`FAN` is an anisotropic Gaussian-style filter. It applies degree smoothing and
order smoothing so the weight surface in `(degree, order)` space is fan-shaped.
The purpose is stronger attenuation of high-order components that express
stripe noise while keeping the method deterministic and independent of external
models.

Repository parameters:

```json
"fan": {
  "radius1_km": 300,
  "radius2_km": 300
}
```

### P4M6_FAN

`P4M6_FAN` combines explicit polynomial de-striping with the anisotropic Fan
smoother:

```text
corrected SH -> P4M6 -> FAN -> EWH grid
```

This is useful as a higher-resolution alternative to `P4M6_GAUSS`, especially
when comparing stripe suppression versus amplitude damping.

### DDK

`DDK` is a non-isotropic de-correlation/smoothing family based on block-diagonal
filter matrices. The conventional DDK levels run from strongest smoothing
(`DDK1`) to weakest smoothing (`DDK8`). The repository default is `DDK4`,
matching the existing `cfg.filter.ddk.type` and previous regression constraints.

Important routing rule: a requested DDK product must preserve its explicit tag
(`DDK4`, `DDK5`, etc.) and must never silently fall back to Gaussian.

### HSAF

`HSAF` is this program's grid-domain Hankel Spectrum Adaptive Filter. It is not
an official GRACE Tellus product. It is a program-specific experimental
de-striping stage that operates after a configured upstream product.

Default input:

```json
"pre_hankel_input": "P4M6"
```

That means:

```text
corrected SH -> P4M6 -> EWH grid -> HSAF
```

Keep the HSAF parameters in JSON. Do not hard-code them in scripts.

## Recommended Product Graph

For full runs, produce all of these tags from the same corrected monthly SH
input:

```text
RAW
P4M6
GAUSS
FAN
P4M6_GAUSS
P4M6_FAN
DDK4
HSAF       (from cfg.filter.pre_hankel_input, default P4M6)
```

The graph should be computed as a DAG, not as repeated full recomputation:

```text
C0,S0
  |-- RAW -> grid
  |-- P4M6 -> grid
  |      |-- Gaussian -> P4M6_GAUSS grid
  |      |-- Fan      -> P4M6_FAN grid
  |      `-- HSAF input by default
  |-- Gaussian -> GAUSS grid
  |-- Fan      -> FAN grid
  `-- DDK4     -> DDK4 grid
```

This matches `matlab/src/main/main_compute_products_month.m`.

## Program Configuration Defaults

Recommended defaults for land and basin analysis:

```json
{
  "filter": {
    "gaussian": { "enable": true, "radius_km": 300 },
    "p4m6": { "enable": true, "poly_deg": 4, "m_start": 6 },
    "fan": { "enable": true, "radius1_km": 300, "radius2_km": 300 },
    "ddk": { "enable": true, "type": "DDK4" },
    "hankel": { "enable": true },
    "pre_hankel_input": "P4M6"
  }
}
```

For ocean-bottom-pressure style experiments, prefer a separate config with
`gaussian.radius_km = 500` and explicit leakage handling. Do not mix this into
the default land/basin config.

## Validation Checklist

Before accepting a run:

1. Confirm all configured filter tags appear in monthly outputs and stack files.
2. Confirm DDK output tag matches the requested DDK type.
3. Confirm HSAF input tag equals `cfg.filter.pre_hankel_input`.
4. Confirm stack grids remain `[nLon x nLat x Nt]`.
5. Confirm local outputs go under `output/local/...` and remote outputs under
   `output/remote/<jobid>/...`.
6. Compare basin time series across `P4M6_GAUSS`, `P4M6_FAN`, `DDK4`, and
   `HSAF` before choosing a preferred science product.

## References Checked

- GRACE Tellus Land monthly mass grid processing:
  https://grace.jpl.nasa.gov/data/get-data/monthly-mass-grids-land/
- GRACE Tellus Ocean monthly mass grid processing:
  https://grace.jpl.nasa.gov/data/get-data/monthly-mass-grids-ocean/
- GRACE Tellus solution choice guidance:
  https://grace.jpl.nasa.gov/data/choosing-a-solution/
- JPL RL06.3 mascon product notes:
  https://grace.jpl.nasa.gov/data/get-data/jpl_global_mascons/
- ICGEM DDK filter note:
  https://icgem.gfz-potsdam.de/docs/Note_on_the_DDK_filters.pdf
- Zhang et al. fan filter paper:
  https://doi.org/10.1029/2009GL039459
