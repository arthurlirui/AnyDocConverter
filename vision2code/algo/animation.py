"""
Animation Code Generator — 将 DocumentLayout 转换为带动画效果的 HTML/CSS/JS 代码。

参考 Opus 5.5 社区的"图像→动画代码"实践和 Hyperframes 的 HTML→视频渲染理念：
- 从解析出的版面结构生成带有 CSS 动画/过渡效果的可编辑代码
- 元素按阅读顺序依次入场（淡入 + 上滑），模拟电影级叙事节奏
- 标题元素使用更醒目的动画（缩放 + 淡入）
- 图片元素使用视差/缩放效果
- 所有动画使用纯 CSS keyframes，无需 JS 依赖，用户可直接编辑

动画策略：
- **标题**：scale + fadeIn，0.6s，最先入场
- **正文**：fadeIn + slideUp，0.5s，按阅读顺序错开 0.1s
- **图片**：fadeIn + scale，0.8s
- **整页**：背景淡入，0.3s
- **交互**：鼠标悬停时元素轻微放大 + 阴影
- **控制**：JS 提供播放/重播/暂停动画的控制按钮
"""

from __future__ import annotations

import logging
from typing import Optional

from vision_to_code import (
    DocumentLayout,
    PageLayout,
    TextElement,
    ImageElement,
    generate_code,
    _escape_html,
    _clean_font_name,
    _int_to_hex,
)

logger = logging.getLogger(__name__)

# ── 动画预设 ────────────────────────────────────────────────────────

# 每种元素类型的动画参数
_ANIMATION_PRESETS = {
    "title": {
        "name": "anim-title",
        "duration": "0.7s",
        "timing": "cubic-bezier(0.34, 1.56, 0.64, 1)",  # 弹性缓动
        "fill": "both",
    },
    "text": {
        "name": "anim-text",
        "duration": "0.5s",
        "timing": "ease-out",
        "fill": "both",
    },
    "image": {
        "name": "anim-image",
        "duration": "0.8s",
        "timing": "cubic-bezier(0.25, 0.46, 0.45, 0.94)",
        "fill": "both",
    },
    "page": {
        "name": "anim-page",
        "duration": "0.4s",
        "timing": "ease-in-out",
        "fill": "both",
    },
}

# 元素间错开延迟（秒）
_STAGGER_DELAY = 0.08
# 标题与正文之间的额外延迟
_TITLE_PAUSE = 0.15


def generate_animated_code(
    layout: DocumentLayout,
    animation_style: str = "cinematic",
) -> str:
    """将 DocumentLayout 转换为带动画效果的可编辑 HTML/CSS/JS 代码。

    在静态代码生成的基础上，为每个元素添加 CSS 入场动画：
    - 元素按阅读顺序依次入场，形成叙事节奏
    - 不同元素类型使用不同动画效果（标题缩放、正文上滑、图片淡入缩放）
    - 内置播放控制按钮（播放/重播/暂停）

    Args:
        layout: 解析阶段产出的文档布局
        animation_style: 动画风格，目前支持 "cinematic"（电影感）

    Returns:
        完整的 HTML 文件内容（字符串），包含 CSS 动画和 JS 控制
    """
    parts: list[str] = []

    # ── HTML 头部 ──
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head>")
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append(f"<title>{_escape_html(layout.title)}</title>")
    parts.append("<style>")
    parts.append(_generate_animated_css(layout))
    parts.append("</style>")
    parts.append("</head>")
    parts.append("<body>")

    # ── 动画控制栏 ──
    parts.append(_generate_controls())

    # ── 每页内容 ──
    for page_idx, page in enumerate(layout.pages):
        parts.append(f'  <!-- Page {page_idx + 1} -->')
        page_delay = page_idx * 0.3  # 页间延迟
        parts.append(
            f'  <div class="page anim-page" '
            f'style="width:{page.width}px;height:{page.height}px;'
            f'animation-delay:{page_delay:.2f}s;">'
        )

        element_idx = 0  # 全页元素计数器，用于错开延迟

        # 图片元素
        for img_el in page.image_elements:
            delay = page_delay + 0.2 + element_idx * _STAGGER_DELAY
            img_html = _image_element_to_animated_html(img_el, delay)
            parts.append(f"    {img_html}")
            element_idx += 1

        # 图像输入的整页背景
        if layout.source_type == "image" and page.page_image_b64 and not page.image_elements:
            import base64
            mime = "image/png"
            parts.append(
                f'    <img class="page-bg anim-image" '
                f'src="data:{mime};base64,{page.page_image_b64}" '
                f'style="position:absolute;top:0;left:0;width:100%;height:100%;'
                f'object-fit:contain;animation-delay:{page_delay + 0.1:.2f}s;" />'
            )

        # 文本元素 — 按阅读顺序（y 坐标排序）
        sorted_text = sorted(page.text_elements, key=lambda e: (e.y, e.x))
        for text_el in sorted_text:
            if text_el.is_heading:
                delay = page_delay + 0.15 + element_idx * _STAGGER_DELAY
            else:
                delay = page_delay + 0.3 + element_idx * _STAGGER_DELAY

            text_html = _text_element_to_animated_html(text_el, delay)
            parts.append(f"    {text_html}")
            element_idx += 1

        parts.append("  </div>")

    # ── JavaScript 控制逻辑 ──
    parts.append(_generate_js())

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)


# ════════════════════════════════════════════════════════════════════
# CSS 生成
# ════════════════════════════════════════════════════════════════════

def _generate_animated_css(layout: DocumentLayout) -> str:
    """生成包含动画的完整 CSS。"""
    return """
/* ── 全局重置 ── */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: #1a1a2e;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px;
  gap: 24px;
  min-height: 100vh;
}

/* ── 动画控制栏 ── */
.anim-controls {
  position: fixed;
  top: 16px;
  right: 16px;
  display: flex;
  gap: 8px;
  z-index: 9999;
  background: rgba(255, 255, 255, 0.95);
  padding: 8px 12px;
  border-radius: 24px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}

.anim-btn {
  border: none;
  background: #6366f1;
  color: white;
  padding: 6px 16px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.anim-btn:hover {
  background: #4f46e5;
  transform: translateY(-1px);
}

.anim-btn.secondary {
  background: #e0e7ff;
  color: #4f46e5;
}

.anim-btn.secondary:hover {
  background: #c7d2fe;
}

/* ── 页面容器 ── */
.page {
  position: relative;
  background: white;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  border-radius: 4px;
}

/* ── 文本元素（绝对定位） ── */
.text-element {
  position: absolute;
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.2;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.text-element:hover {
  transform: scale(1.02);
  z-index: 10;
}

/* ── 标题样式 ── */
.heading-1 { font-weight: 700; }
.heading-2 { font-weight: 600; }
.heading-3 { font-weight: 600; }

/* ── 图片元素 ── */
.image-element {
  position: absolute;
  object-fit: fill;
  transition: transform 0.3s ease;
}

.image-element:hover {
  transform: scale(1.02);
  z-index: 10;
}

.page-bg {
  z-index: 0;
}

.text-element {
  z-index: 1;
}

/* ════════════════════════════════════════════════════════════════ */
/* 动画关键帧定义                                                   */
/* ════════════════════════════════════════════════════════════════ */

/* 页面入场：淡入 + 轻微上移 */
@keyframes anim-page {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 标题入场：缩放 + 淡入（弹性效果） */
@keyframes anim-title {
  from {
    opacity: 0;
    transform: scale(0.8) translateY(20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

/* 正文入场：淡入 + 上滑 */
@keyframes anim-text {
  from {
    opacity: 0;
    transform: translateY(15px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 图片入场：淡入 + 缩放 */
@keyframes anim-image {
  from {
    opacity: 0;
    transform: scale(0.92);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* ── 动画类绑定 ── */
.anim-page {
  animation: anim-page 0.4s ease-in-out both;
}

.anim-title {
  animation: anim-title 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.anim-text {
  animation: anim-text 0.5s ease-out both;
}

.anim-image {
  animation: anim-image 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94) both;
}

/* ── 暂停状态 ── */
.anim-paused * {
  animation-play-state: paused !important;
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .anim-controls {
    top: 8px;
    right: 8px;
  }
  .anim-btn {
    padding: 5px 12px;
    font-size: 12px;
  }
}
""".strip()


# ════════════════════════════════════════════════════════════════════
# 控制栏
# ════════════════════════════════════════════════════════════════════

def _generate_controls() -> str:
    """生成动画控制栏 HTML。"""
    return """
  <div class="anim-controls">
    <button class="anim-btn" onclick="replayAnimation()">▶ 重播</button>
    <button class="anim-btn secondary" onclick="togglePause()">⏸ 暂停</button>
  </div>
""".strip()


# ════════════════════════════════════════════════════════════════════
# JavaScript 控制
# ════════════════════════════════════════════════════════════════════

def _generate_js() -> str:
    """生成动画控制 JavaScript。"""
    return """
  <script>
    // ── 重播动画 ──
    function replayAnimation() {
      const animated = document.querySelectorAll('.anim-page, .anim-title, .anim-text, .anim-image');
      animated.forEach(el => {
        el.style.animation = 'none';
        el.offsetHeight; // 触发重排
        el.style.animation = '';
      });
      document.body.classList.remove('anim-paused');
    }

    // ── 暂停/继续 ──
    let isPaused = false;
    function togglePause() {
      isPaused = !isPaused;
      document.body.classList.toggle('anim-paused', isPaused);
      const btn = event.target;
      btn.textContent = isPaused ? '▶ 继续' : '⏸ 暂停';
    }

    // ── 页面加载后自动播放 ──
    document.addEventListener('DOMContentLoaded', () => {
      console.log('Vision2Code — 动画代码已加载');
    });
  </script>
""".strip()


# ════════════════════════════════════════════════════════════════════
# 元素渲染（带动画类和延迟）
# ════════════════════════════════════════════════════════════════════

def _text_element_to_animated_html(el: TextElement, delay: float) -> str:
    """将文本元素转换为带动画的 HTML。"""
    styles = [
        f"left:{el.x:.1f}px",
        f"top:{el.y:.1f}px",
        f"width:{el.width:.1f}px",
        f"min-height:{el.height:.1f}px",
        f"font-size:{el.font_size:.1f}px",
        f"color:{el.color}",
        f"animation-delay:{delay:.2f}s",
    ]

    if el.font_name:
        styles.append(f"font-family:'{el.font_name}', sans-serif")
    if el.bold:
        styles.append("font-weight:bold")
    if el.italic:
        styles.append("font-style:italic")

    style_str = ";".join(styles)
    text = _escape_html(el.text)

    if el.is_heading and el.heading_level > 0:
        level = min(el.heading_level, 3)
        anim_class = "anim-title"
        return f'<h{level} class="text-element heading-{level} {anim_class}" style="{style_str}">{text}</h{level}>'
    else:
        return f'<div class="text-element anim-text" style="{style_str}">{text}</div>'


def _image_element_to_animated_html(el: ImageElement, delay: float) -> str:
    """将图片元素转换为带动画的 HTML。"""
    if not el.image_bytes:
        return ""

    import base64
    b64 = base64.b64encode(el.image_bytes).decode("ascii")
    mime = f"image/{el.fmt}" if el.fmt != "jpg" else "image/jpeg"

    styles = [
        f"left:{el.x:.1f}px",
        f"top:{el.y:.1f}px",
        f"width:{el.width:.1f}px",
        f"height:{el.height:.1f}px",
        f"animation-delay:{delay:.2f}s",
    ]
    style_str = ";".join(styles)

    return f'<img class="image-element anim-image" src="data:{mime};base64,{b64}" style="{style_str}" />'


# ════════════════════════════════════════════════════════════════════
# 公共 API
# ════════════════════════════════════════════════════════════════════

def convert_to_animated_code(file_path: str, dpi: int = 150) -> str:
    """端到端：PDF / 图像 → 带动画效果的可编辑 HTML/CSS 代码。

    Args:
        file_path: 源 PDF 或图像文件路径
        dpi: 渲染分辨率

    Returns:
        完整的 HTML 文件内容（字符串），包含 CSS 动画和 JS 控制
    """
    layout = parse_to_layout_for_animation(file_path, dpi)
    return generate_animated_code(layout)


def parse_to_layout_for_animation(file_path: str, dpi: int = 150):
    """解析文件为 DocumentLayout（委托给 vision_to_code）。"""
    from vision_to_code import parse_to_layout
    return parse_to_layout(file_path, dpi)
