"""
algo/utils — 共享格式工具函数。

统一管理格式标识符 ↔ 文件扩展名 / MIME 类型的映射。
所有模块（pipeline / workers / API）都应引用本模块以避免散落重复映射。

约定
----
- ``FORMAT_EXTENSIONS`` / ``FORMAT_MIME_TYPES``：已知格式全集（含 ``pdf-edit``），
  用于前端格式列表展示与下载 MIME 推断。
- ``CONVERTER_FORMATS``：pipeline 实际有实体实现的子集（algo/converters 中
  有对应 ``to_*_converter`` 的格式）。新增转换器时需同步更新此处。
"""

from __future__ import annotations

# ── 格式 → 文件扩展名 ──────────────────────────────────────────────
FORMAT_EXTENSIONS: dict[str, str] = {
    "docx": ".docx",
    "xlsx": ".xlsx",
    "pptx": ".pptx",
    "html": ".html",
    "markdown": ".md",
    "txt": ".txt",
    "png": ".png",
    "jpg": ".jpg",
    "pdf-edit": ".pdf",
}

# ── 格式 → MIME 类型 ───────────────────────────────────────────────
FORMAT_MIME_TYPES: dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html",
    "markdown": "text/markdown",
    "txt": "text/plain",
    "png": "image/png",
    "jpg": "image/jpeg",
    "pdf-edit": "application/pdf",
}

# ── Pipeline 中实际支持的转换器格式（algo/converters 中有实体实现）──
CONVERTER_FORMATS: list[str] = ["docx", "pptx", "xlsx", "html", "jpg", "png", "markdown", "txt"]


def get_extension(format_id: str) -> str:
    """根据格式标识符返回文件扩展名（含 dot）。

    未知格式回退为 ``.{format_id}``，保证总能拿到一个可用扩展名。
    """
    return FORMAT_EXTENSIONS.get(format_id, f".{format_id}")


def get_mime_type(format_id: str) -> str:
    """根据格式标识符返回 MIME 类型。

    未知格式回退为 ``application/octet-stream``。
    """
    return FORMAT_MIME_TYPES.get(format_id, "application/octet-stream")


def get_supported_formats() -> list[str]:
    """返回所有已知格式列表（含 ``pdf-edit`` 等非转换格式）。"""
    return list(FORMAT_EXTENSIONS.keys())


def get_converter_formats() -> list[str]:
    """返回 pipeline 实际支持的转换格式列表。"""
    return list(CONVERTER_FORMATS)
