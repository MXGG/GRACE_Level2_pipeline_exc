# Packaging Layout

`packaging/` is the canonical location for build, installer, runtime packaging, and deployment helpers.

## Layout

```text
packaging/
├─ windows/
│  ├─ python/      # PyInstaller and Windows Python build helpers
│  ├─ matlab/      # MATLAB Runtime or MATLAB batch packaging notes
│  └─ installer/   # Inno Setup scripts and installer assets
├─ linux/
│  ├─ python/      # Linux CLI build helpers
│  └─ matlab/      # Linux MATLAB batch/runtime notes
└─ hpc/            # Windows-to-HPC wrappers and SLURM helpers
```

## Policy

- Build outputs should not be committed.
- Release assets should be generated from this directory and uploaded to GitHub Releases.
- The current supported Inno Setup entrypoint is `installer/grace-l2.iss`; the root `grace-l2.iss` is only a deprecation stub to prevent accidental builds with the old relative paths.
- Platform-specific scripts should not be mixed with source code directories.
