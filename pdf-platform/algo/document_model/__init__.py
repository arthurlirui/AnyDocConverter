"""
DocumentModel — 端到端文档重建的中间表示 (Intermediate Representation)。

设计灵感来自 MinerU / Docling / SmolDocling 的统一文档模型思路：
将"解析"与"生成"解耦，解析阶段产出结构化 DocumentModel，
生成阶段消费该模型渲染为 DOCX / PPTX / HTML / Markdown 等目标格式。

核心抽象
--------
- :class:`BBox` — 归一化坐标 [0,1]，与页面尺寸解耦
- :class:`TextRun` — 带字体元数据（字体名、字号、粗体/斜体、颜色）的文本片段
- :class:`TableCell` — 单元格内容 + 合并信息 (rowspan/colspan)
- :class:`TableBlock` — 表格，含行列结构与单元格
- :class:`LayoutBlock` — 版面块（段落 / 标题 / 列表 / 图片 / 表格 / 公式 / 页眉页脚）
- :class:`Page` — 单页：尺寸 + 有序版面块列表
- :class:`DocumentModel` — 整篇文档：元信息 + 页列表

阅读顺序
--------
每个 LayoutBlock 携带 ``reading_order`` 索引（0-based），
页面内按该索引排序即为正确阅读顺序。解析阶段负责计算该索引，
生成阶段直接消费，无需重复推断。

坐标系统
--------
所有 BBox 使用归一化坐标 (x0, y0, x1, y1) ∈ [0, 1]，
相对于页面宽高。生成阶段按目标格式 DPI / 尺寸还原为绝对坐标。
这样解析阶段不关心输出分辨率，生成阶段不关心源格式。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """归一化边界框，坐标 ∈ [0, 1]，相对于页面宽高。"""

    x0: float = Field(0.0, ge=0.0, le=1.0, description="左边界")
    y0: float = Field(0.0, ge=0.0, le=1.0, description="上边界")
    x1: float = Field(1.0, ge=0.0, le=1.0, description="右边界")
    y1: float = Field(1.0, ge=0.0, le=1.0, description="下边界")

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    def to_pixels(self, page_w: float, page_h: float) -> tuple[float, float, float, float]:
        """转换为像素坐标。"""
        return (self.x0 * page_w, self.y0 * page_h, self.x1 * page_w, self.y1 * page_h)


class TextRun(BaseModel):
    """带格式信息的文本片段（一个 run = 同一段内相同样式的连续文字）。"""

    text: str
    font_name: Optional[str] = None
    font_size: Optional[float] = None  # pt
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: Optional[str] = None  # "#RRGGBB"
    # 用于 superscript / subscript 等，目前保留扩展位
    baseline_offset: Optional[int] = None  # 正数=上标, 负数=下标


class TableCell(BaseModel):
    """表格单元格。"""

    row: int = Field(0, description="起始行号 (0-based)")
    col: int = Field(0, description="起始列号 (0-based)")
    rowspan: int = Field(1, ge=1, description="纵向合并跨度")
    colspan: int = Field(1, ge=1, description="横向合并跨度")
    runs: list[TextRun] = Field(default_factory=list, description="单元格内文本")
    is_header: bool = False

    @property
    def text(self) -> str:
        """拼接所有 run 的纯文本。"""
        return "".join(r.text for r in self.runs)


class TableBlock(BaseModel):
    """表格块，含行列结构与单元格。"""

    bbox: BBox
    rows: int = Field(0, ge=0, description="总行数")
    cols: int = Field(0, ge=0, description="总列数")
    cells: list[TableCell] = Field(default_factory=list)

    def cell_at(self, row: int, col: int) -> Optional[TableCell]:
        """返回覆盖 (row, col) 的单元格（考虑合并）。"""
        for cell in self.cells:
            if cell.row <= row < cell.row + cell.rowspan and cell.col <= col < cell.col + cell.colspan:
                return cell
        return None


class ImageBlock(BaseModel):
    """图片块。"""

    bbox: BBox
    image_path: Optional[str] = None  # 裁剪后的图片文件路径
    image_bytes: Optional[bytes] = None  # 或直接持有 bytes
    caption: Optional[str] = None
    fmt: str = "png"  # 图片格式


class FormulaBlock(BaseModel):
    """公式块，保留 LaTeX 源码。"""

    bbox: BBox
    latex: str = ""
    inline: bool = False


# ── 版面块标签 ──────────────────────────────────────────────────────
BlockType = str  # "text" | "title" | "list" | "table" | "image" | "formula" | "header" | "footer" | "caption"


class LayoutBlock(BaseModel):
    """版面块 — 文档结构的基本单元。

    每个块有明确的类型标签、边界框、阅读顺序索引，
    以及与类型对应的内容（runs / table / image / formula）。
    """

    block_type: BlockType = Field("text", description="块类型")
    bbox: BBox = Field(default_factory=BBox)
    reading_order: int = Field(0, ge=0, description="页面内阅读顺序 (0-based)")

    # 文本内容（text / title / list / header / footer / caption 类型使用）
    runs: list[TextRun] = Field(default_factory=list)

    # 表格内容（table 类型使用）
    table: Optional[TableBlock] = None

    # 图片内容（image 类型使用）
    image: Optional[ImageBlock] = None

    # 公式内容（formula 类型使用）
    formula: Optional[FormulaBlock] = None

    # 标题级别（仅 title 类型，1=H1, 2=H2, ...）
    heading_level: Optional[int] = None

    @property
    def text(self) -> str:
        """拼接所有 run 的纯文本。"""
        return "".join(r.text for r in self.runs)


class Page(BaseModel):
    """文档单页。"""

    index: int = Field(0, description="页码 (0-based)")
    width: float = Field(595.0, description="页面宽度 (pt)")
    height: float = Field(842.0, description="页面高度 (pt)")
    blocks: list[LayoutBlock] = Field(default_factory=list)

    @property
    def sorted_blocks(self) -> list[LayoutBlock]:
        """按阅读顺序排序的块列表。"""
        return sorted(self.blocks, key=lambda b: b.reading_order)

    @property
    def text_blocks(self) -> list[LayoutBlock]:
        return [b for b in self.blocks if b.block_type in ("text", "title", "list")]

    @property
    def tables(self) -> list[LayoutBlock]:
        return [b for b in self.blocks if b.block_type == "table" and b.table is not None]

    @property
    def images(self) -> list[LayoutBlock]:
        return [b for b in self.blocks if b.block_type == "image" and b.image is not None]

    @property
    def has_multiple_columns(self) -> bool:
        """启发式：检测是否有多列文本布局。

        如果多个文本块的 x 范围不重叠且纵向有重叠，则判定为多列。
        """
        text_blocks = [b for b in self.blocks if b.block_type in ("text", "title", "list")]
        if len(text_blocks) < 4:
            return False
        for i, a in enumerate(text_blocks):
            for b in text_blocks[i + 1 :]:
                # x 范围不重叠
                x_overlap = not (a.bbox.x1 <= b.bbox.x0 or b.bbox.x1 <= a.bbox.x0)
                # y 范围重叠
                y_overlap = not (a.bbox.y1 <= b.bbox.y0 or b.bbox.y1 <= a.bbox.y0)
                if not x_overlap and y_overlap:
                    return True
        return False


class DocumentModel(BaseModel):
    """完整文档的中间表示 — 解析阶段产出，生成阶段消费。"""

    source_path: str = ""
    source_type: str = "pdf"  # "pdf" | "image"
    needs_ocr: bool = False
    pages: list[Page] = Field(default_factory=list)

    # 文档级元信息
    title: Optional[str] = None
    language: Optional[str] = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def all_blocks(self) -> list[tuple[Page, LayoutBlock]]:
        """遍历所有页的所有块（按页序 + 阅读顺序）。"""
        for page in self.pages:
            for block in page.sorted_blocks:
                yield page, block
