"""
HTMLGenerator — DocumentModel → 可编辑 .html。

从 :class:`~algo.document_model.DocumentModel` 生成结构化 HTML：

- 每页 → 一个 ``<section class="page">`` 容器
- title 块 → ``<h1>``–``<h6>`` （按 heading_level）
- text 块 → ``<p>`` （run 级 ``<span>`` 保留字体/粗体/颜色）
- table 块 → ``<table>`` + ``<thead>`` / ``<tbody>``（保留合并单元格 rowspan/colspan）
- image 块 → ``<img>`` base64 内嵌（按比例缩放）
- 多列布局 → CSS ``column-count``
- 阅读顺序 → DOM 顺序

设计要点
--------
HTML 同时支持两种模式：
1. **语义流模式**（默认）：语义化标签 + CSS，可编辑、可重排
2. **定位模式**：绝对定位还原版式（类似 PPTX 的策略），通过参数控制

本生成器默认输出语义流模式，兼顾可读性与可编辑性。
图片以 base64 内嵌，生成单文件 HTML 便于分享。
"""

from __future__ import annotations

import base64
import html as html_lib
import io
import logging
import os
from typing import Optional

from algo.document_model import (
    BBox,
    DocumentModel,
    ImageBlock,
    LayoutBlock,
    Page,
    TableBlock,
    TableCell,
    TextRun,
)
from algo.models.params import ConvertParams

logger = logging.getLogger(__name__)


def generate_html(
    model: DocumentModel,
    output_path: str,
    params: Optional[ConvertParams] = None,
) -> str:
    """从 DocumentModel 生成 HTML 文件。

    Args:
        model: 解析阶段产出的文档模型。
        output_path: 输出 .html 文件路径。
        params: 转换参数。

    Returns:
        输出文件路径。
    """
    if params is None:
        params = ConvertParams()

    parts: list[str] = []
    _write_html_head(parts, model)
    parts.append("<body>")

    for page in model.pages:
        _write_page(parts, page, model, params)

    parts.append("</body>")
    parts.append("</html>")

    content = "\n".join(parts)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("HTML generated: %s", output_path)
    return output_path


# ════════════════════════════════════════════════════════════════════
# 文档头部
# ════════════════════════════════════════════════════════════════════

def _write_html_head(parts: list[str], model: DocumentModel):
    """写入 HTML <head>，包含基础 CSS。"""
    title = html_lib.escape(model.title or "Converted Document")
    parts.extend([
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{title}</title>",
        "<style>",
        "/* ── 基础重置 ── */",
        "* { margin: 0; padding: 0; box-sizing: border-box; }",
        "body {",
        "  font-family: 'Noto Sans CJK SC', 'Segoe UI', sans-serif;",
        "  background: #f5f5f5;",
        "  color: #222;",
        "  line-height: 1.6;",
        "}",
        "/* ── 页面容器 ── */",
        ".page {",
        "  max-width: 794px; /* A4 @ 96dpi */",
        "  margin: 24px auto;",
        "  background: #fff;",
        "  padding: 48px 56px;",
        "  box-shadow: 0 2px 12px rgba(0,0,0,0.08);",
        "  border-radius: 4px;",
        "}",
        ".page.multi-col { column-count: 2; column-gap: 32px; }",
        "/* ── 标题 ── */",
        "h1, h2, h3, h4, h5, h6 { margin: 0.8em 0 0.4em; line-height: 1.3; }",
        "h1 { font-size: 1.8em; }",
        "h2 { font-size: 1.5em; }",
        "h3 { font-size: 1.25em; }",
        "h4 { font-size: 1.1em; }",
        "/* ── 段落 ── */",
        "p { margin: 0 0 0.6em 0; }",
        "/* ── 列表 ── */",
        "ul, ol { margin: 0 0 0.6em 1.5em; }",
        "li { margin-bottom: 0.2em; }",
        "/* ── 表格 ── */",
        "table {",
        "  width: 100%;",
        "  border-collapse: collapse;",
        "  margin: 0.8em 0;",
        "  font-size: 0.95em;",
        "}",
        "th, td {",
        "  border: 1px solid #ddd;",
        "  padding: 6px 10px;",
        "  text-align: left;",
        "}",
        "th { background: #f0f0f0; font-weight: 600; }",
        "/* ── 图片 ── */",
        "img { max-width: 100%; height: auto; margin: 0.8em 0; }",
        ".caption { text-align: center; font-style: italic; color: #666; font-size: 0.9em; }",
        "/* ── 页眉页脚 ── */",
        ".header, .footer { color: #888; font-size: 0.85em; margin-bottom: 0.4em; }",
        ".footer { margin-top: 0.4em; margin-bottom: 0; }",
        "/* ── 公式 ── */",
        ".formula { font-style: italic; font-family: 'Cambria Math', serif; margin: 0.4em 0; }",
        "</style>",
        "</head>",
    ])


# ════════════════════════════════════════════════════════════════════
# 页面
# ════════════════════════════════════════════════════════════════════

def _write_page(
    parts: list[str],
    page: Page,
    model: DocumentModel,
    params: ConvertParams,
):
    """写入单页。"""
    classes = ["page"]
    if page.has_multiple_columns and len(page.text_blocks) >= 4:
        classes.append("multi-col")

    parts.append(f'<section class="{" ".join(classes)}">')

    for block in page.sorted_blocks:
        _write_block(parts, block, params)

    parts.append("</section>")


# ════════════════════════════════════════════════════════════════════
# 块级元素
# ════════════════════════════════════════════════════════════════════

def _write_block(parts: list[str], block: LayoutBlock, params: ConvertParams):
    """写入单个版面块。"""
    if block.block_type == "title":
        _write_heading(parts, block)
    elif block.block_type == "text":
        _write_paragraph(parts, block)
    elif block.block_type == "list":
        _write_list_item(parts, block)
    elif block.block_type == "table" and block.table:
        _write_table(parts, block.table)
    elif block.block_type == "image" and block.image:
        _write_image(parts, block.image)
    elif block.block_type == "formula" and block.formula:
        parts.append(f'<div class="formula">{html_lib.escape(block.formula.latex)}</div>')
    elif block.block_type == "header":
        parts.append(f'<div class="header">{_runs_to_html(block.runs)}</div>')
    elif block.block_type == "footer":
        parts.append(f'<div class="footer">{_runs_to_html(block.runs)}</div>')
    elif block.block_type == "caption":
        parts.append(f'<div class="caption">{_runs_to_html(block.runs)}</div>')


def _write_heading(parts: list[str], block: LayoutBlock):
    """写入标题。"""
    level = min(max(block.heading_level or 1, 1), 6)
    text = _runs_to_html(block.runs)
    if not text.strip():
        return
    parts.append(f"<h{level}>{text}</h{level}>")


def _write_paragraph(parts: list[str], block: LayoutBlock):
    """写入段落。"""
    text = _runs_to_html(block.runs)
    if not text.strip():
        return
    parts.append(f"<p>{text}</p>")


def _write_list_item(parts: list[str], block: LayoutBlock):
    """写入列表项。"""
    text = _runs_to_html(block.runs)
    if not text.strip():
        return
    parts.append(f"<ul><li>{text}</li></ul>")


def _write_table(parts: list[str], table: TableBlock):
    """写入表格，保留合并单元格。"""
    if table.rows == 0 or table.cols == 0:
        return

    parts.append("<table>")

    # 构建单元格网格
    grid: list[list[Optional[TableCell]]] = [
        [None] * table.cols for _ in range(table.rows)
    ]
    for cell in table.cells:
        for r in range(cell.row, min(cell.row + cell.rowspan, table.rows)):
            for c in range(cell.col, min(cell.col + cell.colspan, table.cols)):
                grid[r][c] = cell

    # 分离表头和表体
    has_header = any(c.is_header for c in table.cells)
    header_rows = 0
    if has_header:
        # 表头行 = 第一行标记为 header 的连续行
        for r in range(table.rows):
            if any(grid[r][c] and grid[r][c].is_header for c in range(table.cols)):
                header_rows = r + 1
            else:
                break

    occupied = [[False] * table.cols for _ in range(table.rows)]

    if header_rows > 0:
        parts.append("<thead>")
        for r in range(header_rows):
            parts.append("<tr>")
            for c in range(table.cols):
                if occupied[r][c]:
                    continue
                cell = grid[r][c]
                if cell is None:
                    parts.append("<th></th>")
                    continue
                occupied[r][c] = True
                attrs = _cell_attrs(cell)
                parts.append(f"<th{attrs}>{_runs_to_html(cell.runs)}</th>")
            parts.append("</tr>")
        parts.append("</thead>")

    parts.append("<tbody>")
    for r in range(header_rows, table.rows):
        parts.append("<tr>")
        for c in range(table.cols):
            if occupied[r][c]:
                continue
            cell = grid[r][c]
            if cell is None:
                parts.append("<td></td>")
                continue
            # 标记被合并覆盖的格子
            for rr in range(r, min(r + cell.rowspan, table.rows)):
                for cc in range(c, min(c + cell.colspan, table.cols)):
                    occupied[rr][cc] = True
            attrs = _cell_attrs(cell)
            parts.append(f"<td{attrs}>{_runs_to_html(cell.runs)}</td>")
        parts.append("</tr>")
    parts.append("</tbody>")
    parts.append("</table>")


def _cell_attrs(cell: TableCell) -> str:
    """生成单元格的 rowspan/colspan 属性。"""
    attrs = []
    if cell.rowspan > 1:
        attrs.append(f' rowspan="{cell.rowspan}"')
    if cell.colspan > 1:
        attrs.append(f' colspan="{cell.colspan}"')
    return "".join(attrs)


def _write_image(parts: list[str], img: ImageBlock):
    """写入图片（base64 内嵌）。"""
    if img.image_bytes:
        b64 = base64.b64encode(img.image_bytes).decode("ascii")
        mime = f"image/{img.fmt}" if img.fmt != "jpg" else "image/jpeg"
        parts.append(f'<img src="data:{mime};base64,{b64}" alt="{html_lib.escape(img.caption or "")}">')
    elif img.image_path and os.path.isfile(img.image_path):
        with open(img.image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = os.path.splitext(img.image_path)[1].lstrip(".")
        mime = f"image/{ext}" if ext != "jpg" else "image/jpeg"
        parts.append(f'<img src="data:{mime};base64,{b64}" alt="{html_lib.escape(img.caption or "")}">')

    if img.caption:
        parts.append(f'<div class="caption">{html_lib.escape(img.caption)}</div>')


# ════════════════════════════════════════════════════════════════════
# Run 级渲染
# ════════════════════════════════════════════════════════════════════

def _runs_to_html(runs: list[TextRun]) -> str:
    """将 TextRun 列表渲染为 HTML，保留字体元数据。

    每个 run 包裹在 ``<span>`` 中，通过 inline style 保留字体名、字号、
    粗体、斜体、颜色。
    """
    if not runs:
        return ""

    spans: list[str] = []
    for run in runs:
        if not run.text:
            continue
        text = html_lib.escape(run.text)
        styles: list[str] = []

        if run.font_name:
            styles.append(f"font-family:'{run.font_name}'")
        if run.font_size:
            styles.append(f"font-size:{run.font_size}pt")
        if run.bold:
            styles.append("font-weight:bold")
        if run.italic:
            styles.append("font-style:italic")
        if run.underline:
            styles.append("text-decoration:underline")
        if run.color:
            styles.append(f"color:{run.color}")

        if styles:
            style_str = ";".join(styles)
            spans.append(f'<span style="{style_str}">{text}</span>')
        else:
            spans.append(text)

    return "".join(spans)
