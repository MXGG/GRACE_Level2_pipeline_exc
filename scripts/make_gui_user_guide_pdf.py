from __future__ import annotations

import os
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "output" / "pdf"
PDF_PATH = OUT_DIR / "grace_l2_python_pyside_gui_user_guide_zh.pdf"

FONT_YAHEI = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_YAHEI_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_TIMES = Path(r"C:\Windows\Fonts\times.ttf")
FONT_TIMES_BOLD = Path(r"C:\Windows\Fonts\timesbd.ttf")

SCREENSHOTS = {
    "dashboard": ROOT / "docs" / "assets" / "grace_l2_overview" / "dashboard.png",
    "dashboard_running": ROOT / "docs" / "assets" / "grace_l2_overview" / "dashboard_running.png",
    "data_paths": ROOT / "docs" / "assets" / "grace_l2_overview" / "data_paths.png",
    "processing": ROOT / "docs" / "assets" / "grace_l2_overview" / "processing_setup.png",
    "preview": ROOT / "docs" / "assets" / "grace_l2_overview" / "preview.png",
    "leakage": ROOT / "design" / "stitch" / "leakage_correction" / "screen.png",
    "basin": ROOT / "design" / "stitch" / "basin_analysis" / "screen.png",
    "monitor": ROOT / "design" / "stitch" / "run_monitor" / "screen.png",
}

DOC_LINKS = [
    ("项目 README", "../README.md"),
    ("Python README", "../python/README.md"),
    ("MATLAB README", "../matlab/README.md"),
    ("HPC 使用说明", "HPC_PYTHON_MATLAB_USAGE.md"),
    ("滤波与算法说明", "GRACE_FILTER_METHODS_AND_ALGORITHM.md"),
    ("工程结构说明", "ENGINEERING_STRUCTURE.md"),
    ("中文 Markdown 说明", "GRACE_L2_PYTHON_PYSIDE_GUI_USER_GUIDE_ZH.md"),
]

FEATURE_PAGES = [
    {
        "title": "Dashboard - 总览、运行入口与状态摘要",
        "image": "dashboard_running",
        "caption": "Dashboard 聚合当前配置、运行状态、输出位置和常用操作，是用户进入处理流程的第一屏。",
        "cards": [
            ["Project Configuration Summary", "显示项目名、最后编辑时间、配置 UID 和配置状态。", "读取/展示当前配置上下文，帮助用户确认正在处理哪一个配置版本。"],
            ["Pipeline Controls", "Run Filters、Pause、Stop、Load/Save Config、Validate Paths、Data Paths、Processing Setup、Preview、Console。", "按钮连接 MainWindowController；运行任务通过后台线程启动，状态和日志回写到界面。"],
            ["Output Root", "展示解析后的输出根目录和本地/远程输出提示。", "由配置中的 path.OUTPUT 与运行上下文解析，配合本地 output/local 和远程 output/remote/<jobid> 约定。"],
            ["Data Availability", "显示 GFC 文件数量、可用时间跨度和数据扫描状态。", "通过时间索引和 GFC 探测逻辑更新，用于运行前判断输入是否足够。"],
            ["Current Run", "展示当前任务状态、进度、阶段、滤波列表和 I/O 状态。", "由 Qt signals 驱动，接收 pipeline progress/status/log 事件。"],
            ["Run Output Preview", "列出最新产物、stack、monthly MAT、plots、logs 等解析路径。", "用于快速跳转和核对结果目录，避免用户在输出树中手动查找。"],
        ],
        "notes": [
            "适合作为运行前检查页：先验证路径，再保存配置，最后启动 Run Filters。",
            "运行中应观察 Current Run 和控制台日志；如果日志安静，应结合 Run Output 页面进一步判断。",
        ],
    },
    {
        "title": "Data Paths - 输入、输出和参考数据路径",
        "image": "data_paths",
        "caption": "Data Paths 页面集中维护全部文件路径，是减少输入缺失和路径错误的关键页面。",
        "cards": [
            ["Input Directories", "GFC Input Directory、DDK Data Directory、GFC detected range。", "GFC 目录用于时间索引和月份探测；DDK 目录供 DDK 滤波器读取算子。"],
            ["Output Directories", "Remote Sync、Main Output Root、Logs Directory。", "决定本地输出和远程同步策略；日志目录用于 GUI 和批处理诊断。"],
            ["Reference Paths", "Aux Root、Boundary Root、Boundary Shapefile、C20、Degree-1、GIA、Mascon Root、Mascon Reference/GAD/GIA。", "这些路径被配置服务写回 JSON，并由低阶项替换、GIA 改正、Mascon 匹配和地图叠加模块使用。"],
            ["Path Badges", "Verified、OK、Ready 等状态标识。", "路径验证结果直接反馈到控件旁，便于用户修复缺失文件。"],
            ["Load/Save/Validate", "加载配置、保存配置、全量路径验证。", "用户修改路径后应保存配置，并在正式运行前执行 Validate All Paths。"],
        ],
        "notes": [
            "更换机器、数据版本、处理中心或输出根目录后，必须重新验证路径。",
            "HPC 运行前需确认远程端也存在必要输入，而不只是本地路径有效。",
        ],
    },
    {
        "title": "Processing Setup - 科学处理参数与滤波策略",
        "image": "processing",
        "caption": "Processing Setup 决定反演、改正、格网、滤波和 HSAF 等核心科学处理策略。",
        "cards": [
            ["Detected Time Range", "自动探测 GFC 覆盖范围，或启用 Manual Override 后手动设置 Start/End Date。", "由 GFC 时间索引服务读取文件名和头信息，构建实际可处理月份。"],
            ["Inversion & Corrections", "Maximum Degree/Order、Mean/Anomaly、Anomaly Baseline、Low-Degree、Degree-1、C20、C30、GIA。", "对应球谐反演和标准改正链路；低阶项和 GIA 由配置路径提供输入。"],
            ["Spatial Grid", "Resolution、Lat/Lon Min/Max，默认全球范围。", "输出网格约定为 [nLon x nLat x Nt]，区域裁剪需明确研究目的。"],
            ["SH / Grid Utility", "Tool Source、Run SH -> Grid Synthesis、Run Grid -> SH Analysis。", "为单文件调试或辅助转换提供入口，不替代完整 pipeline。"],
            ["滤波方法", "Gaussian、P4M6、P4M6_GAUSS、DDK、FAN、P4M6_FAN、HSAF。", "多选后进入 pipeline plan；当前要求输出 DDK4、FAN、GAUSS+P4M6、FAN+P4M6 等产品。"],
            ["HSAF 参数区", "HSAF 输入、迭代、自适应/全局策略和相关参数。", "默认 pre_hankel_input 建议使用 P4M6，参数以 JSON 为准，避免界面和配置不一致。"],
            ["Presets / Save Config", "加载预设和保存当前处理参数。", "实验前保存配置，确保结果可复现。"],
        ],
        "notes": [
            "均值基线、低阶项替换和 GIA 改正会显著影响结果，应在报告中明确说明。",
            "HPC 当前运行建议 parallel.nWorkers=52，并与 SLURM --cpus-per-task=52 匹配。",
        ],
    },
    {
        "title": "Preview Results - 地图预览、图层控制和导出",
        "image": "preview",
        "caption": "Preview 页面用于加载 stack 或格网产品，快速检查空间结果并导出图件。",
        "cards": [
            ["Dataset Source", "选择 stack/MAT/NetCDF/HDF 产品并读取 Stack Info。", "通过 stack probe/loader 获取变量、维度、时间信息和切片。"],
            ["Time / Variable", "Data Variable、Time Index。", "选择变量和月份切片，检查单月结果或代表性月份。"],
            ["Projection", "Equal Earth、Robinson、Mollweide、Mercator、Lambert 等投影。", "投影工具位于 ui/plotting/projections.py，保证全球和区域图件显示合理。"],
            ["Color Control", "Colormap、Color Min、Color Max。", "支持自动色标或手动色标，便于不同滤波产品对比。"],
            ["Region", "Use Detected Extent、Lon/Lat Min/Max。", "默认使用数据范围，也可手动裁剪流域或区域。"],
            ["Layer Stack", "Data、Coastlines、Basin Boundaries、Grid Lines、River Networks。", "叠加层来自 plotting overlays/boundaries，用于图件质检和表达。"],
            ["Render / Export", "Render Preview、Export Figure。", "渲染画布后可导出图件，作为报告或结果检查附件。"],
            ["Map Status", "Dataset、Cursor Position、Grid Value、Engine Latency。", "显示光标位置、栅格值和绘图响应状态。"],
        ],
        "notes": [
            "质量检查时建议开启海岸线和经纬网，以便发现经纬方向、投影或边界错位。",
            "比较不同滤波产品时，应固定色标范围和月份，避免视觉误判。",
        ],
    },
    {
        "title": "Leakage Correction - 区域泄漏校正与诊断",
        "image": "leakage",
        "caption": "泄漏校正页面面向湖泊、流域和区域产品，用于校正滤波和平滑造成的信号泄漏。",
        "cards": [
            ["Recommendation Summary", "显示推荐策略和当前场景判断。", "classify_leakage_scene 和 recommend_correction_method 根据输入类型、边界和区域特征给出建议。"],
            ["Input and Output", "LRC Input、Reference Input、Regional Boundary、Output Path、Load Input Info。", "读取待校正 stack、参考场和边界文件，并解析输出目录。"],
            ["Strategy", "校正策略、场景、官方模式、DDK 类型等。", "支持比例因子、海岸缓冲、正则化、Forward Modelling 等策略选择。"],
            ["Parameters", "Gaussian radius、Scale Factor、Coastal Buffer、Regularization Lambda、Iterations、FM Max Iterations 等。", "参数绑定到服务层变量，运行时传入 leakage workflow。"],
            ["Result Entry", "Corrected/Difference/Raw Stack、Global/Regional Map、Open Current Result、View Corrected Stack in Preview。", "运行完成后将校正结果接入 Preview 页面复查地图和时间序列。"],
            ["Diagnostics", "日志、输入检查、策略提示和异常信息。", "用于判断边界、掩膜、参考输入或参数是否合理。"],
            ["Run Controls", "Run Correction、Pause、Stop。", "泄漏校正任务独立于主 pipeline，可单独运行和暂停。"],
        ],
        "notes": [
            "泄漏校正应记录输入产品、边界文件、策略和参数，否则难以复现。",
            "校正后必须回到 Preview 或 Basin Analysis 复查地图和时间序列。",
        ],
    },
    {
        "title": "Basin Analysis - 流域掩膜、序列提取与统计",
        "image": "basin",
        "caption": "Basin Analysis 页面把格网产品转换为流域尺度时间序列和统计指标。",
        "cards": [
            ["Grid Data", "Grid Stack、Read Grid Metadata、Input Status、Grid Shape、Time Coverage、Data Variable。", "读取 MAT/NC/HDF stack，确认维度、时间和变量是否符合分析要求。"],
            ["Boundary and Mask", "Boundary File、Name Field、Selection Mode、Read Boundary、Generate Mask。", "读取矢量边界，支持 Multi-Selector、Global Scan、Point Buffer，并生成流域掩膜。"],
            ["Basin Data Preview", "流域表格、当前选择、掩膜状态和地图预览。", "帮助用户确认选中的流域和边界字段是否正确。"],
            ["Products and Output", "Export Path、Area-weighted basin time series、Trend/statistics、Mask grids、TXT/CSV、MAT。", "控制输出内容和格式，兼顾 MATLAB 后续分析和文本表格分享。"],
            ["Time-Series Analysis", "Aggregation、Gap Handling、趋势/年周期/半年周期说明。", "用于月尺度 GRACE 序列统计，缺月策略应在报告中说明。"],
            ["Analysis Tools", "Extract Basin Series、Estimate Trend / Amplitude。", "提供单独工具入口，便于先提取序列再做谐波拟合。"],
            ["Run Controls", "Run Analysis、Pause、Stop。", "触发完整流域分析流程，结果写入指定输出目录。"],
        ],
        "notes": [
            "多流域分析应由 JSON 显式控制，不建议默认自动开启。",
            "流域平均结果应注明面积权重、掩膜来源和缺月处理方式。",
        ],
    },
    {
        "title": "Run Output - 运行监控、输出定位与日志",
        "image": "monitor",
        "caption": "Run Output 页面用于定位当前运行状态、解析后的配置、输出目录和实时日志。",
        "cards": [
            ["Run Summary", "Pipeline 状态、整体进度、当前任务。", "接收 pipeline progress/status 信号，作为运行总状态展示。"],
            ["Resolved Context", "Config、Filters、Output Root、Time Span。", "把配置解析结果展示给用户，避免实际运行内容和预期不一致。"],
            ["Resolved Outputs", "Output Root、Stacks、Plots、Latest Artifact。", "集中展示结果入口，减少手动查找目录的成本。"],
            ["Run Controls", "Pause Current Run、Stop Current Run、Clear Run State。", "用于处理中断、清理状态或恢复界面。"],
            ["Live Process Logs", "实时日志窗口。", "汇总标准输出、错误和服务层日志，是排查失败原因的第一来源。"],
        ],
        "notes": [
            "本地运行重点检查 output/local 和 GUI 日志。",
            "HPC 运行重点检查 output/remote/<jobid>/logs、SLURM 状态、CPU 和输出文件数量。",
        ],
    },
]


def register_fonts() -> tuple[str, str, str, str]:
    yahei = "MicrosoftYaHei"
    yahei_bold = "MicrosoftYaHeiBold"
    times = "TimesNewRoman"
    times_bold = "TimesNewRomanBold"
    pdfmetrics.registerFont(TTFont(yahei, str(FONT_YAHEI), subfontIndex=0))
    pdfmetrics.registerFont(TTFont(yahei_bold, str(FONT_YAHEI_BOLD), subfontIndex=0))
    pdfmetrics.registerFont(TTFont(times, str(FONT_TIMES)))
    pdfmetrics.registerFont(TTFont(times_bold, str(FONT_TIMES_BOLD)))
    return yahei, yahei_bold, times, times_bold


def build_styles(font_name: str, bold_name: str, times: str, times_bold: str):
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            fontName=bold_name,
            fontSize=26,
            leading=34,
            textColor=colors.HexColor("#123A66"),
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            fontName=font_name,
            fontSize=10.8,
            leading=18,
            textColor=colors.HexColor("#475569"),
            wordWrap="CJK",
            spaceAfter=9,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            fontName=bold_name,
            fontSize=17,
            leading=23,
            textColor=colors.HexColor("#123A66"),
            spaceBefore=12,
            spaceAfter=8,
            wordWrap="CJK",
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subsection",
            fontName=bold_name,
            fontSize=12.6,
            leading=18,
            textColor=colors.HexColor("#1F2937"),
            spaceBefore=8,
            spaceAfter=5,
            wordWrap="CJK",
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyCN",
            fontName=font_name,
            fontSize=9.1,
            leading=15,
            textColor=colors.HexColor("#1F2937"),
            wordWrap="CJK",
            alignment=TA_LEFT,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallCN",
            fontName=font_name,
            fontSize=7.7,
            leading=11,
            textColor=colors.HexColor("#4B5563"),
            wordWrap="CJK",
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Caption",
            fontName=font_name,
            fontSize=7.8,
            leading=11,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            wordWrap="CJK",
            spaceBefore=4,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            fontName=bold_name,
            fontSize=7.6,
            leading=10.5,
            textColor=colors.white,
            alignment=TA_CENTER,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName=font_name,
            fontSize=7.25,
            leading=10.5,
            textColor=colors.HexColor("#1F2937"),
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeCN",
            fontName=times,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#111827"),
            backColor=colors.HexColor("#F3F4F6"),
            borderColor=colors.HexColor("#E5E7EB"),
            borderWidth=0.35,
            borderPadding=5,
            wordWrap="CJK",
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LinkCN",
            fontName=font_name,
            fontSize=8.4,
            leading=13,
            textColor=colors.HexColor("#0B63B6"),
            wordWrap="CJK",
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            fontName=times,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B"),
            wordWrap="CJK",
        )
    )
    return styles


def p(text: str, styles, style: str = "BodyCN") -> Paragraph:
    return Paragraph(text, styles[style])


def bullet_table(items: list[str], styles) -> list[Paragraph]:
    return [p(f"- {item}", styles, "BodyCN") for item in items]


def scaled_image(path: Path, max_width: float, max_height: float) -> Image:
    with PILImage.open(path) as im:
        width, height = im.size
    scale = min(max_width / width, max_height / height)
    img = Image(str(path), width=width * scale, height=height * scale)
    img.hAlign = "CENTER"
    return img


def screenshot_block(title: str, path: Path, caption: str, styles, max_height: float = 8.2 * cm):
    block = [p(title, styles, "Subsection")]
    if path.exists():
        block.append(scaled_image(path, 16.0 * cm, max_height))
        block.append(p(caption, styles, "Caption"))
    else:
        block.append(p(f"截图文件未找到：{path}", styles, "SmallCN"))
    return KeepTogether(block)


def make_table(data: list[list[str]], widths: list[float], styles, header: bool = True) -> Table:
    rows = []
    for r, row in enumerate(data):
        style_name = "TableHeader" if header and r == 0 else "TableCell"
        rows.append([p(cell, styles, style_name) for cell in row])
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.32, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4E89")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    else:
        commands.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]))
    t.setStyle(TableStyle(commands))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D6DEE8"))
    canvas.setLineWidth(0.5)
    canvas.line(1.55 * cm, height - 1.28 * cm, width - 1.55 * cm, height - 1.28 * cm)
    canvas.line(1.55 * cm, 1.28 * cm, width - 1.55 * cm, 1.28 * cm)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("TimesNewRoman", 7.5)
    canvas.drawString(1.55 * cm, height - 0.98 * cm, "GRACE Level-2 Python/PySide GUI User Guide")
    canvas.setFont("MicrosoftYaHei", 7.5)
    canvas.drawRightString(width - 1.55 * cm, 0.82 * cm, f"第 {doc.page} 页")
    canvas.restoreState()


def add_doc_links(story, styles):
    rows = [["文档", "相对链接", "用途"]]
    uses = {
        "项目 README": "项目入口、启动矩阵、共享约定",
        "Python README": "Python GUI/CLI 启动与打包说明",
        "MATLAB README": "MATLAB 后端和本地运行说明",
        "HPC 使用说明": "远程提交、拉取结果和集群运行说明",
        "滤波与算法说明": "滤波方法、算法背景和参数含义",
        "工程结构说明": "模块边界、目录职责和维护参考",
        "中文 Markdown 说明": "与本 PDF 对应的纯文本说明",
    }
    for label, href in DOC_LINKS:
        rows.append([f'<link href="{href}">{label}</link>', href, uses[label]])
    story.append(make_table(rows, [4.2 * cm, 5.7 * cm, 6.1 * cm], styles))


def add_feature_page(story, feature, styles):
    story.append(p(feature["title"], styles, "Section"))
    story.append(screenshot_block("", SCREENSHOTS[feature["image"]], feature["caption"], styles, 7.4 * cm))
    story.append(p("页面功能卡片与实现说明", styles, "Subsection"))
    rows = [["功能卡片/区域", "用户可见功能", "实现与数据流说明"], *feature["cards"]]
    story.append(make_table(rows, [3.7 * cm, 5.7 * cm, 6.6 * cm], styles))
    story.append(p("使用建议", styles, "Subsection"))
    story.extend(bullet_table(feature["notes"], styles))
    story.append(PageBreak())


def build_story(styles):
    story = []
    story.append(Spacer(1, 1.0 * cm))
    story.append(p("GRACE Level-2 Python/PySide GUI 程序图文说明", styles, "CoverTitle"))
    story.append(
        p(
            "面向桌面端用户、科研处理人员和维护人员。本版采用结构化编排，按功能页面说明截图、功能卡片、实现逻辑、输入输出和使用建议，"
            "并提供可点击的相对文档链接，便于从 PDF 跳转到仓库 README 与专题说明。",
            styles,
            "CoverSubtitle",
        )
    )
    story.append(
        make_table(
            [
                ["项目", "内容"],
                ["程序名称", "GRACE Level-2 Pipeline"],
                ["界面技术", "Python + PySide6"],
                ["字体规范", "中文使用微软雅黑；英文、数字和命令使用 Times New Roman"],
                ["主要任务", "GRACE/GRACE-FO Level-2 球谐数据处理、滤波、结果预览、流域分析、泄漏校正和 HPC 批处理"],
                ["输出约定", "本地输出 output/local；远程输出 output/remote/<jobid>"],
            ],
            [4.0 * cm, 12.0 * cm],
            styles,
        )
    )
    story.append(Spacer(1, 0.35 * cm))
    story.append(scaled_image(SCREENSHOTS["dashboard"], 16.0 * cm, 7.3 * cm))
    story.append(p("图 1  程序主界面 Dashboard。", styles, "Caption"))
    story.append(PageBreak())

    story.append(p("1. 程序概述", styles, "Section"))
    story.append(
        p(
            "GRACE Level-2 Pipeline 是一套面向 GRACE/GRACE-FO 卫星重力 Level-2 数据的桌面处理程序。"
            "GUI 负责配置、交互、运行控制和结果检查；核心处理通过统一 JSON 配置驱动，并与 MATLAB 后端保持一致的数据路径、滤波策略和输出约定。",
            styles,
        )
    )
    story.append(
        make_table(
            [
                ["维度", "说明"],
                ["处理对象", "GRACE/GRACE-FO GSM 或兼容 GFC 球谐系数，以及必要的低阶项、GIA、DDK、Mascon、边界和掩膜数据。"],
                ["科学产品", "等效水高 EWH 月尺度格网、滤波 stack、趋势/周期图件、流域序列和泄漏校正结果。"],
                ["运行环境", "Windows GUI、本地 Python CLI、MATLAB 本地验证、Linux/HPC SLURM 批处理。"],
                ["配置原则", "所有关键路径和科学参数均应写入 JSON，保证运行可追溯和可复现。"],
            ],
            [3.2 * cm, 12.8 * cm],
            styles,
        )
    )
    story.append(p("2. 结构化功能总览", styles, "Section"))
    story.append(
        make_table(
            [
                ["页面", "核心用户任务", "关键输出/状态"],
                ["Dashboard", "总览配置、验证路径、启动运行、查看进度", "运行状态、输出根目录、数据可用性、最新产物"],
                ["Data Paths", "维护输入/输出/参考路径", "路径验证结果、GFC 探测范围、日志目录"],
                ["Processing Setup", "设置科学参数和滤波组合", "时间范围、格网、改正项、滤波计划"],
                ["Preview Results", "加载产品并渲染地图", "地图预览、图层状态、导出图件"],
                ["Leakage Correction", "执行区域泄漏校正", "校正 stack、差异结果、诊断信息"],
                ["Basin Analysis", "提取流域序列和统计指标", "流域时间序列、趋势/周期、掩膜和 MAT/TXT 输出"],
                ["Run Output", "监控运行和排查问题", "日志、解析配置、输出路径、任务控制"],
            ],
            [3.3 * cm, 7.4 * cm, 5.3 * cm],
            styles,
        )
    )
    story.append(PageBreak())

    for feature in FEATURE_PAGES:
        add_feature_page(story, feature, styles)

    story.append(p("10. 输入、输出与数据约定", styles, "Section"))
    story.append(
        make_table(
            [
                ["类别", "内容", "说明"],
                ["主要输入", "GFC/GSM、低阶项、GIA、DDK、Mascon、边界、海岸线、陆海掩膜", "运行前必须确认本地或远程环境均可访问。"],
                ["主要输出", "EWH 格网、滤波 stack、月产品、图件、流域序列、泄漏校正、日志", "不同模块输出应保留配置和日志以便复现。"],
                ["本地输出", "output/local/...", "用于 Windows 本地或源码调试运行。"],
                ["远程输出", "output/remote/<jobid>/...", "用于 HPC/SLURM 作业结果归档。"],
                ["格网约定", "[nLon x nLat x Nt]", "跨 Python/MATLAB 管线保持一致。"],
                ["HSAF 默认输入", "P4M6", "需要与 pre_hankel_input 和实际输入路由保持一致。"],
            ],
            [3.0 * cm, 6.5 * cm, 6.5 * cm],
            styles,
        )
    )

    story.append(p("11. 推荐使用流程", styles, "Section"))
    story.append(p("GUI 交互式运行流程：", styles, "Subsection"))
    story.extend(
        bullet_table(
            [
                "进入 Data Paths，设置并验证输入、输出和参考数据路径。",
                "进入 Processing Setup，设置时间范围、格网、改正项、滤波方法和 HSAF 参数。",
                "回到 Dashboard，保存配置并启动 Run Filters。",
                "在 Run Output 查看日志、进度、解析后的配置和输出路径。",
                "进入 Preview Results 加载输出 stack，检查地图显示和产品质量。",
                "需要区域研究时，进入 Basin Analysis 提取流域时间序列。",
                "需要边界泄漏修正时，进入 Leakage Correction 运行校正并复查结果。",
            ],
            styles,
        )
    )
    story.append(p("HPC 批处理流程：", styles, "Subsection"))
    story.extend(
        bullet_table(
            [
                "先在本地用 GUI 或 CLI 验证配置。",
                "确认远程端输入文件齐全，尤其是 GFC、Mascon、DDK、低阶项和 GIA。",
                "从仓库根目录使用 hpc.ps1 提交作业。",
                "检查 output/remote/<jobid>/logs、SLURM 状态、CPU 和输出文件数量。",
                "拉回结果后用 Preview 或脚本复查图件、stack 和指标。",
            ],
            styles,
        )
    )
    story.append(PageBreak())

    story.append(p("12. 常用命令", styles, "Section"))
    story.append(p("Python 源码 GUI：", styles, "Subsection"))
    story.append(p("cd G:\\GRACE_Level2_pipeline_exc\\python<br/>python -m grace_pipeline.gui_entry", styles, "CodeCN"))
    story.append(p("Python CLI：", styles, "Subsection"))
    story.append(
        p(
            "cd G:\\GRACE_Level2_pipeline_exc\\python<br/>grace-pipeline run -c ..\\matlab\\cfg\\user.json -d ..\\matlab\\cfg\\default.json",
            styles,
            "CodeCN",
        )
    )
    story.append(p("配置检查：", styles, "Subsection"))
    story.append(p("cd G:\\GRACE_Level2_pipeline_exc\\python<br/>grace-pipeline info -c ..\\matlab\\cfg\\user.json", styles, "CodeCN"))
    story.append(p("HPC 提交：", styles, "Subsection"))
    story.append(p("cd G:\\GRACE_Level2_pipeline_exc<br/>.\\hpc.ps1 -Runtime matlab", styles, "CodeCN"))

    story.append(p("13. 相关文档链接", styles, "Section"))
    story.append(p("以下链接为相对路径，PDF 与仓库目录一起移动时仍可作为本地阅读入口。", styles))
    add_doc_links(story, styles)
    return story


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font_name, bold_name, times, times_bold = register_fonts()
    styles = build_styles(font_name, bold_name, times, times_bold)
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        rightMargin=1.55 * cm,
        leftMargin=1.55 * cm,
        topMargin=1.62 * cm,
        bottomMargin=1.62 * cm,
        title="GRACE Level-2 Python/PySide GUI 程序图文说明",
        author="GRACE Level-2 Pipeline",
    )
    doc.build(build_story(styles), onFirstPage=header_footer, onLaterPages=header_footer)
    print(PDF_PATH)
    print(os.path.getsize(PDF_PATH))


if __name__ == "__main__":
    main()
