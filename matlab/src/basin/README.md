# Basin Module

## Responsibility

**English**

`matlab/src/basin/` handles basin-boundary reading, mask generation, basin-average time series, and seasonal / trend fitting.

**中文**

`matlab/src/basin/` 负责流域边界读取、掩膜生成、流域平均时间序列计算，以及季节项与趋势项拟合。

## Operational Rule

**English**

The multi-basin workflow should be controlled by JSON configuration and should not auto-enable itself through hidden runtime branches.

**中文**

多流域工作流应由 JSON 配置控制，不应通过隐藏的运行时分支自动启用。
