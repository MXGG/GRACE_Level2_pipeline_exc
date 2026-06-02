# Leakage Module

## Responsibility

**English**

`matlab/src/leakage/` contains the active leakage-reduction and leakage-correction workflows, including scale-factor and forward-model approaches.

**中文**

`matlab/src/leakage/` 存放当前启用的泄漏削减与泄漏校正流程，包括尺度因子法和 forward-model 方法。

## Rules

**English**

- Keep active leakage logic here.
- Historical one-off scripts belong in `matlab/_legacy/`.
- Configuration should determine whether a leakage workflow runs.

**中文**

- 当前有效的泄漏处理逻辑应放在这里。
- 历史一次性脚本应转移到 `matlab/_legacy/`。
- 是否运行泄漏流程应由配置决定。
