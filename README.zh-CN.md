# GRACE Level-2 Pipeline

[English README](README.md)

本仓库用于 GRACE/GRACE-FO Level-2 球谐系数数据处理，支持球谐反演、低阶项替换、GIA 改正、Gaussian/Fan/去相关/DDK/HSAF 滤波、流域尺度 TWSA 提取、泄漏校正、诊断绘图、Windows 桌面运行、Linux 批处理和 HPC 提交。

当前仓库处于分阶段目录迁移阶段。旧路径 `python/`、`matlab/`、`installer/`、`output/` 继续保留用于兼容；新的运行命令优先使用 `configs/`、`packaging/` 和 `outputs/`。

## 仓库目录

| 路径 | 说明 |
| --- | --- |
| `configs/` | Python 与 MATLAB 共用的 JSON 配置目录。 |
| `python/` | 当前 Python 后端与打包脚本。 |
| `matlab/` | 当前 MATLAB 后端与兼容脚本。 |
| `data/` | 本地输入数据目录，大型数据不入库。 |
| `outputs/` | 规范化输出目录，运行结果不入库。 |
| `packaging/` | Windows、Linux、安装器、Release 与 HPC 辅助脚本。 |
| `docs/` | 用户、开发、运行、数据、发布与算法文档。 |
| `examples/` | 小型复现实例。 |
| `archive/` | 历史或废弃材料。 |

## 配置文件

共用配置目录为 `configs/`。

Windows：

```powershell
Copy-Item configs\user.example.json configs\user.json
```

Linux/macOS：

```bash
cp configs/user.example.json configs/user.json
```

然后根据本机数据路径、时间范围、滤波方法和并行线程数修改 `configs/user.json`。

## 数据目录

大型输入数据不随仓库分发，应放在 `data/` 下。

```text
data/
├─ GRACE/GSM/
├─ GRACE/LowDegree/
├─ GRACE/GIA/
├─ DDK/
├─ Boundary/
├─ Reference/Mascon/
└─ Hydro/GLDAS/
```

详细数据说明见 `data/INPUT_FILES.md` 和 `docs/data/`。

## Windows 桌面版安装程序

从 GitHub Releases 下载最新的 `grace-l2-pipeline-vX.Y.Z-win-x64-setup.exe` 并运行安装。

安装版典型结构：

```text
<install-root>/
├─ dist/grace-pipeline-gui.exe
├─ dist/grace-pipeline.exe
├─ configs/
├─ data/
└─ outputs/
```

启动示例：

```powershell
"C:\Program Files\GRACE_L2\dist\grace-pipeline-gui.exe"
```

实际安装根目录以安装时选择的路径为准。

### WinGet

当安装包 manifest 被官方 Windows Package Manager community repository 接收后，可使用：

```powershell
winget install --id MXGG.GRACELevel2Pipeline -e
```

正式接收前，请从 GitHub Releases 下载 Windows 安装包。

## Python 源码安装与运行

核心 CLI 安装不包含 PySide6 等 GUI 专用依赖，适合 Windows、Linux、macOS 和 HPC/headless 环境。

Windows PowerShell：

```powershell
cd python
python -m pip install --upgrade pip
python -m pip install -e .
grace-pipeline doctor -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline info   -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline run    -c ..\configs\user.json -d ..\configs\default.json
```

Linux/macOS：

```bash
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
grace-pipeline doctor -c ../configs/user.json -d ../configs/default.json
grace-pipeline info   -c ../configs/user.json -d ../configs/default.json
grace-pipeline run    -c ../configs/user.json -d ../configs/default.json
```

GUI 源码调试需要安装额外依赖：

```powershell
cd python
python -m pip install -e ".[gui]"
python -m grace_pipeline.gui_entry
```

Linux GUI 用户需要图形会话或可用的 Qt 后端；HPC/headless 用户应使用核心 CLI 安装。

常用 CLI 参数：

```text
-c, --config PATH
-d, --default-config PATH
-o, --output PATH
--start YYYY-MM
--end YYYY-MM
-j, --jobs N
--no-parallel
-v, --verbose
```

## MATLAB 本地运行

标准入口：

```matlab
run('matlab/src/main/run_oneclick.m')
```

显式指定共用配置：

```matlab
addpath(genpath('matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

MATLAB 入口现在优先使用 `configs/user.json` 和 `configs/default.json`，`matlab/cfg/` 仅作为迁移期兼容路径保留。

Linux MATLAB batch：

```bash
matlab -batch "run('matlab/src/main/run_oneclick.m')"
```

## HPC 提交

规范入口为 `packaging/hpc/hpc.ps1`。该脚本通过环境变量传递远端路径，不再依赖写死的个人 HPC 路径。

Python 后端：

```powershell
.\packaging\hpc\hpc.ps1 `
  -Runtime python `
  -Remote user@host `
  -RemoteRoot /remote/path/GRACE_Level2_pipeline `
  -ConfigPath configs/user.json `
  -DefaultConfigPath configs/default.json `
  -PythonBin python3
```

MATLAB 后端：

```powershell
.\packaging\hpc\hpc.ps1 `
  -Runtime matlab `
  -Remote user@host `
  -RemoteRoot /remote/path/GRACE_Level2_pipeline `
  -ConfigPath configs/user.json `
  -DefaultConfigPath configs/default.json `
  -MatlabBin matlab
```

可移植 SLURM 入口为：

```text
packaging/hpc/slurm/run_python.slurm
packaging/hpc/slurm/run_matlab.slurm
```

使用前应按目标集群修改 partition、QoS、运行时间、CPU 数和模块加载方式。

## 打包

Windows 可执行文件构建：

```powershell
cd python
.\build.ps1
```

可执行文件生成后，Windows 安装包构建：

```powershell
cd installer
ISCC.exe .\grace-l2.iss
```

请使用 `installer/grace-l2.iss` 作为当前 Inno Setup 入口。根目录 `grace-l2.iss` 只是防误用的废弃提示文件。

Linux 可执行文件构建：

```bash
cd python
bash build.sh
```

普通 Linux CLI 用户不需要安装 GUI 或打包依赖。

## 输出目录

规范输出根目录为：

```text
outputs/
├─ local/
├─ remote/
├─ figures/
└─ logs/
```

## 注意事项

- 不要提交大型 GRACE、GLDAS、Mascon、Hydroweb、边界、中间结果或输出文件。
- Python 与 MATLAB 应在球谐反演、低阶项替换、滤波、流域统计、泄漏校正和输出元信息上保持一致。
- 新命令优先使用 `configs/` 和 `outputs/`；旧 `matlab/cfg/` 与 `output/` 仅作为兼容路径保留。
