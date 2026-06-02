# Documentation Index

## Purpose

**English**

This folder contains project-level technical notes, workflow references, and design documents. The root `README.md` remains the primary operational entry for end users. Documents in `docs/` should expand on specific topics instead of repeating the entire startup guide.

**中文**

本目录用于存放项目级技术说明、工作流参考和设计文档。对终端用户而言，根目录下的 `README.md` 仍然是首要运行入口；`docs/` 中的文档应围绕专题展开，而不是重复整套启动说明。

## Core Documents

| File | English | 中文 |
| --- | --- | --- |
| `README.md` | Project home and startup matrix | 项目主页与启动矩阵 |
| `HPC_PYTHON_MATLAB_USAGE.md` | One-click HPC workflow for both backends | Python 与 MATLAB 双后端的一键 HPC 工作流 |
| `GRACE_L2_DESKTOP_OVERVIEW.md` | Desktop application overview | 桌面程序概览 |
| `ENGINEERING_STRUCTURE.md` | Engineering boundaries and ownership | 工程结构边界与职责说明 |
| `REPO_STRUCTURE.md` | Repository structure reference | 仓库结构参考 |
| `SH_INVERSION_REFERENCE_NOTES.md` | SH inversion, low-degree replacement, and filter theory notes | 球谐反演、低阶项替换与滤波理论说明 |
| `HSAF_STACK_IMPLEMENTATION.md` | HSAF stack and storage implementation details | HSAF stack 与存储实现细节 |

## Recommended Reading Order

**English**

1. Start from the root `README.md` for the launch matrix and shared conventions.
2. Read `matlab/README.md` or `python/README.md` depending on the backend you are using.
3. Open topic documents in `docs/` only when you need deeper implementation or theory detail.

**中文**

1. 先阅读根目录 `README.md`，了解启动矩阵与共享约定。
2. 根据所用后端，继续阅读 `matlab/README.md` 或 `python/README.md`。
3. 只有在需要更深入的实现或理论信息时，再进入 `docs/` 下的专题文档。

## Writing Rules

**English**

- Keep one responsibility per document.
- Avoid copying the same startup commands into many files.
- Prefer linking to the canonical document rather than duplicating long paragraphs.
- User-facing documents should place English first and Chinese second.

**中文**

- 每份文档只承担一个明确职责。
- 不要把同一套启动命令复制到多个文件中。
- 优先链接到权威文档，而不是重复搬运长段说明。
- 面向用户的文档统一采用“英文在前、中文在后”的顺序。
