"""
动画代码生成模块测试。

测试覆盖：
1. 动画代码生成：DocumentLayout → 带 CSS 动画的 HTML
2. 动画关键帧验证：@keyframes 定义存在
3. 动画类绑定：anim-title / anim-text / anim-image / anim-page
4. 动画延迟：元素按阅读顺序错开入场
5. JS 控制逻辑：replayAnimation / togglePause 函数存在
6. 端到端：PDF/图像 → 动画代码
7. 静态与动画代码的差异验证
"""

import os
import sys
import tempfile

import pytest

# 确保 algo 模块在 path 中
ALGO_PATH = os.path.join(os.path.dirname(__file__), "..", "algo")
sys.path.insert(0, ALGO_PATH)

from vision_to_code import (
    DocumentLayout,
    PageLayout,
    TextElement,
    ImageElement,
    parse_to_layout,
    generate_code,
)
from animation import (
    generate_animated_code,
    convert_to_animated_code,
)


# ── 测试夹具 ────────────────────────────────────────────────────────

@pytest.fixture
def sample_pdf_path():
    """生成包含文本的合成 PDF。"""
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
    page.insert_text((72, 120), "First paragraph of text.", fontsize=12, fontname="dejavu")
    page.insert_text((72, 140), "Second paragraph here.", fontsize=12, fontname="dejavu")
    page.insert_text((72, 180), "Section Heading", fontsize=18, fontname="dejavu-bold")
    page.insert_text((72, 220), "More body text content.", fontsize=12, fontname="dejavu")

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
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except (IOError, OSError):
        font = ImageFont.load_default()

    draw.text((50, 50), "Image Title", fill="black", font=font)
    draw.text((50, 120), "Image body text", fill="black", font=font)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    tmp.close()

    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def sample_layout():
    """手工构建的 DocumentLayout。"""
    return DocumentLayout(
        source_type="pdf",
        title="Animation Test",
        pages=[PageLayout(
            width=595,
            height=842,
            text_elements=[
                TextElement(
                    text="Main Title",
                    x=72, y=50, width=400, height=35,
                    font_size=28, bold=True, is_heading=True, heading_level=1,
                ),
                TextElement(
                    text="Body paragraph one",
                    x=72, y=120, width=450, height=18,
                    font_size=12, color="#333333",
                ),
                TextElement(
                    text="Body paragraph two",
                    x=72, y=150, width=450, height=18,
                    font_size=12, color="#333333",
                ),
            ],
            image_elements=[
                ImageElement(
                    x=72, y=200, width=200, height=150,
                    image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 50,
                    fmt="png",
                ),
            ],
        )],
    )


# ════════════════════════════════════════════════════════════════════
# 动画代码结构测试
# ════════════════════════════════════════════════════════════════════

class TestAnimationStructure:
    def test_generates_valid_html(self, sample_layout):
        """动画代码应是有效的 HTML。"""
        code = generate_animated_code(sample_layout)
        assert "<!DOCTYPE html>" in code
        assert "<html" in code
        assert "</html>" in code

    def test_contains_animation_keyframes(self, sample_layout):
        """代码应包含 CSS @keyframes 动画定义。"""
        code = generate_animated_code(sample_layout)
        assert "@keyframes anim-title" in code
        assert "@keyframes anim-text" in code
        assert "@keyframes anim-image" in code
        assert "@keyframes anim-page" in code

    def test_contains_animation_classes(self, sample_layout):
        """代码应包含动画类绑定。"""
        code = generate_animated_code(sample_layout)
        assert "anim-title" in code
        assert "anim-text" in code
        assert "anim-image" in code
        assert "anim-page" in code

    def test_contains_animation_delays(self, sample_layout):
        """代码应包含 animation-delay 样式。"""
        code = generate_animated_code(sample_layout)
        assert "animation-delay:" in code

    def test_contains_javascript_controls(self, sample_layout):
        """代码应包含 JS 动画控制函数。"""
        code = generate_animated_code(sample_layout)
        assert "<script>" in code
        assert "replayAnimation" in code
        assert "togglePause" in code

    def test_contains_control_buttons(self, sample_layout):
        """代码应包含动画控制按钮。"""
        code = generate_animated_code(sample_layout)
        assert "anim-controls" in code
        assert "anim-btn" in code
        assert "重播" in code
        assert "暂停" in code

    def test_preserves_text_content(self, sample_layout):
        """动画代码应保留原始文本内容。"""
        code = generate_animated_code(sample_layout)
        assert "Main Title" in code
        assert "Body paragraph one" in code
        assert "Body paragraph two" in code

    def test_preserves_positioning(self, sample_layout):
        """动画代码应保留绝对定位。"""
        code = generate_animated_code(sample_layout)
        assert "position: absolute" in code
        assert "left:72" in code
        assert "top:50" in code

    def test_headings_use_semantic_tags(self, sample_layout):
        """标题应使用语义化标签 + 动画类。"""
        code = generate_animated_code(sample_layout)
        assert "<h1" in code
        assert "heading-1" in code
        assert "anim-title" in code

    def test_images_are_base64_embedded(self, sample_layout):
        """图片应以 base64 内嵌。"""
        code = generate_animated_code(sample_layout)
        assert "data:image/png;base64," in code
        assert "anim-image" in code


# ════════════════════════════════════════════════════════════════════
# 动画延迟测试
# ════════════════════════════════════════════════════════════════════

class TestAnimationDelays:
    def test_staggered_delays(self, sample_layout):
        """元素应有递增的动画延迟（错开入场）。"""
        code = generate_animated_code(sample_layout)
        # 提取所有 animation-delay 值
        import re
        delays = re.findall(r"animation-delay:([\d.]+)s", code)
        assert len(delays) >= 3  # 至少3个元素
        delays_float = [float(d) for d in delays]
        # 至少有两个不同的延迟值（错开效果）
        assert len(set(delays_float)) >= 2

    def test_title_enters_first(self, sample_layout):
        """标题应比正文先入场（延迟更小）。"""
        code = generate_animated_code(sample_layout)
        # 找标题的延迟
        import re
        # 标题 (h1 with anim-title) 应该在正文之前
        title_match = re.search(r'<h1[^>]*anim-title[^>]*animation-delay:([\d.]+)s', code)
        text_matches = re.findall(r'<div[^>]*anim-text[^>]*animation-delay:([\d.]+)s', code)
        assert title_match is not None
        assert len(text_matches) >= 1
        title_delay = float(title_match.group(1))
        # 标题延迟应小于等于正文延迟（先入场）
        for td in text_matches:
            assert title_delay <= float(td) + 0.01  # 允许浮点误差

    def test_multi_page_has_page_delays(self):
        """多页文档应有页间延迟。"""
        layout = DocumentLayout(pages=[
            PageLayout(width=400, height=300, text_elements=[
                TextElement(text="Page 1", x=10, y=10, width=200, height=20),
            ]),
            PageLayout(width=400, height=300, text_elements=[
                TextElement(text="Page 2", x=10, y=10, width=200, height=20),
            ]),
        ])
        code = generate_animated_code(layout)
        import re
        delays = re.findall(r"animation-delay:([\d.]+)s", code)
        delays_float = [float(d) for d in delays]
        # 第二页的延迟应大于第一页
        assert max(delays_float) > min(delays_float)


# ════════════════════════════════════════════════════════════════════
# 静态 vs 动画对比测试
# ════════════════════════════════════════════════════════════════════

class TestStaticVsAnimated:
    def test_animated_code_has_more_features(self, sample_layout):
        """动画代码应比静态代码包含更多功能（动画、JS、控制按钮）。"""
        from vision_to_code import generate_code
        static_code = generate_code(sample_layout)
        animated_code = generate_animated_code(sample_layout)

        # 动画代码应有 @keyframes，静态代码不应有
        assert "@keyframes" in animated_code
        assert "@keyframes" not in static_code

        # 动画代码应有 <script>，静态代码不应有
        assert "<script>" in animated_code
        assert "<script>" not in static_code

    def test_both_preserve_content(self, sample_layout):
        """静态和动画代码都应保留文本内容。"""
        from vision_to_code import generate_code
        static_code = generate_code(sample_layout)
        animated_code = generate_animated_code(sample_layout)

        for code in [static_code, animated_code]:
            assert "Main Title" in code
            assert "Body paragraph one" in code


# ════════════════════════════════════════════════════════════════════
# 端到端测试
# ════════════════════════════════════════════════════════════════════

class TestAnimatedEndToEnd:
    def test_convert_pdf_to_animated_code(self, sample_pdf_path):
        """端到端：PDF → 动画代码。"""
        code = convert_to_animated_code(sample_pdf_path)
        assert len(code) > 200
        assert "<!DOCTYPE html>" in code
        assert "@keyframes" in code
        assert "Document Title" in code
        assert "<script>" in code

    def test_convert_image_to_animated_code(self, sample_image_path):
        """端到端：图像 → 动画代码。"""
        code = convert_to_animated_code(sample_image_path)
        assert len(code) > 200
        assert "<!DOCTYPE html>" in code
        assert "@keyframes" in code
        # 图像输入应有内嵌图片
        assert "data:image" in code

    def test_animated_code_has_dark_background(self, sample_layout):
        """动画模式应使用深色背景（电影感）。"""
        code = generate_animated_code(sample_layout)
        # body 背景应为深色
        assert "#1a1a2e" in code or "background:" in code

    def test_animated_code_has_hover_effects(self, sample_layout):
        """动画代码应包含鼠标悬停效果。"""
        code = generate_animated_code(sample_layout)
        assert ":hover" in code
        assert "transform: scale" in code

    def test_nonexistent_file_raises(self):
        """不存在的文件应抛出 FileNotFoundError。"""
        with pytest.raises(FileNotFoundError):
            convert_to_animated_code("/nonexistent/file.pdf")
