# MATLAB Legacy Archive

## Purpose

**English**

`matlab/_legacy/` stores historical scripts, reference implementations, and migration-only assets that are no longer part of the active MATLAB runtime path.

**中文**

`matlab/_legacy/` 用于存放历史脚本、参考实现以及仅在迁移过程中保留的遗留资源，这些内容不再属于当前 MATLAB 主运行路径。

## Policy

**English**

- Do not add new active pipeline logic here.
- Production code must live under `matlab/src/`.
- Keep only material needed for historical comparison, rollback, or compatibility reference.

**中文**

- 不要在这里新增现行流水线逻辑。
- 生产代码必须放在 `matlab/src/` 下。
- 本目录只保留用于历史对比、回滚或兼容性参考的内容。
