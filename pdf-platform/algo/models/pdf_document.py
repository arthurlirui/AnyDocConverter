"""
PDF 文档数据模型 — Pydantic v2 BaseModel
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """文档中的文字块"""

    text: str = Field(..., description="文本内容")
    font_name: Optional[str] = Field(None, description="字体名称")
    font_size: Optional[float] = Field(None, description="字号（pt）")
    bold: bool = Field(False, description="是否加粗")
    italic: bool = Field(False, description="是否斜体")
    color: Optional[str] = Field(None, description="颜色（十六进制，如 #000000）")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="边界框 (x0, y0, x1, y1)，单位 pt"
    )
    page_num: int = Field(..., description="所在页码（0-indexed）")


class ImageBlock(BaseModel):
    """文档中的图片块"""

    image_data: bytes = Field(..., description="原始图片字节数据")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="边界框 (x0, y0, x1, y1)，单位 pt"
    )
    dpi: Optional[int] = Field(None, description="图片 DPI")
    page_num: int = Field(..., description="所在页码（0-indexed）")
    width: Optional[int] = Field(None, description="图片像素宽度")
    height: Optional[int] = Field(None, description="图片像素高度")
    ext: str = Field("png", description="图片扩展名（png/jpg/...）")


class Page(BaseModel):
    """文档中的一页"""

    page_num: int = Field(..., description="页码（0-indexed）")
    width: float = Field(..., description="页面宽度（pt）")
    height: float = Field(..., description="页面高度（pt）")
    text_blocks: list[TextBlock] = Field(default_factory=list, description="文字块列表")
    image_blocks: list[ImageBlock] = Field(default_factory=list, description="图片块列表")

    @property
    def text(self) -> str:
        """合并所有文字块内容"""
        return "\n".join(tb.text for tb in self.text_blocks)


class PDFDocument(BaseModel):
    """解析后的 PDF 文档结构"""

    file_name: str = Field(..., description="原始 PDF 文件名")
    total_pages: int = Field(..., description="总页数")
    pages: list[Page] = Field(default_factory=list, description="页面列表")

    def get_page(self, page_num: int) -> Page | None:
        """按页码获取页面"""
        for p in self.pages:
            if p.page_num == page_num:
                return p
        return None

    @property
    def all_text(self) -> str:
        """返回文档全文"""
        return "\n\n".join(p.text for p in self.pages)
