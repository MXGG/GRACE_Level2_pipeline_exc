# MATLAB Guide

## Purpose

**English**

`matlab/` contains the production-oriented MATLAB backend, the shared configuration bridge, source modules under `src/`, and the MATLAB side of the HPC submission workflow.

**中文**

`matlab/` 目录包含面向生产运行的 MATLAB 后端、共享配置桥接层、`src/` 下的源码模块，以及 HPC 提交流程中 MATLAB 侧所需的内容。

## Layout

| Path | English | 中文 |
| --- | --- | --- |
| `cfg/` | Shared JSON configs and config helpers | 共用 JSON 配置与配置辅助函数 |
| `src/` | MATLAB source modules grouped by responsibility | 按职责划分的 MATLAB 源码模块 |
| `scripts/` | Run, audit, analysis, plot, and performance scripts | 运行、审计、分析、绘图与性能脚本 |
| `hpc.ps1` | MATLAB-side HPC helper logic | MATLAB 侧 HPC 辅助逻辑 |
| `_legacy/` | Historical code kept only for reference | 仅供参考的历史代码 |

## Local Run

### One-click entry

**English**

Use this entry for the standard local MATLAB run with the shared config pair.

**中文**

这是使用共享配置对进行本地 MATLAB 标准运行的主入口。

```matlab
run('G:\GRACE_Level2_pipeline_exc\matlab\src\main\run_oneclick.m')
```

### Explicit config entry

**English**

Use the config-specific entry when you want to point MATLAB to a specific user config file.

**中文**

当你希望显式指定某个用户配置文件时，使用这个入口。

```matlab
OUT = run_oneclick_cfg('G:\GRACE_Level2_pipeline_exc\matlab\cfg\user.json');
```

### Manual setup

**English**

Use the manual path when debugging environment setup, path loading, or individual pipeline stages.

**中文**

当你需要调试环境初始化、路径加载或单个流程阶段时，使用手动初始化方式。

```matlab
addpath(genpath('matlab/src'));
addpath('matlab/cfg');
cfg = cfg_load('matlab/cfg/user.json', 'matlab/cfg/default.json');
setup_env(cfg);
OUT = run_pipeline(cfg);
```

## HPC Usage

**English**

From the repository root, the recommended user-facing entry is:

```powershell
.\hpc.ps1 -Runtime matlab
```

This root-level helper is responsible for sync, submit, and result pullback. The default SLURM script used for the MATLAB backend is:

- [matlab/scripts/run/run.slurm](/G:/GRACE_Level2_pipeline_exc/matlab/scripts/run/run.slurm)

**中文**

从仓库根目录出发，推荐的用户入口是：

```powershell
.\hpc.ps1 -Runtime matlab
```

这个根目录脚本负责同步、提交以及结果拉回。MATLAB 后端默认使用的 SLURM 脚本是：

- [matlab/scripts/run/run.slurm](/G:/GRACE_Level2_pipeline_exc/matlab/scripts/run/run.slurm)

## Module Map

| Module | English | 中文 |
| --- | --- | --- |
| `src/main/` | Pipeline orchestration and entrypoints | 流水线编排与入口 |
| `src/core/` | Runtime helpers, planning, indexing, checkpoints | 运行时辅助、计划生成、索引与断点 |
| `src/inversion/` | GFC reading, low-degree replacement, EWH synthesis, GIA | GFC 读取、低阶项替换、EWH 合成与 GIA |
| `src/filters/` | GAUSS, FAN, P4M6, DDK, and HSAF filters | GAUSS、FAN、P4M6、DDK 与 HSAF 滤波 |
| `src/io/` | Outputs, stacks, metadata, and logs | 输出、stack、元信息与日志 |
| `src/metrics/` | Reference comparison and evaluation | 参考对比与指标评估 |
| `src/basin/` | Basin analysis and time-series extraction | 流域分析与时间序列提取 |
| `src/leakage/` | Leakage correction workflows | 泄漏校正流程 |
| `src/plot/` | Figures and diagnostics | 绘图与诊断 |
| `src/tools/` | Project helpers and vendored third-party tools | 项目工具函数与随仓库分发的第三方工具 |

## Related Documents

- [README.md](/G:/GRACE_Level2_pipeline_exc/README.md)
- [matlab/cfg/README.md](/G:/GRACE_Level2_pipeline_exc/matlab/cfg/README.md)
- [matlab/scripts/README.md](/G:/GRACE_Level2_pipeline_exc/matlab/scripts/README.md)
- [matlab/src/main/README.md](/G:/GRACE_Level2_pipeline_exc/matlab/src/main/README.md)
