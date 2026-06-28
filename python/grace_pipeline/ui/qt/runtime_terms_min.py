"""Runtime terminology and language-switching fixes."""
from __future__ import annotations

import contextlib

_ORIGINAL = None
TERMS_ZH = {
    "UID": "配置编号",
    "Configuration ID": "配置编号",
    "In-Memory Config": "当前临时配置",
    "Grid Stack": "网格数据栈",
    "Stack Status": "数据栈状态",
    "Input Stack": "输入数据栈",
    "Source Stack File": "源数据栈文件",
    "Stack not loaded.": "数据栈未读取。",
    "Input MAT/NC/HDF stack": "输入 MAT/NC/HDF 数据栈",
    "Open GRACE-L2": "打开 GRACE-L2",
    "Exit": "退出程序",
    "Start Download": "开始下载",
    "Re-authorize": "重新授权",
    "Data Website": "数据网页",
    "Download Confirmation": "下载确认",
    "Blue": "蓝色", "Green": "绿色", "Graphite": "石墨", "Sepia": "暖色", "Violet": "紫色",
}
PREFIX_ZH = {"Stacks: ": "数据栈：", "Stack Status: ": "数据栈状态：", "Config: ": "配置："}


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
