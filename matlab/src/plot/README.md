# Plot Module

## Responsibility

**English**

`matlab/src/plot/` provides quicklook figures, diagnostic plots, and summary visualizations for monthly products, stacks, metrics, and basin outputs.

**中文**

`matlab/src/plot/` 负责逐月产品、stack、指标以及流域结果的快速图、诊断图和汇总图输出。

## Rules

**English**

- Plotting code should stay separate from scientific computation.
- Figures used only for debugging or inspection should still respect the shared output layout.

**中文**

- 绘图代码应与科学计算逻辑保持分离。
- 即便是仅用于调试或检查的图件，也应遵守统一的输出目录规范。
