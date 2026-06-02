# Project Instructions (Session Summary)

## Output layout
- Remote runs (HPC/SLURM): write outputs under `output/remote/<jobid>/...`.
- Local runs: write outputs under `output/local/...`.

## HSAF settings
- Default HSAF input should be `P4M6`.
- Use HSAF parameters as configured in JSON; keep input routing consistent with `pre_hankel_input`.
- Support an additional HSAF iteration option and an adaptive global HSAF output (separate configs/jobs).

## HPC execution
- Use `hpc.ps1` to push, submit `matlab/scripts/run/run.slurm`, and pull results.
- `matlab/scripts/run/run.slurm` should request `--cpus-per-task=52` and match the configured MATLAB parallel workers.

## Parallel settings
- Set `cfg.parallel.nWorkers=52` when running on HPC for current runs.

## Data layout
- Store grids consistently as `[nLon x nLat x Nt]` across the pipeline.

## Filtering outputs
- Ensure outputs include DDK4, FAN, GAUSS+P4M6, and FAN+P4M6 filters in addition to existing filters.

## Time matching
- Mascon reference matching should not drop two months; allow nearest-month matching within tolerance when needed.

## Basin module
- The multi-basin module should be controlled by JSON (not auto-enabled by default).

## OOM/Crash avoidance (observed on HPC)
- Recent SIGKILL and "corrupted size vs. prev_size" failures were tied to I/O (large MAT saves, parallel writes, missing inputs), not pure RAM exhaustion; successful jobs reached ~70-90GB while failed jobs died at ~47-50GB.
- Always use safe save (write to *.tmp then move) for MAT outputs; avoid writing the same file from multiple workers.
- Do not save large MAT files inside parfor; collect results then save once on the main worker.
- Clear large intermediates after each filter step to reduce peak memory and I/O pressure.
- Ensure required inputs exist on remote (e.g., CSR_EWH_data.mat, CSR_CGS_EWH_data.mat) before submitting jobs.
- Keep output/log directories small (clean old runs/logs) to avoid filesystem stress during large saves.

## Chat file-link and image rendering conventions
- For clickable local file hyperlinks in this client, use Markdown links with `/G:/...` style targets (example: `[name](/G:/GRACE_Level2_pipeline_exc/output/local/xxx.png)`).
- Do not use `file:///...`, `G:\...`, or `/mnt/g/...` as the primary clickable target in chat responses.
- When sharing generated images that can be rendered in chat, prioritize direct inline rendering in both progress updates and final results, then provide the `/G:/...` clickable link.

