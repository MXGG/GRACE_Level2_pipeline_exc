"""Runtime terminology and language-switching fixes."""
from __future__ import annotations

import contextlib

_ORIGINAL = None
TERMS_ZH = {
    # Core terminology.
    "UID": "配置编号",
    "Configuration ID": "配置编号",
    "In-Memory Config": "当前临时配置",
    "Grid Stack": "网格数据栈",
    "Stack Status": "数据栈状态",
    "Input Stack": "输入数据栈",
    "Source Stack File": "源数据栈文件",
    "Stack not loaded.": "数据栈未读取。",
    "Input MAT/NC/HDF stack": "输入 MAT/NC/HDF 数据栈",

    # Shell and navigation.
    "GRACE Level-2 Pipeline": "GRACE 二级处理流程",
    "Precision Processing Pipeline": "精密处理流程",
    "Overview": "总览",
    "Processing": "滤波处理",
    "Leakage Correction": "泄漏校正",
    "Flow Analysis": "流域分析",
    "Preview": "预览",
    "Help": "帮助",
    "Log": "日志",
    "Appearance": "外观",
    "Ready": "就绪",
    "Open GRACE-L2": "打开 GRACE-L2",
    "Exit": "退出程序",
    "Version / User": "版本 / 用户",

    # Overview/dashboard cards.
    "SYSTEM AND PROJECT STATUS": "系统与项目状态",
    "CONFIGURATION": "配置",
    "LAST UPDATED": "最后更新",
    "STATE": "状态",
    "USER": "用户",
    "VERSION": "版本",
    "TIME": "时间",
    "MEMORY": "内存",
    "CURRENT RUN": "当前任务",
    "STATUS": "状态",
    "PROGRESS": "进度",
    "STAGE": "阶段",
    "FILTER CHAIN": "滤波链",
    "DATA AND OUTPUTS": "数据与输出",
    "AVAILABLE MONTHS": "可用月份",
    "OUTPUT ROOT": "输出根目录",
    "OUTPUT STRUCTURE": "输出结构",
    "LATEST ARTIFACT": "最新产物",
    "LOCAL": "本地输出",
    "MONTHLY": "月度数据",
    "LOGS": "日志",
    "ROOT": "根目录",
    "STACKS": "数据栈",
    "FIGURES": "图件",
    "RUNTIME": "运行环境",
    "Current configuration": "当前配置",
    "Run completed": "运行完成",
    "Completed": "已完成",
    "Idle": "空闲",
    "Task Idle": "任务空闲",

    # Paths and artifacts.
    "Output Root": "输出根目录",
    "Output Directory": "输出目录",
    "Local Output": "本地输出",
    "Monthly MAT": "月度 MAT",
    "Figures": "图件",
    "Logs": "日志",
    "Runtime": "运行环境",
    "Available Months": "可用月份",
    "Latest Artifact": "最新产物",

    # Dialogs and actions.
    "Start Download": "开始下载",
    "Re-authorize": "重新授权",
    "Data Website": "数据网页",
    "Download Confirmation": "下载确认",
    "Settings": "设置",
    "Theme": "主题",
    "Language": "语言",
    "English": "英语",
    "Chinese": "中文",
    "OK": "确定",
    "Cancel": "取消",
    "Apply": "应用",
    "Choose between English and Simplified Chinese for the interface.": "选择界面使用英语或简体中文。",

    # Extra theme labels.
    "Blue": "蓝色",
    "Green": "绿色",
    "Graphite": "石墨",
    "Sepia": "暖色",
    "Violet": "紫色",
}
PREFIX_ZH = {
    "Stacks: ": "数据栈：",
    "Stack Status: ": "数据栈状态：",
    "Config: ": "配置：",
    "Status: ": "状态：",
    "Progress: ": "进度：",
    "Stage: ": "阶段：",
    "Output Root: ": "输出根目录：",
    "Root: ": "根目录：",
    "Local: ": "本地输出：",
    "Monthly: ": "月度数据：",
    "Logs: ": "日志：",
    "Figures: ": "图件：",
    "Runtime: ": "运行环境：",
}


def canonical(text: str) -> str:
    value = str(text or "")
    if not value:
        return value
    from grace_pipeline.ui.qt import i18n
    rev = getattr(i18n, "_runtime_reverse", None)
    if rev is None:
        rev = {str(v): str(k) for k, v in i18n.TRANSLATIONS.get("zh", {}).items()}
        i18n._runtime_reverse = rev
    if value in rev:
        return rev[value]
    prev = getattr(i18n, "_runtime_prefix_reverse", None)
    if prev is None:
        prev = {str(v): str(k) for k, v in i18n.PREFIX_TRANSLATIONS.get("zh", {}).items()}
        i18n._runtime_prefix_reverse = prev
    for zh, en in prev.items():
        if zh and value.startswith(zh):
            return en + value[len(zh):]
    return value


def translate(text: str, language: str = "en") -> str:
    src = canonical(text)
    if str(language or "en").lower() == "en":
        return src
    return _ORIGINAL(src, language) if _ORIGINAL else src


def install() -> None:
    global _ORIGINAL
    from grace_pipeline.ui.qt import i18n
    i18n.TRANSLATIONS.setdefault("zh", {}).update(TERMS_ZH)
    i18n.PREFIX_TRANSLATIONS.setdefault("zh", {}).update(PREFIX_ZH)
    for name in ("_runtime_reverse", "_runtime_prefix_reverse"):
        with contextlib.suppress(Exception):
            delattr(i18n, name)
    if _ORIGINAL is None:
        _ORIGINAL = i18n.translate_text
    i18n.translate_text = translate
