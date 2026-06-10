"""Structured help documentation dialog for the Qt desktop interface."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class HelpTopic:
    key: str
    title_en: str
    title_zh: str
    icon: str
    html_en: str
    html_zh: str


def _topic(title_en: str, title_zh: str, key: str, icon: str, body_en: str, body_zh: str) -> HelpTopic:
    return HelpTopic(key=key, title_en=title_en, title_zh=title_zh, icon=icon, html_en=body_en, html_zh=body_zh)


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
    ),
]


class HelpDocsDialog(QDialog):
    """Two-pane documentation dialog with bilingual content."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.language = getattr(window.ui_preferences, "language", "en")
        self.setWindowTitle("帮助文档" if self.language == "zh" else "Documentation")
        self.resize(1080, 760)
        self.setMinimumSize(860, 560)
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
        header_layout.setSpacing(6)
        title = QLabel(self._tr("GRACE-L2 Documentation", "GRACE-L2 帮助文档"))
        title.setObjectName("PageTitle")
        subtitle = QLabel(
            self._tr(
                "A categorized guide for page responsibilities, workflow order, inputs, outputs, and quality checks.",
                "按功能归类说明各页面职责、处理顺序、输入输出和质量检查要点。",
            )
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.topic_list = QListWidget()
        self.topic_list.setObjectName("HelpTopicList")
        self.topic_list.setMinimumWidth(250)
        self.topic_list.setMaximumWidth(320)
        for topic in HELP_TOPICS:
            label = f"{topic.icon}  {topic.title_zh if self.language == 'zh' else topic.title_en}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, topic.key)
            self.topic_list.addItem(item)
        self.topic_list.currentRowChanged.connect(self._on_topic_changed)

        self.browser = QTextBrowser()
        self.browser.setObjectName("HelpBrowser")
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet(self._browser_css())
        body.addWidget(self.topic_list, 0)
        body.addWidget(self.browser, 1)
        root.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton(self._tr("Close", "关闭"))
        close_btn.setObjectName("PrimaryButton")
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        root.addLayout(footer)

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

    def _wrap_html(self, topic: HelpTopic) -> str:
        body = topic.html_zh if self.language == "zh" else topic.html_en
        return f"""
        <html><head><style>
        body {{ font-family: 'Segoe UI', 'Microsoft YaHei UI', Arial, sans-serif; color: #17233c; line-height: 1.65; }}
        h1 {{ font-size: 26px; margin: 0 0 12px 0; color: #0b254f; }}
        h2 {{ font-size: 17px; margin: 22px 0 8px 0; color: #005b96; }}
        p {{ margin: 8px 0 12px 0; }}
        ul, ol {{ margin-top: 8px; padding-left: 24px; }}
        li {{ margin: 6px 0; }}
        b {{ color: #0b254f; }}
        </style></head><body>{body}</body></html>
        """

    def _on_topic_changed(self, row: int) -> None:
        if row < 0 or row >= len(HELP_TOPICS):
            return
        self.browser.setHtml(self._wrap_html(HELP_TOPICS[row]))

    def _select_current_page_topic(self) -> None:
        key = "getting_started"
        current = getattr(self.window, "stack", None).currentWidget() if getattr(self.window, "stack", None) is not None else None
        for page_key, widget in getattr(self.window, "_pages", {}).items():
            if widget is current:
                key = page_key
                break
        keys = [topic.key for topic in HELP_TOPICS]
        row = keys.index(key) if key in keys else 0
        self.topic_list.setCurrentRow(row)


def show_help_docs(window) -> None:
    dialog = HelpDocsDialog(window)
    dialog.exec()


def bind_help_docs(window) -> None:
    """Replace legacy plain-text help binding with the structured docs dialog."""

    with contextlib.suppress(Exception):
        window.btn_help.clicked.disconnect()
    window.btn_help.clicked.connect(lambda: show_help_docs(window))
