# Compatibility Layer

## Purpose

**English**

`python/grace_pipeline/compat/` is the temporary home for import shims and migration bridges. Its purpose is to keep older import paths working while the package structure is being cleaned up.

**中文**

`python/grace_pipeline/compat/` 是临时兼容层，用于存放导入转发和迁移桥接代码。它的作用是在包结构整理过程中，保持旧导入路径仍然可用。

## Rules

**English**

- New code should not depend on `compat/`.
- Files here should forward to canonical modules under `app/`, `domain/`, `infra/`, or `ui`.
- Business logic, heavy I/O, and GUI workflow code should not live here.

**中文**

- 新代码不应依赖 `compat/`。
- 这里的文件应转发到 `app/`、`domain/`、`infra/` 或 `ui` 下的正式模块。
- 业务逻辑、重型 I/O 和 GUI 工作流代码不应放在这里。
