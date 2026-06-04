# Linux Packaging

Linux packaging prioritizes non-GUI execution.

## Python CLI

Future canonical location:

```text
packaging/linux/python/
```

Recommended future command:

```bash
cd src/python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
grace-pipeline run -c ../../configs/user.json -d ../../configs/default.json
```

## MATLAB batch

Future canonical location:

```text
packaging/linux/matlab/
```

Recommended future command:

```bash
matlab -batch "addpath(genpath('src/matlab')); run_oneclick_cfg('configs/user.json')"
```

The MATLAB command should be updated after the MATLAB backend is moved or converted to a package namespace.
