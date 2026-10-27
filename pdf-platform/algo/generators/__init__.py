"""
generators — DocumentModel → 目标格式。

每个生成器消费 :class:`~algo.document_model.DocumentModel`，
输出为目标格式的文件。生成器与解析阶段完全解耦。
"""

from .docx_generator import generate_docx
from .pptx_generator import generate_pptx
from .html_generator import generate_html
from .markdown_generator import generate_markdown

__all__ = ["generate_docx", "generate_pptx", "generate_html", "generate_markdown"]
