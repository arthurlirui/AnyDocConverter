"""
转换器抽象基类。

所有格式转换器（``to_docx_converter`` / ``to_pptx_converter`` / …）
都应继承 :class:`BaseConverter`，实现 :meth:`convert`。

注意：当前 pipeline 实际调用的是各 ``to_*_converter.convert`` 模块级函数，
而非本基类的实例方法。本基类保留作为面向对象式转换器的契约与工具方法
（输出目录创建、输出路径生成），便于后续重构时复用。
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from algo.models.params import ConvertParams
from algo.models.pdf_document import PDFDocument

logger = logging.getLogger(__name__)


class BaseConverter(ABC):
    """所有转换器的抽象基类。

    子类需覆盖类属性 :attr:`format_name`，并实现 :meth:`convert`。

    Attributes:
        format_name: 目标格式标识符，子类必须覆盖（例如 ``"docx"``）。
        params: 转换参数，传入后由实例持有供 ``convert`` 读取。
    """

    format_name: str = ""  # 子类覆盖

    def __init__(self, params: ConvertParams):
        self.params = params

    @abstractmethod
    def convert(self, pdf_doc: PDFDocument, output_dir: str) -> str:
        """执行转换，返回输出文件路径。

        Args:
            pdf_doc: 已解析的 PDFDocument 数据模型。
            output_dir: 输出目录（不存在时应由实现负责创建）。

        Returns:
            输出文件路径；多文件输出时返回输出目录路径。
        """
        ...

    def _ensure_output_dir(self, output_dir: str) -> str:
        """确保输出目录存在（不存在则创建），返回原路径。"""
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _output_path(self, output_dir: str, ext: str, base_name: str = "output") -> str:
        """生成 ``{output_dir}/{base_name}.{ext}`` 形式的输出文件路径。"""
        return os.path.join(output_dir, f"{base_name}.{ext}")
