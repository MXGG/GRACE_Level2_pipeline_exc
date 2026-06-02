# Main Module

## Responsibility

**English**

`matlab/src/main/` is the top-level orchestration layer of the MATLAB backend. It connects config loading, runtime setup, monthly processing, stack building, optional HSAF processing, metrics, basin stages, and final output assembly.

**中文**

`matlab/src/main/` 是 MATLAB 后端的顶层编排层，负责把配置加载、运行环境初始化、逐月处理、stack 构建、可选 HSAF 处理、指标评估、流域阶段以及最终输出整合起来。

## Typical Files

| File | English | 中文 |
| --- | --- | --- |
| `run_oneclick.m` | Main one-click local entry | 本地一键运行主入口 |
| `run_pipeline.m` | Full pipeline driver | 完整流水线驱动函数 |
| `pipeline_process_month.m` | Monthly processing stage | 逐月处理阶段 |
| `pipeline_run_hsaf_stack_stage.m` | HSAF stack stage | HSAF stack 阶段 |
| `pipeline_run_basin_stage.m` | Basin-analysis stage | 流域分析阶段 |

## Rules

**English**

- Keep orchestration here, not heavy mathematical kernels.
- Do not reimplement filter or inversion algorithms in this folder.
- When adding a new pipeline stage, wire it here but place the actual scientific implementation in the appropriate module.

**中文**

- 本目录只负责编排，不承载重型数学计算内核。
- 不要在这里重复实现滤波或反演算法。
- 新增流水线阶段时，在这里接入流程，但实际科学实现应放到对应模块中。
