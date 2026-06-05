"""
集成测试 — PDF 转换管线覆写测试

使用 PyMuPDF 生成测试 PDF，逐一验证每种格式的转换管道的完整路径。
"""

from __future__ import annotations

import os
import shutil
import tempfile

import fitz  # PyMuPDF
import pytest

from algo.models.params import ConvertParams
from algo.pipeline import convert
from algo.utils import get_converter_formats


# ── Helpers ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def test_pdf_path() -> str:
    """生成一个含文字和图片的测试 PDF，返回文件路径。"""
    tmpdir = tempfile.mkdtemp(prefix="pdf_test_")
    pdf_path = os.path.join(tmpdir, "test_doc.pdf")

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # 插入文字
    page.insert_text(
        point=(72, 100),
        text="Hello World\n这是中文测试段落。\nPDF Conversion Test Page 1",
        fontsize=14,
        fontname="helv",
    )

    # 第二页
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text(
        point=(72, 200),
        text="Page 2 content with numbers: 12345 67890",
        fontsize=12,
        fontname="helv",
    )

    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_pdf_generation(test_pdf_path: str):
    """验证测试 PDF 生成正确。"""
    assert os.path.isfile(test_pdf_path)
    doc = fitz.open(test_pdf_path)
    assert doc.page_count == 2
    assert len(doc[0].get_text().strip()) > 0
    doc.close()


# ── 管道测试 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", get_converter_formats())
def test_pipeline_conversion(test_pdf_path: str, fmt: str):
    """测试每种格式的完整转换流程。

    验证:
    1. convert() 返回非空路径
    2. 输出文件/目录存在
    3. 输出非空
    """
    output_dir = tempfile.mkdtemp(prefix=f"pdf_out_{fmt}_")
    params = ConvertParams()

    try:
        result = convert(
            file_path=test_pdf_path,
            target_format=fmt,
            params=params,
            output_dir=output_dir,
        )

        # 验证返回值
        assert result, f"convert() returned empty result for {fmt}"
        assert os.path.exists(result), f"Output path does not exist: {result}"

        # 验证输出非空
        if os.path.isfile(result):
            assert os.path.getsize(result) > 0, (
                f"Output file is empty for {fmt}: {result}"
            )
        elif os.path.isdir(result):
            files = os.listdir(result)
            assert len(files) > 0, (
                f"Output directory is empty for {fmt}: {result}"
            )
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_pipeline_invalid_format(test_pdf_path: str):
    """测试不支持的格式返回 ValueError。"""
    with pytest.raises(ValueError, match="Unsupported format"):
        convert(file_path=test_pdf_path, target_format="invalid")


def test_pipeline_file_not_found():
    """测试不存在的 PDF 返回 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError, match="PDF file not found"):
        convert(file_path="/nonexistent/test.pdf", target_format="docx")
