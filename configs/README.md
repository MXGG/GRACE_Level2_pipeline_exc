# Shared Configuration

`configs/` is the canonical configuration root for both Python and MATLAB backends.

The legacy configuration files under `matlab/cfg/` are kept during the staged migration so existing commands continue to work. New commands and documentation should prefer `configs/`.

## Files

| File | Purpose |
| --- | --- |
| `default.json` | Version-controlled default processing configuration. |
| `user.example.json` | Local user template. Copy to `user.json` before running. |
| `hpc.example.json` | HPC-oriented template with conservative output and resume settings. |
| `schema/grace_l2_config.schema.json` | JSON schema placeholder for future validation. |

## Recommended workflow

```powershell
Copy-Item configs\user.example.json configs\user.json
```

Then adjust local data paths and worker settings in `configs/user.json`.

## Path convention

`ROOT` is resolved to the repository root. Runtime outputs should use:

```text
${ROOT}/outputs
```

Input data should remain under:

```text
${ROOT}/data
```

Large input and output files should not be committed.
