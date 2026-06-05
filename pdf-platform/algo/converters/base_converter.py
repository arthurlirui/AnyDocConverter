"""
抽象基类 — 所有转换器继承此类
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
    """转换器基类"""

    format_name: str = ""  # 子类覆盖

    def __init__(self, params: ConvertParams):
        self.params = params

    @abstractmethod
    def convert(self, pdf_doc: PDFDocument, output_dir: str) -> str:
        """执行转换，返回输出文件路径"""
        ...

    def _ensure_output_dir(self, output_dir: str) -> str:
        """确保输出目录存在"""
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _output_path(self, output_dir: str, ext: str, base_name: str = "output") -> str:
        """生成输出文件路径"""
        return os.path.join(output_dir, f"{base_name}.{ext}")
