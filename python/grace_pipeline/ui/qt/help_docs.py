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
        "Getting started",
        "快速开始",
        "getting_started",
        "★",
        """
        <h1>Getting started</h1>
        <p>This desktop program supports a reproducible GRACE/GRACE-FO Level-2 workflow from monthly spherical harmonic coefficients to gridded equivalent water height products, leakage correction, basin statistics, and preview figures.</p>
        <h2>Recommended order</h2>
        <ol>
          <li>Open <b>Data Paths</b> and confirm input, auxiliary, low-degree, GIA, DDK, boundary, and output directories.</li>
          <li>Open <b>Processing Setup</b> and verify the time span, maximum degree, grid resolution, filters, and parallel settings.</li>
          <li>Return to <b>Dashboard</b> and run the complete workflow after path validation succeeds.</li>
          <li>Use <b>Run Monitor</b> to inspect logs and output locations during processing.</li>
          <li>Use <b>Preview</b>, <b>Leakage Correction</b>, or <b>Basin Analysis</b> for downstream diagnostics.</li>
        </ol>
        <h2>Basic rule</h2>
        <p>Keep raw Level-2 input files immutable. All corrected stacks, figures, logs, and summaries should be written under the configured output directory.</p>
        """,
        """
        <h1>快速开始</h1>
        <p>本桌面程序用于支持 GRACE/GRACE-FO Level-2 数据从月球谐系数到格网等效水高产品、泄漏校正、流域统计和图件预览的可复现处理流程。</p>
        <h2>推荐操作顺序</h2>
        <ol>
          <li>进入 <b>数据路径</b>，确认输入、辅助数据、低阶项、GIA、DDK、边界和输出目录。</li>
          <li>进入 <b>滤波处理</b>，核对时间范围、最大阶数、格网分辨率、滤波器和并行设置。</li>
          <li>回到 <b>总览</b>，在路径校验通过后运行完整流程。</li>
          <li>通过 <b>运行监控</b> 查看运行日志、阶段进度和输出位置。</li>
          <li>使用 <b>预览</b>、<b>泄漏校正</b> 或 <b>流域分析</b> 完成后处理诊断。</li>
        </ol>
        <h2>基本原则</h2>
        <p>原始 Level-2 输入文件应保持不可变。校正栈、图件、日志和摘要文件应统一写入配置的输出目录。</p>
        """,
        ("start", "workflow", "quick"),
    ),
    _topic(
        "Dashboard",
        "总览页面",
        "dashboard",
        "⌂",
        """
        <h1>Dashboard</h1>
        <p>The Dashboard is the entry point for project status, configuration integrity, quick execution, and output discovery.</p>
        <h2>Main functions</h2>
        <ul>
          <li><b>Configuration summary:</b> displays the active configuration name, processing center, time span, filter chain, and output root.</li>
          <li><b>Path validation:</b> checks whether required directories and auxiliary files are available before running.</li>
          <li><b>Run controls:</b> starts, pauses, resumes, or stops the complete workflow.</li>
          <li><b>Output summary:</b> shows where monthly grids, stacks, figures, and logs will be written.</li>
        </ul>
        <h2>Recommended use</h2>
        <p>Use this page as a final checkpoint. Do not start a full run until the status badge indicates that the configuration is ready.</p>
        """,
        """
        <h1>总览页面</h1>
        <p>总览页是项目状态、配置完整性、快速运行和输出定位的入口。</p>
        <h2>主要功能</h2>
        <ul>
          <li><b>项目配置摘要：</b>显示当前配置名称、处理中心、时间范围、滤波链和输出根目录。</li>
          <li><b>路径校验：</b>在运行前检查必要目录和辅助文件是否可用。</li>
          <li><b>运行控制：</b>启动、暂停、恢复或停止完整处理流程。</li>
          <li><b>输出结构：</b>展示月度格网、栈文件、图件和日志的保存位置。</li>
        </ul>
        <h2>使用建议</h2>
        <p>将该页面作为正式运行前的最后检查点。建议在配置状态显示可运行后再启动完整流程。</p>
        """,
        ("dashboard", "run", "status", "summary"),
    ),
    _topic(
        "Data Paths",
        "数据路径",
        "data_paths",
        "◧",
        """
        <h1>Data Paths</h1>
        <p>This page defines the file-system contract of the workflow. It should describe where the program reads Level-2 products and auxiliary data, and where it writes reproducible outputs.</p>
        <h2>Input groups</h2>
        <ul>
          <li><b>GFC/GSM input:</b> monthly Level-2 spherical harmonic files from HUST-Grace2024, CSR, GFZ, JPL, or compatible products.</li>
          <li><b>Low-degree replacement:</b> C20/C30 and degree-1 replacement files, normally derived from SLR or external constraints.</li>
          <li><b>GIA model:</b> optional glacial isostatic adjustment correction.</li>
          <li><b>DDK kernels:</b> files required for DDK filtering when that method is enabled.</li>
          <li><b>Boundaries and references:</b> basin shapefiles, coastlines, mascon references, or validation data.</li>
        </ul>
        <h2>Output groups</h2>
        <ul>
          <li><b>local/stacks:</b> corrected stack products.</li>
          <li><b>local/monthly_mat:</b> monthly converted products.</li>
          <li><b>local/plots:</b> preview and diagnostic figures.</li>
          <li><b>local/logs:</b> run logs and processing traces.</li>
        </ul>
        """,
        """
        <h1>数据路径</h1>
        <p>本页面定义处理流程的文件系统约定，用于明确程序从哪里读取 Level-2 产品和辅助数据，以及将可复现结果写入哪里。</p>
        <h2>输入数据组</h2>
        <ul>
          <li><b>GFC/GSM 输入：</b>HUST-Grace2024、CSR、GFZ、JPL 或兼容产品的月度 Level-2 球谐文件。</li>
          <li><b>低阶项替换：</b>C20/C30 与一阶项替换文件，通常来自 SLR 或外部约束。</li>
          <li><b>GIA 模型：</b>可选的冰川均衡调整改正文件。</li>
          <li><b>DDK 核文件：</b>启用 DDK 滤波时所需的核函数文件。</li>
          <li><b>边界和参考数据：</b>流域边界、海岸线、Mascon 参考或验证数据。</li>
        </ul>
        <h2>输出数据组</h2>
        <ul>
          <li><b>local/stacks：</b>校正后的栈产品。</li>
          <li><b>local/monthly_mat：</b>月尺度转换产品。</li>
          <li><b>local/plots：</b>预览图和诊断图件。</li>
          <li><b>local/logs：</b>运行日志和处理轨迹。</li>
        </ul>
        """,
        ("path", "directory", "input", "output"),
    ),
    _topic(
        "Processing Setup",
        "滤波处理",
        "processing",
        "Σ",
        """
        <h1>Processing Setup</h1>
        <p>This page controls the scientific processing contract: time indexing, low-degree replacement, GIA correction, grid synthesis, filtering, and parallel execution.</p>
        <h2>Key settings</h2>
        <ul>
          <li><b>Time range:</b> start and end months; missing months should remain explicit in the index.</li>
          <li><b>Inversion:</b> maximum degree/order, Love numbers, units, and replacement policies.</li>
          <li><b>Grid synthesis:</b> spatial resolution, longitude convention, and output unit.</li>
          <li><b>Filters:</b> Gaussian, Fan, PnMm decorrelation, DDK, and HSAF parameters.</li>
          <li><b>Parallel execution:</b> worker count and runtime limits. Conservative values are recommended for frozen Windows builds.</li>
        </ul>
        <h2>Quality advice</h2>
        <p>Do not mix products with different processing centers, release versions, maximum degrees, baselines, or low-degree replacement policies unless the difference is deliberate and documented.</p>
        """,
        """
        <h1>滤波处理</h1>
        <p>本页面控制科学处理约定，包括时间索引、低阶项替换、GIA 改正、格网合成、滤波和并行执行。</p>
        <h2>关键设置</h2>
        <ul>
          <li><b>时间范围：</b>起止月份；缺失月份应在索引中显式保留。</li>
          <li><b>反演设置：</b>最大阶次、Love 数、单位和低阶项替换策略。</li>
          <li><b>格网合成：</b>空间分辨率、经度约定和输出单位。</li>
          <li><b>滤波方法：</b>Gaussian、Fan、PnMm 去相关、DDK 和 HSAF 参数。</li>
          <li><b>并行执行：</b>工作进程数量和运行限制。冻结版 Windows 程序建议采用保守设置。</li>
        </ul>
        <h2>质量建议</h2>
        <p>除非有明确目的并记录说明，不建议混用不同处理中心、版本、最大阶次、基准期或低阶项替换策略的产品。</p>
        """,
        ("processing", "filter", "hankel", "ddk", "gaussian"),
    ),
    _topic(
        "Leakage Correction",
        "泄漏校正",
        "leakage",
        "↔",
        """
        <h1>Leakage Correction</h1>
        <p>This page is used after gridded or stacked products are available. It estimates and corrects spatial leakage caused by spherical harmonic truncation and filtering.</p>
        <h2>Workflow</h2>
        <ol>
          <li>Select the input stack, usually a corrected EWH/TWSA stack.</li>
          <li>Inspect the input dimensions, coordinate convention, and time labels.</li>
          <li>Select global or regional correction mode. Regional correction requires a reliable boundary file.</li>
          <li>Choose a correction strategy or keep the automatic recommendation.</li>
          <li>Run correction and inspect corrected_stack, difference_stack, summary, and preview manifest outputs.</li>
        </ol>
        <h2>Method notes</h2>
        <ul>
          <li><b>Scale factor:</b> restores damped signal amplitudes after truncation and filtering.</li>
          <li><b>Additive correction:</b> estimates leakage-in and leakage-out terms using external or synthetic references.</li>
          <li><b>Mascon input:</b> native mascon products should not be blindly passed through a second SH leakage workflow.</li>
        </ul>
        """,
        """
        <h1>泄漏校正</h1>
        <p>本页面用于格网或栈产品生成之后，估计并校正球谐截断和滤波引起的空间泄漏误差。</p>
        <h2>处理流程</h2>
        <ol>
          <li>选择输入栈，通常为已生成的 EWH/TWSA 校正栈。</li>
          <li>读取并检查输入维度、坐标约定和时间标签。</li>
          <li>选择全球或区域校正模式。区域校正需要可靠的边界文件。</li>
          <li>选择校正策略，或保留自动推荐。</li>
          <li>运行校正并检查 corrected_stack、difference_stack、summary 和 preview manifest 输出。</li>
        </ol>
        <h2>方法说明</h2>
        <ul>
          <li><b>尺度因子：</b>恢复截断和滤波后衰减的信号振幅。</li>
          <li><b>加法校正：</b>通过外部或合成参考估计内泄漏与外泄漏项。</li>
          <li><b>Mascon 输入：</b>原生 Mascon 产品不应盲目再次进入球谐泄漏校正流程。</li>
        </ul>
        """,
        ("leakage", "scale factor", "correction", "mascon"),
    ),
    _topic(
        "Basin Analysis",
        "流域分析",
        "basin",
        "◌",
        """
        <h1>Basin Analysis</h1>
        <p>This page converts gridded products into basin-mean time series and regional statistics. It is intended for hydrological interpretation and method comparison.</p>
        <h2>Main functions</h2>
        <ul>
          <li>Read a stack product and a basin boundary file.</li>
          <li>Construct area-weighted basin masks on the product grid.</li>
          <li>Generate basin-mean TWSA/EWH time series.</li>
          <li>Fit annual, semi-annual, trend, RMS, and residual statistics.</li>
          <li>Export tables and optional diagnostic figures.</li>
        </ul>
        <h2>Quality advice</h2>
        <p>Confirm that basin names, boundary fields, longitude convention, and the product baseline are consistent before comparing different filters or centers.</p>
        """,
        """
        <h1>流域分析</h1>
        <p>本页面将格网产品转换为流域平均时间序列和区域统计量，主要用于水文解释和不同方法对比。</p>
        <h2>主要功能</h2>
        <ul>
          <li>读取栈产品和流域边界文件。</li>
          <li>在产品格网上构建面积加权流域掩膜。</li>
          <li>生成流域平均 TWSA/EWH 时间序列。</li>
          <li>拟合年周期、半年周期、趋势、RMS 和残差统计量。</li>
          <li>导出表格和可选诊断图件。</li>
        </ul>
        <h2>质量建议</h2>
        <p>在比较不同滤波方法或不同中心产品前，应确认流域名称、边界字段、经度约定和产品基准期一致。</p>
        """,
        ("basin", "statistics", "time series"),
    ),
    _topic(
        "Preview",
        "预览页面",
        "preview",
        "◎",
        """
        <h1>Preview</h1>
        <p>The Preview page is used to inspect map products and figures before downstream interpretation. It is not a replacement for quantitative validation.</p>
        <h2>Supported checks</h2>
        <ul>
          <li>Open stack products and browse monthly frames.</li>
          <li>Inspect spatial patterns, coastlines, basin boundaries, and projection choices.</li>
          <li>Compare corrected and difference stacks after leakage correction.</li>
          <li>Export figures for reports or quick diagnosis.</li>
        </ul>
        <h2>Interpretation advice</h2>
        <p>Always combine visual checks with basin statistics, independent references, or spectral diagnostics. Map appearance alone is insufficient for judging method quality.</p>
        """,
        """
        <h1>预览页面</h1>
        <p>预览页用于在后续解释前检查地图产品和图件，但不能替代定量验证。</p>
        <h2>支持的检查</h2>
        <ul>
          <li>打开栈产品并浏览月尺度帧。</li>
          <li>检查空间分布、海岸线、流域边界和投影选择。</li>
          <li>对比泄漏校正后的 corrected stack 与 difference stack。</li>
          <li>导出报告或快速诊断所需图件。</li>
        </ul>
        <h2>解释建议</h2>
        <p>应将视觉检查与流域统计、独立参考或频谱诊断结合使用。仅凭地图外观不足以判断方法优劣。</p>
        """,
        ("preview", "map", "plot", "export"),
    ),
    _topic(
        "Run Monitor and logs",
        "运行监控与日志",
        "monitor",
        "▣",
        """
        <h1>Run Monitor and logs</h1>
        <p>The Run Monitor collects workflow progress, stage messages, output paths, warnings, and terminal logs. It should be used during long processing tasks and troubleshooting.</p>
        <h2>What to inspect</h2>
        <ul>
          <li><b>Current stage:</b> input indexing, preprocessing, filtering, synthesis, basin analysis, or leakage correction.</li>
          <li><b>Progress:</b> completed months or tasks relative to the expected workload.</li>
          <li><b>Warnings:</b> missing months, invalid paths, unsupported formats, or fallback behavior.</li>
          <li><b>Output paths:</b> the actual files produced by the current run.</li>
        </ul>
        <h2>Troubleshooting</h2>
        <p>If a run fails, keep the log file and the active JSON configuration. Re-running with the same inputs and configuration is the fastest way to reproduce the issue.</p>
        """,
        """
        <h1>运行监控与日志</h1>
        <p>运行监控页汇总工作流进度、阶段信息、输出路径、警告和终端日志，适合在长任务运行和问题排查时使用。</p>
        <h2>需要关注的内容</h2>
        <ul>
          <li><b>当前阶段：</b>输入索引、预处理、滤波、合成、流域分析或泄漏校正。</li>
          <li><b>运行进度：</b>已完成月份或任务相对于总任务量的比例。</li>
          <li><b>警告信息：</b>缺失月份、路径错误、格式不支持或回退行为。</li>
          <li><b>输出路径：</b>当前运行实际生成的文件位置。</li>
        </ul>
        <h2>问题排查</h2>
        <p>如果运行失败，应保留日志文件和当前 JSON 配置。使用相同输入与配置重新运行，是复现问题最快的方式。</p>
        """,
        ("monitor", "log", "warning", "error"),
    ),
    _topic(
        "Copying paths and output layout",
        "复制路径与输出结构",
        "copy_paths",
        "⧉",
        """
        <h1>Copying paths and output layout</h1>
        <p>Most path fields can be selected and copied with the standard system shortcut. The Help window also provides a shortcut button that copies the standard output layout to the clipboard.</p>
        <h2>Standard output layout</h2>
        <pre>OUTPUT/
  local/
    monthly_mat/
    stacks/
    plots/
    logs/
    leakage/
    basin/
  CACHE/
    qt_ui/</pre>
        <h2>Recommended file naming</h2>
        <ul>
          <li><b>corrected_stack.mat:</b> main corrected gridded product.</li>
          <li><b>difference_stack.mat:</b> correction difference or diagnostic field.</li>
          <li><b>summary.json:</b> machine-readable run summary.</li>
          <li><b>preview_manifest.json:</b> preview page entry point.</li>
        </ul>
        <h2>Windows path advice</h2>
        <p>Prefer short ASCII project paths for heavy batch runs. Avoid directories requiring administrator permission when running the portable program.</p>
        """,
        """
        <h1>复制路径与输出结构</h1>
        <p>多数路径输入框都可以使用系统快捷键选中并复制。本帮助窗口也提供快捷按钮，可将标准输出目录结构复制到剪贴板。</p>
        <h2>标准输出结构</h2>
        <pre>OUTPUT/
  local/
    monthly_mat/
    stacks/
    plots/
    logs/
    leakage/
    basin/
  CACHE/
    qt_ui/</pre>
        <h2>推荐文件命名</h2>
        <ul>
          <li><b>corrected_stack.mat：</b>主要校正格网产品。</li>
          <li><b>difference_stack.mat：</b>校正差值或诊断场。</li>
          <li><b>summary.json：</b>机器可读的运行摘要。</li>
          <li><b>preview_manifest.json：</b>预览页入口文件。</li>
        </ul>
        <h2>Windows 路径建议</h2>
        <p>重批处理建议使用较短的英文路径。便携版程序运行时，应避免将输出写入需要管理员权限的目录。</p>
        """,
        ("copy", "clipboard", "output", "path"),
    ),
    _topic(
        "Troubleshooting",
        "常见错误排查",
        "troubleshooting",
        "!",
        """
        <h1>Troubleshooting</h1>
        <h2>Path validation fails</h2>
        <p>Check whether the path exists, whether the file extension matches the expected input, and whether the current user has read/write permission.</p>
        <h2>No valid months are found</h2>
        <p>Confirm the GSM/GFC file naming convention, center/release selection, and time range. Missing months should be expected for some GRACE/GRACE-FO periods, but the month identifier must remain readable.</p>
        <h2>DDK filtering fails</h2>
        <p>Verify the DDK kernel directory and the selected DDK level. If DDK is not required, disable it and run Gaussian/Fan/HSAF first.</p>
        <h2>MATLAB or external scripts fail</h2>
        <p>Check MATLAB executable path, toolbox path, and whether command-line execution is allowed. Use the log panel to copy the exact command and error message.</p>
        <h2>GUI freezes during processing</h2>
        <p>Use conservative worker counts in frozen Windows builds. Large HSAF or leakage-correction jobs should be tested on a small month subset first.</p>
        """,
        """
        <h1>常见错误排查</h1>
        <h2>路径校验失败</h2>
        <p>检查路径是否存在、文件后缀是否符合预期，以及当前用户是否具备读写权限。</p>
        <h2>没有识别到有效月份</h2>
        <p>核对 GSM/GFC 文件命名、处理中心/版本选择和时间范围。部分 GRACE/GRACE-FO 时段存在缺失月份是正常的，但月份标识必须能够被程序解析。</p>
        <h2>DDK 滤波失败</h2>
        <p>检查 DDK 核函数目录和所选 DDK 等级。如果当前不需要 DDK，可先关闭该方法，使用 Gaussian/Fan/HSAF 进行测试。</p>
        <h2>MATLAB 或外部脚本失败</h2>
        <p>检查 MATLAB 可执行文件路径、工具箱路径以及命令行调用权限。可在日志面板复制完整命令和错误信息。</p>
        <h2>GUI 在运行时卡顿</h2>
        <p>冻结版 Windows 程序建议使用保守的并行进程数。大型 HSAF 或泄漏校正任务应先用少量月份试运行。</p>
        """,
        ("error", "troubleshooting", "fail", "freeze"),
    ),
    _topic(
        "Keyboard shortcuts",
        "快捷键说明",
        "shortcuts",
        "⌨",
        """
        <h1>Keyboard shortcuts</h1>
        <table>
          <tr><th>Shortcut</th><th>Action</th></tr>
          <tr><td>Ctrl + Plus</td><td>Increase UI font size.</td></tr>
          <tr><td>Ctrl + Minus</td><td>Decrease UI font size.</td></tr>
          <tr><td>Ctrl + 0</td><td>Reset UI font scale.</td></tr>
          <tr><td>Ctrl + C</td><td>Copy selected text in path fields, logs, or documentation.</td></tr>
          <tr><td>Ctrl + A</td><td>Select all text in the focused editable field or log view.</td></tr>
          <tr><td>Esc</td><td>Close modal dialogs where supported.</td></tr>
        </table>
        <p>Some operating systems or input methods may reserve key combinations. In that case, use the visible toolbar buttons.</p>
        """,
        """
        <h1>快捷键说明</h1>
        <table>
          <tr><th>快捷键</th><th>作用</th></tr>
          <tr><td>Ctrl + Plus</td><td>增大界面字号。</td></tr>
          <tr><td>Ctrl + Minus</td><td>减小界面字号。</td></tr>
          <tr><td>Ctrl + 0</td><td>重置界面字号缩放。</td></tr>
          <tr><td>Ctrl + C</td><td>复制路径输入框、日志或文档中的选中文本。</td></tr>
          <tr><td>Ctrl + A</td><td>全选当前聚焦输入框或日志视图中的文本。</td></tr>
          <tr><td>Esc</td><td>在支持的模态窗口中关闭对话框。</td></tr>
        </table>
        <p>部分操作系统或输入法可能占用组合键。遇到冲突时，可使用界面上的按钮完成相同操作。</p>
        """,
        ("shortcut", "keyboard", "ctrl"),
    ),
    _topic(
        "Button-level context help",
        "按钮级上下文帮助",
        "button_help",
        "?",
        """
        <h1>Button-level context help</h1>
        <p>Main controls now provide tooltip and context-help text. Hover over a button to read a short explanation. In Qt environments that support What's This help, the same information is also available as context help.</p>
        <h2>Core controls</h2>
        <ul>
          <li><b>Run:</b> starts the configured workflow.</li>
          <li><b>Pause/Resume:</b> temporarily suspends or continues the active task.</li>
          <li><b>Stop:</b> requests a safe stop for the active task.</li>
          <li><b>Log:</b> opens or hides the process log panel.</li>
          <li><b>Appearance:</b> opens theme and language preferences.</li>
          <li><b>Help:</b> opens this documentation window.</li>
        </ul>
        <h2>Page-specific controls</h2>
        <p>Configuration, validation, browsing, download, preview, leakage, and basin-analysis buttons have tooltips describing their expected input and effect.</p>
        """,
        """
        <h1>按钮级上下文帮助</h1>
        <p>主要控件已补充工具提示和上下文帮助文本。将鼠标悬停在按钮上可读取简短说明。在支持 What's This 的 Qt 环境中，也可通过上下文帮助查看同一信息。</p>
        <h2>核心控件</h2>
        <ul>
          <li><b>Run：</b>启动当前配置的处理流程。</li>
          <li><b>Pause/Resume：</b>临时暂停或继续当前任务。</li>
          <li><b>Stop：</b>请求安全停止当前任务。</li>
          <li><b>Log：</b>打开或隐藏处理日志面板。</li>
          <li><b>Appearance：</b>打开主题和语言设置。</li>
          <li><b>Help：</b>打开本帮助文档窗口。</li>
        </ul>
        <h2>页面内控件</h2>
        <p>配置、校验、浏览、下载、预览、泄漏校正和流域分析相关按钮均补充了预期输入与作用说明。</p>
        """,
        ("button", "tooltip", "context"),
    ),
    _topic(
        "Version and runtime information",
        "版本与运行环境",
        "version",
        "ⓘ",
        """
        <h1>Version and runtime information</h1>
        <p>The version information page records the GUI release identity and the local runtime environment. Include this information when reporting an issue.</p>
        <h2>Current GUI release</h2>
        <ul>
          <li><b>Application:</b> GRACE Level-2 Pipeline</li>
          <li><b>GUI version:</b> 0.1</li>
          <li><b>Repository branch:</b> wip/python-runtime-qt-monitor-refactor</li>
        </ul>
        <h2>Issue report checklist</h2>
        <ul>
          <li>Active JSON configuration.</li>
          <li>Log file or copied error message.</li>
          <li>Input file type and processing center/release.</li>
          <li>Operating system, Python version, and PySide version.</li>
        </ul>
        """,
        """
        <h1>版本与运行环境</h1>
        <p>版本信息页记录 GUI 发布标识和本地运行环境。反馈问题时建议同时提供这些信息。</p>
        <h2>当前 GUI 版本</h2>
        <ul>
          <li><b>应用程序：</b>GRACE Level-2 Pipeline</li>
          <li><b>GUI 版本：</b>0.1</li>
          <li><b>仓库分支：</b>wip/python-runtime-qt-monitor-refactor</li>
        </ul>
        <h2>问题反馈清单</h2>
        <ul>
          <li>当前 JSON 配置文件。</li>
          <li>日志文件或复制的错误信息。</li>
          <li>输入文件类型及处理中心/版本。</li>
          <li>操作系统、Python 版本和 PySide 版本。</li>
        </ul>
        """,
        ("version", "runtime", "environment"),
    ),
    _topic(
        "External links",
        "外部文档链接",
        "external_links",
        "↗",
        f"""
        <h1>External links</h1>
        <p>These links are provided for source code, releases, issue reports, and upstream data/documentation.</p>
        <ul>
          <li><a href=\"{REPOSITORY_URL}\">Project repository</a></li>
          <li><a href=\"{RELEASES_URL}\">GitHub Releases</a></li>
          <li><a href=\"{ISSUES_URL}\">Issue tracker</a></li>
          <li><a href=\"https://podaac.jpl.nasa.gov/GRACE\">NASA PO.DAAC GRACE/GRACE-FO data</a></li>
          <li><a href=\"https://www2.csr.utexas.edu/grace/\">UTCSR GRACE resources</a></li>
          <li><a href=\"https://icgem.gfz.de/\">ICGEM gravity field models</a></li>
        </ul>
        <p>External pages may change. Always record the access date and product release when citing data sources.</p>
        """,
        f"""
        <h1>外部文档链接</h1>
        <p>以下链接用于访问源码、版本发布、问题反馈以及上游数据/文档。</p>
        <ul>
          <li><a href=\"{REPOSITORY_URL}\">项目仓库</a></li>
          <li><a href=\"{RELEASES_URL}\">GitHub Releases</a></li>
          <li><a href=\"{ISSUES_URL}\">问题反馈</a></li>
          <li><a href=\"https://podaac.jpl.nasa.gov/GRACE\">NASA PO.DAAC GRACE/GRACE-FO 数据</a></li>
          <li><a href=\"https://www2.csr.utexas.edu/grace/\">UTCSR GRACE 资源</a></li>
          <li><a href=\"https://icgem.gfz.de/\">ICGEM 重力场模型</a></li>
        </ul>
        <p>外部页面可能发生变化。引用数据源时应记录访问日期和产品版本。</p>
        """,
        ("link", "github", "release", "data"),
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
