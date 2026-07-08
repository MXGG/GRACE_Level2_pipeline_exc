"""Structured help documentation dialog for the Qt desktop interface."""

from __future__ import annotations

import contextlib
import platform
import re
import sys
from dataclasses import dataclass

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

APP_VERSION = "0.1"
REPOSITORY_URL = "https://github.com/MXGG/GRACE_Level2_pipeline_exc"
RELEASES_URL = f"{REPOSITORY_URL}/releases"
ISSUES_URL = f"{REPOSITORY_URL}/issues"


@dataclass(frozen=True)
class HelpTopic:
    key: str
    title_en: str
    title_zh: str
    icon: str
    html_en: str
    html_zh: str
    tags: tuple[str, ...] = ()


def _topic(
    title_en: str,
    title_zh: str,
    key: str,
    icon: str,
    body_en: str,
    body_zh: str,
    tags: tuple[str, ...] = (),
) -> HelpTopic:
    return HelpTopic(
        key=key,
        title_en=title_en,
        title_zh=title_zh,
        icon=icon,
        html_en=body_en,
        html_zh=body_zh,
        tags=tags,
    )


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")


HELP_TOPICS: list[HelpTopic] = [
    _topic(
        'About this software',
        '关于本软件',
        'about_software',
        'ⓘ',
        f"""
        <h1>About this software</h1>
        <p><b>GRACE Level-2 Pipeline</b> is a desktop application for GRACE/GRACE-FO Level-2 spherical harmonic data processing. It supports gridded equivalent water height generation, filtering, leakage correction, basin statistics, result preview, and diagnostic export.</p>
        <h2>Software information</h2>
        <ul>
          <li><b>Application:</b> GRACE Level-2 Pipeline</li>
          <li><b>Version:</b> {APP_VERSION}</li>
          <li><b>Runtime:</b> Python {sys.version.split()[0]} / PySide {PYSIDE_VERSION}</li>
          <li><b>Repository:</b> <a href="{REPOSITORY_URL}">{REPOSITORY_URL}</a></li>
        </ul>
        <h2>Development and maintenance</h2>
        <ul>
          <li><b>Developer / maintainer:</b> MXGG</li>
          <li><b>GitHub:</b> <a href="https://github.com/MXGG">https://github.com/MXGG</a></li>
          <li><b>Project repository:</b> MXGG/GRACE_Level2_pipeline_exc</li>
        </ul>
        <h2>Intended use</h2>
        <p>This software is intended for local scientific processing, batch configuration, result inspection, and reproducible workflow management. Before a full run, validate all paths and keep the active configuration and logs for traceability.</p>
        <p>---</p>
                """
,
        f"""
        <h1>关于本软件</h1>
        <p><b>GRACE-L2 精密处理流程</b> 是一款面向 GRACE/GRACE-FO Level-2 球谐数据的桌面处理软件，支持等效水高格网产品生成、滤波处理、泄漏校正、流域统计、结果预览。</p>
        <h2>软件信息</h2>
        <ul>
          <li><b>软件名称：</b> GRACE Level-2 Pipeline</li>
          <li><b>当前版本：</b> {APP_VERSION}</li>
          <li><b>运行环境：</b> Python {sys.version.split()[0]} / PySide {PYSIDE_VERSION}</li>
          <li><b>项目仓库：</b> <a href="{REPOSITORY_URL}">{REPOSITORY_URL}</a></li>
        </ul>
        <h2>开发与维护</h2>
        <ul>
          <li><b>开发者 / 维护者：</b> MXGG</li>
          <li><b>GitHub 主页：</b> <a href="https://github.com/MXGG">https://github.com/MXGG</a></li>
          <li><b>项目仓库：</b> MXGG/GRACE_Level2_pipeline_exc</li>
        </ul>
        <h2>适用场景</h2>
        <p>本软件主要用于本地科学计算、批处理配置、结果检查和流程复现管理。建议在正式处理前完成路径校验，并保留运行配置与日志，便于后续追踪和复现。</p>
                """
,
        ('about', 'software', 'version', 'developer', 'MXGG', '关于', '开发者'),
    ),
    _topic(
        'Getting started',
        '快速开始',
        'getting_started',
        '★',
        """
        <h1>Getting started</h1>
        <p>This program converts monthly GRACE/GRACE-FO Level-2 spherical harmonic coefficients into gridded equivalent water height products, with support for filtering, leakage correction, basin statistics, and figure preview.</p>
        <h2>Recommended workflow</h2>
        <ol>
          <li>Open <b>Data Paths</b> and configure input data, auxiliary files, low-degree terms, GIA, DDK kernels, boundary files, and the output directory.</li>
          <li>Open <b>Processing Setup</b> and check the time range, maximum degree, grid resolution, filter methods, and parallel settings.</li>
          <li>Return to <b>Dashboard</b> and start processing after the status indicates that the configuration is ready.</li>
          <li>Use <b>Run Monitor and logs</b> to review stage progress, warnings, and output locations.</li>
          <li>Use <b>Preview</b>, <b>Leakage Correction</b>, or <b>Basin Analysis</b> for post-processing checks and diagnostics.</li>
        </ol>
        <h2>Basic rule</h2>
        <p>Raw Level-2 data should not be modified by the program. Corrected stacks, figures, logs, and summary files should be written under the configured output directory.</p>
        <p>---</p>
                """
,
        """
        <h1>快速开始</h1>
        <p>本程序用于将 GRACE/GRACE-FO Level-2 月度球谐系数转换为格网等效水高产品，并支持滤波处理、泄漏校正、流域统计和图件预览。</p>
        <h2>推荐流程</h2>
        <ol>
          <li>打开 <b>数据路径</b>，设置输入数据、辅助文件、低阶项、GIA、DDK、边界文件和输出目录。</li>
          <li>打开 <b>滤波处理</b>，核对时间范围、最大阶数、格网分辨率、滤波方法和并行设置。</li>
          <li>返回 <b>总览页面</b>，确认配置状态为“可开始处理”后启动流程。</li>
          <li>在 <b>运行监控与日志</b> 中查看阶段进度、警告信息和输出路径。</li>
          <li>使用 <b>预览页面</b>、<b>泄漏校正</b> 或 <b>流域分析</b> 进行后处理检查与诊断。</li>
        </ol>
        <h2>使用原则</h2>
        <p>原始 Level-2 数据不应被程序修改。校正栈、图件、日志和摘要文件应统一写入当前配置的输出目录。</p>
                """
,
        ('start', 'workflow', 'quick'),
    ),
    _topic(
        'Dashboard',
        '总览页面',
        'dashboard',
        '⌂',
        """
        <h1>Dashboard</h1>
        <p>The Dashboard summarizes project status, configuration details, run progress, and output locations. It is the main checkpoint before starting a full run.</p>
        <h2>Main functions</h2>
        <ul>
          <li><b>Configuration summary:</b> displays the active configuration name, processing center, time span, filter chain, and output root.</li>
          <li><b>Path validation:</b> checks whether required directories and auxiliary files are accessible before processing.</li>
          <li><b>Run controls:</b> starts, pauses, resumes, or stops the active workflow.</li>
          <li><b>Output locations:</b> shows where monthly grids, stacks, figures, and logs are saved.</li>
        </ul>
        <h2>Recommended use</h2>
        <p>Use the Dashboard as the final checkpoint before a full run. Start processing only after the status indicates that the configuration is ready.</p>
        <p>---</p>
                """
,
        """
        <h1>总览页面</h1>
        <p>总览页面用于集中查看项目状态、配置摘要、运行进度和输出位置，是正式运行前的主要检查入口。</p>
        <h2>主要功能</h2>
        <ul>
          <li><b>配置摘要：</b> 显示当前配置名称、处理中心、时间范围、滤波链和输出根目录。</li>
          <li><b>路径校验：</b> 运行前检查必要目录和辅助文件是否可访问。</li>
          <li><b>运行控制：</b> 启动、暂停、恢复或停止当前处理流程。</li>
          <li><b>输出定位：</b> 显示月度格网、栈文件、图件和日志的保存位置。</li>
        </ul>
        <h2>使用建议</h2>
        <p>建议将总览页面作为正式运行前的最后检查点。仅当状态显示为可运行时，再启动完整流程。</p>
                """
,
        ('dashboard', 'run', 'status', 'summary'),
    ),
    _topic(
        'Data Paths',
        '数据路径',
        'data_paths',
        '◧',
        """
        <h1>Data Paths</h1>
        <p>The Data Paths page configures input data, auxiliary files, and output directories so that the program can read Level-2 products and save reproducible results correctly.</p>
        <h2>Input data</h2>
        <ul>
          <li><b>GFC/GSM input:</b> monthly Level-2 spherical harmonic files from HUST-Grace2024, CSR, GFZ, JPL, or other compatible products.</li>
          <li><b>Low-degree replacement:</b> C20, C30, and degree-1 replacement files, usually derived from SLR or other external constraints.</li>
          <li><b>GIA model:</b> optional glacial isostatic adjustment correction file.</li>
          <li><b>DDK kernels:</b> kernel directory required when DDK filtering is enabled.</li>
          <li><b>Boundaries and references:</b> basin boundaries, coastlines, mascon products, or other validation data.</li>
        </ul>
        <h2>Output directories</h2>
        <ul>
          <li><b>local/stacks:</b> corrected stack products.</li>
          <li><b>local/monthly_mat:</b> monthly converted results.</li>
          <li><b>local/plots:</b> preview and diagnostic figures.</li>
          <li><b>local/logs:</b> run logs and processing records.</li>
        </ul>
        <h2>Path advice</h2>
        <p>Prefer short ASCII paths. Avoid spaces, special characters, and directories that require administrator permission.</p>
        <p>---</p>
                """
,
        """
        <h1>数据路径</h1>
        <p>数据路径页面用于配置流程所需的输入、辅助数据和输出目录，确保程序能够正确读取 Level-2 产品并保存可复现结果。</p>
        <h2>输入数据</h2>
        <ul>
          <li><b>GFC/GSM 输入：</b> HUST-Grace2024、CSR、GFZ、JPL 或其他兼容格式的月度 Level-2 球谐文件。</li>
          <li><b>低阶项替换：</b> C20、C30 和一阶项替换文件，通常来自 SLR 或其他外部约束。</li>
          <li><b>GIA 模型：</b> 可选的冰川均衡调整改正文件。</li>
          <li><b>DDK 核文件：</b> 启用 DDK 滤波时需要指定对应核函数目录。</li>
          <li><b>边界与参考数据：</b> 流域边界、海岸线、Mascon 产品或其他验证数据。</li>
        </ul>
        <h2>输出目录</h2>
        <ul>
          <li><b>local/stacks：</b> 校正后的栈产品。</li>
          <li><b>local/monthly_mat：</b> 月尺度转换结果。</li>
          <li><b>local/plots：</b> 预览图和诊断图件。</li>
          <li><b>local/logs：</b> 运行日志和处理记录。</li>
        </ul>
        <h2>使用建议</h2>
        <p>建议使用较短的英文路径，避免空格、特殊符号和需要管理员权限的目录。</p>
                """
,
        ('path', 'directory', 'input', 'output'),
    ),
    _topic(
        'Processing Setup',
        '滤波处理',
        'processing',
        'Σ',
        """
        <h1>Processing Setup</h1>
        <p>The Processing Setup page defines parameters for GRACE/GRACE-FO Level-2 processing, including time range, low-degree replacement, GIA correction, grid synthesis, filtering, and parallel execution.</p>
        <h2>Key settings</h2>
        <ul>
          <li><b>Time range:</b> set start and end months, and keep missing months identifiable in the processing index.</li>
          <li><b>Inversion parameters:</b> set maximum degree/order, Love numbers, unit conversion, and low-degree replacement policy.</li>
          <li><b>Grid synthesis:</b> set spatial resolution, longitude range, and output unit.</li>
          <li><b>Filters:</b> configure Gaussian, Fan, PnMm decorrelation, DDK, and HSAF parameters.</li>
          <li><b>Parallel execution:</b> set worker count and runtime limits. Conservative worker counts are recommended for packaged Windows builds.</li>
        </ul>
        <h2>Quality advice</h2>
        <p>When comparing products from different centers, releases, maximum degrees, baselines, or replacement policies, document these differences in the configuration and logs. Avoid mixing products with different processing conventions in a single run unless it is intentional.</p>
        <p>---</p>
                """
,
        """
        <h1>滤波处理</h1>
        <p>滤波处理页面用于设置 GRACE/GRACE-FO Level-2 数据处理参数，包括时间范围、低阶项替换、GIA 改正、格网合成、滤波方法和并行执行。</p>
        <h2>关键设置</h2>
        <ul>
          <li><b>时间范围：</b> 设置起止月份，并在处理索引中保留可识别的缺失月份。</li>
          <li><b>反演参数：</b> 设置最大阶次、Love 数、单位转换和低阶项替换策略。</li>
          <li><b>格网合成：</b> 设置空间分辨率、经度范围和输出单位。</li>
          <li><b>滤波方法：</b> 配置 Gaussian、Fan、PnMm 去相关、DDK 和 HSAF 等方法参数。</li>
          <li><b>并行执行：</b> 设置工作进程数量和运行限制。Windows 打包版建议使用较保守的并行数量。</li>
        </ul>
        <h2>质量建议</h2>
        <p>如需对比不同处理中心、版本、最大阶次、基准期或低阶项替换策略，应在配置和日志中明确记录。除非有明确目的，不建议在同一次处理流程中混用来源或处理口径不同的产品。</p>
                """
,
        ('processing', 'filter', 'hankel', 'ddk', 'gaussian'),
    ),
    _topic(
        'Leakage Correction',
        '泄漏校正',
        'leakage',
        '↔',
        """
        <h1>Leakage Correction</h1>
        <p>The Leakage Correction page estimates and corrects signal leakage caused by spherical harmonic truncation, spatial filtering, and regional boundaries after gridded or stacked products have been generated.</p>
        <h2>Workflow</h2>
        <ol>
          <li>Select the input stack, usually a generated EWH/TWSA product.</li>
          <li>Check data dimensions, coordinate convention, time labels, and units.</li>
          <li>Select global or regional correction mode. Regional correction requires a reliable boundary file.</li>
          <li>Choose a correction strategy or use the recommended settings.</li>
          <li>Run the correction and inspect outputs such as <code>corrected_stack</code>, <code>difference_stack</code>, <code>summary</code>, and <code>preview_manifest</code>.</li>
        </ol>
        <h2>Method notes</h2>
        <ul>
          <li><b>Scale factor:</b> restores signal amplitudes damped by truncation and filtering.</li>
          <li><b>Additive correction:</b> estimates leakage-in and leakage-out components using external references or synthetic signals.</li>
          <li><b>Mascon products:</b> native mascon products already include their own inversion and regularization strategy, so they should not be blindly processed through a second spherical-harmonic leakage correction workflow.</li>
        </ul>
        <p>---</p>
                """
,
        """
        <h1>泄漏校正</h1>
        <p>泄漏校正页面用于在格网或栈产品生成后，估计并修正球谐截断、空间滤波和区域边界造成的信号泄漏误差。</p>
        <h2>处理步骤</h2>
        <ol>
          <li>选择输入栈文件，通常为已生成的 EWH/TWSA 产品。</li>
          <li>检查数据维度、坐标约定、时间标签和单位是否正确。</li>
          <li>选择全球或区域校正模式。区域校正需要可靠的边界文件。</li>
          <li>选择校正策略，或使用程序推荐设置。</li>
          <li>运行校正，并检查 <code>corrected_stack</code>、<code>difference_stack</code>、<code>summary</code> 和 <code>preview_manifest</code> 等输出。</li>
        </ol>
        <h2>方法说明</h2>
        <ul>
          <li><b>尺度因子：</b> 用于恢复截断和滤波后被衰减的信号振幅。</li>
          <li><b>加法校正：</b> 基于外部参考或合成信号估计内泄漏与外泄漏分量。</li>
          <li><b>Mascon 产品：</b> 原生 Mascon 产品已有特定反演与正则化处理，不建议直接重复套用球谐泄漏校正流程。</li>
        </ul>
                """
,
        ('leakage', 'scale factor', 'correction', 'mascon'),
    ),
    _topic(
        'Basin Analysis',
        '流域分析',
        'basin',
        '◌',
        """
        <h1>Basin Analysis</h1>
        <p>The Basin Analysis page converts gridded products into basin-mean time series and regional statistics for hydrological interpretation, method comparison, and result validation.</p>
        <h2>Main functions</h2>
        <ul>
          <li>Read a stack product and a basin boundary file.</li>
          <li>Build area-weighted basin masks on the product grid.</li>
          <li>Generate basin-mean TWSA/EWH time series.</li>
          <li>Fit annual, semi-annual, long-term trend, RMS, and residual statistics.</li>
          <li>Export statistical tables and optional diagnostic figures.</li>
        </ul>
        <h2>Quality advice</h2>
        <p>Before comparing different filters or processing centers, confirm that basin name fields, boundary files, longitude convention, units, and baseline period are consistent.</p>
        <p>---</p>
                """
,
        """
        <h1>流域分析</h1>
        <p>流域分析页面用于将格网产品转换为流域平均时间序列和区域统计结果，适用于水文解释、方法对比和结果验证。</p>
        <h2>主要功能</h2>
        <ul>
          <li>读取栈产品和流域边界文件。</li>
          <li>在产品格网上构建面积加权流域掩膜。</li>
          <li>生成流域平均 TWSA/EWH 时间序列。</li>
          <li>拟合年周期、半年周期、长期趋势、RMS 和残差统计量。</li>
          <li>导出统计表格和图片。</li>
        </ul>
        <h2>质量建议</h2>
        <p>比较不同滤波方法或不同中心产品前，应确认流域名称字段、边界文件、经度约定、单位和基准期一致。</p>
                """
,
        ('basin', 'statistics', 'time series'),
    ),
    _topic(
        'Preview',
        '预览页面',
        'preview',
        '◎',
        """
        <h1>Preview</h1>
        <p>The Preview page provides quick inspection of map products, time frames, and diagnostic figures. It helps identify obvious path, coordinate, unit, or processing issues. Preview results are for inspection only and should not replace quantitative validation.</p>
        <h2>Supported checks</h2>
        <ul>
          <li>Open stack products and browse monthly frames.</li>
          <li>Inspect spatial patterns, coastlines, basin boundaries, and projection settings.</li>
          <li>Compare <code>corrected_stack</code> and <code>difference_stack</code> before and after leakage correction.</li>
          <li>Export figures for reports or quick diagnostics.</li>
        </ul>
        <h2>Interpretation advice</h2>
        <p>Visual inspection should be combined with basin statistics, independent references, or spectral diagnostics. Map appearance alone is not sufficient for evaluating method performance.</p>
        <p>---</p>
                """
,
        """
        <h1>预览页面</h1>
        <p>预览页面用于快速检查地图产品、时间帧和诊断图件，帮助发现明显的路径、坐标、单位或处理异常。预览结果仅用于检查，不应替代定量验证。</p>
        <h2>支持检查</h2>
        <ul>
          <li>打开栈产品并浏览月尺度图像。</li>
          <li>检查空间分布、海岸线、流域边界和投影设置。</li>
          <li>对比泄漏校正前后的 <code>corrected_stack</code> 与 <code>difference_stack</code>。</li>
          <li>导出报告或快速诊断所需图件。</li>
        </ul>
        <h2>解释建议</h2>
        <p>视觉检查应与流域统计、独立参考数据或频谱诊断结合使用。仅凭地图外观无法充分判断方法优劣。</p>
                """
,
        ('preview', 'map', 'plot', 'export'),
    ),
    _topic(
        'Run Monitor and logs',
        '运行监控与日志',
        'monitor',
        '▣',
        """
        <h1>Run Monitor and logs</h1>
        <p>The Run Monitor and logs page displays workflow progress, stage messages, output paths, warnings, and errors. It is useful for long runs, result tracking, and troubleshooting.</p>
        <h2>What to inspect</h2>
        <ul>
          <li><b>Current stage:</b> input indexing, preprocessing, filtering, grid synthesis, basin analysis, or leakage correction.</li>
          <li><b>Progress:</b> completed months or tasks and their proportion of the expected workload.</li>
          <li><b>Warnings:</b> missing months, invalid paths, unsupported formats, parameter fallback, or external program failures.</li>
          <li><b>Output paths:</b> actual files produced by the current run.</li>
        </ul>
        <h2>Troubleshooting advice</h2>
        <p>If a run fails, keep the log file and the active JSON configuration. Re-running with the same inputs and configuration is the basis for reproducing and diagnosing the issue.</p>
        <p>---</p>
                """
,
        """
        <h1>运行监控与日志</h1>
        <p>运行监控与日志页面用于查看流程进度、阶段信息、输出路径、警告和错误信息，适合长任务运行、结果追踪和问题排查。</p>
        <h2>重点关注</h2>
        <ul>
          <li><b>当前阶段：</b> 输入索引、预处理、滤波、格网合成、流域分析或泄漏校正。</li>
          <li><b>运行进度：</b> 已完成月份或任务数量，以及相对于总任务量的比例。</li>
          <li><b>警告信息：</b> 缺失月份、路径错误、格式不支持、参数回退或外部程序调用异常。</li>
          <li><b>输出路径：</b> 当前运行实际生成的文件位置。</li>
        </ul>
        <h2>排查建议</h2>
        <p>如果运行失败，请保留日志文件和当前 JSON 配置。使用相同输入和配置重新运行，是复现问题和定位原因的基础。</p>
                """
,
        ('monitor', 'log', 'warning', 'error'),
    ),
    _topic(
        'Copying paths and output layout',
        '复制路径与输出结构',
        'copy_paths',
        '⧉',
        """
        <h1>Copying paths and output layout</h1>
        <p>Most path fields, log windows, and text areas support standard copy shortcuts. The Help window also provides a shortcut button for copying the standard output layout to the clipboard.</p>
        <h2>Standard output layout</h2>
        <p>``<code>text OUTPUT/ ├─ local/ │  ├─ monthly_mat/ │  ├─ stacks/ │  ├─ plots/ │  ├─ logs/ │  ├─ leakage/ │  └─ basin/ └─ CACHE/ └─ qt_ui/ </code>``</p>
        <h2>Recommended file naming</h2>
        <ul>
          <li><b>corrected_stack.mat:</b> main corrected gridded product.</li>
          <li><b>difference_stack.mat:</b> correction difference or diagnostic field.</li>
          <li><b>summary.json:</b> machine-readable run summary.</li>
          <li><b>preview_manifest.json:</b> entry file for the Preview page.</li>
        </ul>
        <h2>Windows path advice</h2>
        <p>Use short ASCII paths for heavy batch processing. For portable builds, avoid writing outputs to locations that may require administrator permission, such as <code>Program Files</code> or the root of the system drive.</p>
        <p>---</p>
                """
,
        """
        <h1>复制路径与输出结构</h1>
        <p>多数路径输入框、日志窗口和文本区域均支持系统快捷键复制。本帮助窗口也提供快捷按钮，可将标准输出目录结构复制到剪贴板。</p>
        <h2>标准输出结构</h2>
        <p>``<code>text OUTPUT/ ├─ local/ │  ├─ monthly_mat/ │  ├─ stacks/ │  ├─ plots/ │  ├─ logs/ │  ├─ leakage/ │  └─ basin/ └─ CACHE/ └─ qt_ui/ </code>``</p>
        <h2>推荐文件命名</h2>
        <ul>
          <li><b>corrected_stack.mat：</b> 主要校正格网产品。</li>
          <li><b>difference_stack.mat：</b> 校正差值或诊断场。</li>
          <li><b>summary.json：</b> 机器可读的运行摘要。</li>
          <li><b>preview_manifest.json：</b> 预览页面入口文件。</li>
        </ul>
        <h2>Windows 路径建议</h2>
        <p>重批处理建议使用较短的英文路径。便携版程序运行时，避免将输出写入 <code>Program Files</code>、系统盘根目录等可能需要管理员权限的位置。</p>
                """
,
        ('copy', 'clipboard', 'output', 'path'),
    ),
    _topic(
        'Troubleshooting',
        '常见错误排查',
        'troubleshooting',
        '!',
        """
        <h1>Troubleshooting</h1>
        <h2>Path validation fails</h2>
        <p>Check whether the path exists, whether the file extension matches the requirement, and whether the current user has read/write permission. Use a normal user-writable project directory for outputs.</p>
        <h2>No valid months are detected</h2>
        <p>Check GSM/GFC file naming, processing center, release selection, and time range. Missing months are normal for some GRACE/GRACE-FO periods, but the month identifier in the file name must be readable by the program.</p>
        <h2>DDK filtering fails</h2>
        <p>Check whether the DDK kernel directory matches the selected DDK level. If DDK is not required for the current task, disable it and test with Gaussian, Fan, or HSAF first.</p>
        <h2>MATLAB or external scripts fail</h2>
        <p>Check the MATLAB executable path, toolbox path, and command-line permission. Copy the full command and error message from the log panel for reproduction and diagnosis.</p>
        <h2>GUI freezes during processing</h2>
        <p>Use conservative worker counts in packaged Windows builds. For large HSAF or leakage-correction jobs, test a small month subset first and run the full task after the configuration is confirmed.</p>
        <p>---</p>
                """
,
        """
        <h1>常见错误排查</h1>
        <h2>路径校验失败</h2>
        <p>检查路径是否存在、文件后缀是否符合要求，以及当前用户是否具有读写权限。输出目录建议使用普通用户可写的项目路径。</p>
        <h2>未识别到有效月份</h2>
        <p>检查 GSM/GFC 文件命名、处理中心、版本选择和时间范围。GRACE/GRACE-FO 部分时段存在缺失月份是正常现象，但文件名中的月份标识必须能够被程序解析。</p>
        <h2>DDK 滤波失败</h2>
        <p>检查 DDK 核函数目录和所选 DDK 等级是否匹配。如果当前任务不需要 DDK，可先关闭该方法，并使用 Gaussian、Fan 或 HSAF 进行测试。</p>
        <h2>MATLAB 或外部脚本失败</h2>
        <p>检查 MATLAB 可执行文件路径、工具箱路径和命令行调用权限。可在日志面板复制完整命令和错误信息，用于复现和排查。</p>
        <h2>GUI 运行时卡顿</h2>
        <p>Windows 打包版建议使用较保守的并行进程数。大型 HSAF 或泄漏校正任务建议先选择少量月份试运行，确认配置无误后再执行完整处理。</p>
                """
,
        ('error', 'troubleshooting', 'fail', 'freeze'),
    ),
    _topic(
        'Keyboard shortcuts',
        '快捷键说明',
        'shortcuts',
        '⌨',
        """
        <h1>Keyboard shortcuts</h1>
        <table>
          <thead><tr>
            <th>Shortcut</th>
            <th>Action</th>
          </tr></thead>
          <tbody>
          <tr>
            <td>Ctrl + Plus</td>
            <td>Increase UI font size.</td>
          </tr>
          <tr>
            <td>Ctrl + Minus</td>
            <td>Decrease UI font size.</td>
          </tr>
          <tr>
            <td>Ctrl + 0</td>
            <td>Reset UI font scale.</td>
          </tr>
          <tr>
            <td>Ctrl + C</td>
            <td>Copy selected text in path fields, logs, or documentation.</td>
          </tr>
          <tr>
            <td>Ctrl + A</td>
            <td>Select all text in the focused input field or log view.</td>
          </tr>
          <tr>
            <td>Esc</td>
            <td>Close supported dialogs.</td>
          </tr>
          </tbody>
        </table>
        <p>Some operating systems or input methods may reserve key combinations. If a shortcut conflicts with the system, use the visible UI button instead.</p>
        <p>---</p>
                """
,
        """
        <h1>快捷键说明</h1>
        <table>
          <thead><tr>
            <th>快捷键</th>
            <th>作用</th>
          </tr></thead>
          <tbody>
          <tr>
            <td>Ctrl + Plus</td>
            <td>增大界面字号。</td>
          </tr>
          <tr>
            <td>Ctrl + Minus</td>
            <td>减小界面字号。</td>
          </tr>
          <tr>
            <td>Ctrl + 0</td>
            <td>重置界面字号缩放。</td>
          </tr>
          <tr>
            <td>Ctrl + C</td>
            <td>复制路径输入框、日志或文档中的选中文本。</td>
          </tr>
          <tr>
            <td>Ctrl + A</td>
            <td>全选当前聚焦输入框或日志视图中的文本。</td>
          </tr>
          <tr>
            <td>Esc</td>
            <td>在支持的弹窗中关闭对话框。</td>
          </tr>
          </tbody>
        </table>
        <p>部分操作系统或输入法可能占用组合键。遇到快捷键冲突时，可使用界面按钮完成相同操作。</p>
                """
,
        ('shortcut', 'keyboard', 'ctrl'),
    ),
    _topic(
        'Version and runtime information',
        '版本与运行环境',
        'version',
        'ⓘ',
        f"""
        <h1>Version and runtime information</h1>
        <p>The Version and runtime information page records the GUI version, repository branch, and local runtime environment. Include this information when reporting an issue so that the problem can be reproduced and diagnosed more quickly.</p>
        <h2>Current version</h2>
        <ul>
          <li><b>Application:</b> GRACE Level-2 Pipeline</li>
          <li><b>GUI version:</b> {APP_VERSION}</li>
          <li><b>Repository branch:</b> wip/python-runtime-qt-monitor-refactor</li>
        </ul>
        <h2>Issue report checklist</h2>
        <ul>
          <li>Active JSON configuration.</li>
          <li>Log file or copied error message.</li>
          <li>Input file type, processing center, and release.</li>
          <li>Operating system, Python version, and PySide version.</li>
          <li>Steps to reproduce and the page where the issue occurred.</li>
        </ul>
        <p>---</p>
                """
,
        f"""
        <h1>版本与运行环境</h1>
        <p>版本与运行环境页面记录 GUI 版本、仓库分支和本地运行环境。反馈问题时，建议同时提供这些信息，以便快速复现和定位。</p>
        <h2>当前版本</h2>
        <ul>
          <li><b>应用程序：</b> GRACE Level-2 Pipeline</li>
          <li><b>GUI 版本：</b> {APP_VERSION}</li>
          <li><b>仓库分支：</b> wip/python-runtime-qt-monitor-refactor</li>
        </ul>
        <h2>问题反馈清单</h2>
        <ul>
          <li>当前 JSON 配置文件。</li>
          <li>日志文件或复制的错误信息。</li>
          <li>输入文件类型、处理中心和版本。</li>
          <li>操作系统、Python 版本和 PySide 版本。</li>
          <li>复现步骤和出现问题的具体页面。</li>
        </ul>
                """
,
        ('version', 'runtime', 'environment'),
    ),
    _topic(
        'External links',
        '外部文档链接',
        'external_links',
        '↗',
        """
        <h1>External links</h1>
        <p>This page collects entries for source code, releases, issue reporting, and upstream data or documentation.</p>
        <h2>Common links</h2>
        <ul>
          <li>Project repository</li>
          <li>GitHub Releases</li>
          <li>Issue tracker</li>
          <li>NASA PO.DAAC GRACE/GRACE-FO data</li>
          <li>UTCSR GRACE resources</li>
          <li>ICGEM gravity field models</li>
        </ul>
        <h2>Citation advice</h2>
        <p>External pages, data releases, and download addresses may change. When citing a data source, record the access date, product name, release version, and processing center.</p>
        <p>---</p>
                """
,
        """
        <h1>外部文档链接</h1>
        <p>本页面汇总源码、版本发布、问题反馈以及上游数据和文档入口。</p>
        <h2>常用链接</h2>
        <ul>
          <li>项目仓库</li>
          <li>GitHub Releases</li>
          <li>问题反馈</li>
          <li>NASA PO.DAAC GRACE/GRACE-FO 数据</li>
          <li>UTCSR GRACE 资源</li>
          <li>ICGEM 重力场模型</li>
        </ul>
        <h2>引用建议</h2>
        <p>外部页面、数据版本和下载地址可能更新。引用数据源时，应记录访问日期、产品名称、发布版本和处理中心。</p>
                """
,
        ('link', 'github', 'release', 'data'),
    ),
]


class HelpDocsDialog(QDialog):
    """Two-pane documentation dialog with bilingual content and search."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.language = getattr(window.ui_preferences, "language", "en")
        self._visible_topics: list[HelpTopic] = list(HELP_TOPICS)
        self.setWindowTitle("帮助文档" if self.language == "zh" else "Documentation")
        self.resize(1120, 780)
        self.setMinimumSize(900, 600)
        self._build_ui()
        self._select_current_page_topic()

    def _tr(self, en: str, zh: str) -> str:
        return zh if self.language == "zh" else en

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QFrame()
        header.setObjectName("HelpHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(8)
        title = QLabel(self._tr("GRACE-L2 Documentation", "GRACE-L2 帮助文档"))
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            self._tr(
                "Searchable guide for page responsibilities, workflow order, inputs, outputs, errors, shortcuts, and context help.",
                "可搜索的功能说明，覆盖页面职责、处理顺序、输入输出、错误排查、快捷键和上下文帮助。",
            )
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self._tr("Search documentation...", "搜索帮助文档..."))
        self.search_box.textChanged.connect(self._apply_search)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(self.search_box)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.topic_list = QListWidget()
        self.topic_list.setObjectName("HelpTopicList")
        self.topic_list.setMinimumWidth(270)
        self.topic_list.setMaximumWidth(340)
        self.topic_list.currentRowChanged.connect(self._on_topic_changed)

        self.browser = QTextBrowser()
        self.browser.setObjectName("HelpBrowser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet(self._browser_css())
        body.addWidget(self.topic_list, 0)
        body.addWidget(self.browser, 1)
        root.addLayout(body, 1)

        footer = QHBoxLayout()
        self.copy_topic_btn = QPushButton(self._tr("Copy current topic", "复制当前主题"))
        self.copy_topic_btn.setObjectName("GhostButton")
        self.copy_topic_btn.clicked.connect(self._copy_current_topic)
        self.copy_paths_btn = QPushButton(self._tr("Copy output layout", "复制输出结构"))
        self.copy_paths_btn.setObjectName("GhostButton")
        self.copy_paths_btn.clicked.connect(self._copy_output_layout)
        close_btn = QPushButton(self._tr("Close", "关闭"))
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(self.copy_topic_btn)
        footer.addWidget(self.copy_paths_btn)
        footer.addStretch(1)
        footer.addWidget(close_btn)
        root.addLayout(footer)

        self._render_topic_list()

    def _browser_css(self) -> str:
        return """
        QTextBrowser {
            background: #ffffff;
            border: 1px solid #d8e2ef;
            border-radius: 14px;
            padding: 16px;
            color: #17233c;
            font-size: 14px;
            line-height: 1.65;
        }
        """

    def _topic_label(self, topic: HelpTopic) -> str:
        return f"{topic.icon}  {topic.title_zh if self.language == 'zh' else topic.title_en}"

    def _render_topic_list(self, selected_key: str | None = None) -> None:
        self.topic_list.blockSignals(True)
        self.topic_list.clear()
        for topic in self._visible_topics:
            item = QListWidgetItem(self._topic_label(topic))
            item.setData(Qt.UserRole, topic.key)
            self.topic_list.addItem(item)
        self.topic_list.blockSignals(False)
        if not self._visible_topics:
            self.browser.setHtml(self._empty_search_html())
            return
        row = 0
        if selected_key:
            keys = [topic.key for topic in self._visible_topics]
            if selected_key in keys:
                row = keys.index(selected_key)
        self.topic_list.setCurrentRow(row)
        self._on_topic_changed(row)

    def _empty_search_html(self) -> str:
        return self._wrap_body(
            "<h1>No matching topics</h1><p>Try a broader keyword such as path, filter, leakage, log, shortcut, or error.</p>"
            if self.language != "zh"
            else "<h1>没有匹配主题</h1><p>可尝试更宽泛的关键词，例如：路径、滤波、泄漏、日志、快捷键或错误。</p>"
        )

    def _wrap_body(self, body: str) -> str:
        runtime = self._runtime_footer()
        return f"""
        <html><head><style>
        body {{ font-family: 'Segoe UI', 'Microsoft YaHei UI', Arial, sans-serif; color: #17233c; line-height: 1.65; }}
        h1 {{ font-size: 26px; margin: 0 0 12px 0; color: #0b254f; }}
        h2 {{ font-size: 17px; margin: 22px 0 8px 0; color: #005b96; }}
        p {{ margin: 8px 0 12px 0; }}
        ul, ol {{ margin-top: 8px; padding-left: 24px; }}
        li {{ margin: 6px 0; }}
        b {{ color: #0b254f; }}
        pre {{ background: #f3f6fb; border: 1px solid #d8e2ef; border-radius: 8px; padding: 10px; white-space: pre-wrap; }}
        table {{ border-collapse: collapse; margin-top: 8px; width: 100%; }}
        th, td {{ border: 1px solid #d8e2ef; padding: 8px 10px; text-align: left; }}
        th {{ background: #f3f6fb; color: #0b254f; }}
        a {{ color: #006ba6; text-decoration: none; }}
        .runtime {{ margin-top: 28px; padding-top: 12px; border-top: 1px solid #d8e2ef; color: #637089; font-size: 12px; }}
        </style></head><body>{body}{runtime}</body></html>
        """

    def _wrap_html(self, topic: HelpTopic) -> str:
        body = topic.html_zh if self.language == "zh" else topic.html_en
        return self._wrap_body(body)

    def _runtime_footer(self) -> str:
        return (
            "<div class='runtime'>"
            f"GRACE Level-2 Pipeline v{APP_VERSION} | Python {sys.version.split()[0]} | "
            f"PySide {PYSIDE_VERSION} | {platform.system()} {platform.release()}"
            "</div>"
        )

    def _on_topic_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._visible_topics):
            return
        self.browser.setHtml(self._wrap_html(self._visible_topics[row]))

    def _apply_search(self, text: str) -> None:
        query = (text or "").strip().lower()
        selected_key = None
        current = self.topic_list.currentItem()
        if current is not None:
            selected_key = current.data(Qt.UserRole)
        if not query:
            self._visible_topics = list(HELP_TOPICS)
            self._render_topic_list(selected_key=selected_key)
            return
        matched: list[HelpTopic] = []
        for topic in HELP_TOPICS:
            haystack = " ".join(
                [
                    topic.key,
                    topic.title_en,
                    topic.title_zh,
                    _strip_html(topic.html_en),
                    _strip_html(topic.html_zh),
                    " ".join(topic.tags),
                ]
            ).lower()
            if query in haystack:
                matched.append(topic)
        self._visible_topics = matched
        self._render_topic_list()

    def _select_current_page_topic(self) -> None:
        key = "getting_started"
        current = getattr(self.window, "stack", None).currentWidget() if getattr(self.window, "stack", None) is not None else None
        for page_key, widget in getattr(self.window, "_pages", {}).items():
            if widget is current:
                key = page_key
                break
        keys = [topic.key for topic in self._visible_topics]
        row = keys.index(key) if key in keys else 0
        self.topic_list.setCurrentRow(row)

    def _copy_current_topic(self) -> None:
        row = self.topic_list.currentRow()
        if row < 0 or row >= len(self._visible_topics):
            return
        topic = self._visible_topics[row]
        title = topic.title_zh if self.language == "zh" else topic.title_en
        body = _strip_html(topic.html_zh if self.language == "zh" else topic.html_en)
        QApplication.clipboard().setText(f"{title}\n\n{body}")

    def _copy_output_layout(self) -> None:
        text = """OUTPUT/
  local/
    monthly_mat/
    stacks/
    plots/
    logs/
    leakage/
    basin/
  CACHE/
    qt_ui/
"""
        QApplication.clipboard().setText(text)


BUTTON_HELP: dict[str, tuple[str, str]] = {
    "btn_run": ("Start the configured GRACE Level-2 workflow.", "启动当前配置的 GRACE Level-2 处理流程。"),
    "btn_pause": ("Pause or resume the active processing task.", "暂停或继续当前处理任务。"),
    "btn_stop": ("Request a safe stop for the active processing task.", "请求安全停止当前处理任务。"),
    "btn_console": ("Show or hide the process log panel.", "显示或隐藏处理日志面板。"),
    "btn_help": ("Open the searchable documentation window.", "打开可搜索帮助文档窗口。"),
    "btn_settings": ("Open theme and language preferences.", "打开主题和语言设置。"),
    "btn_nav_toggle": ("Collapse or expand the left navigation rail.", "折叠或展开左侧导航栏。"),
    "btn_load_config": ("Load a JSON configuration file.", "加载 JSON 配置文件。"),
    "btn_save_config": ("Save the current settings as a JSON configuration file.", "将当前设置保存为 JSON 配置文件。"),
    "btn_validate_paths": ("Validate required input, auxiliary, and output paths.", "校验必要输入、辅助数据和输出路径。"),
    "btn_open_data_paths": ("Open the Data Paths page.", "打开数据路径页面。"),
    "btn_open_processing": ("Open the Processing Setup page.", "打开滤波处理页面。"),
    "btn_open_preview": ("Open the Preview page.", "打开预览页面。"),
    "btn_download_gfc_range": ("Download Level-2 GFC files for the selected center and time range.", "下载所选中心和时间范围的 Level-2 GFC 文件。"),
    "btn_open_download_site": ("Open the upstream data download website.", "打开上游数据下载网站。"),
    "btn_tool_sh_to_grid": ("Convert spherical harmonic coefficients to a gridded EWH/TWSA product.", "将球谐系数转换为格网 EWH/TWSA 产品。"),
    "btn_tool_grid_to_sh": ("Convert a gridded product back to spherical harmonic coefficients when supported.", "在支持时将格网产品转换回球谐系数。"),
    "btn_lrc_load_info": ("Read metadata and dimensions from the leakage-correction input stack.", "读取泄漏校正输入栈的元数据和维度。"),
    "btn_lrc_run": ("Run the selected leakage-correction strategy.", "运行所选泄漏校正策略。"),
    "btn_lrc_preview": ("Open leakage-correction output in the Preview page.", "在预览页面打开泄漏校正输出。"),
    "btn_basin_load_info": ("Read stack and basin-boundary metadata for basin analysis.", "读取流域分析所需的栈和边界元数据。"),
    "btn_basin_run": ("Run basin-mean time-series and statistics analysis.", "运行流域平均时间序列和统计分析。"),
}


def _iter_named_widgets(window):
    yield window
    for page in getattr(window, "_pages", {}).values():
        yield page


def install_button_context_help(window) -> None:
    """Attach concise tooltip/What's This text to known top-level and page buttons."""

    is_zh = getattr(window.ui_preferences, "language", "en") == "zh"
    for container in _iter_named_widgets(window):
        for attr, (en, zh) in BUTTON_HELP.items():
            button = getattr(container, attr, None)
            if button is None or not hasattr(button, "setToolTip"):
                continue
            text = zh if is_zh else en
            button.setToolTip(text)
            with contextlib.suppress(Exception):
                button.setWhatsThis(text)


def show_help_docs(window) -> None:
    dialog = HelpDocsDialog(window)
    dialog.exec()


def bind_help_docs(window) -> None:
    """Replace legacy plain-text help binding with the structured docs dialog."""

    install_button_context_help(window)
    with contextlib.suppress(Exception):
        window.btn_help.clicked.disconnect()
    window.btn_help.clicked.connect(lambda: show_help_docs(window))
