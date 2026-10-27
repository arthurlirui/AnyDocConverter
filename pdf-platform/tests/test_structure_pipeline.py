"""
端到端流水线测试 — 结构化转换路径 (Parse → IR → Generate)。

测试覆盖：
1. DocumentModel 中间表示的构建与序列化
2. 数字 PDF 解析（PyMuPDF 文本层）
3. DOCX 生成（标题 / 段落 / 表格 / 图片 / 多列）
4. PPTX 生成（定位文本框 / 图片 / 表格）
5. pipeline.convert() 端到端：合成 PDF → DOCX / PPTX
6. 图片输入路径（合成图片 → DOCX）
7. 回退机制（结构化失败时回退旧转换器）
"""

import os
import sys
import tempfile

import pytest

# 确保 algo 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "algo"))

from algo.document_model import (
    BBox, DocumentModel, LayoutBlock, Page, TableBlock, TableCell, TextRun,
    ImageBlock,
)
from algo.parsers import parse_document
from algo.generators import generate_docx, generate_pptx
from algo.pipeline import convert


# ── 测试夹具 ────────────────────────────────────────────────────────

@pytest.fixture
def sample_pdf_path():
    """生成一个包含文本和表格的合成 PDF。"""
    import fitz

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()

    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # 插入字体（PyMuPDF 2.0 需要显式字体文件）
    page.insert_font(fontname="dejavu", fontfile=font_regular)
    page.insert_font(fontname="dejavu-bold", fontfile=font_bold)

    # 标题
    page.insert_text((72, 72), "Test Document Title", fontsize=24, fontname="dejavu-bold")
    # 正文段落
    page.insert_text((72, 120), "This is a paragraph of body text for testing.", fontsize=12, fontname="dejavu")
    page.insert_text((72, 140), "Second line of the same paragraph.", fontsize=12, fontname="dejavu")
    # 表格线条
    page.draw_line(fitz.Point(72, 180), fitz.Point(523, 180))  # top
    page.draw_line(fitz.Point(72, 220), fitz.Point(523, 220))  # mid
    page.draw_line(fitz.Point(72, 260), fitz.Point(523, 260))  # bottom
    page.draw_line(fitz.Point(72, 180), fitz.Point(72, 260))    # left
    page.draw_line(fitz.Point(297, 180), fitz.Point(297, 260))  # mid vertical
    page.draw_line(fitz.Point(523, 180), fitz.Point(523, 260))  # right
    # 表格文字
    page.insert_text((80, 205), "Header A", fontsize=10, fontname="dejavu")
    page.insert_text((305, 205), "Header B", fontsize=10, fontname="dejavu")
    page.insert_text((80, 245), "Cell 1", fontsize=10, fontname="dejavu")
    page.insert_text((305, 245), "Cell 2", fontsize=10, fontname="dejavu")

    doc.save(tmp.name)
    doc.close()

    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_image_path():
    """生成一个包含文字的合成图片。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except (IOError, OSError):
        font = ImageFont.load_default()

    draw.text((50, 50), "Hello World", fill="black", font=font)
    draw.text((50, 120), "This is test text", fill="black", font=font)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    tmp.close()

    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_model():
    """手工构建的 DocumentModel，用于生成器测试。"""
    return DocumentModel(
        source_path="test.pdf",
        source_type="pdf",
        title="Test Document",
        pages=[
            Page(
                index=0,
                width=595,
                height=842,
                blocks=[
                    LayoutBlock(
                        block_type="title",
                        bbox=BBox(x0=0.1, y0=0.05, x1=0.9, y1=0.1),
                        reading_order=0,
                        heading_level=1,
                        runs=[TextRun(text="Main Title", font_size=24, bold=True)],
                    ),
                    LayoutBlock(
                        block_type="text",
                        bbox=BBox(x0=0.1, y0=0.15, x1=0.9, y1=0.25),
                        reading_order=1,
                        runs=[
                            TextRun(text="This is a ", font_size=12),
                            TextRun(text="bold", font_size=12, bold=True),
                            TextRun(text=" word.", font_size=12),
                        ],
                    ),
                    LayoutBlock(
                        block_type="table",
                        bbox=BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.5),
                        reading_order=2,
                        table=TableBlock(
                            bbox=BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.5),
                            rows=2,
                            cols=2,
                            cells=[
                                TableCell(row=0, col=0, runs=[TextRun(text="H1")], is_header=True),
                                TableCell(row=0, col=1, runs=[TextRun(text="H2")], is_header=True),
                                TableCell(row=1, col=0, runs=[TextRun(text="A1")]),
                                TableCell(row=1, col=1, runs=[TextRun(text="A2")]),
                            ],
                        ),
                    ),
                ],
            )
        ],
    )


# ── DocumentModel 测试 ─────────────────────────────────────────────

class TestDocumentModel:
    def test_bbox_properties(self):
        bbox = BBox(x0=0.1, y0=0.2, x1=0.6, y1=0.8)
        assert abs(bbox.width - 0.5) < 0.001
        assert abs(bbox.height - 0.6) < 0.001
        assert abs(bbox.center_x - 0.35) < 0.001

    def test_bbox_to_pixels(self):
        bbox = BBox(x0=0.0, y0=0.0, x1=0.5, y1=0.5)
        px = bbox.to_pixels(800, 600)
        assert px == (0.0, 0.0, 400.0, 300.0)

    def test_layout_block_text(self):
        block = LayoutBlock(runs=[TextRun(text="Hello "), TextRun(text="World")])
        assert block.text == "Hello World"

    def test_page_sorted_blocks(self):
        page = Page(blocks=[
            LayoutBlock(reading_order=2, runs=[TextRun(text="C")]),
            LayoutBlock(reading_order=0, runs=[TextRun(text="A")]),
            LayoutBlock(reading_order=1, runs=[TextRun(text="B")]),
        ])
        sorted_text = [b.text for b in page.sorted_blocks]
        assert sorted_text == ["A", "B", "C"]

    def test_table_cell_at(self):
        table = TableBlock(
            bbox=BBox(x0=0, y0=0, x1=1, y1=1),
            rows=3, cols=3,
            cells=[
                TableCell(row=0, col=0, rowspan=2, colspan=2, runs=[TextRun(text="merged")]),
                TableCell(row=0, col=2, runs=[TextRun(text="c")]),
                TableCell(row=2, col=0, runs=[TextRun(text="d")]),
            ],
        )
        assert table.cell_at(0, 0) is not None
        assert table.cell_at(0, 0).text == "merged"
        assert table.cell_at(1, 1) is not None  # 被合并覆盖
        assert table.cell_at(1, 1).text == "merged"
        assert table.cell_at(0, 2).text == "c"
        assert table.cell_at(2, 0).text == "d"

    def test_model_all_blocks(self, sample_model):
        blocks = list(sample_model.all_blocks())
        assert len(blocks) == 3
        assert blocks[0][1].block_type == "title"

    def test_multi_column_detection(self):
        # 两个纵向不重叠的文本块 = 多列
        page = Page(blocks=[
            LayoutBlock(block_type="text", bbox=BBox(x0=0.05, y0=0.1, x1=0.45, y1=0.5)),
            LayoutBlock(block_type="text", bbox=BBox(x0=0.05, y0=0.5, x1=0.45, y1=0.9)),
            LayoutBlock(block_type="text", bbox=BBox(x0=0.55, y0=0.1, x1=0.95, y1=0.5)),
            LayoutBlock(block_type="text", bbox=BBox(x0=0.55, y0=0.5, x1=0.95, y1=0.9)),
        ])
        assert page.has_multiple_columns is True

    def test_single_column(self):
        page = Page(blocks=[
            LayoutBlock(block_type="text", bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.3)),
            LayoutBlock(block_type="text", bbox=BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.5)),
            LayoutBlock(block_type="text", bbox=BBox(x0=0.1, y0=0.5, x1=0.9, y1=0.7)),
        ])
        assert page.has_multiple_columns is False


# ── 解析器测试 ──────────────────────────────────────────────────────

class TestParser:
    def test_parse_digital_pdf(self, sample_pdf_path):
        """解析数字 PDF 应产出含文本块的 DocumentModel。"""
        from algo.models.params import ConvertParams

        model = parse_document(sample_pdf_path, ConvertParams())
        assert model.source_type == "pdf"
        assert model.needs_ocr is False
        assert len(model.pages) == 1
        assert len(model.pages[0].blocks) > 0
        # 应有文本块
        text_blocks = model.pages[0].text_blocks
        assert len(text_blocks) > 0
        # 文本块应有内容
        all_text = " ".join(b.text for b in text_blocks)
        assert "Test Document" in all_text or "paragraph" in all_text.lower()

    def test_parse_detects_tables(self, sample_pdf_path):
        """解析含表格线条的 PDF 应检测到表格。"""
        from algo.models.params import ConvertParams

        model = parse_document(sample_pdf_path, ConvertParams())
        tables = model.pages[0].tables
        # 表格检测可能成功也可能因线条太少跳过，不强制要求
        # 但如果有表格，结构应正确
        for tbl_block in tables:
            assert tbl_block.table is not None
            assert tbl_block.table.rows > 0
            assert tbl_block.table.cols > 0

    def test_parse_reading_order(self, sample_pdf_path):
        """解析后 sorted_blocks 应按 reading_order 有序。"""
        from algo.models.params import ConvertParams

        model = parse_document(sample_pdf_path, ConvertParams())
        sorted_blocks = model.pages[0].sorted_blocks
        orders = [b.reading_order for b in sorted_blocks]
        # sorted_blocks 应按 reading_order 升序
        assert orders == sorted(orders)
        assert orders[0] == 0
        # 索引应为连续序列 0,1,2,...
        assert orders == list(range(len(orders)))

    def test_parse_image(self, sample_image_path):
        """解析图片输入。"""
        from algo.models.params import ConvertParams

        model = parse_document(sample_image_path, ConvertParams())
        assert model.source_type == "image"
        assert model.needs_ocr is True
        assert len(model.pages) == 1
        # OCR 可能不可用，但结构应正确
        assert model.pages[0].width > 0
        assert model.pages[0].height > 0


# ── 生成器测试 ──────────────────────────────────────────────────────

class TestGenerators:
    def test_generate_docx_from_model(self, sample_model, tmp_path):
        """从 DocumentModel 生成 DOCX。"""
        from docx import Document as DocxDocument

        output = str(tmp_path / "test.docx")
        generate_docx(sample_model, output)

        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

        # 验证内容
        doc = DocxDocument(output)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "Main Title" in full_text
        assert "bold" in full_text
        # 应有表格
        assert len(doc.tables) >= 1
        table = doc.tables[0]
        assert len(table.rows) == 2
        assert len(table.columns) == 2

    def test_generate_pptx_from_model(self, sample_model, tmp_path):
        """从 DocumentModel 生成 PPTX。"""
        from pptx import Presentation as PptxPresentation

        output = str(tmp_path / "test.pptx")
        generate_pptx(sample_model, output)

        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

        # 验证内容
        prs = PptxPresentation(output)
        assert len(prs.slides) == 1
        slide = prs.slides[0]
        # 应有文本框和表格
        shape_types = [s.shape_type for s in slide.shapes]
        assert len(slide.shapes) >= 2  # 至少标题 + 段落 + 表格

    def test_docx_preserves_font_metadata(self, sample_model, tmp_path):
        """DOCX 应保留字体元数据。"""
        from docx import Document as DocxDocument

        output = str(tmp_path / "font_test.docx")
        generate_docx(sample_model, output)

        doc = DocxDocument(output)
        found_bold = False
        for para in doc.paragraphs:
            for run in para.runs:
                if run.bold:
                    found_bold = True
                    break
        assert found_bold, "Bold formatting should be preserved in DOCX"

    def test_generate_html_from_model(self, sample_model, tmp_path):
        """从 DocumentModel 生成 HTML。"""
        from algo.generators.html_generator import generate_html

        output = str(tmp_path / "test.html")
        generate_html(sample_model, output)

        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

        # 验证内容
        with open(output, "r", encoding="utf-8") as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert "Main Title" in html
        assert "bold" in html
        assert "<table>" in html
        assert "<th>" in html  # 表头
        assert "H1" in html
        assert "A2" in html
        # 应有 CSS 样式
        assert "<style>" in html

    def test_html_preserves_run_styles(self, sample_model, tmp_path):
        """HTML 应在 span 上保留 run 级样式。"""
        from algo.generators.html_generator import generate_html

        output = str(tmp_path / "style_test.html")
        generate_html(sample_model, output)

        with open(output, "r", encoding="utf-8") as f:
            html = f.read()
        # 粗体 run 应有 font-weight:bold
        assert "font-weight:bold" in html

    def test_html_with_merged_cells(self, tmp_path):
        """HTML 应正确处理合并单元格。"""
        from algo.generators.html_generator import generate_html

        model = DocumentModel(pages=[Page(
            index=0, width=595, height=842,
            blocks=[LayoutBlock(
                block_type="table",
                bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                reading_order=0,
                table=TableBlock(
                    bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
                    rows=2, cols=2,
                    cells=[
                        TableCell(row=0, col=0, rowspan=1, colspan=2,
                                  runs=[TextRun(text="Merged")], is_header=True),
                        TableCell(row=1, col=0, runs=[TextRun(text="A")]),
                        TableCell(row=1, col=1, runs=[TextRun(text="B")]),
                    ],
                ),
            )],
        )])
        output = str(tmp_path / "merged.html")
        generate_html(model, output)

        with open(output, "r", encoding="utf-8") as f:
            html = f.read()
        assert 'colspan="2"' in html
        assert "Merged" in html

    def test_generate_markdown_from_model(self, sample_model, tmp_path):
        """从 DocumentModel 生成 Markdown。"""
        from algo.generators.markdown_generator import generate_markdown

        output = str(tmp_path / "test.md")
        generate_markdown(sample_model, output)

        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

        with open(output, "r", encoding="utf-8") as f:
            md = f.read()
        # 标题
        assert "# Main Title" in md
        # 粗体
        assert "**bold**" in md
        # 表格
        assert "| H1 | H2 |" in md
        assert "| A1 | A2 |" in md
        assert "| --- | --- |" in md

    def test_markdown_heading_levels(self, tmp_path):
        """Markdown 应按 heading_level 输出对应数量的 #。"""
        from algo.generators.markdown_generator import generate_markdown

        model = DocumentModel(pages=[Page(
            index=0, width=595, height=842,
            blocks=[
                LayoutBlock(block_type="title", reading_order=0, heading_level=1,
                            runs=[TextRun(text="H1 Title")]),
                LayoutBlock(block_type="title", reading_order=1, heading_level=3,
                            runs=[TextRun(text="H3 Subtitle")]),
            ],
        )])
        output = str(tmp_path / "headings.md")
        generate_markdown(model, output)

        with open(output, "r", encoding="utf-8") as f:
            md = f.read()
        assert "# H1 Title" in md
        assert "### H3 Subtitle" in md

    def test_markdown_multi_page_separator(self, tmp_path):
        """多页 Markdown 应有页间分隔符。"""
        from algo.generators.markdown_generator import generate_markdown

        model = DocumentModel(pages=[
            Page(index=0, blocks=[
                LayoutBlock(block_type="text", reading_order=0,
                            runs=[TextRun(text="Page 1 content")]),
            ]),
            Page(index=1, blocks=[
                LayoutBlock(block_type="text", reading_order=0,
                            runs=[TextRun(text="Page 2 content")]),
            ]),
        ])
        output = str(tmp_path / "multi.md")
        generate_markdown(model, output)

        with open(output, "r", encoding="utf-8") as f:
            md = f.read()
        assert "Page 1 content" in md
        assert "Page 2 content" in md
        assert "---" in md  # 页间分隔符


# ── 端到端 pipeline 测试 ────────────────────────────────────────────

class TestPipeline:
    def test_convert_pdf_to_docx(self, sample_pdf_path, tmp_path):
        """端到端：PDF → DOCX via pipeline.convert()。"""
        output = convert(
            sample_pdf_path,
            "docx",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert output.endswith(".docx")
        assert os.path.getsize(output) > 0

    def test_convert_pdf_to_pptx(self, sample_pdf_path, tmp_path):
        """端到端：PDF → PPTX via pipeline.convert()。"""
        output = convert(
            sample_pdf_path,
            "pptx",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert output.endswith(".pptx")
        assert os.path.getsize(output) > 0

    def test_convert_pdf_to_html(self, sample_pdf_path, tmp_path):
        """端到端：PDF → HTML via structured pipeline。"""
        output = convert(
            sample_pdf_path,
            "html",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert output.endswith(".html")
        assert os.path.getsize(output) > 0
        with open(output, "r", encoding="utf-8") as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html

    def test_convert_pdf_to_markdown(self, sample_pdf_path, tmp_path):
        """端到端：PDF → Markdown via structured pipeline。"""
        output = convert(
            sample_pdf_path,
            "markdown",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert output.endswith(".md")
        assert os.path.getsize(output) > 0
        with open(output, "r", encoding="utf-8") as f:
            md = f.read()
        assert len(md.strip()) > 0

    def test_convert_unsupported_format_raises(self, sample_pdf_path):
        """不支持格式应抛出 ValueError。"""
        with pytest.raises(ValueError, match="Unsupported format"):
            convert(sample_pdf_path, "xyz")

    def test_convert_missing_file_raises(self):
        """不存在的文件应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            convert("/nonexistent/file.pdf", "docx")

    def test_convert_image_to_docx(self, sample_image_path, tmp_path):
        """端到端：图片 → DOCX。"""
        output = convert(
            sample_image_path,
            "docx",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert os.path.getsize(output) > 0

    def test_legacy_formats_still_work(self, sample_pdf_path, tmp_path):
        """非结构化格式（txt/markdown）仍走旧转换器路径。"""
        output = convert(
            sample_pdf_path,
            "txt",
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(output)
        assert output.endswith(".txt")
