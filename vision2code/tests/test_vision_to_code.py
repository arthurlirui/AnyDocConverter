"""
Vision-to-Code 模块测试。

测试覆盖：
1. 解析器：PDF → DocumentLayout（文本元素、图片元素、坐标）
2. 解析器：图像 → DocumentLayout
3. 代码生成：DocumentLayout → HTML/CSS（结构验证、内容验证、样式验证）
4. 端到端：PDF → 代码、图像 → 代码
5. 辅助函数：颜色转换、字体清理、HTML 转义
"""

import os
import sys
import tempfile

import pytest

# 确保 algo 模块在 path 中
ALGO_PATH = os.path.join(os.path.dirname(__file__), "..", "algo")
sys.path.insert(0, ALGO_PATH)

from vision_to_code import (
    convert_to_code,
    parse_to_layout,
    generate_code,
    DocumentLayout,
    PageLayout,
    TextElement,
    ImageElement,
    _int_to_hex,
    _clean_font_name,
    _escape_html,
)


# ── 测试夹具 ────────────────────────────────────────────────────────

@pytest.fixture
def sample_pdf_path():
    """生成包含文本和图片的合成 PDF。"""
    import fitz

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()

    font_regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_font(fontname="dejavu", fontfile=font_regular)
    page.insert_font(fontname="dejavu-bold", fontfile=font_bold)

    page.insert_text((72, 72), "Document Title", fontsize=28, fontname="dejavu-bold")
    page.insert_text((72, 120), "Body text paragraph here.", fontsize=12, fontname="dejavu")
    page.insert_text((72, 140), "Second line of text.", fontsize=12, fontname="dejavu")
    page.insert_text((72, 180), "Section Heading", fontsize=18, fontname="dejavu-bold")

    # 画一个矩形作为简单图形
    page.draw_rect(fitz.Rect(72, 220, 300, 280), color=(0, 0, 1), width=2)
    page.insert_text((80, 255), "Box content", fontsize=10, fontname="dejavu")

    doc.save(tmp.name)
    doc.close()

    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_image_path():
    """生成包含文字的合成图片。"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except (IOError, OSError):
        font = ImageFont.load_default()
        font_small = font

    draw.text((50, 50), "Hello World", fill="black", font=font)
    draw.text((50, 120), "This is a test image", fill="blue", font=font_small)
    draw.rectangle([50, 200, 400, 350], outline="red", width=3)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    tmp.close()

    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_layout():
    """手工构建的 DocumentLayout，用于代码生成测试。"""
    return DocumentLayout(
        source_type="pdf",
        title="Test Doc",
        pages=[
            PageLayout(
                width=595,
                height=842,
                text_elements=[
                    TextElement(
                        text="Main Title",
                        x=72, y=50, width=400, height=35,
                        font_size=28, bold=True, is_heading=True, heading_level=1,
                    ),
                    TextElement(
                        text="Body paragraph text",
                        x=72, y=120, width=450, height=18,
                        font_size=12, color="#333333",
                    ),
                ],
                image_elements=[
                    ImageElement(
                        x=72, y=200, width=200, height=150,
                        image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,  # minimal fake PNG
                        fmt="png",
                    ),
                ],
            )
        ],
    )


# ════════════════════════════════════════════════════════════════════
# 解析器测试
# ════════════════════════════════════════════════════════════════════

class TestParser:
    def test_parse_pdf_returns_layout(self, sample_pdf_path):
        """解析 PDF 应返回 DocumentLayout。"""
        layout = parse_to_layout(sample_pdf_path)
        assert isinstance(layout, DocumentLayout)
        assert layout.source_type == "pdf"
        assert len(layout.pages) == 1

    def test_parse_pdf_extracts_text_elements(self, sample_pdf_path):
        """解析 PDF 应提取文本元素。"""
        layout = parse_to_layout(sample_pdf_path)
        page = layout.pages[0]
        assert len(page.text_elements) > 0

        all_text = " ".join(el.text for el in page.text_elements)
        assert "Document Title" in all_text
        assert "Body text" in all_text

    def test_parse_pdf_text_element_has_position(self, sample_pdf_path):
        """文本元素应有坐标信息。"""
        layout = parse_to_layout(sample_pdf_path)
        for el in layout.pages[0].text_elements:
            assert el.x >= 0
            assert el.y >= 0
            assert el.width > 0
            assert el.height > 0

    def test_parse_pdf_detects_headings(self, sample_pdf_path):
        """大字号文本应被检测为标题。"""
        layout = parse_to_layout(sample_pdf_path)
        headings = [el for el in layout.pages[0].text_elements if el.is_heading]
        assert len(headings) > 0
        # "Document Title" 是最大字号，应为 heading
        title_el = [el for el in headings if "Title" in el.text]
        assert len(title_el) >= 1
        assert title_el[0].heading_level >= 1

    def test_parse_pdf_text_element_has_font_info(self, sample_pdf_path):
        """文本元素应保留字体信息。"""
        layout = parse_to_layout(sample_pdf_path)
        for el in layout.pages[0].text_elements:
            assert el.font_size > 0
            assert el.color.startswith("#")

    def test_parse_pdf_page_dimensions(self, sample_pdf_path):
        """页面尺寸应正确。"""
        layout = parse_to_layout(sample_pdf_path)
        page = layout.pages[0]
        assert page.width == 595
        assert page.height == 842

    def test_parse_image_returns_layout(self, sample_image_path):
        """解析图像应返回 DocumentLayout。"""
        layout = parse_to_layout(sample_image_path)
        assert isinstance(layout, DocumentLayout)
        assert layout.source_type == "image"
        assert len(layout.pages) == 1
        assert layout.pages[0].width > 0
        assert layout.pages[0].height > 0

    def test_parse_image_has_page_image(self, sample_image_path):
        """图像输入应保存整页 base64。"""
        layout = parse_to_layout(sample_image_path)
        assert layout.pages[0].page_image_b64 is not None
        assert len(layout.pages[0].page_image_b64) > 0

    def test_parse_nonexistent_file_raises(self):
        """不存在的文件应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            parse_to_layout("/nonexistent/file.pdf")


# ════════════════════════════════════════════════════════════════════
# 代码生成器测试
# ════════════════════════════════════════════════════════════════════

class TestCodeGenerator:
    def test_generate_code_produces_valid_html(self, sample_layout):
        """生成的代码应是有效的 HTML。"""
        code = generate_code(sample_layout)
        assert "<!DOCTYPE html>" in code
        assert "<html" in code
        assert "<head>" in code
        assert "<body>" in code
        assert "</html>" in code

    def test_generate_code_contains_text_content(self, sample_layout):
        """代码应包含原始文本内容。"""
        code = generate_code(sample_layout)
        assert "Main Title" in code
        assert "Body paragraph text" in code

    def test_generate_code_has_css_styles(self, sample_layout):
        """代码应包含内联 CSS。"""
        code = generate_code(sample_layout)
        assert "<style>" in code
        assert ".page" in code
        assert ".text-element" in code
        assert "position: absolute" in code

    def test_generate_code_uses_absolute_positioning(self, sample_layout):
        """文本元素应使用绝对定位。"""
        code = generate_code(sample_layout)
        # 第一个文本元素 x=72, y=50
        assert "left:72" in code or "left:72.0" in code
        assert "top:50" in code or "top:50.0" in code

    def test_generate_code_preserves_font_size(self, sample_layout):
        """代码应保留字号。"""
        code = generate_code(sample_layout)
        assert "font-size:28" in code or "font-size:28.0" in code
        assert "font-size:12" in code or "font-size:12.0" in code

    def test_generate_code_preserves_color(self, sample_layout):
        """代码应保留颜色。"""
        code = generate_code(sample_layout)
        assert "#333333" in code

    def test_generate_code_headings_use_semantic_tags(self, sample_layout):
        """标题应使用语义化标签。"""
        code = generate_code(sample_layout)
        assert "<h1" in code
        assert "heading-1" in code

    def test_generate_code_images_are_base64_embedded(self, sample_layout):
        """图片应以 base64 内嵌。"""
        code = generate_code(sample_layout)
        assert "data:image/png;base64," in code
        assert "image-element" in code

    def test_generate_code_page_dimensions(self, sample_layout):
        """页面容器应有精确尺寸。"""
        code = generate_code(sample_layout)
        assert "width:595px" in code
        assert "height:842px" in code

    def test_generate_code_escapes_html(self, sample_layout):
        """特殊字符应被转义。"""
        layout = DocumentLayout(
            pages=[PageLayout(
                width=400, height=300,
                text_elements=[TextElement(
                    text="<script>alert('xss')</script>",
                    x=10, y=10, width=200, height=20,
                )],
            )]
        )
        code = generate_code(layout)
        assert "<script>alert('xss')</script>" not in code
        assert "&lt;script&gt;" in code


# ════════════════════════════════════════════════════════════════════
# 端到端测试
# ════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_convert_pdf_to_code(self, sample_pdf_path):
        """端到端：PDF → 可编辑代码。"""
        code = convert_to_code(sample_pdf_path)
        assert len(code) > 100
        assert "<!DOCTYPE html>" in code
        assert "Document Title" in code
        assert "Body text" in code
        assert "<style>" in code

    def test_convert_image_to_code(self, sample_image_path):
        """端到端：图像 → 可编辑代码。"""
        code = convert_to_code(sample_image_path)
        assert len(code) > 100
        assert "<!DOCTYPE html>" in code
        # 图像输入应有整页背景图
        assert "data:image" in code

    def test_convert_nonexistent_file_raises(self):
        """不存在的文件应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            convert_to_code("/nonexistent/file.pdf")


# ════════════════════════════════════════════════════════════════════
# 辅助函数测试
# ════════════════════════════════════════════════════════════════════

class TestHelpers:
    def test_int_to_hex(self):
        assert _int_to_hex(0) == "#000000"
        assert _int_to_hex(0xFF0000) == "#FF0000"
        assert _int_to_hex(0x00FF00) == "#00FF00"
        assert _int_to_hex(0x0000FF) == "#0000FF"
        assert _int_to_hex(0xFFFFFF) == "#FFFFFF"

    def test_clean_font_name(self):
        assert _clean_font_name("Helvetica") == "Helvetica"
        assert _clean_font_name("ABCDEF+Helvetica-Bold") == "Helvetica"
        assert _clean_font_name("Arial-BoldItalic") == "Arial"
        assert _clean_font_name("NotoSans-Regular") == "NotoSans"
        assert _clean_font_name("") == "sans-serif"

    def test_escape_html(self):
        assert _escape_html("<b>") == "&lt;b&gt;"
        assert _escape_html('"hello"') == "&quot;hello&quot;"
        assert _escape_html("a&b") == "a&amp;b"
        assert _escape_html("it's") == "it&#039;s"
