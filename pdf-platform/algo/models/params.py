"""
转换/处理参数模型
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class OCRParams(BaseModel):
    """OCR 参数"""

    enabled: bool = Field(False, description="是否启用 OCR 增强")
    engine: str = Field("paddle", description="OCR 引擎: paddle / tesseract")
    language: str = Field("chi_sim", description="OCR 语言")
    min_confidence: float = Field(0.5, description="最低置信度阈值", ge=0.0, le=1.0)


class LayoutParams(BaseModel):
    """版面分析参数"""

    detect_tables: bool = Field(True, description="是否检测表格")
    detect_images: bool = Field(True, description="是否检测图片")
    detect_headers_footers: bool = Field(True, description="是否检测页眉页脚")
    reading_order: bool = Field(True, description="是否还原阅读顺序")


class ImageParams(BaseModel):
    """图片处理参数"""

    quality: int = Field(85, description="JPG 质量", ge=1, le=100)
    max_width: Optional[int] = Field(None, description="最大宽度（px）")
    max_height: Optional[int] = Field(None, description="最大高度（px）")
    dpi: int = Field(150, description="输出 DPI")


class FontParams(BaseModel):
    """字体参数"""

    fallback_font: str = Field("Noto Sans CJK SC", description="中文字体回退")
    embed_fonts: bool = Field(True, description="是否嵌入字体")
    preserve_size: bool = Field(True, description="是否保留原始字号")


class ConvertParams(BaseModel):
    """转换参数 — 嵌套所有子参数"""

    ocr: OCRParams = Field(default_factory=OCRParams)
    layout: LayoutParams = Field(default_factory=LayoutParams)
    image: ImageParams = Field(default_factory=ImageParams)
    font: FontParams = Field(default_factory=FontParams)

    # 顶层快捷字段
    output_format: str = Field("docx", description="目标格式: docx/pptx/xlsx/html/jpg")
    start_page: int = Field(0, description="起始页（0-indexed）", ge=0)
    end_page: Optional[int] = Field(None, description="结束页（含，None=最后一页）")
