# Core Module

## Responsibility

**English**

`matlab/src/core/` contains reusable runtime helpers shared by the MATLAB pipeline, including planning, time-index construction, path setup, progress reporting, checkpoint state, and grid-orientation handling.

**中文**

`matlab/src/core/` 存放 MATLAB 流水线共用的运行时辅助模块，包括计划生成、时间索引构建、路径初始化、进度输出、断点状态以及格网方向处理等内容。

## Typical Responsibilities

- Build the list of months to process
- Resolve local and remote output paths
- Maintain runtime state and checkpoints
- Normalize stack and grid orientation
- Provide shared progress and performance helpers

- 构建待处理月份列表
- 解析本地与远程输出路径
- 维护运行状态与断点信息
- 统一 stack 与格网方向
- 提供共用的进度与性能辅助函数

## Rules

**English**

- Keep backend-wide runtime utilities here.
- Avoid putting scientific domain logic here unless it is genuinely cross-cutting infrastructure.
- If a helper is specific to inversion, filtering, plotting, or basin analysis, place it in that module instead.

**中文**

- 需要被整个后端复用的运行时工具函数应放在这里。
- 除非某段逻辑确实属于跨模块基础设施，否则不要把科学领域逻辑放在这里。
- 若辅助函数明显属于反演、滤波、绘图或流域分析，应放回对应模块。
