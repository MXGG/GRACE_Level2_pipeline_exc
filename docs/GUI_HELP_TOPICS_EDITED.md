# GRACE-L2 GUI Help Topics — Revised Copy

This file is the editable source copy for GUI help text. Each topic contains Chinese and English text. The previous control-level help topic has been removed from the Help dialog; control-level tooltips can remain in code where needed.

## Topic Index
1. `about_software` — 关于本软件 / About this software
2. `getting_started` — 快速开始 / Getting started
3. `dashboard` — 总览页面 / Dashboard
4. `data_paths` — 数据路径 / Data Paths
5. `processing` — 滤波处理 / Processing Setup
6. `leakage` — 泄漏校正 / Leakage Correction
7. `basin` — 流域分析 / Basin Analysis
8. `preview` — 预览页面 / Preview
9. `monitor` — 运行监控与日志 / Run Monitor and logs
10. `copy_paths` — 复制路径与输出结构 / Copying paths and output layout
11. `troubleshooting` — 常见错误排查 / Troubleshooting
12. `shortcuts` — 快捷键说明 / Keyboard shortcuts
13. `version` — 版本与运行环境 / Version and runtime information
14. `external_links` — 外部文档链接 / External links

## 1. 关于本软件 / About this software
- Key: `about_software`
- Icon: `ⓘ`
- Tags: about, software, version, developer, MXGG, 关于, 开发者

### 中文标题
关于本软件

### 中文正文
# 关于本软件

**GRACE-L2 精密处理流程** 是一款面向 GRACE/GRACE-FO Level-2 球谐数据的桌面处理软件，支持等效水高格网产品生成、滤波处理、泄漏校正、流域统计、结果预览。

#### 软件信息

- **软件名称：** GRACE Level-2 Pipeline
- **当前版本：** 0.1
- **运行环境：** Python 3.12.10 / PySide 6.11.1
- **项目仓库：** https://github.com/MXGG/GRACE_Level2_pipeline_exc

#### 开发与维护

- **开发者 / 维护者：** MXGG
- **GitHub 主页：** https://github.com/MXGG
- **项目仓库：** MXGG/GRACE_Level2_pipeline_exc

#### 适用场景

本软件主要用于本地科学计算、批处理配置、结果检查和流程复现管理。建议在正式处理前完成路径校验，并保留运行配置与日志，便于后续追踪和复现。

### English Title
About this software

### English Body
# About this software

**GRACE Level-2 Pipeline** is a desktop application for GRACE/GRACE-FO Level-2 spherical harmonic data processing. It supports gridded equivalent water height generation, filtering, leakage correction, basin statistics, result preview, and diagnostic export.

#### Software information

- **Application:** GRACE Level-2 Pipeline
- **Version:** 0.1
- **Runtime:** Python 3.12.10 / PySide 6.11.1
- **Repository:** https://github.com/MXGG/GRACE_Level2_pipeline_exc

#### Development and maintenance

- **Developer / maintainer:** MXGG
- **GitHub:** https://github.com/MXGG
- **Project repository:** MXGG/GRACE_Level2_pipeline_exc

#### Intended use

This software is intended for local scientific processing, batch configuration, result inspection, and reproducible workflow management. Before a full run, validate all paths and keep the active configuration and logs for traceability.

---

## 2. 快速开始 / Getting started
- Key: `getting_started`
- Icon: `★`
- Tags: start, workflow, quick

### 中文标题
快速开始

### 中文正文
# 快速开始

本程序用于将 GRACE/GRACE-FO Level-2 月度球谐系数转换为格网等效水高产品，并支持滤波处理、泄漏校正、流域统计和图件预览。

#### 推荐流程

1. 打开 **数据路径**，设置输入数据、辅助文件、低阶项、GIA、DDK、边界文件和输出目录。
2. 打开 **滤波处理**，核对时间范围、最大阶数、格网分辨率、滤波方法和并行设置。
3. 返回 **总览页面**，确认配置状态为“可开始处理”后启动流程。
4. 在 **运行监控与日志** 中查看阶段进度、警告信息和输出路径。
5. 使用 **预览页面**、**泄漏校正** 或 **流域分析** 进行后处理检查与诊断。

#### 使用原则

原始 Level-2 数据不应被程序修改。校正栈、图件、日志和摘要文件应统一写入当前配置的输出目录。

### English Title
Getting started

### English Body
# Getting started

This program converts monthly GRACE/GRACE-FO Level-2 spherical harmonic coefficients into gridded equivalent water height products, with support for filtering, leakage correction, basin statistics, and figure preview.

#### Recommended workflow

1. Open **Data Paths** and configure input data, auxiliary files, low-degree terms, GIA, DDK kernels, boundary files, and the output directory.
2. Open **Processing Setup** and check the time range, maximum degree, grid resolution, filter methods, and parallel settings.
3. Return to **Dashboard** and start processing after the status indicates that the configuration is ready.
4. Use **Run Monitor and logs** to review stage progress, warnings, and output locations.
5. Use **Preview**, **Leakage Correction**, or **Basin Analysis** for post-processing checks and diagnostics.

#### Basic rule

Raw Level-2 data should not be modified by the program. Corrected stacks, figures, logs, and summary files should be written under the configured output directory.

---

## 3. 总览页面 / Dashboard
- Key: `dashboard`
- Icon: `⌂`
- Tags: dashboard, run, status, summary

### 中文标题
总览页面

### 中文正文
# 总览页面

总览页面用于集中查看项目状态、配置摘要、运行进度和输出位置，是正式运行前的主要检查入口。

#### 主要功能

- **配置摘要：** 显示当前配置名称、处理中心、时间范围、滤波链和输出根目录。
- **路径校验：** 运行前检查必要目录和辅助文件是否可访问。
- **运行控制：** 启动、暂停、恢复或停止当前处理流程。
- **输出定位：** 显示月度格网、栈文件、图件和日志的保存位置。

#### 使用建议

建议将总览页面作为正式运行前的最后检查点。仅当状态显示为可运行时，再启动完整流程。

### English Title
Dashboard

### English Body
# Dashboard

The Dashboard summarizes project status, configuration details, run progress, and output locations. It is the main checkpoint before starting a full run.

#### Main functions

- **Configuration summary:** displays the active configuration name, processing center, time span, filter chain, and output root.
- **Path validation:** checks whether required directories and auxiliary files are accessible before processing.
- **Run controls:** starts, pauses, resumes, or stops the active workflow.
- **Output locations:** shows where monthly grids, stacks, figures, and logs are saved.

#### Recommended use

Use the Dashboard as the final checkpoint before a full run. Start processing only after the status indicates that the configuration is ready.

---

## 4. 数据路径 / Data Paths
- Key: `data_paths`
- Icon: `◧`
- Tags: path, directory, input, output

### 中文标题
数据路径

### 中文正文
# 数据路径

数据路径页面用于配置流程所需的输入、辅助数据和输出目录，确保程序能够正确读取 Level-2 产品并保存可复现结果。

#### 输入数据

- **GFC/GSM 输入：** HUST-Grace2024、CSR、GFZ、JPL 或其他兼容格式的月度 Level-2 球谐文件。
- **低阶项替换：** C20、C30 和一阶项替换文件，通常来自 SLR 或其他外部约束。
- **GIA 模型：** 可选的冰川均衡调整改正文件。
- **DDK 核文件：** 启用 DDK 滤波时需要指定对应核函数目录。
- **边界与参考数据：** 流域边界、海岸线、Mascon 产品或其他验证数据。

#### 输出目录

- **local/stacks：** 校正后的栈产品。
- **local/monthly_mat：** 月尺度转换结果。
- **local/plots：** 预览图和诊断图件。
- **local/logs：** 运行日志和处理记录。

#### 使用建议

建议使用较短的英文路径，避免空格、特殊符号和需要管理员权限的目录。

### English Title
Data Paths

### English Body
# Data Paths

The Data Paths page configures input data, auxiliary files, and output directories so that the program can read Level-2 products and save reproducible results correctly.

#### Input data

- **GFC/GSM input:** monthly Level-2 spherical harmonic files from HUST-Grace2024, CSR, GFZ, JPL, or other compatible products.
- **Low-degree replacement:** C20, C30, and degree-1 replacement files, usually derived from SLR or other external constraints.
- **GIA model:** optional glacial isostatic adjustment correction file.
- **DDK kernels:** kernel directory required when DDK filtering is enabled.
- **Boundaries and references:** basin boundaries, coastlines, mascon products, or other validation data.

#### Output directories

- **local/stacks:** corrected stack products.
- **local/monthly_mat:** monthly converted results.
- **local/plots:** preview and diagnostic figures.
- **local/logs:** run logs and processing records.

#### Path advice

Prefer short ASCII paths. Avoid spaces, special characters, and directories that require administrator permission.

---

## 5. 滤波处理 / Processing Setup
- Key: `processing`
- Icon: `Σ`
- Tags: processing, filter, hankel, ddk, gaussian

### 中文标题
滤波处理

### 中文正文
# 滤波处理

滤波处理页面用于设置 GRACE/GRACE-FO Level-2 数据处理参数，包括时间范围、低阶项替换、GIA 改正、格网合成、滤波方法和并行执行。

#### 关键设置

- **时间范围：** 设置起止月份，并在处理索引中保留可识别的缺失月份。
- **反演参数：** 设置最大阶次、Love 数、单位转换和低阶项替换策略。
- **格网合成：** 设置空间分辨率、经度范围和输出单位。
- **滤波方法：** 配置 Gaussian、Fan、PnMm 去相关、DDK 和 HSAF 等方法参数。
- **并行执行：** 设置工作进程数量和运行限制。Windows 打包版建议使用较保守的并行数量。

#### 质量建议

如需对比不同处理中心、版本、最大阶次、基准期或低阶项替换策略，应在配置和日志中明确记录。除非有明确目的，不建议在同一次处理流程中混用来源或处理口径不同的产品。

### English Title
Processing Setup

### English Body
# Processing Setup

The Processing Setup page defines parameters for GRACE/GRACE-FO Level-2 processing, including time range, low-degree replacement, GIA correction, grid synthesis, filtering, and parallel execution.

#### Key settings

- **Time range:** set start and end months, and keep missing months identifiable in the processing index.
- **Inversion parameters:** set maximum degree/order, Love numbers, unit conversion, and low-degree replacement policy.
- **Grid synthesis:** set spatial resolution, longitude range, and output unit.
- **Filters:** configure Gaussian, Fan, PnMm decorrelation, DDK, and HSAF parameters.
- **Parallel execution:** set worker count and runtime limits. Conservative worker counts are recommended for packaged Windows builds.

#### Quality advice

When comparing products from different centers, releases, maximum degrees, baselines, or replacement policies, document these differences in the configuration and logs. Avoid mixing products with different processing conventions in a single run unless it is intentional.

---

## 6. 泄漏校正 / Leakage Correction
- Key: `leakage`
- Icon: `↔`
- Tags: leakage, scale factor, correction, mascon

### 中文标题
泄漏校正

### 中文正文
# 泄漏校正

泄漏校正页面用于在格网或栈产品生成后，估计并修正球谐截断、空间滤波和区域边界造成的信号泄漏误差。

#### 处理步骤

1. 选择输入栈文件，通常为已生成的 EWH/TWSA 产品。
2. 检查数据维度、坐标约定、时间标签和单位是否正确。
3. 选择全球或区域校正模式。区域校正需要可靠的边界文件。
4. 选择校正策略，或使用程序推荐设置。
5. 运行校正，并检查 `corrected_stack`、`difference_stack`、`summary` 和 `preview_manifest` 等输出。

#### 方法说明

- **尺度因子：** 用于恢复截断和滤波后被衰减的信号振幅。
- **加法校正：** 基于外部参考或合成信号估计内泄漏与外泄漏分量。
- **Mascon 产品：** 原生 Mascon 产品已有特定反演与正则化处理，不建议直接重复套用球谐泄漏校正流程。

### English Title
Leakage Correction

### English Body
# Leakage Correction

The Leakage Correction page estimates and corrects signal leakage caused by spherical harmonic truncation, spatial filtering, and regional boundaries after gridded or stacked products have been generated.

#### Workflow

1. Select the input stack, usually a generated EWH/TWSA product.
2. Check data dimensions, coordinate convention, time labels, and units.
3. Select global or regional correction mode. Regional correction requires a reliable boundary file.
4. Choose a correction strategy or use the recommended settings.
5. Run the correction and inspect outputs such as `corrected_stack`, `difference_stack`, `summary`, and `preview_manifest`.

#### Method notes

- **Scale factor:** restores signal amplitudes damped by truncation and filtering.
- **Additive correction:** estimates leakage-in and leakage-out components using external references or synthetic signals.
- **Mascon products:** native mascon products already include their own inversion and regularization strategy, so they should not be blindly processed through a second spherical-harmonic leakage correction workflow.

---

## 7. 流域分析 / Basin Analysis
- Key: `basin`
- Icon: `◌`
- Tags: basin, statistics, time series

### 中文标题
流域分析

### 中文正文
# 流域分析

流域分析页面用于将格网产品转换为流域平均时间序列和区域统计结果，适用于水文解释、方法对比和结果验证。

#### 主要功能

- 读取栈产品和流域边界文件。
- 在产品格网上构建面积加权流域掩膜。
- 生成流域平均 TWSA/EWH 时间序列。
- 拟合年周期、半年周期、长期趋势、RMS 和残差统计量。
- 导出统计表格和图片。

#### 质量建议

比较不同滤波方法或不同中心产品前，应确认流域名称字段、边界文件、经度约定、单位和基准期一致。

### English Title
Basin Analysis

### English Body
# Basin Analysis

The Basin Analysis page converts gridded products into basin-mean time series and regional statistics for hydrological interpretation, method comparison, and result validation.

#### Main functions

- Read a stack product and a basin boundary file.
- Build area-weighted basin masks on the product grid.
- Generate basin-mean TWSA/EWH time series.
- Fit annual, semi-annual, long-term trend, RMS, and residual statistics.
- Export statistical tables and optional diagnostic figures.

#### Quality advice

Before comparing different filters or processing centers, confirm that basin name fields, boundary files, longitude convention, units, and baseline period are consistent.

---

## 8. 预览页面 / Preview
- Key: `preview`
- Icon: `◎`
- Tags: preview, map, plot, export

### 中文标题
预览页面

### 中文正文
# 预览页面

预览页面用于快速检查地图产品、时间帧和诊断图件，帮助发现明显的路径、坐标、单位或处理异常。预览结果仅用于检查，不应替代定量验证。

#### 支持检查

- 打开栈产品并浏览月尺度图像。
- 检查空间分布、海岸线、流域边界和投影设置。
- 对比泄漏校正前后的 `corrected_stack` 与 `difference_stack`。
- 导出报告或快速诊断所需图件。

#### 解释建议

视觉检查应与流域统计、独立参考数据或频谱诊断结合使用。仅凭地图外观无法充分判断方法优劣。

### English Title
Preview

### English Body
# Preview

The Preview page provides quick inspection of map products, time frames, and diagnostic figures. It helps identify obvious path, coordinate, unit, or processing issues. Preview results are for inspection only and should not replace quantitative validation.

#### Supported checks

- Open stack products and browse monthly frames.
- Inspect spatial patterns, coastlines, basin boundaries, and projection settings.
- Compare `corrected_stack` and `difference_stack` before and after leakage correction.
- Export figures for reports or quick diagnostics.

#### Interpretation advice

Visual inspection should be combined with basin statistics, independent references, or spectral diagnostics. Map appearance alone is not sufficient for evaluating method performance.

---

## 9. 运行监控与日志 / Run Monitor and logs
- Key: `monitor`
- Icon: `▣`
- Tags: monitor, log, warning, error

### 中文标题
运行监控与日志

### 中文正文
# 运行监控与日志

运行监控与日志页面用于查看流程进度、阶段信息、输出路径、警告和错误信息，适合长任务运行、结果追踪和问题排查。

#### 重点关注

- **当前阶段：** 输入索引、预处理、滤波、格网合成、流域分析或泄漏校正。
- **运行进度：** 已完成月份或任务数量，以及相对于总任务量的比例。
- **警告信息：** 缺失月份、路径错误、格式不支持、参数回退或外部程序调用异常。
- **输出路径：** 当前运行实际生成的文件位置。

#### 排查建议

如果运行失败，请保留日志文件和当前 JSON 配置。使用相同输入和配置重新运行，是复现问题和定位原因的基础。

### English Title
Run Monitor and logs

### English Body
# Run Monitor and logs

The Run Monitor and logs page displays workflow progress, stage messages, output paths, warnings, and errors. It is useful for long runs, result tracking, and troubleshooting.

#### What to inspect

- **Current stage:** input indexing, preprocessing, filtering, grid synthesis, basin analysis, or leakage correction.
- **Progress:** completed months or tasks and their proportion of the expected workload.
- **Warnings:** missing months, invalid paths, unsupported formats, parameter fallback, or external program failures.
- **Output paths:** actual files produced by the current run.

#### Troubleshooting advice

If a run fails, keep the log file and the active JSON configuration. Re-running with the same inputs and configuration is the basis for reproducing and diagnosing the issue.

---

## 10. 复制路径与输出结构 / Copying paths and output layout
- Key: `copy_paths`
- Icon: `⧉`
- Tags: copy, clipboard, output, path

### 中文标题
复制路径与输出结构

### 中文正文
# 复制路径与输出结构

多数路径输入框、日志窗口和文本区域均支持系统快捷键复制。本帮助窗口也提供快捷按钮，可将标准输出目录结构复制到剪贴板。

#### 标准输出结构

```text
OUTPUT/
├─ local/
│  ├─ monthly_mat/
│  ├─ stacks/
│  ├─ plots/
│  ├─ logs/
│  ├─ leakage/
│  └─ basin/
└─ CACHE/
   └─ qt_ui/
```

#### 推荐文件命名

- **corrected_stack.mat：** 主要校正格网产品。
- **difference_stack.mat：** 校正差值或诊断场。
- **summary.json：** 机器可读的运行摘要。
- **preview_manifest.json：** 预览页面入口文件。

#### Windows 路径建议

重批处理建议使用较短的英文路径。便携版程序运行时，避免将输出写入 `Program Files`、系统盘根目录等可能需要管理员权限的位置。

### English Title
Copying paths and output layout

### English Body
# Copying paths and output layout

Most path fields, log windows, and text areas support standard copy shortcuts. The Help window also provides a shortcut button for copying the standard output layout to the clipboard.

#### Standard output layout

```text
OUTPUT/
├─ local/
│  ├─ monthly_mat/
│  ├─ stacks/
│  ├─ plots/
│  ├─ logs/
│  ├─ leakage/
│  └─ basin/
└─ CACHE/
   └─ qt_ui/
```

#### Recommended file naming

- **corrected_stack.mat:** main corrected gridded product.
- **difference_stack.mat:** correction difference or diagnostic field.
- **summary.json:** machine-readable run summary.
- **preview_manifest.json:** entry file for the Preview page.

#### Windows path advice

Use short ASCII paths for heavy batch processing. For portable builds, avoid writing outputs to locations that may require administrator permission, such as `Program Files` or the root of the system drive.

---

## 11. 常见错误排查 / Troubleshooting
- Key: `troubleshooting`
- Icon: `!`
- Tags: error, troubleshooting, fail, freeze

### 中文标题
常见错误排查

### 中文正文
# 常见错误排查

#### 路径校验失败

检查路径是否存在、文件后缀是否符合要求，以及当前用户是否具有读写权限。输出目录建议使用普通用户可写的项目路径。

#### 未识别到有效月份

检查 GSM/GFC 文件命名、处理中心、版本选择和时间范围。GRACE/GRACE-FO 部分时段存在缺失月份是正常现象，但文件名中的月份标识必须能够被程序解析。

#### DDK 滤波失败

检查 DDK 核函数目录和所选 DDK 等级是否匹配。如果当前任务不需要 DDK，可先关闭该方法，并使用 Gaussian、Fan 或 HSAF 进行测试。

#### MATLAB 或外部脚本失败

检查 MATLAB 可执行文件路径、工具箱路径和命令行调用权限。可在日志面板复制完整命令和错误信息，用于复现和排查。

#### GUI 运行时卡顿

Windows 打包版建议使用较保守的并行进程数。大型 HSAF 或泄漏校正任务建议先选择少量月份试运行，确认配置无误后再执行完整处理。

### English Title
Troubleshooting

### English Body
# Troubleshooting

#### Path validation fails

Check whether the path exists, whether the file extension matches the requirement, and whether the current user has read/write permission. Use a normal user-writable project directory for outputs.

#### No valid months are detected

Check GSM/GFC file naming, processing center, release selection, and time range. Missing months are normal for some GRACE/GRACE-FO periods, but the month identifier in the file name must be readable by the program.

#### DDK filtering fails

Check whether the DDK kernel directory matches the selected DDK level. If DDK is not required for the current task, disable it and test with Gaussian, Fan, or HSAF first.

#### MATLAB or external scripts fail

Check the MATLAB executable path, toolbox path, and command-line permission. Copy the full command and error message from the log panel for reproduction and diagnosis.

#### GUI freezes during processing

Use conservative worker counts in packaged Windows builds. For large HSAF or leakage-correction jobs, test a small month subset first and run the full task after the configuration is confirmed.

---

## 12. 快捷键说明 / Keyboard shortcuts
- Key: `shortcuts`
- Icon: `⌨`
- Tags: shortcut, keyboard, ctrl

### 中文标题
快捷键说明

### 中文正文
# 快捷键说明

| 快捷键 | 作用 |
|---|---|
| Ctrl + Plus | 增大界面字号。 |
| Ctrl + Minus | 减小界面字号。 |
| Ctrl + 0 | 重置界面字号缩放。 |
| Ctrl + C | 复制路径输入框、日志或文档中的选中文本。 |
| Ctrl + A | 全选当前聚焦输入框或日志视图中的文本。 |
| Esc | 在支持的弹窗中关闭对话框。 |

部分操作系统或输入法可能占用组合键。遇到快捷键冲突时，可使用界面按钮完成相同操作。

### English Title
Keyboard shortcuts

### English Body
# Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl + Plus | Increase UI font size. |
| Ctrl + Minus | Decrease UI font size. |
| Ctrl + 0 | Reset UI font scale. |
| Ctrl + C | Copy selected text in path fields, logs, or documentation. |
| Ctrl + A | Select all text in the focused input field or log view. |
| Esc | Close supported dialogs. |

Some operating systems or input methods may reserve key combinations. If a shortcut conflicts with the system, use the visible UI button instead.

---

## 13. 版本与运行环境 / Version and runtime information
- Key: `version`
- Icon: `ⓘ`
- Tags: version, runtime, environment

### 中文标题
版本与运行环境

### 中文正文
# 版本与运行环境

版本与运行环境页面记录 GUI 版本、仓库分支和本地运行环境。反馈问题时，建议同时提供这些信息，以便快速复现和定位。

#### 当前版本

- **应用程序：** GRACE Level-2 Pipeline
- **GUI 版本：** 0.1
- **仓库分支：** wip/python-runtime-qt-monitor-refactor

#### 问题反馈清单

- 当前 JSON 配置文件。
- 日志文件或复制的错误信息。
- 输入文件类型、处理中心和版本。
- 操作系统、Python 版本和 PySide 版本。
- 复现步骤和出现问题的具体页面。

### English Title
Version and runtime information

### English Body
# Version and runtime information

The Version and runtime information page records the GUI version, repository branch, and local runtime environment. Include this information when reporting an issue so that the problem can be reproduced and diagnosed more quickly.

#### Current version

- **Application:** GRACE Level-2 Pipeline
- **GUI version:** 0.1
- **Repository branch:** wip/python-runtime-qt-monitor-refactor

#### Issue report checklist

- Active JSON configuration.
- Log file or copied error message.
- Input file type, processing center, and release.
- Operating system, Python version, and PySide version.
- Steps to reproduce and the page where the issue occurred.

---

## 14. 外部文档链接 / External links
- Key: `external_links`
- Icon: `↗`
- Tags: link, github, release, data

### 中文标题
外部文档链接

### 中文正文
# 外部文档链接

本页面汇总源码、版本发布、问题反馈以及上游数据和文档入口。

#### 常用链接

- 项目仓库
- GitHub Releases
- 问题反馈
- NASA PO.DAAC GRACE/GRACE-FO 数据
- UTCSR GRACE 资源
- ICGEM 重力场模型

#### 引用建议

外部页面、数据版本和下载地址可能更新。引用数据源时，应记录访问日期、产品名称、发布版本和处理中心。

### English Title
External links

### English Body
# External links

This page collects entries for source code, releases, issue reporting, and upstream data or documentation.

#### Common links

- Project repository
- GitHub Releases
- Issue tracker
- NASA PO.DAAC GRACE/GRACE-FO data
- UTCSR GRACE resources
- ICGEM gravity field models

#### Citation advice

External pages, data releases, and download addresses may change. When citing a data source, record the access date, product name, release version, and processing center.

---
