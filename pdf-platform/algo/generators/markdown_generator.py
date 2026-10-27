"""
MarkdownGenerator — DocumentModel → 可编辑 .md。

从 :class:`~algo.document_model.DocumentModel` 生成结构化 Markdown：

- title 块 → ``#``–``######`` （按 heading_level）
- text 块 → 普通段落（run 级 ``**bold**`` / ``*italic*``）
- table 块 → GitHub Flavored Markdown 表格（保留对齐）
- image 块 → ``![caption](path)`` （图片保存到输出目录）
- list 块 → ``- item``
- formula 块 → ``$$latex$$``
- 阅读顺序 → 文档内容顺序
- 多页 → 页间 ``---`` 分隔符

设计要点
--------
Markdown 是纯文本格式，无法精确定位元素，因此本生成器走语义化路线：
将版面块按阅读顺序输出为结构化 Markdown，最大化可编辑性与可读性。
表格使用 GFM 语法，图片引用输出目录中的文件。
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from algo.document_model import (
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


def generate_markdown(
    model: DocumentModel,
    output_path: str,
    params: Optional[ConvertParams] = None,
) -> str:
    """从 DocumentModel 生成 Markdown 文件。

    Args:
        model: 解析阶段产出的文档模型。
        output_path: 输出 .md 文件路径。
        params: 转换参数。

    Returns:
        输出文件路径。
    """
    if params is None:
        params = ConvertParams()

    output_dir = os.path.dirname(output_path)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    img_dir = os.path.join(output_dir, f"{base_name}_images")
    img_counter = 0

    lines: list[str] = []

    # 文档标题
    if model.title:
        lines.append(f"# {model.title}")
        lines.append("")

    for page_idx, page in enumerate(model.pages):
        if page_idx > 0:
            lines.append("")
            lines.append("---")
            lines.append("")

        for block in page.sorted_blocks:
            if block.block_type == "image" and block.image:
                img_counter += 1
                _write_image(lines, block.image, img_dir, img_counter)
            elif block.block_type == "table" and block.table:
                _write_table(lines, block.table)
            elif block.block_type == "title":
                _write_heading(lines, block)
            elif block.block_type == "text":
                _write_paragraph(lines, block)
            elif block.block_type == "list":
                _write_list_item(lines, block)
            elif block.block_type == "formula" and block.formula:
                if block.formula.inline:
                    lines.append(f"${block.formula.latex}$")
                else:
                    lines.append(f"$$")
                    lines.append(block.formula.latex)
                    lines.append("$$")
                lines.append("")
            elif block.block_type == "caption":
                text = _runs_to_markdown(block.runs)
                if text.strip():
                    lines.append(f"*{text.strip()}*")
                    lines.append("")
            # header / footer 在 Markdown 中跳过（避免噪音）

    content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Markdown generated: %s", output_path)
    return output_path


# ════════════════════════════════════════════════════════════════════
# 块级元素
# ════════════════════════════════════════════════════════════════════

def _write_heading(lines: list[str], block: LayoutBlock):
    """写入标题。标题不加粗体标记（# 已表示标题层级）。"""
    level = min(max(block.heading_level or 1, 1), 6)
    # 标题用纯文本，不加 **bold** —— # 已表示层级
    text = "".join(r.text for r in block.runs).strip()
    if not text:
        return
    lines.append(f"{'#' * level} {text}")
    lines.append("")


def _write_paragraph(lines: list[str], block: LayoutBlock):
    """写入段落。"""
    text = _runs_to_markdown(block.runs).strip()
    if not text:
        return
    lines.append(text)
    lines.append("")


def _write_list_item(lines: list[str], block: LayoutBlock):
    """写入列表项。"""
    text = _runs_to_markdown(block.runs).strip()
    if not text:
        return
    lines.append(f"- {text}")
    lines.append("")


def _write_table(lines: list[str], table: TableBlock):
    """写入 GFM 表格。

    GFM 不原生支持合并单元格，因此合并单元格的内容会被展平：
    - rowspan：被合并的行中对应列留空
    - colspan：被合并的列内容合并到起始单元格
    """
    if table.rows == 0 or table.cols == 0:
        return

    # 构建网格
    grid: list[list[Optional[TableCell]]] = [
        [None] * table.cols for _ in range(table.rows)
    ]
    for cell in table.cells:
        for r in range(cell.row, min(cell.row + cell.rowspan, table.rows)):
            for c in range(cell.col, min(cell.col + cell.colspan, table.cols)):
                grid[r][c] = cell

    # 输出表格
    # 表头行
    header_cells = []
    for c in range(table.cols):
        cell = grid[0][c] if table.rows > 0 else None
        text = _runs_to_markdown(cell.runs).strip() if cell else ""
        # 跳过被合并覆盖的重复单元格
        header_cells.append(text if cell and cell.col == c else "")

    lines.append(f"| {' | '.join(header_cells)} |")
    lines.append(f"| {' | '.join(['---'] * table.cols)} |")

    # 数据行
    for r in range(1, table.rows):
        row_cells = []
        seen = set()
        for c in range(table.cols):
            cell = grid[r][c]
            if cell is None:
                row_cells.append("")
                continue
            # 跳过同一单元格的重复列（colspan）
            cell_key = (cell.row, cell.col)
            if cell_key in seen:
                row_cells.append("")
            else:
                seen.add(cell_key)
                # 跳过 rowspan 覆盖的行
                if cell.row < r:
                    row_cells.append("")
                else:
                    row_cells.append(_runs_to_markdown(cell.runs).strip())

        lines.append(f"| {' | '.join(row_cells)} |")

    lines.append("")


def _write_image(
    lines: list[str],
    img: ImageBlock,
    img_dir: str,
    counter: int,
):
    """写入图片引用。图片字节保存到输出目录。"""
    img_filename = f"image_{counter}.png"

    if img.image_bytes:
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, img_filename)
        with open(img_path, "wb") as f:
            f.write(img.image_bytes)
        rel_path = os.path.join(os.path.basename(img_dir), img_filename)
    elif img.image_path and os.path.isfile(img.image_path):
        os.makedirs(img_dir, exist_ok=True)
        img_path = os.path.join(img_dir, img_filename)
        with open(img.image_path, "rb") as src, open(img_path, "wb") as dst:
            dst.write(src.read())
        rel_path = os.path.join(os.path.basename(img_dir), img_filename)
    else:
        return

    alt = img.caption or f"Image {counter}"
    lines.append(f"![{alt}]({rel_path})")
    lines.append("")


# ════════════════════════════════════════════════════════════════════
# Run 级渲染
# ════════════════════════════════════════════════════════════════════

def _runs_to_markdown(runs: list[TextRun]) -> str:
    """将 TextRun 列表渲染为 Markdown 文本。

    保留粗体（``**text**``）和斜体（``*text*``）。
    字体名和字号在 Markdown 中无法表达，因此丢弃。
    """
    if not runs:
        return ""

    parts: list[str] = []
    for run in runs:
        if not run.text:
            continue
        text = run.text

        # Markdown 转义：只转义会影响渲染的字符
        # 不转义所有特殊字符（会降低可读性），只处理管道符（表格中会冲突）
        # 段落级的转义由调用方按需处理

        if run.bold and run.italic:
            parts.append(f"***{text}***")
        elif run.bold:
            parts.append(f"**{text}**")
        elif run.italic:
            parts.append(f"*{text}*")
        else:
            parts.append(text)

    return "".join(parts)
