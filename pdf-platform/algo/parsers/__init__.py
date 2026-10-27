"""
DocumentParser — PDF / 图片 → DocumentModel。

两条解析路径，统一输出 :class:`~algo.document_model.DocumentModel`：

1. **数字 PDF 路径**（有文本层的 PDF）：
   用 PyMuPDF 提取文本块、字体元数据、图片、表格线条，
   按几何位置推断阅读顺序与标题层级。
   精度高、速度快，字体信息完整。

2. **扫描 / 图片路径**（无文本层的 PDF 或纯图片输入）：
   用 PaddleOCR PP-Structure 做版面分析 + OCR 文字识别，
   裁剪图片区域。OCR 不可用时回退到 PyMuPDF 光栅化 + 基础 OCR。

设计要点
--------
- 解析器不关心输出格式，只产出 DocumentModel。
- 阅读顺序在解析阶段计算完成（几何排序 + 多列检测）。
- 坐标统一归一化到 [0,1]，与页面尺寸解耦。
"""

from __future__ import annotations

import io
import logging
import os
from typing import Optional

import fitz  # PyMuPDF

from algo.document_model import (
    BBox,
    DocumentModel,
    FormulaBlock,
    ImageBlock,
    LayoutBlock,
    Page,
    TableBlock,
    TableCell,
    TextRun,
)
from algo.models.params import ConvertParams
from algo.ocr.ocr_text import is_image_file

logger = logging.getLogger(__name__)


def parse_document(
    file_path: str,
    params: Optional[ConvertParams] = None,
) -> DocumentModel:
    """解析 PDF 或图片为 DocumentModel。

    自动选择解析路径：
    - 图片输入 → 图片/OCR 路径
    - PDF 有文本层 → 数字 PDF 路径
    - PDF 无文本层（扫描件）→ OCR 路径

    Args:
        file_path: 源文件路径。
        params: 转换参数（使用 ocr / layout / start_page / end_page）。

    Returns:
        结构化 :class:`DocumentModel`。
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    if params is None:
        params = ConvertParams()

    if is_image_file(file_path):
        return _parse_image(file_path, params)

    # PDF: 检测是否有文本层
    doc = fitz.open(file_path)
    start = max(0, params.start_page)
    end = params.end_page if params.end_page is not None else doc.page_count - 1
    end = min(end, doc.page_count - 1)

    has_text_layer = _detect_text_layer(doc, start, end)
    doc.close()

    if has_text_layer and not params.ocr.enabled:
        return _parse_digital_pdf(file_path, params)
    else:
        return _parse_scanned_pdf(file_path, params)


# ════════════════════════════════════════════════════════════════════
# 数字 PDF 路径
# ════════════════════════════════════════════════════════════════════

def _detect_text_layer(doc: fitz.Document, start: int, end: int) -> bool:
    """检测 PDF 是否有可用的嵌入文本层。"""
    sample_pages = min(end - start + 1, 3)
    for i in range(start, start + sample_pages):
        if i >= doc.page_count:
            break
        text = doc[i].get_text("text").strip()
        if len(text) > 10:
            return True
    return False


def _parse_digital_pdf(file_path: str, params: ConvertParams) -> DocumentModel:
    """解析有文本层的 PDF：提取文本块、字体、图片、表格结构。"""
    logger.info("Parsing digital PDF: %s", file_path)
    doc = fitz.open(file_path)
    start = max(0, params.start_page)
    end = params.end_page if params.end_page is not None else doc.page_count - 1
    end = min(end, doc.page_count - 1)

    model = DocumentModel(
        source_path=file_path,
        source_type="pdf",
        needs_ocr=False,
    )

    for i in range(start, end + 1):
        page = doc[i]
        page_model = _parse_digital_page(page, i, params)
        model.pages.append(page_model)

    doc.close()

    # 推断标题
    _infer_document_title(model)
    return model


def _parse_digital_page(
    page: fitz.Page,
    page_index: int,
    params: ConvertParams,
) -> Page:
    """解析单页数字 PDF。"""
    page_w = page.rect.width
    page_h = page.rect.height
    page_model = Page(index=page_index, width=page_w, height=page_h)

    # 1. 提取文本块
    text_blocks_raw = []
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:  # 0 = text block
            continue
        layout_block = _parse_text_block(block, page_w, page_h)
        if layout_block.text.strip() or layout_block.runs:
            text_blocks_raw.append(layout_block)

    # 2. 提取图片块
    if params.layout.detect_images:
        for block in page_dict.get("blocks", []):
            if block.get("type") == 1:  # image block
                img_block = _parse_image_block(page, block, page_w, page_h, page_index)
                if img_block:
                    page_model.blocks.append(img_block)

    # 3. 检测表格（基于线条几何）
    if params.layout.detect_tables:
        tables = _detect_tables_geometric(page, page_w, page_h, text_blocks_raw)
        page_model.blocks.extend(tables)

    # 4. 添加非表格文本块
    table_bboxes = [t.bbox for t in tables]
    for blk in text_blocks_raw:
        if not _bbox_inside_any(blk.bbox, table_bboxes):
            page_model.blocks.append(blk)

    # 5. 检测页眉页脚
    if params.layout.detect_headers_footers:
        _mark_headers_footers(page_model)

    # 6. 推断标题层级
    _infer_heading_levels(page_model)

    # 7. 计算阅读顺序
    if params.layout.reading_order:
        _compute_reading_order(page_model)
    else:
        for idx, blk in enumerate(page_model.blocks):
            blk.reading_order = idx

    return page_model


def _parse_text_block(block: dict, page_w: float, page_h: float) -> LayoutBlock:
    """将 PyMuPDF 文本 block 转为 LayoutBlock。"""
    bbox_raw = block.get("bbox", (0, 0, 0, 0))
    bbox = _normalize_bbox(bbox_raw, page_w, page_h)

    runs: list[TextRun] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text:
                continue
            runs.append(TextRun(
                text=text,
                font_name=span.get("font", ""),
                font_size=round(span.get("size", 12), 1),
                bold=_is_bold_font(span.get("font", "")),
                color=_int_to_hex(span.get("color", 0)),
            ))

    return LayoutBlock(
        block_type="text",
        bbox=bbox,
        runs=runs,
    )


def _parse_image_block(
    page: fitz.Page,
    block: dict,
    page_w: float,
    page_h: float,
    page_index: int,
) -> Optional[LayoutBlock]:
    """提取图片块并裁剪保存。"""
    bbox_raw = block.get("bbox", (0, 0, 0, 0))
    bbox = _normalize_bbox(bbox_raw, page_w, page_h)

    # 尝试提取图片
    try:
        img_list = page.get_images(full=True)
        for img_info in img_list:
            xref = img_info[0]
            base_image = page.parent.extract_image(xref)
            image_bytes = base_image["image"]
            fmt = base_image.get("ext", "png")
            return LayoutBlock(
                block_type="image",
                bbox=bbox,
                image=ImageBlock(
                    bbox=bbox,
                    image_bytes=image_bytes,
                    fmt=fmt,
                ),
            )
    except Exception as e:
        logger.debug("Image extraction failed on page %d: %s", page_index, e)

    # 回退：裁剪页面区域为图片
    try:
        clip = fitz.Rect(bbox_raw)
        pix = page.get_pixmap(clip=clip, dpi=150)
        image_bytes = pix.tobytes("png")
        return LayoutBlock(
            block_type="image",
            bbox=bbox,
            image=ImageBlock(
                bbox=bbox,
                image_bytes=image_bytes,
                fmt="png",
            ),
        )
    except Exception as e:
        logger.warning("Image crop fallback failed on page %d: %s", page_index, e)
        return None


def _detect_tables_geometric(
    page: fitz.Page,
    page_w: float,
    page_h: float,
    text_blocks: list[LayoutBlock],
) -> list[LayoutBlock]:
    """基于线条几何检测表格。

    使用 PyMuPDF 的 drawings (线条/矩形) 检测表格边界，
    然后将落在表格区域内的文本组织为单元格。
    """
    drawings = page.get_drawings()
    h_lines: list[float] = []  # y 坐标
    v_lines: list[float] = []  # x 坐标

    for drw in drawings:
        for item in drw.get("items", []):
            if item[0] == "l":  # line
                p1, p2 = item[1], item[2]
                if _is_horizontal(p1, p2):
                    h_lines.append(p1.y)
                elif _is_vertical(p1, p2):
                    v_lines.append(p1.x)
            elif item[0] == "re":  # rectangle
                rect = item[1]
                h_lines.extend([rect.y0, rect.y1])
                v_lines.extend([rect.x0, rect.x1])

    # 聚类相近线条
    h_lines = _cluster_coords(h_lines, tolerance=3.0)
    v_lines = _cluster_coords(v_lines, tolerance=3.0)

    if len(h_lines) < 2 or len(v_lines) < 2:
        return []

    # 构建表格
    rows = len(h_lines) - 1
    cols = len(v_lines) - 1
    if rows < 1 or cols < 1:
        return []

    table_bbox = BBox(
        x0=min(v_lines) / page_w,
        y0=min(h_lines) / page_h,
        x1=max(v_lines) / page_w,
        y1=max(h_lines) / page_h,
    )

    cells: list[TableCell] = []
    for r in range(rows):
        for c in range(cols):
            cell_x0 = v_lines[c] / page_w
            cell_y0 = h_lines[r] / page_h
            cell_x1 = v_lines[c + 1] / page_w
            cell_y1 = h_lines[r + 1] / page_h
            cell_bbox = BBox(x0=cell_x0, y0=cell_y0, x1=cell_x1, y1=cell_y1)

            # 找落在此单元格内的文本
            cell_runs = _collect_text_in_bbox(text_blocks, cell_bbox)
            cells.append(TableCell(
                row=r,
                col=c,
                runs=cell_runs,
                is_header=(r == 0),
            ))

    table = TableBlock(bbox=table_bbox, rows=rows, cols=cols, cells=cells)
    return [LayoutBlock(
        block_type="table",
        bbox=table_bbox,
        reading_order=0,
        table=table,
    )]


# ════════════════════════════════════════════════════════════════════
# 扫描 PDF / 图片路径
# ════════════════════════════════════════════════════════════════════

def _parse_scanned_pdf(file_path: str, params: ConvertParams) -> DocumentModel:
    """解析扫描版 PDF：光栅化每页后走图片 OCR 路径。"""
    logger.info("Parsing scanned PDF: %s", file_path)
    doc = fitz.open(file_path)
    start = max(0, params.start_page)
    end = params.end_page if params.end_page is not None else doc.page_count - 1
    end = min(end, doc.page_count - 1)

    model = DocumentModel(source_path=file_path, source_type="pdf", needs_ocr=True)

    for i in range(start, end + 1):
        page = doc[i]
        page_w = page.rect.width
        page_h = page.rect.height
        page_model = Page(index=i, width=page_w, height=page_h)

        # 光栅化页面
        pix = page.get_pixmap(dpi=params.image.dpi or 200)
        img_bytes = pix.tobytes("png")

        # 用 OCR 解析这一页
        blocks = _ocr_page_to_blocks(img_bytes, page_w, page_h, params)
        page_model.blocks.extend(blocks)

        _infer_heading_levels(page_model)
        _compute_reading_order(page_model)

        model.pages.append(page_model)

    doc.close()
    _infer_document_title(model)
    return model


def _parse_image(file_path: str, params: ConvertParams) -> DocumentModel:
    """解析图片输入（照片、截图、海报等）。"""
    logger.info("Parsing image: %s", file_path)
    from PIL import Image

    img = Image.open(file_path)
    img_w, img_h = img.size

    with open(file_path, "rb") as f:
        img_bytes = f.read()

    model = DocumentModel(
        source_path=file_path,
        source_type="image",
        needs_ocr=True,
    )

    page = Page(index=0, width=float(img_w), height=float(img_h))

    blocks = _ocr_page_to_blocks(img_bytes, float(img_w), float(img_h), params)
    page.blocks.extend(blocks)

    _infer_heading_levels(page)
    _compute_reading_order(page)

    model.pages.append(page)
    _infer_document_title(model)
    return model


def _ocr_page_to_blocks(
    img_bytes: bytes,
    page_w: float,
    page_h: float,
    params: ConvertParams,
) -> list[LayoutBlock]:
    """对光栅化页面图片执行 OCR，返回版面块列表。

    优先使用 PaddleOCR PP-Structure（版面分析 + 表格 + OCR）。
    PaddleOCR 不可用时回退到 PyMuPDF 内置 OCR（基于 Tesseract）。
    """
    # 尝试 PaddleOCR PP-Structure
    blocks = _try_paddle_structure(img_bytes, page_w, page_h, params)
    if blocks is not None:
        return blocks

    # 回退：PyMuPDF OCR
    logger.warning("PaddleOCR unavailable, falling back to PyMuPDF OCR")
    return _try_fitz_ocr(img_bytes, page_w, page_h, params)


def _try_paddle_structure(
    img_bytes: bytes,
    page_w: float,
    page_h: float,
    params: ConvertParams,
) -> Optional[list[LayoutBlock]]:
    """用 PaddleOCR PP-Structure 做版面分析 + OCR。"""
    try:
        from paddleocr import PPStructure
    except ImportError:
        return None

    try:
        import tempfile
        # 写临时文件（PaddleOCR 需要文件路径）
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        try:
            engine = PPStructure(
                show_log=False,
                lang=params.ocr.language,
                layout=True,
                table=True,
                ocr=True,
            )
            result = engine(tmp_path)
        finally:
            os.unlink(tmp_path)

        blocks: list[LayoutBlock] = []
        for region in result:
            bbox_raw = region.get("bbox", [0, 0, 0, 0])
            region_type = region.get("type", "text")
            bbox = _normalize_bbox(
                (bbox_raw[0], bbox_raw[1], bbox_raw[2], bbox_raw[3]),
                page_w, page_h,
            )

            if region_type == "table":
                table_block = _paddle_table_to_block(region, bbox, page_w, page_h)
                if table_block:
                    blocks.append(table_block)
            elif region_type == "figure":
                blocks.append(LayoutBlock(
                    block_type="image",
                    bbox=bbox,
                    image=ImageBlock(bbox=bbox, image_bytes=img_bytes, fmt="png"),
                ))
            elif region_type == "title":
                runs = _paddle_res_to_runs(region.get("res", []))
                blocks.append(LayoutBlock(
                    block_type="title",
                    bbox=bbox,
                    runs=runs,
                    heading_level=1,
                ))
            else:
                runs = _paddle_res_to_runs(region.get("res", []))
                blocks.append(LayoutBlock(
                    block_type="text",
                    bbox=bbox,
                    runs=runs,
                ))

        return blocks if blocks else None
    except Exception as e:
        logger.warning("PaddleOCR PP-Structure failed: %s", e)
        return None


def _paddle_res_to_runs(res: list) -> list[TextRun]:
    """将 PaddleOCR 识别结果转为 TextRun 列表。"""
    runs: list[TextRun] = []
    for item in res:
        if isinstance(item, dict):
            text = item.get("text", "")
            conf = item.get("confidence", 1.0)
            if text and conf > 0.3:
                runs.append(TextRun(text=text))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            # PaddleOCR 格式: (bbox, (text, confidence))
            text_info = item[1] if len(item[1]) >= 1 else ""
            if isinstance(text_info, (list, tuple)):
                text = text_info[0] if text_info else ""
            else:
                text = str(text_info)
            if text:
                runs.append(TextRun(text=text))
    return runs


def _paddle_table_to_block(
    region: dict,
    bbox: BBox,
    page_w: float,
    page_h: float,
) -> Optional[LayoutBlock]:
    """将 PaddleOCR 表格识别结果转为 TableBlock。"""
    html = region.get("html", "")
    if not html:
        return None

    # 简化：从 HTML 表格解析行列结构
    import re
    rows_match = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)
    if not rows_match:
        return None

    cells: list[TableCell] = []
    max_col = 0
    for r, row_html in enumerate(rows_match):
        cell_matches = re.findall(
            r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL | re.IGNORECASE
        )
        colspan_match = re.findall(r"colspan=['\"]?(\d+)", row_html, re.IGNORECASE)
        rowspan_match = re.findall(r"rowspan=['\"]?(\d+)", row_html, re.IGNORECASE)
        is_header_row = bool(re.search(r"<th", row_html, re.IGNORECASE))

        c = 0
        for ci, cell_text in enumerate(cell_matches):
            clean = re.sub(r"<[^>]+>", "", cell_text).strip()
            cs = int(colspan_match[ci]) if ci < len(colspan_match) else 1
            rs = int(rowspan_match[ci]) if ci < len(rowspan_match) else 1
            cells.append(TableCell(
                row=r,
                col=c,
                rowspan=rs,
                colspan=cs,
                runs=[TextRun(text=clean)] if clean else [],
                is_header=is_header_row,
            ))
            c += cs
            max_col = max(max_col, c)

    return LayoutBlock(
        block_type="table",
        bbox=bbox,
        table=TableBlock(
            bbox=bbox,
            rows=len(rows_match),
            cols=max_col,
            cells=cells,
        ),
    )


def _try_fitz_ocr(
    img_bytes: bytes,
    page_w: float,
    page_h: float,
    params: ConvertParams,
) -> list[LayoutBlock]:
    """回退 OCR：用 PyMuPDF 内置 OCR（基于 Tesseract）。

    如果 Tesseract 也不可用，至少做基础文本提取。
    """
    blocks: list[LayoutBlock] = []
    try:
        # 创建临时 PDF 页面来做 OCR
        tmp_doc = fitz.open()
        tmp_page = tmp_doc.new_page(width=page_w, height=page_h)
        tmp_page.insert_image(fitz.Rect(0, 0, page_w, page_h), stream=img_bytes)

        # 尝试 OCR
        text_page = tmp_page.get_textpage_ocr(
            dpi=200,
            language=params.ocr.language if params.ocr.language != "ch" else "eng",
        )
        page_dict = text_page.extract("dict")

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            bbox = _normalize_bbox(block.get("bbox", (0, 0, 0, 0)), page_w, page_h)
            runs = []
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if text:
                        runs.append(TextRun(text=text))
            if runs:
                blocks.append(LayoutBlock(block_type="text", bbox=bbox, runs=runs))

        tmp_doc.close()
    except Exception as e:
        logger.warning("PyMuPDF OCR also failed: %s", e)

    return blocks


# ════════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════════

def _normalize_bbox(raw: tuple, page_w: float, page_h: float) -> BBox:
    """将像素/pt 坐标归一化到 [0,1]。"""
    x0 = max(0.0, min(1.0, raw[0] / page_w)) if page_w > 0 else 0.0
    y0 = max(0.0, min(1.0, raw[1] / page_h)) if page_h > 0 else 0.0
    x1 = max(0.0, min(1.0, raw[2] / page_w)) if page_w > 0 else 1.0
    y1 = max(0.0, min(1.0, raw[3] / page_h)) if page_h > 0 else 1.0
    # 确保最小尺寸
    if x1 <= x0:
        x1 = min(1.0, x0 + 0.01)
    if y1 <= y0:
        y1 = min(1.0, y0 + 0.01)
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _is_bold_font(font_name: str) -> bool:
    """从字体名推断是否粗体。"""
    name_lower = font_name.lower()
    return any(k in name_lower for k in ("bold", "black", "heavy", "demibold"))


def _int_to_hex(color_int: int) -> str:
    """PyMuPDF 颜色整数 → "#RRGGBB"。"""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def _is_horizontal(p1, p2, tol=2.0) -> bool:
    return abs(p1.y - p2.y) < tol


def _is_vertical(p1, p2, tol=2.0) -> bool:
    return abs(p1.x - p2.x) < tol


def _cluster_coords(coords: list[float], tolerance: float = 3.0) -> list[float]:
    """聚类相近坐标，返回去重后的排序坐标。"""
    if not coords:
        return []
    sorted_coords = sorted(coords)
    clusters = [[sorted_coords[0]]]
    for c in sorted_coords[1:]:
        if c - clusters[-1][-1] < tolerance:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    return [sum(cl) / len(cl) for cl in clusters]


def _collect_text_in_bbox(blocks: list[LayoutBlock], bbox: BBox) -> list[TextRun]:
    """收集落在大致在 bbox 内的文本 runs。"""
    runs = []
    for blk in blocks:
        # 中心点是否在单元格内
        cx = blk.bbox.center_x
        cy = blk.bbox.center_y
        if bbox.x0 <= cx <= bbox.x1 and bbox.y0 <= cy <= bbox.y1:
            runs.extend(blk.runs)
    return runs


def _bbox_inside_any(bbox: BBox, bboxes: list[BBox]) -> bool:
    """检查 bbox 是否被任何一个 bboxes 包含。"""
    for b in bboxes:
        if (bbox.x0 >= b.x0 and bbox.y0 >= b.y0 and
                bbox.x1 <= b.x1 and bbox.y1 <= b.y1):
            return True
    return False


def _mark_headers_footers(page: Page):
    """标记页眉页脚：页面顶部 10% 和底部 10% 区域的文本块。"""
    for blk in page.blocks:
        if blk.block_type not in ("text", "title"):
            continue
        if blk.bbox.y1 <= 0.1:  # 顶部 10%
            blk.block_type = "header"
        elif blk.bbox.y0 >= 0.9:  # 底部 10%
            blk.block_type = "footer"


def _infer_heading_levels(page: Page):
    """根据字号推断标题层级。

    启发式：字号最大的文本块 → H1，次大 → H2，以此类推。
    只对 title 类型的块或字号显著大于正文（>1.2x 中位数字号）的块标记。
    """
    text_blocks = [b for b in page.blocks if b.block_type in ("text", "title")]
    if not text_blocks:
        return

    # 收集所有字号
    sizes = []
    for blk in text_blocks:
        for run in blk.runs:
            if run.font_size:
                sizes.append(run.font_size)

    if not sizes:
        return

    sizes.sort(reverse=True)
    median_size = sizes[len(sizes) // 2] if sizes else 12

    for blk in text_blocks:
        max_size = max((r.font_size or 0) for r in blk.runs) if blk.runs else 0
        if max_size > 0 and max_size >= median_size * 1.2:
            blk.block_type = "title"
            # 级别推断：越大级别越高
            if max_size >= median_size * 1.8:
                blk.heading_level = 1
            elif max_size >= median_size * 1.5:
                blk.heading_level = 2
            elif max_size >= median_size * 1.2:
                blk.heading_level = 3


def _compute_reading_order(page: Page):
    """计算页面内阅读顺序。

    策略：
    1. 检测多列布局
    2. 单列：从上到下排序
    3. 多列：先按列分组（左到右），列内从上到下
    4. 表格和图片按其垂直位置插入阅读流
    """
    blocks = list(page.blocks)
    if not blocks:
        return

    if not page.has_multiple_columns:
        # 单列：直接按 y0 排序
        blocks.sort(key=lambda b: (b.bbox.y0, b.bbox.x0))
    else:
        # 多列：按 x 中心分列，列内按 y 排序
        # 简化：用 0.5 作为分列阈值
        left_col = [b for b in blocks if b.bbox.center_x < 0.5]
        right_col = [b for b in blocks if b.bbox.center_x >= 0.5]
        left_col.sort(key=lambda b: b.bbox.y0)
        right_col.sort(key=lambda b: b.bbox.y0)
        blocks = left_col + right_col

    for idx, blk in enumerate(blocks):
        blk.reading_order = idx


def _infer_document_title(model: DocumentModel):
    """推断文档标题：取第一页第一个标题块。"""
    if model.pages:
        for blk in model.pages[0].sorted_blocks:
            if blk.block_type == "title" and blk.text.strip():
                model.title = blk.text.strip()[:200]
                return
