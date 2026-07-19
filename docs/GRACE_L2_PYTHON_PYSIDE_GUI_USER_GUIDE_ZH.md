# GRACE Level-2 Python/PySide GUI 程序说明文档

## 1. 程序基本情况

GRACE Level-2 Pipeline 是一套面向 GRACE/GRACE-FO 卫星重力 Level-2 数据处理的桌面程序与批处理工作流。当前图形界面基于 Python 和 PySide6 开发，主要用于配置、运行和检查 GRACE/GRACE-FO 球谐系数到等效水高（Equivalent Water Height, EWH）格网产品的处理流程。

程序同时保留 Python 与 MATLAB 两套后端能力。GUI 侧主要承担用户交互、配置管理、路径检查、运行控制、结果预览、流域分析和泄漏校正等任务；核心科学处理通过统一的 JSON 配置驱动，并与 MATLAB 流程保持一致的数据路径、滤波方法、输出目录和结果组织方式。

本程序适合 Windows 本地桌面运行、Python 源码调试、MATLAB 本地验证，以及通过 `hpc.ps1` 提交到 Linux/HPC 集群执行大规模批处理任务。

## 2. 主要能力概览

程序围绕 GRACE/GRACE-FO Level-2 数据处理的完整链路设计，主要能力包括：

- 数据路径配置：管理 GFC 球谐系数、DDK 滤波文件、边界数据、低阶项替换文件、GIA 文件、Mascon 参考数据等路径。
- 处理参数配置：设置时间范围、最大阶数、空间格网、均值场扣除、低阶项替换、GIA 改正、滤波方法和并行参数。
- 一键运行处理：从图形界面启动滤波处理流程，并在运行监控页面查看日志、进度、输出目录和运行状态。
- 多滤波产品输出：支持 Gaussian、P4M6、P4M6_GAUSS、DDK、FAN、P4M6_FAN、HSAF 等滤波或组合滤波结果。
- 结果预览：加载 stack 或网格产品，渲染全球或区域空间分布图，叠加海岸线、流域边界、经纬网等图层，并导出图件。
- 泄漏校正：针对区域或流域产品进行泄漏误差识别、策略推荐、前向建模或比例因子等校正处理。
- 流域分析：读取网格产品和流域边界，生成掩膜，提取面积加权时间序列，估计趋势、年周期和半年周期信号。
- 命令行与批处理：除 GUI 外，也提供 `grace-pipeline` CLI，便于可复现脚本运行和 HPC 自动化。

## 3. 程序结构

仓库的主要目录如下：

| 路径 | 说明 |
| --- | --- |
| `python/` | Python 包、PySide6 GUI、命令行入口、打包脚本和测试 |
| `matlab/` | MATLAB 后端、统一 JSON 配置、HPC SLURM 脚本和算法模块 |
| `data/` | GFC 输入、低阶项替换、Mascon 参考、边界和辅助数据 |
| `outputs/local/` | 本地运行输出目录 |
| `outputs/remote/<jobid>/` | HPC/SLURM 远程运行输出目录 |
| `docs/` | 技术说明、用户说明和算法参考文档 |
| `dist/` | 打包后的 Windows 可执行程序 |
| `release/` | 可分发压缩包和发布产物 |

Python GUI 相关的核心模块包括：

| 模块 | 说明 |
| --- | --- |
| `python/grace_pipeline/ui/qt/app.py` | PySide6 应用启动与运行环境初始化 |
| `python/grace_pipeline/ui/qt/main_window.py` | 主窗口、左侧导航栏、顶部状态栏、控制台面板 |
| `python/grace_pipeline/ui/qt/pages.py` | 各功能页面的控件布局 |
| `python/grace_pipeline/ui/qt/controller.py` | GUI 与配置、管线、绘图、流域、泄漏校正服务之间的连接层 |
| `python/grace_pipeline/app/pipeline.py` | Python 管线执行入口 |
| `python/grace_pipeline/infra/config.py` | JSON 配置读取与合并 |
| `python/grace_pipeline/infra/stack/` | stack 产品探测、读取和切片 |
| `python/grace_pipeline/ui/plotting/` | 预览图件、投影、边界和叠加图层 |

## 4. 启动方式

### 4.1 使用打包后的 GUI

适合普通桌面用户或不需要源码调试的场景：

```powershell
G:\GRACE_Level2_pipeline_exc\dist\grace-pipeline-gui.exe
```

也可以使用发布包中的便携版程序。便携版一般包含可执行文件、必要的运行库以及默认数据/输出目录结构。

### 4.2 使用 Python 源码启动 GUI

适合调试 GUI、控制器、绘图或 Python 后端逻辑：

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
python -m pip install -e ".[gui]"
python -m grace_pipeline.gui_entry
```

安装命令入口后，也可以使用：

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
grace-pipeline gui
```

### 4.3 使用 Python CLI 运行

适合脚本化处理、自动化测试或不打开 GUI 的后台运行：

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
grace-pipeline run -c ..\configs\user.json -d ..\configs\default.json
```

常用参数包括：

| 参数 | 说明 |
| --- | --- |
| `-c, --config` | 用户配置 JSON |
| `-d, --default-config` | 默认配置 JSON |
| `-o, --output` | 覆盖输出目录 |
| `--start YYYY-MM` | 覆盖起始月份 |
| `--end YYYY-MM` | 覆盖结束月份 |
| `-j, --jobs` | 并行 worker 数 |
| `--no-parallel` | 禁用并行 |
| `-v, --verbose` | 输出详细错误信息 |

查看配置和数据探测信息：

```powershell
cd G:\GRACE_Level2_pipeline_exc\python
grace-pipeline info -c ..\configs\user.json -d ..\configs\default.json
```

### 4.4 MATLAB 与 HPC 运行

MATLAB 本地运行入口：

```matlab
run('G:\GRACE_Level2_pipeline_exc\matlab\src\main\run_oneclick.m')
```

HPC 提交建议从仓库根目录使用：

```powershell
cd G:\GRACE_Level2_pipeline_exc
.\hpc.ps1 -Runtime matlab
```

远程运行输出应写入：

```text
outputs/remote/<jobid>/
```

本地运行输出应写入：

```text
outputs/local/
```

## 5. GUI 功能详情

### 5.1 Dashboard

Dashboard 是程序的总览和快捷操作页面，主要用于：

- 查看当前工程配置摘要、输出根目录和数据可用性。
- 快速进入 Data Paths、Processing Setup、Preview Results 和 Console。
- 启动、暂停或停止滤波处理任务。
- 加载和保存配置文件。
- 执行路径验证，减少运行前因输入缺失造成的失败。
- 查看当前运行状态、进度和近期输出概览。

该页面适合用户在正式运行前检查配置状态，并作为日常处理流程的起点。

### 5.2 Data Paths Configuration

Data Paths 页面用于集中配置输入、输出和参考数据路径，主要包括：

- GFC 输入目录：存放 GRACE/GRACE-FO GSM 或其他兼容 `.gfc` 文件。
- DDK 数据目录：存放 DDK 滤波所需文件。
- 输出目录：设置本地输出或远程输出根路径。
- 辅助数据目录：管理边界、海岸线、陆海掩膜等辅助文件。
- 低阶项替换文件：包括 Degree-1、C20、C30 等替换数据。
- GIA 文件：用于冰后回弹改正。
- Mascon 参考数据：用于参考产品、GAD/GIA 组件和验证对比。
- 远程同步设置：用于配合 HPC 运行时的路径和数据同步。

建议在每次更换数据集、处理中心、机器环境或输出位置后，先使用路径验证功能确认文件存在。

### 5.3 Processing Setup

Processing Setup 页面用于设置核心科学处理参数，主要包括：

- 时间范围：支持自动探测 GFC 文件覆盖月份，也支持手动覆盖起止月份。
- 反演与改正：
  - 最大阶数 `Lmax`
  - 均值场/异常扣除
  - 低阶项替换
  - Degree-1 地心项
  - C20 与 C30 SLR 替换
  - GIA 改正
- 空间格网：
  - 经度范围、纬度范围
  - 经/纬向分辨率
  - 输出网格约定为 `[nLon x nLat x Nt]`
- SH/Grid 工具：
  - 球谐到格网合成
  - 格网到球谐分析
- 滤波方法：
  - Gaussian
  - P4M6
  - P4M6_GAUSS
  - DDK
  - FAN
  - P4M6_FAN
  - HSAF
- HSAF 相关参数：
  - 默认输入建议使用 P4M6
  - 支持全局、区域、迭代或自适应策略
  - 具体参数由 JSON 配置控制

该页面决定了最终产品的科学处理策略，建议在正式批量运行前保存配置文件，便于复现。

### 5.4 Leakage Correction

Leakage Correction 页面用于对流域或区域结果进行泄漏误差校正。主要功能包括：

- 开启或关闭泄漏校正模块。
- 读取待校正输入 stack、参考输入和区域边界。
- 自动识别输入产品类型和适用场景。
- 给出推荐校正策略。
- 设置校正方法和参数。
- 运行泄漏校正、暂停或停止任务。
- 查看校正结果入口，并将校正后的 stack 发送到 Preview 页面查看。
- 输出诊断信息，辅助判断输入、边界和校正策略是否合理。

适用场景包括湖泊、流域、区域水储量变化等存在边界泄漏或滤波削弱效应的分析任务。

### 5.5 Basin Analysis

Basin Analysis 页面用于流域尺度统计分析，主要功能包括：

- 启用或关闭流域分析模块。
- 加载格网数据或 stack 产品。
- 读取流域边界文件。
- 生成流域掩膜。
- 支持多流域选择、全局扫描或点缓冲分析。
- 预览流域数据和属性表。
- 输出面积加权流域时间序列。
- 计算趋势、年周期、半年周期等统计量。
- 保存 TXT/CSV 表格、MAT 文件、掩膜网格和诊断网格。

该模块应通过 JSON 配置显式控制，默认不应自动开启多流域分析。适合对单个湖泊、流域、行政区或研究区进行水储量变化分析。

### 5.6 Preview Results

Preview 页面用于结果可视化和快速质量检查，主要功能包括：

- 加载 stack 或其他网格产品。
- 读取产品元数据和时间切片。
- 选择月份、变量和绘图范围。
- 自动使用检测到的空间范围，或手动设置区域范围。
- 支持多种地图投影和经度模式。
- 控制图层叠加：
  - 数据层
  - 海岸线
  - 流域边界
  - 经纬网
  - 河流网络
- 渲染预览图。
- 导出图件。

该页面主要用于确认输出结果是否正常、空间范围是否正确、滤波产品是否存在明显异常，以及为报告或论文准备初步图件。

### 5.7 Run Output

Run Output 页面用于运行监控和日志查看，主要功能包括：

- 查看当前运行摘要。
- 查看解析后的配置上下文。
- 查看解析后的输出路径。
- 暂停、停止或清理运行状态。
- 显示实时处理日志。
- 辅助定位输入缺失、配置错误、保存失败、并行任务异常等问题。

对于 HPC 运行，应优先检查 `outputs/remote/<jobid>/logs/` 和对应作业输出目录；对于本地运行，应检查 `outputs/local/` 以及 GUI 控制台日志。

## 6. 输入数据与输出产品

### 6.1 主要输入

程序常见输入包括：

- GRACE/GRACE-FO Level-2 GSM 球谐系数文件。
- SLR 或其他兼容 `.gfc` 格式数据。
- Degree-1 地心项替换数据。
- C20/C30 SLR 替换数据。
- GIA 模型文件。
- DDK 滤波文件。
- Mascon 参考 NetCDF 产品。
- 流域边界、海岸线和其他矢量边界。
- 陆海掩膜或辅助格网。

### 6.2 主要输出

程序输出通常包括：

- 月尺度 EWH 格网产品。
- 不同滤波方法的 stack 产品。
- 趋势、年周期、半年周期图件。
- 流域平均时间序列。
- 泄漏校正结果。
- 指标、诊断表和处理日志。
- 可视化预览图和导出图件。

本地输出约定为：

```text
outputs/local/...
```

HPC/SLURM 输出约定为：

```text
outputs/remote/<jobid>/...
```

## 7. 适用范围

本程序适用于：

- GRACE/GRACE-FO Level-2 球谐系数到 EWH 格网产品的批量处理。
- 多滤波方法对比和产品生成。
- 全球或区域水储量变化分析。
- 流域、湖泊、冰盖边缘、地下水区等区域的时间序列提取。
- GIA 改正、低阶项替换和均值场扣除等标准预处理流程。
- 与 Mascon 产品或其他参考数据进行对比分析。
- 本地桌面交互式处理与 HPC 大规模运行。
- 科研项目中的结果预览、流程复现和方法调试。

不建议将本程序直接用于以下场景，除非用户已补充相应验证和配置：

- 非 GRACE/GRACE-FO 数据源且格式不兼容 `.gfc` 或现有读取器的任务。
- 需要实时业务化生产、自动告警或高可用服务的系统。
- 对误差传播、协方差和不确定度有严格审计要求但未启用相应误差输入的任务。
- 未准备低阶项、GIA、DDK、边界或参考数据却要求完整科学产品的任务。
- 未经验证的极高分辨率全球格网或超长时间序列任务。

## 8. 配置与复现建议

程序使用统一 JSON 配置，常用配置文件位于：

```text
configs/default.json
configs/user.json
```

建议遵循以下原则：

- 运行前保存用户配置，保留可复现的 JSON 文件。
- 更换处理中心、版本、数据目录或时间范围后，重新执行路径验证和时间覆盖检查。
- HSAF 输入默认使用 P4M6，并保持 `pre_hankel_input` 与实际输入路由一致。
- HPC 当前运行建议设置 `cfg.parallel.nWorkers=52`，并确保 SLURM 的 `--cpus-per-task=52` 与 MATLAB parallel workers 匹配。
- 多流域模块通过 JSON 显式控制，不应默认自动启用。
- Mascon 参考匹配应允许容差内最近月份匹配，避免不必要地丢失月份。
- 对重要实验保留配置文件、日志、输出目录和图件，便于复查。

## 9. 稳定性与运行注意事项

为降低大规模运行时的失败风险，建议注意：

- 运行前确认所有输入文件在本地或远程机器上存在，尤其是 stack、Mascon、DDK、低阶项和 GIA 文件。
- 大型 MAT 输出应采用安全保存策略：先写入临时文件，再原子移动到目标文件。
- 避免在 `parfor` 或多 worker 中同时写同一个输出文件。
- 大型中间变量在每个滤波步骤后及时清理，降低峰值内存和 I/O 压力。
- 远程输出目录和日志目录不要长期堆积过多旧结果，避免文件系统压力。
- HPC 任务如果日志长时间安静，应结合 CPU 占用、进程状态、输出文件数量和 SLURM 状态判断，不要只根据日志判断是否卡死。
- GUI 调试时如遇界面或绘图问题，应优先从 `python -m grace_pipeline.gui_entry` 启动，以便直接查看 Python 异常。

## 10. 常见使用流程

推荐的 GUI 使用顺序如下：

1. 打开程序。
2. 进入 Data Paths，设置并验证输入、输出和参考数据路径。
3. 进入 Processing Setup，设置时间范围、格网、改正项和滤波方法。
4. 回到 Dashboard，保存配置并启动 Run Filters。
5. 在 Run Output 查看日志、进度和输出路径。
6. 进入 Preview Results 加载输出 stack，检查空间图件。
7. 如需要区域研究，进入 Basin Analysis 提取流域时间序列。
8. 如需要修正边界泄漏，进入 Leakage Correction 运行校正并复查结果。

对于批量或远程运行，推荐流程如下：

1. 本地用 GUI 或 CLI 验证配置。
2. 确认远程输入文件齐全。
3. 使用 `hpc.ps1` 同步并提交作业。
4. 监控 SLURM 状态和日志。
5. 将 `outputs/remote/<jobid>/` 结果拉回本地。
6. 使用 Preview 或脚本复查图件和指标。

## 11. 相关文档

- [项目总览 README](/G:/GRACE_Level2_pipeline_exc/README.md)
- [Python 使用说明](/G:/GRACE_Level2_pipeline_exc/python/README.md)
- [MATLAB 使用说明](/G:/GRACE_Level2_pipeline_exc/matlab/README.md)
- [HPC 使用说明](/G:/GRACE_Level2_pipeline_exc/docs/HPC_PYTHON_MATLAB_USAGE.md)
- [桌面应用概览](/G:/GRACE_Level2_pipeline_exc/docs/GRACE_L2_DESKTOP_OVERVIEW.md)
- [滤波方法与算法说明](/G:/GRACE_Level2_pipeline_exc/docs/GRACE_FILTER_METHODS_AND_ALGORITHM.md)
- [工程结构说明](/G:/GRACE_Level2_pipeline_exc/docs/ENGINEERING_STRUCTURE.md)
