# HSAF Strategy Parity (Python vs MATLAB)

To guarantee that Python and MATLAB runs use the same HSAF processing strategy, both runtimes now write:

- `output/.../logs/hsaf_strategy.json`

This file records the **effective** HSAF strategy used by the run.

## Recorded fields

- `strategy`: `global_fixed` or `latitude_adaptive`
- `variant_requested`
- `variant_effective`
- `input_tag`
- `stack_mode`
- `params`: `N`, `P`, `K`, `J`, `iterations`
- `adaptive_zone_count`
- `generated_at`

## Runtime behavior

- Variant aliases are normalized consistently:
  - Adaptive aliases: `adaptive`, `lat_adaptive`, `latitude_adaptive`, `adaptive_lat`, `latitude`
  - Others fallback to `global`
- If adaptive variant is requested but no adaptive zones are configured, runtime falls back to global.

## Quick parity check

Compare the two `hsaf_strategy.json` files from a Python run and a MATLAB run.
If the following fields are identical, HSAF strategy parity is guaranteed:

- `strategy`
- `input_tag`
- `stack_mode`
- `params` (`N`, `P`, `K`, `J`, `iterations`)
- `adaptive_zone_count` (for adaptive runs)
