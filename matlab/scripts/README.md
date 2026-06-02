# Scripts Guide

## Purpose

**English**

This folder contains operational scripts such as run helpers, audits, plotting helpers, and performance checks. It is not the home of the main scientific source code.

**中文**

本目录用于存放运行辅助脚本、审计脚本、绘图辅助脚本和性能检查脚本，不是主科学计算源码所在目录。

## Subfolders

| Path | English | 中文 |
| --- | --- | --- |
| `run/` | SLURM job scripts and backend launchers | SLURM 作业脚本与后端启动器 |
| `audit/` | Repository, interface, and layout audits | 仓库、接口与目录结构审计脚本 |
| `analysis/` | Analysis helpers | 分析辅助脚本 |
| `plot/` | Plotting helpers | 绘图辅助脚本 |
| `perf/` | Performance helpers | 性能辅助脚本 |

## Important Entrypoints

| File | English | 中文 |
| --- | --- | --- |
| [hpc.ps1](/G:/GRACE_Level2_pipeline_exc/hpc.ps1) | Repository-root wrapper for push / submit / pull | 仓库根目录的推送 / 提交 / 拉回封装脚本 |
| [matlab/hpc.ps1](/G:/GRACE_Level2_pipeline_exc/matlab/hpc.ps1) | MATLAB-side helper implementation | MATLAB 侧的辅助实现 |
| [matlab/scripts/run/run.slurm](/G:/GRACE_Level2_pipeline_exc/matlab/scripts/run/run.slurm) | Default MATLAB SLURM script | 默认 MATLAB SLURM 脚本 |
| [matlab/scripts/run/run_python.slurm](/G:/GRACE_Level2_pipeline_exc/matlab/scripts/run/run_python.slurm) | Default Python SLURM script | 默认 Python SLURM 脚本 |

## Rules

**English**

- Put new operational scripts into the correct subfolder.
- Do not move scientific source-module logic into `scripts/`.
- Keep scratch or throwaway files out of this tree.
- Prefer linking back to the canonical module README instead of duplicating long explanations here.

**中文**

- 新增脚本时，放到职责正确的子目录中。
- 不要把科学计算源码逻辑挪进 `scripts/`。
- 不要把临时试验文件或一次性文件留在这个目录树中。
- 这里优先回链到权威模块 README，而不是重复拷贝长篇说明。
