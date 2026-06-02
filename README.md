# GRACE Level-2 Pipeline

## Overview

**English**

This repository is a shared GRACE/GRACE-FO Level-2 processing workspace. MATLAB and Python implementations are maintained side by side and are expected to follow the same scientific processing strategy, the same JSON configuration system, the same data layout, and the same output conventions. The repository supports local desktop usage on Windows, source-level debugging for the Python GUI, MATLAB local execution, and one-click submission to Linux/HPC environments.

**中文**

本仓库是一个共享的 GRACE/GRACE-FO Level-2 数据处理工作区。MATLAB 与 Python 两套实现并行维护，并要求遵循同一套科学处理策略、同一套 JSON 配置系统、同一套数据组织方式以及同一套输出规范。仓库同时支持 Windows 本地桌面使用、Python GUI 源码调试、MATLAB 本地执行，以及面向 Linux/HPC 环境的一键提交流程。

## Repository Layout

| Path | English | 中文 |
| --- | --- | --- |
| `matlab/` | MATLAB pipeline, configs, source modules, and HPC helpers | MATLAB 流水线、配置、源码模块与 HPC 辅助脚本 |
| `python/` | Python package, CLI, GUI, packaging scripts, and tests | Python 包、命令行、图形界面、打包脚本与测试 |
| `data/` | GFC inputs, auxiliary data, low-degree files, references, and boundaries | GFC 输入、辅助数据、低阶项文件、参考数据与边界文件 |
| `output/` | Local and remote run outputs | 本地与远程运行输出 |
| `docs/` | Project-level technical and usage documents | 项目级技术文档与使用说明 |
| `dist/` / `dist_preview/` | Packaged Windows GUI outputs | Windows GUI 打包产物 |
| `_archive/` | Archived or superseded materials not used by active runtime | 已归档或已替代、且不参与当前运行的历史材料 |

## Shared Conventions

**English**

- Shared configs: `matlab/cfg/default.json` and `matlab/cfg/user.json`
- Local outputs: `output/local/...`
- Remote HPC outputs: `output/remote/<jobid>/...`
- Grid stack shape: `[nLon x nLat x Nt]`
- Default HSAF input: `P4M6`
- Python and MATLAB should stay aligned in inversion, low-degree replacement, filtering strategy, and output metadata

**中文**

- 共用配置文件：`matlab/cfg/default.json` 与 `matlab/cfg/user.json`
- 本地输出路径：`output/local/...`
- 远程 HPC 输出路径：`output/remote/<jobid>/...`
- 格网 stack 统一维度：`[nLon x nLat x Nt]`
- HSAF 默认输入：`P4M6`
- Python 与 MATLAB 需要在球谐反演、低阶项替换、滤波策略和输出元信息上保持一致

## Startup Matrix

### Windows: Python GUI source debug

**English**

Use this path when debugging GUI logic, controller behavior, plotting, or source-level runtime issues.

**中文**

当需要调试 GUI 逻辑、控制器行为、绘图过程或源码级运行问题时，优先使用这一入口。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
python -m grace_pipeline.gui_entry
```

### Windows: Python CLI

**English**

Use the CLI when you want a reproducible, scriptable Python run without opening the GUI.

**中文**

当你希望用可脚本化、可复现的方式运行 Python 流程，而不打开 GUI 时，使用命令行入口。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
python -m pip install -e .
grace-pipeline info -c ..\matlab\cfg\user.json
grace-pipeline run -c ..\matlab\cfg\user.json -d ..\matlab\cfg\default.json
```

### Windows: packaged GUI

**English**

Use the packaged executable when you want an end-user desktop experience without a Python development environment.

**中文**

当你希望像普通桌面软件一样直接使用，而不依赖 Python 开发环境时，使用打包后的可执行程序。

```powershell
G:\GRACE_Level2_pipeline_exc\dist\grace-pipeline-gui.exe
```

### Windows: MATLAB local run

**English**

Use MATLAB local mode for interactive algorithm debugging, direct inspection of workspace variables, or MATLAB-only workflow verification.

**中文**

当需要在 MATLAB 中交互式调试算法、直接查看工作区变量，或验证 MATLAB 专用流程时，使用本地 MATLAB 运行方式。

```matlab
run('G:\GRACE_Level2_pipeline_exc\matlab\src\main\run_oneclick.m')
```

### Linux: Python CLI

**English**

This is the standard non-GUI path for Linux servers or manual remote runs.

**中文**

这是 Linux 服务器或手动远程运行时的标准非 GUI 入口。

```bash
cd /path/to/GRACE_Level2_pipeline_exc/python
python -m pip install -e .
python -m grace_pipeline.cli run -c ../matlab/cfg/user.json -d ../matlab/cfg/default.json
```

### Linux: MATLAB batch

**English**

Use MATLAB batch mode on Linux when running the MATLAB backend without a desktop session.

**中文**

在 Linux 上使用 MATLAB 后端且没有图形界面时，使用 MATLAB batch 模式。

```bash
cd /path/to/GRACE_Level2_pipeline_exc
matlab -batch "run('matlab/src/main/run_oneclick.m')"
```

### Windows to HPC: one-click submit

**English**

From the repository root, the recommended user-facing HPC entry is `hpc.ps1`. It syncs the project, submits the selected backend, and can pull results back to the local machine.

**中文**

从仓库根目录出发，推荐面向用户的 HPC 入口是 `hpc.ps1`。它负责同步项目、提交指定后端的作业，并可将结果拉回本地。

```powershell
cd G:\GRACE_Level2_pipeline_exc
.\hpc.ps1 -Runtime matlab
.\hpc.ps1 -Runtime python
```

## Common Commands

### Python CLI

**English**

The Python command-line interface is suitable for scripted local runs, CI-like checks, and backend-only debugging.

**中文**

Python 命令行接口适用于脚本化本地运行、类似 CI 的检查，以及仅后端流程的调试。

```powershell
grace-pipeline run [options]
```

Important options:

- `-c, --config PATH`
- `-d, --default-config PATH`
- `-o, --output PATH`
- `--start YYYY-MM`
- `--end YYYY-MM`
- `-j, --jobs N`
- `--no-parallel`
- `-v, --verbose`

### HPC helper

**English**

`hpc.ps1` is the top-level helper for pushing the workspace, choosing Python or MATLAB backend submission, and collecting outputs.

**中文**

`hpc.ps1` 是顶层 HPC 辅助脚本，用于推送工作区、选择 Python 或 MATLAB 后端提交，并回收输出结果。

```powershell
.\hpc.ps1 [options]
```

Important options:

- `-Runtime matlab|python`
- `-Remote user@host`
- `-RemotePort 21150`
- `-RemoteRoot /remote/path`
- `-ConfigPath matlab/cfg/user.json`
- `-DefaultConfigPath matlab/cfg/default.json`
- `-SyncMode auto|git|scp`
- `-PythonBin python3`

## Recommended Debug Paths

**English**

- GUI issues: start with `python -m grace_pipeline.gui_entry`
- Python pipeline issues: start with `grace-pipeline run -v`
- MATLAB issues: reproduce with `run_oneclick_cfg(...)` in MATLAB desktop
- HPC issues: inspect `output/remote/<jobid>/logs/` and `output/logs/`

**中文**

- GUI 问题：优先从 `python -m grace_pipeline.gui_entry` 进入
- Python 流程问题：优先用 `grace-pipeline run -v` 复现
- MATLAB 问题：优先在 MATLAB 桌面环境中用 `run_oneclick_cfg(...)` 复现
- HPC 问题：优先检查 `output/remote/<jobid>/logs/` 与 `output/logs/`

## Document Map

| File | English | 中文 |
| --- | --- | --- |
| [docs/README.md](/G:/GRACE_Level2_pipeline_exc/docs/README.md) | Documentation index | 文档索引 |
| [matlab/README.md](/G:/GRACE_Level2_pipeline_exc/matlab/README.md) | MATLAB-specific guide | MATLAB 说明 |
| [python/README.md](/G:/GRACE_Level2_pipeline_exc/python/README.md) | Python-specific guide | Python 说明 |
| [matlab/cfg/README.md](/G:/GRACE_Level2_pipeline_exc/matlab/cfg/README.md) | Shared configuration guide | 共享配置说明 |
| [matlab/scripts/README.md](/G:/GRACE_Level2_pipeline_exc/matlab/scripts/README.md) | Script layout and operational helpers | 脚本布局与运行辅助说明 |
| [docs/HPC_PYTHON_MATLAB_USAGE.md](/G:/GRACE_Level2_pipeline_exc/docs/HPC_PYTHON_MATLAB_USAGE.md) | HPC usage details | HPC 使用细则 |
| [docs/GRACE_L2_DESKTOP_OVERVIEW.md](/G:/GRACE_Level2_pipeline_exc/docs/GRACE_L2_DESKTOP_OVERVIEW.md) | Desktop application overview | 桌面程序概览 |
