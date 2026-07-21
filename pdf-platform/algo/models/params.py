"""
转换 / 处理参数模型。

定义 :class:`ConvertParams` 及其 4 个子参数组（OCR / Layout / Image / Font），
作为 pipeline、worker、API 之间传递转换配置的统一契约。

后端 ``app.schemas.task.ConvertParams`` 是本模块的结构镜像，二者字段必须保持
一致，以便 API 层直接 ``model_dump`` → ``algo.ConvertParams(**payload)`` 透传，
避免有损字段翻译。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class OCRParams(BaseModel):
    """OCR 参数。

    Attributes:
        enabled: 是否启用 OCR 增强（扫描页 / 图片输入时需要）。
        engine: OCR 引擎，``paddle`` 或 ``tesseract``。
        language: OCR 语言代码。PaddleOCR 推荐
            ``ch`` / ``en`` / ``japan`` / ``korean`` / ``chinese_cht``。
        min_confidence: 最低置信度阈值，低于此值的识别结果会被丢弃。
        enhance_image: 是否启用困难图像预处理。
        enhance_mode: 预处理强度，``standard`` 或 ``hard``。
        upscale_factor: OCR 前放大倍数（1.0–4.0）。
        contrast: 对比度增强倍数（0.5–3.0）。
        sharpness: 锐化增强倍数（0.5–3.0）。
        binarize: 是否对困难图像做二值化。
    """

    enabled: bool = Field(False, description="是否启用 OCR 增强")
    engine: str = Field("paddle", description="OCR 引擎: paddle / tesseract")
    language: str = Field("ch", description="OCR 语言：PaddleOCR 推荐 ch/en/japan/korean/chinese_cht")
    min_confidence: float = Field(0.45, description="最低置信度阈值", ge=0.0, le=1.0)
    enhance_image: bool = Field(False, description="是否启用困难图像增强")
    enhance_mode: str = Field("standard", description="图像增强模式: standard / hard")
    upscale_factor: float = Field(1.0, description="OCR 前放大倍数", ge=1.0, le=4.0)
    contrast: float = Field(1.15, description="对比度增强倍数", ge=0.5, le=3.0)
    sharpness: float = Field(1.05, description="锐化增强倍数", ge=0.5, le=3.0)
    binarize: bool = Field(False, description="是否对困难图像做二值化")


class LayoutParams(BaseModel):
    """版面分析参数。

    Attributes:
        detect_tables: 是否检测表格。
        detect_images: 是否检测图片。
        detect_headers_footers: 是否检测页眉页脚。
        reading_order: 是否还原阅读顺序。
    """

    detect_tables: bool = Field(True, description="是否检测表格")
    detect_images: bool = Field(True, description="是否检测图片")
    detect_headers_footers: bool = Field(True, description="是否检测页眉页脚")
    reading_order: bool = Field(True, description="是否还原阅读顺序")


class ImageParams(BaseModel):
    """图片处理参数。

    Attributes:
        quality: JPG 输出质量（1–100）。
        max_width: 最大宽度（px），``None`` 表示不限制。
        max_height: 最大高度（px），``None`` 表示不限制。
        dpi: 渲染 / 输出 DPI。
    """

    quality: int = Field(85, description="JPG 质量", ge=1, le=100)
    max_width: Optional[int] = Field(None, description="最大宽度（px）")
    max_height: Optional[int] = Field(None, description="最大高度（px）")
    dpi: int = Field(150, description="输出 DPI")


class FontParams(BaseModel):
    """字体参数。

    Attributes:
        fallback_font: 中文字体回退名称（用于无内嵌字体时）。
        embed_fonts: 是否在输出中嵌入字体。
        preserve_size: 是否保留原始字号。
    """

    fallback_font: str = Field("Noto Sans CJK SC", description="中文字体回退")
    embed_fonts: bool = Field(True, description="是否嵌入字体")
    preserve_size: bool = Field(True, description="是否保留原始字号")


class ConvertParams(BaseModel):
    """转换参数 — 顶层聚合，嵌套所有子参数。

    Attributes:
        ocr: OCR 参数。
        layout: 版面分析参数。
        image: 图片处理参数。
        font: 字体参数。
        output_format: 目标格式标识符（由 pipeline 自动覆写）。
        start_page: 起始页（0-indexed，含）。
        end_page: 结束页（含），``None`` 表示到最后一页。
    """

    ocr: OCRParams = Field(default_factory=OCRParams)
    layout: LayoutParams = Field(default_factory=LayoutParams)
    image: ImageParams = Field(default_factory=ImageParams)
    font: FontParams = Field(default_factory=FontParams)

    # 顶层快捷字段
    output_format: str = Field("docx", description="目标格式: docx/pptx/xlsx/html/jpg")
    start_page: int = Field(0, description="起始页（0-indexed）", ge=0)
    end_page: Optional[int] = Field(None, description="结束页（含，None=最后一页）")
