# Tools Boundary

## Responsibility

**English**

`matlab/src/tools/` contains low-level project helpers and vendored third-party toolboxes required by the active MATLAB pipeline.

**中文**

`matlab/src/tools/` 用于存放当前 MATLAB 主流水线所依赖的底层项目工具函数，以及随仓库一并分发的第三方工具箱。

## Rules

**English**

- Project-owned helpers may stay at the root of `tools/` or inside project subfolders.
- Vendored third-party code should remain isolated in its own subtree.
- Duplicate or historical copies should move to `matlab/_legacy/` instead of remaining on the active path.

**中文**

- 项目自有工具函数可以放在 `tools/` 根目录或项目子目录下。
- 第三方工具代码应保持在各自独立的子目录中。
- 重复实现或历史副本应迁移到 `matlab/_legacy/`，而不是继续留在当前运行路径上。
