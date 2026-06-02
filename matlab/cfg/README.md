# Configuration Guide

## Purpose

**English**

This folder stores the shared JSON configuration system used by both MATLAB and Python. Scientific strategy should be expressed in configuration whenever practical, rather than hidden behind language-specific branches.

**中文**

本目录保存 MATLAB 与 Python 共用的 JSON 配置系统。只要条件允许，科学处理策略都应体现在配置中，而不应隐藏在某一语言特有的分支逻辑里。

## Canonical Files

| File | English | 中文 |
| --- | --- | --- |
| `default.json` | Repository-level canonical defaults | 仓库级权威默认配置 |
| `user.json` | Main user override file | 主用户覆盖配置 |
| `user_*.json` | Scenario-specific user configs | 面向特定场景的用户配置 |
| `template_*.json` | Template configs for experiments | 用于实验的模板配置 |

## Loading Order

**English**

1. Load `default.json`
2. Load the selected user config
3. Deep-merge the two
4. Resolve `${ROOT}` placeholders
5. Validate required fields

**中文**

1. 先加载 `default.json`
2. 再加载指定的用户配置
3. 对两者进行深度合并
4. 解析 `${ROOT}` 占位符
5. 校验必需字段

MATLAB:

```matlab
cfg = cfg_load('matlab/cfg/user.json', 'matlab/cfg/default.json');
```

Python:

```powershell
grace-pipeline run -c ..\matlab\cfg\user.json -d ..\matlab\cfg\default.json
```

## Core Sections

| Section | English | 中文 |
| --- | --- | --- |
| `path` | GFC, output, auxiliary, DDK, and boundary paths | GFC、输出、辅助数据、DDK 与边界路径 |
| `reference` | Mascon and reference-matching settings | Mascon 与参考匹配设置 |
| `time` | Auto-detect or fixed time range | 自动识别或固定时间范围 |
| `grid` | Output grid definition | 输出格网定义 |
| `inversion` | `Lmax`, mean removal, low-degree replacement, and GIA | `Lmax`、均值场、低阶项替换与 GIA |
| `filter` | GAUSS, FAN, P4M6, DDK, HSAF, and `pre_hankel_input` | GAUSS、FAN、P4M6、DDK、HSAF 与 `pre_hankel_input` |
| `basin` | Basin-analysis switches | 流域分析开关 |
| `leakage` | Scale-factor and forward-model settings | 尺度因子与 forward-model 设置 |
| `metrics` | Evaluation switches | 指标评估开关 |
| `io` | Monthly and stack save / return settings | 逐月与 stack 的保存 / 返回设置 |
| `plot` | Plotting switches | 绘图开关 |
| `parallel` | Worker count and parallel behavior | 并行 worker 数与并行行为 |
| `perf` | Runtime tuning and diagnostics | 运行时调优与诊断 |

## Important Project Defaults

**English**

- Local runs write under `output/local/...`
- Remote HPC runs write under `output/remote/<jobid>/...`
- Default HSAF input is `P4M6`
- Shared stack shape is `[nLon x nLat x Nt]`
- Current HPC runs use `parallel.nWorkers = 52`

**中文**

- 本地运行写入 `output/local/...`
- 远程 HPC 运行写入 `output/remote/<jobid>/...`
- HSAF 默认输入为 `P4M6`
- 共用 stack 维度为 `[nLon x nLat x Nt]`
- 当前 HPC 运行采用 `parallel.nWorkers = 52`

## Rules

**English**

- Keep scientific strategy in JSON whenever possible.
- Prefer creating a new `user_*.json` for scenario runs instead of editing `default.json`.
- When comparing MATLAB and Python outputs, use the same `user.json` and `default.json` pair.

**中文**

- 只要可以，就把科学处理策略写入 JSON 配置。
- 做场景化实验时，优先新增 `user_*.json`，而不是直接改 `default.json`。
- 比较 MATLAB 与 Python 输出时，必须使用同一组 `user.json` 与 `default.json`。
