# Filters Module

## Responsibility

**English**

`matlab/src/filters/` contains the active spectral and grid-domain filters used by the project. This module is responsible for the operational implementations of Gaussian, FAN, P4M6, DDK, and HSAF filtering.

**中文**

`matlab/src/filters/` 存放项目当前启用的谱域与格网域滤波算法，是 Gaussian、FAN、P4M6、DDK 和 HSAF 的正式运行实现所在目录。

## Typical Files

| File | English | 中文 |
| --- | --- | --- |
| `filter_sh_gaussian.m` | Gaussian smoothing | Gaussian 平滑 |
| `filter_sh_p4m6.m` | P4M6 destriping | P4M6 去相关滤波 |
| `filter_sh_fan.m` | FAN filter | FAN 滤波 |
| `filter_sh_ddk.m` | DDK filter | DDK 滤波 |
| `filter_grid_hsaf.m` | HSAF entrypoint | HSAF 主入口 |

## Operational Conventions

**English**

- Default HSAF input should be `P4M6`.
- HSAF parameters should come from JSON rather than hidden branches.
- Operational outputs should continue to support `RAW`, `GAUSS`, `FAN`, `P4M6`, `DDK4`, and `HSAF`.
- Historical HSAF experiments belong in `matlab/_legacy/`, not in the active runtime tree.

**中文**

- HSAF 默认输入应为 `P4M6`。
- HSAF 参数应来自 JSON 配置，而不是隐藏分支。
- 现行输出应持续支持 `RAW`、`GAUSS`、`FAN`、`P4M6`、`DDK4` 和 `HSAF`。
- 历史 HSAF 试验代码应放在 `matlab/_legacy/`，而不应留在当前运行目录。
