"""
Vision-to-Code 模块 — 将图像 / PDF 转换为可编辑的 HTML/CSS 代码。

参考 Hyperframes / screenshot-to-code 的核心理念：
1. **解析阶段**：从图像/PDF中提取结构化信息（文本块、位置、字体、颜色、图片区域）
2. **代码生成阶段**：将结构化信息转换为语义化 HTML + CSS 代码
3. **保真策略**：使用绝对定位 + 精确坐标还原原始版式，同时保留语义标签

输出是单文件 HTML（内联 CSS），用户可直接编辑代码并实时预览渲染结果。

两条路径：
- **数字 PDF**：PyMuPDF 提取文本层（精确字体、坐标、颜色）→ 代码
- **图像 / 扫描件**：PyMuPDF 光栅化 + OCR 文本识别 → 代码
"""

from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════════

@dataclass
class TextElement:
    """文本元素：一个连续的文本片段，带位置和样式。"""
    text: str
    x: float  # 像素坐标（相对于页面）
    y: float
    width: float
    height: float
    font_size: float = 12.0
    font_name: str = "sans-serif"
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    is_heading: bool = False
    heading_level: int = 0


@dataclass
class ImageElement:
    """图片元素：从页面中提取的图片区域。"""
    x: float
    y: float
    width: float
    height: float
    image_bytes: bytes = b""
    fmt: str = "png"


@dataclass
class PageLayout:
    """单页的布局信息。"""
    width: float
    height: float
    text_elements: list[TextElement] = field(default_factory=list)
    image_elements: list[ImageElement] = field(default_factory=list)
    background_color: str = "#ffffff"
    page_image_b64: Optional[str] = None  # 整页渲染图（用于OCR路径的背景）


@dataclass
class DocumentLayout:
    """整篇文档的布局信息。"""
    pages: list[PageLayout] = field(default_factory=list)
    source_type: str = "pdf"  # "pdf" or "image"
    title: str = "Converted Document"


# ════════════════════════════════════════════════════════════════════
# 解析器：PDF / 图像 → DocumentLayout
# ════════════════════════════════════════════════════════════════════

def parse_to_layout(file_path: str, dpi: int = 150) -> DocumentLayout:
    """解析 PDF 或图像文件为 DocumentLayout。

    自动检测输入类型：
    - PDF 有文本层 → 提取精确文本元素（字体、坐标、颜色）
    - PDF 无文本层 / 纯图像 → 光栅化 + 基础文本检测

    Args:
        file_path: 源文件路径
        dpi: 光栅化分辨率（用于图像路径和背景渲染）

    Returns:
        DocumentLayout 包含所有页面的结构化布局信息
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Source file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"):
        return _parse_image_file(file_path, dpi)
    else:
        return _parse_pdf_file(file_path, dpi)


def _parse_pdf_file(file_path: str, dpi: int) -> DocumentLayout:
    """解析 PDF 文件。"""
    doc = fitz.open(file_path)
    layout = DocumentLayout(source_type="pdf")

    # 推断文档标题
    if doc.page_count > 0:
        first_page_text = doc[0].get_text("text").strip()
        if first_page_text:
            first_line = first_page_text.split("\n")[0][:100]
            layout.title = first_line or "Converted Document"

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        page_layout = _parse_pdf_page(page, dpi)
        layout.pages.append(page_layout)

    doc.close()
    return layout


def _parse_pdf_page(page: fitz.Page, dpi: int) -> PageLayout:
    """解析单页 PDF，提取文本和图片元素。"""
    page_w = page.rect.width
    page_h = page.rect.height
    page_layout = PageLayout(width=page_w, height=page_h)

    # 缩放因子：pt → 像素（按 DPI）
    scale = dpi / 72.0

    # 提取文本元素
    text_dict = page.get_text("dict")
    all_font_sizes = []

    # 第一遍：收集所有字号用于标题检测
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 12)
                all_font_sizes.append(size)

    median_size = sorted(all_font_sizes)[len(all_font_sizes) // 2] if all_font_sizes else 12

    # 第二遍：构建 TextElement
    for block in text_dict.get("blocks", []):
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            line_text = "".join(span.get("text", "") for span in line.get("spans", ""))
            if not line_text.strip():
                continue

            bbox = line.get("bbox", (0, 0, 0, 0))
            first_span = line["spans"][0] if line["spans"] else {}

            font_size = first_span.get("size", 12)
            font_name = first_span.get("font", "sans-serif")
            color_int = first_span.get("color", 0)

            # 判断粗体
            font_lower = font_name.lower()
            is_bold = any(k in font_lower for k in ("bold", "black", "heavy", "demibold"))

            # 判断标题
            is_heading = font_size >= median_size * 1.3
            heading_level = 0
            if is_heading:
                if font_size >= median_size * 2.0:
                    heading_level = 1
                elif font_size >= median_size * 1.6:
                    heading_level = 2
                else:
                    heading_level = 3

            page_layout.text_elements.append(TextElement(
                text=line_text.strip(),
                x=bbox[0],
                y=bbox[1],
                width=bbox[2] - bbox[0],
                height=bbox[3] - bbox[1],
                font_size=round(font_size, 1),
                font_name=_clean_font_name(font_name),
                bold=is_bold,
                color=_int_to_hex(color_int),
                is_heading=is_heading,
                heading_level=heading_level,
            ))

    # 提取图片元素
    for block in text_dict.get("blocks", []):
        if block.get("type") != 1:  # image block
            continue
        bbox = block.get("bbox", (0, 0, 0, 0))
        try:
            # 尝试提取原始图片
            img_list = page.get_images(full=True)
            for img_info in img_list:
                xref = img_info[0]
                base_image = page.parent.extract_image(xref)
                page_layout.image_elements.append(ImageElement(
                    x=bbox[0],
                    y=bbox[1],
                    width=bbox[2] - bbox[0],
                    height=bbox[3] - bbox[1],
                    image_bytes=base_image["image"],
                    fmt=base_image.get("ext", "png"),
                ))
                break
        except Exception as e:
            logger.debug("Image extraction failed: %s", e)

    return page_layout


def _parse_image_file(file_path: str, dpi: int) -> DocumentLayout:
    """解析图像文件。"""
    img = Image.open(file_path)
    img_w, img_h = img.size

    # 将图像转为 PDF 页面以便提取文本（如果有嵌入文本）
    # 对于纯图像，我们创建一个以图像为内容的页面
    page_layout = PageLayout(width=float(img_w), height=float(img_h))

    # 尝试 OCR 提取文本（使用 PyMuPDF 的 OCR 功能）
    try:
        tmp_doc = fitz.open()
        tmp_page = tmp_doc.new_page(width=float(img_w), height=float(img_h))
        with open(file_path, "rb") as f:
            img_bytes = f.read()
        tmp_page.insert_image(fitz.Rect(0, 0, float(img_w), float(img_h)), stream=img_bytes)

        # 尝试 OCR
        try:
            text_page = tmp_page.get_textpage_ocr(dpi=200, language="eng")
            blocks = text_page.extract("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    line_text = "".join(span.get("text", "") for span in line.get("spans", ""))
                    if not line_text.strip():
                        continue
                    bbox = line.get("bbox", (0, 0, 0, 0))
                    page_layout.text_elements.append(TextElement(
                        text=line_text.strip(),
                        x=bbox[0],
                        y=bbox[1],
                        width=bbox[2] - bbox[0],
                        height=bbox[3] - bbox[1],
                        font_size=14.0,
                    ))
        except Exception as e:
            logger.debug("OCR not available: %s", e)

        tmp_doc.close()
    except Exception as e:
        logger.warning("Image parsing failed: %s", e)

    # 保存整页图像的 base64（用于背景或图片区域）
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    fmt = os.path.splitext(file_path)[1].lstrip(".").lower()
    if fmt == "jpg":
        fmt = "jpeg"
    page_layout.page_image_b64 = base64.b64encode(img_bytes).decode("ascii")
    page_layout.background_color = "#ffffff"

    layout = DocumentLayout(source_type="image", pages=[page_layout])
    return layout


# ════════════════════════════════════════════════════════════════════
# 代码生成器：DocumentLayout → HTML/CSS 代码
# ════════════════════════════════════════════════════════════════════

def generate_code(layout: DocumentLayout) -> str:
    """将 DocumentLayout 转换为可编辑的 HTML/CSS 代码。

    生成策略：
    - 每页一个 ``<div class="page">`` 容器，尺寸精确匹配原始页面
    - 文本元素使用绝对定位（``position: absolute``），坐标精确到像素
    - 图片元素以 base64 内嵌
    - 标题使用语义化 ``<h1>``-``<h3>`` 标签
    - CSS 内联在 ``<style>`` 标签中
    - 输出是单文件 HTML，用户可直接编辑

    Args:
        layout: 解析阶段产出的文档布局

    Returns:
        完整的 HTML 文件内容（字符串）
    """
    parts: list[str] = []

    # ── HTML 头部 ──
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head>")
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append(f"<title>{_escape_html(layout.title)}</title>")
    parts.append("<style>")
    parts.append(_generate_css(layout))
    parts.append("</style>")
    parts.append("</head>")
    parts.append("<body>")

    # ── 每页内容 ──
    for page_idx, page in enumerate(layout.pages):
        parts.append(f'  <!-- Page {page_idx + 1} -->')
        parts.append(f'  <div class="page" style="width:{page.width}px;height:{page.height}px;">')

        # 图片元素
        for img_el in page.image_elements:
            img_html = _image_element_to_html(img_el)
            parts.append(f"    {img_html}")

        # 如果是图像输入且没有提取到图片元素，用整页图作为背景
        if layout.source_type == "image" and page.page_image_b64 and not page.image_elements:
            mime = "image/png"
            parts.append(
                f'    <img class="page-bg" src="data:{mime};base64,{page.page_image_b64}" '
                f'style="position:absolute;top:0;left:0;width:100%;height:100%;object-fit:contain;" />'
            )

        # 文本元素
        for text_el in page.text_elements:
            text_html = _text_element_to_html(text_el)
            parts.append(f"    {text_html}")

        parts.append("  </div>")

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


def _generate_css(layout: DocumentLayout) -> str:
    """生成全局 CSS 样式。"""
    return """
/* ── 全局重置 ── */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: #e8e8e8;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  gap: 20px;
}

/* ── 页面容器 ── */
.page {
  position: relative;
  background: white;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

/* ── 文本元素（绝对定位） ── */
.text-element {
  position: absolute;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.2;
}

/* ── 标题样式 ── */
.heading-1 { font-weight: 700; }
.heading-2 { font-weight: 600; }
.heading-3 { font-weight: 600; }

/* ── 图片元素 ── */
.image-element {
  position: absolute;
  object-fit: fill;
}

.page-bg {
  z-index: 0;
}

.text-element {
  z-index: 1;
}
""".strip()


def _text_element_to_html(el: TextElement) -> str:
    """将文本元素转换为 HTML。"""
    # 构建 style 属性
    styles = [
        f"left:{el.x:.1f}px",
        f"top:{el.y:.1f}px",
        f"width:{el.width:.1f}px",
        f"min-height:{el.height:.1f}px",
        f"font-size:{el.font_size:.1f}px",
        f"color:{el.color}",
    ]

    if el.font_name:
        styles.append(f"font-family:'{el.font_name}', sans-serif")
    if el.bold:
        styles.append("font-weight:bold")
    if el.italic:
        styles.append("font-style:italic")

    style_str = ";".join(styles)
    text = _escape_html(el.text)

    # 语义化标签
    if el.is_heading and el.heading_level > 0:
        level = min(el.heading_level, 3)
        return f'<h{level} class="text-element heading-{level}" style="{style_str}">{text}</h{level}>'
    else:
        return f'<div class="text-element" style="{style_str}">{text}</div>'


def _image_element_to_html(el: ImageElement) -> str:
    """将图片元素转换为 HTML。"""
    if not el.image_bytes:
        return ""

    b64 = base64.b64encode(el.image_bytes).decode("ascii")
    mime = f"image/{el.fmt}" if el.fmt != "jpg" else "image/jpeg"

    styles = [
        f"left:{el.x:.1f}px",
        f"top:{el.y:.1f}px",
        f"width:{el.width:.1f}px",
        f"height:{el.height:.1f}px",
    ]
    style_str = ";".join(styles)

    return f'<img class="image-element" src="data:{mime};base64,{b64}" style="{style_str}" />'


# ════════════════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════════════════

def _clean_font_name(font_name: str) -> str:
    """清理字体名，提取可用的 CSS font-family 值。"""
    # PyMuPDF 字体名通常包含子集前缀，如 "ABCDEF+Helvetica-Bold"
    name = font_name.split("+")[-1] if "+" in font_name else font_name
    # 移除粗体/斜体标记（CSS 单独处理）
    for suffix in ("-BoldItalic", "-BoldOblique", "-Bold", "-Italic", "-Oblique", "-Regular", "-Light", "-Medium"):
        name = name.replace(suffix, "")
    return name.strip() or "sans-serif"


def _int_to_hex(color_int: int) -> str:
    """PyMuPDF 颜色整数 → '#RRGGBB'。"""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02X}{g:02X}{b:02X}"


def _escape_html(text: str) -> str:
    """HTML 转义。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# ════════════════════════════════════════════════════════════════════
# 公共 API
# ════════════════════════════════════════════════════════════════════

def convert_to_code(file_path: str, dpi: int = 150) -> str:
    """端到端：PDF / 图像 → 可编辑 HTML/CSS 代码。

    这是模块的统一入口。解析文件 → 生成 HTML 代码字符串。

    Args:
        file_path: 源 PDF 或图像文件路径
        dpi: 渲染分辨率

    Returns:
        完整的 HTML 文件内容（字符串），包含内联 CSS 和 base64 图片
    """
    layout = parse_to_layout(file_path, dpi)
    return generate_code(layout)
