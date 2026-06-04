# GRACE Level-2 Pipeline

[English README](README.md)

本仓库用于 GRACE/GRACE-FO Level-2 球谐系数数据处理，支持球谐反演、低阶项替换、GIA 改正、Gaussian/Fan/去相关/DDK/HSAF 滤波、流域尺度 TWSA 提取、泄漏校正、诊断绘图、Windows 桌面运行、Linux 批处理和 HPC 提交。

当前仓库处于目录结构迁移阶段。旧路径 `python/`、`matlab/`、`installer/`、`output/` 仍然保留，用于兼容已有运行方式；新的文档和命令优先使用 `configs/`、`src/`、`packaging/` 和 `outputs/`。

## 仓库目录

| 路径 | 说明 |
| --- | --- |
| `configs/` | Python 与 MATLAB 共用的 JSON 配置目录。 |
| `src/python/` | 后续规范化的 Python 后端目录。 |
| `src/matlab/` | 后续规范化的 MATLAB 后端目录。 |
| `python/` | 旧 Python 后端，迁移期保留。 |
| `matlab/` | 旧 MATLAB 后端，迁移期保留。 |
| `data/` | 本地输入数据目录，大型数据不入库。 |
| `outputs/` | 规范化输出目录，运行结果不入库。 |
| `packaging/` | Windows、Linux、安装器、Release 和 HPC 部署脚本。 |
| `docs/` | 用户、开发、运行、数据、发布和算法文档。 |
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

常用配置文件：

| 文件 | 说明 |
| --- | --- |
| `configs/default.json` | 默认配置，入库维护。 |
| `configs/user.example.json` | 用户配置模板，复制为 `configs/user.json` 后使用。 |
| `configs/hpc.example.json` | HPC 配置模板。 |
| `configs/schema/grace_l2_config.schema.json` | 配置校验 schema 初稿。 |

## 数据目录

大型输入数据不随仓库分发，应放在 `data/` 下。

推荐结构：

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

Windows 桌面版通过 GitHub Releases 发布安装包时使用。

推荐安装方式：

1. 打开仓库 Releases 页面。
2. 下载最新的 `grace-l2-pipeline-vX.Y.Z-win-x64-setup.exe` 安装程序，或者下载便携版 `grace-l2-pipeline-vX.Y.Z-win-x64-portable.zip`。
3. 运行安装程序并按提示安装。
4. 大型输入数据不要放在安装目录中，建议放在独立工作区，例如 `Documents\GRACE-L2-Workspace`。
5. 将 `configs\user.example.json` 复制为 `configs\user.json`，并在运行科学流程前修改本机数据路径。

安装版启动示例：

```powershell
# 具体路径取决于安装程序设置。
"C:\Program Files\GRACE Level-2 Pipeline\grace-pipeline-gui.exe"
```

便携版启动示例：

```powershell
Expand-Archive .\grace-l2-pipeline-vX.Y.Z-win-x64-portable.zip -DestinationPath D:\Tools\GRACE-L2
D:\Tools\GRACE-L2\grace-pipeline-gui.exe
```

### WinGet 状态

当前项目不能直接假定支持 `winget install`。只有在 Windows Package Manager manifest 提交并被接收后，才可以通过 winget 公开安装。单独有 GitHub Release 安装包并不等于已经支持 winget。

正式发布 manifest 后，预期命令形式为：

```powershell
winget search grace
winget install --id <Publisher.PackageId> -e
```

正式发布前，可以用本地 manifest 进行测试：

```powershell
winget validate .\packaging\windows\winget\manifests\<Publisher.PackageId>
winget install --manifest .\packaging\windows\winget\manifests\<Publisher.PackageId>
```

在提交公开 winget 之前，安装程序应先支持静默安装。

## Python 安装与运行

当前最稳妥的旧路径：

```powershell
cd python
python -m pip install -e .
grace-pipeline info -c ..\configs\user.json -d ..\configs\default.json
grace-pipeline run  -c ..\configs\user.json -d ..\configs\default.json
```

执行目录迁移脚本后的新路径：

```powershell
.\scripts\dev\stage_repository_layout.ps1
cd src\python
python -m pip install -e .
grace-pipeline info -c ..\..\configs\user.json -d ..\..\configs\default.json
grace-pipeline run  -c ..\..\configs\user.json -d ..\..\configs\default.json
```

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

## Python GUI 调试

旧路径：

```powershell
cd python
python -m grace_pipeline.gui_entry
```

新路径：

```powershell
cd src\python
python -m grace_pipeline.gui_entry
```

## MATLAB 本地运行

当前最稳妥的旧入口：

```matlab
run('matlab/src/main/run_oneclick.m')
```

如果本地已有显式配置入口：

```matlab
addpath(genpath('matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

执行目录迁移脚本后的新路径：

```matlab
addpath(genpath('src/matlab/src'));
OUT = run_oneclick_cfg('configs/user.json');
```

## Linux 安装与批处理

从源码安装 Python CLI：

```bash
git clone https://github.com/MXGG/GRACE_Level2_pipeline_exc.git
cd GRACE_Level2_pipeline_exc
cp configs/user.example.json configs/user.json
cd python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
grace-pipeline info -c ../configs/user.json -d ../configs/default.json
grace-pipeline run  -c ../configs/user.json -d ../configs/default.json
```

执行目录迁移脚本后的新路径：

```bash
bash scripts/dev/stage_repository_layout.sh
cd src/python
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
grace-pipeline run -c ../../configs/user.json -d ../../configs/default.json
```

MATLAB batch：

```bash
matlab -batch "run('matlab/src/main/run_oneclick.m')"
```

如果后续提供 Linux CLI 发行包：

```bash
tar -xzf grace-l2-pipeline-vX.Y.Z-linux-x86_64-cli.tar.gz
cd grace-l2-pipeline-vX.Y.Z-linux-x86_64-cli
./grace-pipeline --help
./grace-pipeline run -c configs/user.json -d configs/default.json
```

## HPC 提交

规范入口：

```powershell
.\packaging\hpc\hpc.ps1 -Runtime python -ConfigPath configs\user.json -DefaultConfigPath configs\default.json
.\packaging\hpc\hpc.ps1 -Runtime matlab -ConfigPath configs\user.json -DefaultConfigPath configs\default.json
```

常用参数：

```text
-Runtime matlab|python
-Remote user@host
-RemotePort 22
-RemoteRoot /remote/path
-ConfigPath configs/user.json
-DefaultConfigPath configs/default.json
-SyncMode auto|git|scp
-PythonBin python3
```

## 打包

当前旧 Python 打包脚本仍在 `python/` 下：

```powershell
cd python
.\build.ps1
```

Linux：

```bash
cd python
bash build.sh
```

后续打包脚本会逐步迁移到 `packaging/`。

## 目录迁移

复制旧源码到新目录，不删除旧文件：

Windows：

```powershell
.\scripts\dev\stage_repository_layout.ps1
```

Linux/macOS：

```bash
bash scripts/dev/stage_repository_layout.sh
```

复制关系：

```text
python/      -> src/python/
matlab/      -> src/matlab/
installer/   -> packaging/windows/installer/legacy-installer/
output/      -> outputs/legacy-output/
```

## 输出目录

规范输出根目录为：

```text
outputs/
├─ local/
├─ remote/
├─ figures/
└─ logs/
```

推荐单次运行结构：

```text
outputs/local/<run_id>/
├─ grids/
├─ basin/
├─ leakage/
├─ figures/
├─ logs/
└─ metadata.json
```

## 文档索引

| 文档 | 说明 |
| --- | --- |
| `REPOSITORY_MIGRATION.md` | 分阶段目录迁移方案。 |
| `configs/README.md` | 配置文件说明。 |
| `src/README.md` | 源码目录说明。 |
| `packaging/README.md` | 打包与部署目录说明。 |
| `outputs/README.md` | 输出目录规范。 |
| `docs/runtime/` | 运行环境说明。 |
| `docs/data/` | 数据与元数据说明。 |
| `docs/release/` | Release 规范。 |
| `docs/algorithms/` | 算法说明。 |

## 注意事项

- 不要提交大型 GRACE、GLDAS、Mascon、Hydroweb、边界、中间结果或输出文件。
- Python 与 MATLAB 应在球谐反演、低阶项替换、滤波、流域统计、泄漏校正和输出元信息上保持一致。
- 新命令优先使用 `configs/`；旧 `matlab/cfg/` 只作为迁移期兼容路径保留。
