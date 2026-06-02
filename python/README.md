# Python Guide

## Purpose

**English**

`python/` contains the Python implementation of the shared GRACE Level-2 workflow, including the package, CLI, GUI, packaging scripts, and tests. The Python backend is expected to follow the same scientific strategy and configuration rules as the MATLAB backend.

**中文**

`python/` 目录包含共享 GRACE Level-2 流程的 Python 实现，包括 Python 包、命令行、图形界面、打包脚本与测试。Python 后端需要与 MATLAB 后端遵循相同的科学处理策略和配置规则。

## Install

**English**

Install the package in editable mode before local source debugging or CLI usage.

**中文**

在进行本地源码调试或命令行运行前，先以可编辑模式安装该包。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
python -m pip install -e .
```

## Main Entrypoints

### GUI source debug

**English**

Use this entry when debugging GUI behavior, controller state, plotting, or source-level runtime behavior.

**中文**

当需要调试 GUI 行为、控制器状态、绘图过程或源码级运行行为时，使用这一入口。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
python -m grace_pipeline.gui_entry
```

### GUI via CLI

**English**

Use the CLI wrapper when you want to launch the GUI through the installed command.

**中文**

当你希望通过已安装的命令入口启动 GUI 时，使用这个方式。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
grace-pipeline gui
```

### CLI run

**English**

Use this path for scripted Python processing without the GUI.

**中文**

当你希望在不打开 GUI 的情况下脚本化运行 Python 流程时，使用这一方式。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
grace-pipeline run -c ..\matlab\cfg\user.json -d ..\matlab\cfg\default.json
```

### CLI info

**English**

Use `info` to inspect the resolved runtime configuration before running the pipeline.

**中文**

在正式运行前，可以用 `info` 查看解析后的运行配置。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
grace-pipeline info -c ..\matlab\cfg\user.json
```

## CLI Commands

| Command | English | 中文 |
| --- | --- | --- |
| `grace-pipeline gui` | Launch the Python GUI | 启动 Python 图形界面 |
| `grace-pipeline info` | Print resolved runtime/config information | 输出解析后的运行与配置信息 |
| `grace-pipeline init` | Create initial local files or scaffolding | 生成初始本地文件或脚手架 |
| `grace-pipeline run` | Execute the processing pipeline | 执行处理流水线 |

Useful `run` options:

- `-c, --config PATH`
- `-d, --default-config PATH`
- `-o, --output PATH`
- `--start YYYY-MM`
- `--end YYYY-MM`
- `-j, --jobs N`
- `--no-parallel`
- `-v, --verbose`

## Build

**English**

Use the packaging script when creating a distributable Windows GUI build.

**中文**

当需要生成可分发的 Windows GUI 程序时，使用打包脚本。

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
build.bat
```

Packaged executables are written to `..\dist\`.

打包后的可执行文件输出到 `..\dist\`。

## Package Layout

| Path | English | 中文 |
| --- | --- | --- |
| `grace_pipeline/app` | Workflow orchestration and top-level runtime logic | 工作流编排与顶层运行逻辑 |
| `grace_pipeline/domain` | Domain-facing import surface | 面向领域层的导入接口 |
| `grace_pipeline/infra` | Config, runtime, datasets, stack, and I/O infrastructure | 配置、运行时、数据集、stack 与 I/O 基础设施 |
| `grace_pipeline/ui` | GUI shell, controllers, and plotting | GUI 外壳、控制器与绘图 |
| `grace_pipeline/core` | Legacy implementation still used by some wrappers | 仍被部分包装层调用的历史实现 |
| `grace_pipeline/compat` | Temporary compatibility shims | 临时兼容层 |
| `grace_pipeline/services` | Temporary migration surface for old imports | 旧导入路径迁移期间的兼容接口 |

## Related Documents

- [README.md](/G:/GRACE_Level2_pipeline_exc/README.md)
- [python/grace_pipeline/compat/README.md](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/compat/README.md)
- [python/grace_pipeline/services/README.md](/G:/GRACE_Level2_pipeline_exc/python/grace_pipeline/services/README.md)
